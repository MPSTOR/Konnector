# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2016 MPSTOR Ltd. mpstor.com
# All Rights Reserved.

"""
Version of cinder API compatible with Provizo snapshots.
An MPStackware snapshot is implemented as a read-only volume, so our
"create volume from snapshot" function just returns that.
Points to note:
(1) As a policy, for each snapshot, we allow only one volume derived
from it to exist at any time. Since there is only one real volume
anyway (in MPStackware, a snapshot is already implemented as a
volume), to do otherwise would be misleading.
(2) That snapshot volume is read-only. For a writeable version,
the user must create a new volume himself and copy the data from the
read-only snapshot volume.
(3) We do not allow a snapshot to be deleted if a volume created
from it still exists: since deletion of the original volume is
also prevented for as long as a snapshot exists, this avoids the
problem of snapshot volumes that still exist in the Nova database
but not on the storage node after the original volume has been
deleted (MPStackware's snapshot volumes persist only as long as the
original volume).
(4) Because it effectively corresponds to an MPStackware snapshot
volume, and it is not possible to snapshot a snapshot (and would
be useless since that would merely create another read-only copy
of an existing read-only volume), it is not possible to snapshot
a Cinder volume "created from" a snapshot.
(5) MPStackware volumes have a minimum size of 3GB.
We disallow the creation of volumes smaller than that size.
(6) Ideally, this code would alter manager.py instead of api.py to
allow for other, non-MPSTOR cinders being scheduled together with
the MPSTOR cinder-volume process.
Unfortunately, it is the API that adds volumes and snapshots to
the database, a clean implementation of the above indicates the
modified code should be here.
"""

import api
from cinder import context
from cinder import exception
try:
    from oslo_log import log as logging
except:
    from cinder.openstack.common import log as logging

LOG = logging.getLogger(__name__)

MIN_VOL_GB = 3

class API(api.API):

    def create(self, context, size, name, description, snapshot=None,
                image_id=None, volume_type=None, metadata=None,
                availability_zone=None, source_volume=None,
                **kwargs):
        if snapshot is not None:
            self._check_no_snapshot_volume(snapshot,
                    "Cannot create volume from snapshot '%(snapshot)s': "
                    "volume '%(volume)s' created from it already exists.")
        elif source_volume is not None:
            msg = "Cloning of volumes is not presently supported."
            LOG.debug(msg)
            raise exception.InvalidSourceVolume(msg)
        elif size < MIN_VOL_GB:
            msg = "Cannot create volume smaller than %s GB." % MIN_VOL_GB
            LOG.debug(msg)
            raise exception.InvalidVolume(msg)
        return super(API, self).create(context, size, name, description,
                snapshot, image_id, volume_type, metadata,
                availability_zone, source_volume, **kwargs)

    def _create_snapshot(self, context, volume, *args, **kwargs):
        if volume['snapshot_id']:
            msg = "Cannot snapshot a volume created from snapshot."
            LOG.debug(msg)
            raise exception.InvalidSnapshot(msg)
        return super(API, self)._create_snapshot(context, volume,
                *args, **kwargs)

    def delete_snapshot(self, context, snapshot, force=False):
        self._check_no_snapshot_volume(snapshot,
                "Cannot delete snapshot '%(snapshot)s': "
                "volume '%(volume)s' created from it still exists.")
        return super(API, self).delete_snapshot(context, snapshot, force)

    def _check_no_snapshot_volume(self, snapshot, message):
        """Check that no volume derived from a specified snapshot exists.
        Raises an exception with the specified message if one does.
        The message may refer to %(volume)s and %(snapshot).
        """
        volumes = self.db.volume_get_all(context.get_admin_context(),
                None, None, 'created_at', 'desc')
        for volume in volumes:
            if volume['snapshot_id'] == snapshot['id'] \
                    and not volume['deleted']:
                msg = message % { "snapshot": snapshot['display_name'],
                        "volume": volume.name }
                LOG.debug(msg)
                raise exception.InvalidSnapshot(msg)
