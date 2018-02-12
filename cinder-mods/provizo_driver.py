# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2012-2016 MPSTOR mpstor.com.
# All Rights Reserved.
"""
Driver for Provizo (MPStackware) volumes.
"""

from cinder import exception
import cinder.context
from cinder.image import image_utils
try:
    from oslo_log import log as logging
except:
    from cinder.openstack.common import log as logging
from cinder import utils
from cinder.volume.driver import ISCSIDriver
from cinder.volume import volume_types

import json
import random
import socket
import string
import threading
import time

from oslo.config import cfg
CONF = cfg.CONF
CONF.register_opts([
        cfg.StrOpt('sds_uri',
                default='http://$my_ip:9966',
                help='The SDS REST API endpoint.'),
        ])
SDS_HEADERS = {'API-Version':'0'}
import requests
from functools import partial
sds_get=partial(requests.get, headers=SDS_HEADERS)
sds_post=partial(requests.post, headers=SDS_HEADERS)
sds_delete=partial(requests.delete, headers=SDS_HEADERS)


LOG = logging.getLogger("cinder.volume.drivers.provizo_driver")
VOLS_NODE = "/sys/module/mp_target/parameters/volumes"
LOCK = threading.Lock()

class ProvizoDriver(ISCSIDriver):
    """Passes storage requests to Provizo via the APR."""

    def __init__(self, *args, **kwargs):
        super(ProvizoDriver, self).__init__(*args, **kwargs)

    def check_for_setup_error(self):
        pass

    def create_volume(self, volume):
        LOG.debug(_("ProvizoDriver.create_volume %s" % volume['id']))
        params = {"name": volume['id'], "size_gib": volume['size']}
        group_id = _group_id_for_volume(volume)
        if group_id is not None:
            params["group"] = group_id
        resp = sds_post(CONF.sds_uri + "/volumes", data=json.dumps(params))
        resp.raise_for_status()
        result = resp.json()
        LOG.debug("Created volume %s '%s'" % (result['id'], result["name"]))
        attrs = {'provider_location': result['id']}
        # The actual size might be greater than the requested size.
        # (Here we ignore the question that raises for usage quotas.)
        attrs['size'] = int(result.get('size_gib', volume['size']))
        return attrs

    def create_volume_from_snapshot(self, volume, snapshot):
        LOG.debug("ProvizoDriver.create_volume_from_snapshot()")
        # MPStackware has automatically created a read-only volume which
        # effectively is the snapshot: we just use that.
        return

    def create_cloned_volume(self, volume, src_vref):
        raise NotImplementedError()

    def delete_volume(self, volume):
        LOG.debug("ProvizoDriver.delete_volume %s" % volume['id'])
        if volume['snapshot_id']:
            # We do nothing for a volume "created" from a snapshot: no
            # volume was actually created, we just provided read-only access
            # to the MPStackware volume that implements the snapshot.
            LOG.debug("(%s is a snapshot, nothing to do)" % volume['id'])
        elif not volume['provider_location']:
            LOG.warn("Skipping %s: no provider_location" % volume['id'])
        else:
            vol_path = CONF.sds_uri + "/volumes/%s" % (
                    volume['provider_location'])
            resp = sds_delete(vol_path)
            if resp.status_code == 404:
                # If the volume no longer exists then ignore the error
                # so it doesn't get stuck in state "error_deleting".
                LOG.warn("Skipping %s: %s does not exist." % (volume['id'],
                        vol_path))
            else:
                resp.raise_for_status()

    def create_snapshot(self, snapshot):
        # TODO
        raise NotImplementedError()

    def delete_snapshot(self, snapshot):
        # TODO
        raise NotImplementedError()

    def local_path(self, volume):
        LOG.error("Option --use_local_volumes=False is mandatory "
            "with the Provizo volume driver.")
        raise NotImplementedError()

    def ensure_export(self, context, volume):
        """Logical volumes are exported by the storage controller, not
        from a local volume group, so we have nothing to do on startup."""
        LOG.debug("(ProvizoDriver.ensure_export %s)", volume['id'])
        pass

    def create_export(self, context, volume):
        """Logical volumes are exported directly by the storage controller
        and this is done at volume creation; nothing to do locally."""
        LOG.debug("(ProvizoDriver.create_export %s)", volume['id'])
        pass

    def remove_export(self, context, volume):
        """Logical volumes are exported by the storage controller; removing
        the export on LV deletion is the responsibility of APM/SOMA."""
        LOG.debug("(ProvizoDriver.remove_export %s)", volume['id'])
        pass

    def initialize_connection(self, volume, connector):
        """Return connection info for the specified volume."""
        LOG.debug('ProvizoDriver.initialize_connection %s' % volume['id'])
        LOG.debug('ProvizoDriver.initialize_connection %s' % connector)
        # The provider_location stores the SDS volume ID.
        try:
            sds_vol_id = int(volume['provider_location'])
        except:
            raise Exception("Volume %s has no valid provider_location" %
                    volume['id'])
        try:
            params = {"volume": volume['provider_location']}
        except KeyError:
            raise Exception("Volume %s has no provider_location" %
                    volume['id'])
        if 'khost' in connector:
            # connect via Konnector on initiator node
            hostname = connector['khost']
            if '.' not in hostname:
                hostname += '.local.'
            params["khost"] = hostname
            resp = sds_post(CONF.sds_uri + "/connections",
                    data=json.dumps(params))
            resp.raise_for_status()
            result = resp.json()
            return {'driver_volume_type': 'local',
                    'data': {'device_path': result['kdevice']},
                    }
        # if the consumer is also a storage node then make a VBS connection
        node = _get_node_id(connector['host'])
        if node is not None:
            params["consumer"] = node
            resp = sds_post(CONF.sds_uri + "/connections",
                    data=json.dumps(params))
            resp.raise_for_status()
            proxy_vol_id = resp.json()["proxy"]
            resp = sds_get(CONF.sds_uri + "/volumes")
            resp.raise_for_status()
            soma_id = resp.json()["serial"]
            return {'driver_volume_type': 'orkestra_local',
                    'data': {'soma_id': soma_id},
                    }
        # Find an initiator corresponding to the consumer, or create one.
        resp = sds_get(CONF.sds_uri + "/volumes/%s" % sds_vol_id)
        resp.raise_for_status()
        volume = resp.json()
        iqn = connector.get("initiator")
        if iqn and volume.get("portals"):
            # Volume is exported to iSCSI.
            resp = sds_get(CONF.sds_uri + "/initiators")
            resp.raise_for_status()
            inits = resp.json()
            inits = [i for i in inits if i.get("iqn") == iqn]
            if not inits:
                init = {"iqn": iqn}
                myrg = random.SystemRandom()
                alphabet = string.letters + string.digits
                for attr in "password", "username":
                    init[attr] = ''.join(myrg.choice(alphabet)
                            for _ in range(16))
                resp = sds_post(CONF.sds_uri + "/initiators",
                        data=json.dumps(init))
                resp.raise_for_status()
                inits = [resp.json()]
            params["initiator"] = inits[0]["id"]
            resp = sds_post(CONF.sds_uri + "/connections",
                    data=json.dumps(params))
            resp.raise_for_status()
            return {'driver_volume_type': 'iscsi',
                    'data': {
                    'target_discovered': False,
                    'target_iqn': volume['iqn'],
                    'target_portal': volume['portals'][0],
                    # external LUN for iSCSI is always 0
                    'target_lun': 0,
                    'volume_id': 1,
                    'auth_method': 'CHAP',
                    'auth_username': inits[0]['username'],
                    'auth_password': inits[0]['password'],
                    }}

        def strip0x(hexstr):
            return hexstr.replace('0x','')
        wwpns = [strip0x(wwpn) for wwpn in connector.get("wwpns", [])]
        if wwpns and volume.get("wwns"):
            resp = sds_get(CONF.sds_uri + "/initiators")
            resp.raise_for_status()
            inits = [i for i in resp.json() if strip0x(i.get("wwn", ""))
                    in wwpns]
            init_wwns = [strip0x(init.get("wwn", "")) for init in inits]
            for wwpn in wwpns:
                if wwpn not in init_wwns:
                    init = {"wwn": wwpn}
                    resp = sds_post(CONF.sds_uri + "/initiators",
                            data=json.dumps(init))
                    resp.raise_for_status()
                    inits += [resp.json()]
            for init in inits:
                params["initiator"] = init["id"]
                resp = sds_post(CONF.sds_uri + "/connections",
                        data=json.dumps(params))
                resp.raise_for_status()
            return {'driver_volume_type': 'fibre_channel',
                    'data': {
                    'target_discovered': True,
                    'target_lun': volume['lun'],
                    # omit leading '0x' from each WWN in comma-separated list
                    'target_wwn': [strip0x(x) for x in
                    volume['wwns'].split(',')],
                    }}
        raise Exception("No way to attach volume %s (volumes/%s) to %r." %
                (volume['id'], sds_vol_id, connector))

    def terminate_connection(self, volume, connector, force=False, **kwargs):
        """Disallow connection from connector"""
        LOG.debug('ProvizoDriver.terminate_connection %s' % volume['id'])
        try:
            sds_vol_id = int(volume['provider_location'])
        except:
            raise Exception("Volume %s has no valid provider_location" %
                    volume['id'])
        resp = sds_get(CONF.sds_uri + "/connections")
        resp.raise_for_status()
        conns = resp.json()
        conns = [con for con in conns if con["volume"] == sds_vol_id]
        if 'khost' in connector:
            hostname = connector['khost']
            if '.' not in hostname:
                hostname += '.local.'
            to_delete = [con for con in conns if con["khost"] == hostname]
        else:
            node = _get_node_id(connector['host'])
            iqn = connector.get("initiator")
            if node is not None:
                to_delete = [con for con in conns if con["consumer"] == node]
            elif iqn:
                resp = sds_get(CONF.sds_uri + "/initiators")
                resp.raise_for_status()
                inits = resp.json()
                inits = [i for i in inits if i.get("iqn") == iqn]
                to_delete = [con for con in conns if con["initiator"] in
                        [init["id"] for init in inits]]
            else:
                raise Exception("Cannot detach volume %s (volumes/%s) from "
                        "%r." % (volume['id'], sds_vol_id, connector))
        conn_ids = [conn["id"] for conn in to_delete]
        LOG.debug('deleting connections %r.' % conn_ids)
        for conn_id in conn_ids:
            resp = sds_delete(CONF.sds_uri + "/connections/%s" % conn_id)
            resp.raise_for_status()

    def get_volume_stats(self, refresh=False):
        """Return the current state of the volume service. If 'refresh' is
           True, run the update first."""
        return {'vendor_name': 'MPSTOR',
                'total_capacity_gb': 'unknown',
                'free_capacity_gb': 'unknown',
                'reserved_percentage': 0}

    def copy_image_to_volume(self, context, volume, image_service, image_id):
        """Fetch the image from image_service and write it to the volume."""
        LOG.debug(_('ProvizoDriver.copy_image_to_volume %s') % volume['id'])
        connector = utils.brick_get_connector_properties()
        init_conn = self.initialize_connection(volume, connector)
        if init_conn['driver_volume_type'] == 'iscsi':
            return super(ProvizoDriver, self).copy_image_to_volume(context,
                    volume, image_service, image_id)
        try:
            if init_conn['driver_volume_type'] == 'orkestra_local':
                soma_id = init_conn['data']['soma_id']
                volume_path = self._get_device_path(soma_id)
                image_utils.fetch_to_raw(context, image_service, image_id,
                        volume_path)
            else:
                raise NotImplementedError(init_conn['driver_volume_type'])
        finally:
            self.terminate_connection(volume, connector)

    def copy_volume_to_image(self, context, volume, image_service,
            image_meta):
        """Copy the volume to the specified image."""
        LOG.debug(_('ProvizoDriver.copy_volume_to_image %s') % volume['id'])
        connector = utils.brick_get_connector_properties()
        init_conn = self.initialize_connection(volume, connector)
        if init_conn['driver_volume_type'] == 'iscsi':
            return super(ProvizoDriver, self).copy_volume_to_image(context,
                    volume, image_service, image_meta)
        try:
            if init_conn['driver_volume_type'] == 'orkestra_local':
                soma_id = init_conn['data']['soma_id']
                volume_path = self._get_device_path(soma_id)
                image_utils.upload_volume(context, image_service, image_meta,
                        volume_path)
            else:
                raise NotImplementedError(init_conn['driver_volume_type'])
        finally:
            self.terminate_connection(volume, connector)

    def backup_volume(self, context, backup, backup_service):
        """Create a new backup from an existing volume."""
        raise NotImplementedError()

    def restore_backup(self, context, backup, volume, backup_service):
        """Restore an existing backup to a new or existing volume."""
        raise NotImplementedError()

    def _get_device_path(self, soma_id):
        """Given the SOMA id of a volume, get the device path,
        or raise an exception if it can't be found.
        """
        # Retries are in case the volume does not actually exist yet.
        for delay in range(5):
            time.sleep(delay)
            with LOCK:
                # echo [soma id] > /sys/module/mp_target/parameters/volumes
                self._execute('tee', VOLS_NODE, process_input=soma_id,
                        run_as_root=True, check_exit_code=True)
                # cat /sys/module/mp_target/parameters/volumes
                (out, err) = self._execute('cat', VOLS_NODE,
                        run_as_root=True, check_exit_code=True)
            for line in out.split('\n'):
                if soma_id in line:
                    fields = line.split()
                    try:
                        dev = [x for x in fields if x.startswith("lvbd")][-1]
                        return "/dev/" + dev
                    except IndexError:
                        pass
        raise exception.CinderException(_("/dev path not found for %s")
                    % (soma_id))

def _group_id_for_volume(volume):
    """Given a Nova volume, find the ID of its storage group in the CMDB.
    Return None if no storage group is defined for the volume.
    """
    # Support two possibilities: either the storage group ID is a
    # property of the volume type or it's in the volume's metadata.
    # The former is recommended and has priority.
    try:
        volume_type_id = volume['volume_type']['id']
        extra_specs = volume_types.get_volume_type_extra_specs(
                volume_type_id)
        gid = extra_specs['sds:storage_group_id']
        return gid
    except:
        pass
    groups = [i.value for i in volume.get('volume_metadata')
                if i.key == 'storage_group']
    if groups:
        gid = groups[0]
        if len(groups) > 1:
            LOG.warning(_('More than one storage_group was '
                            'detected, using %s') % gid)
        return gid

def _get_node_id(hostname):
    """Return the SDS ID of the storage node with the given hostname,
    or None if it is not a storage node known to SDS.
    """
    resp = sds_get(CONF.sds_uri + "/controllers")
    resp.raise_for_status()
    result = resp.json()
    if '.' not in hostname:
        hostname += '.local.'
    for ctl in result:
        if ctl["hostname"] == hostname:
            return ctl["node"]

