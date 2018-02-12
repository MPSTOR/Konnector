import baseclient
import xml.dom.minidom as minidom

SOMA_PROTOCOL = {'iscsi': 0, 'cifs': 1, 'sas': 2, 'fc': 3}
HOSTTYPE = {'sasfc': 0, 'network': 1}
RAID_ONLINE = '1'
DISK_ONLINE = '1'
DISK_OFFLINE = '2'
INITIATOR_ONLINE = '1'
DISK_ROLE_FREE = '0'
DISK_ROLE_USED = '1'
DISK_ROLE_GLOBAL_SPARE = '3'
IO_MODE_FAST = 0
IO_MODE_SAFE = 1


class SomaClient(baseclient.Client):
    def __init__(self, host):
        super(SomaClient, self).__init__(host)

    def create_raid(self, name, level, initialized, controller_id, disk_ids):
        """If 'initialized' is set then the disks are assumed to be already
        formatted for the RAID and the existing RAID is merely restored.
        """
        num_disks = len(disk_ids)
        soma_level = {0: 0, 1: 1, 5: 2, 6: 3}[level]
        initialized = initialized and 1 or 0
        xml = ('<add><raid name="%(name)s" action="0" parity_algorithm="0"'
                ' recreate="%(initialized)s" softdelete="1"'
                ' chunk_size="64" level="%(soma_level)s" num_spares="0"'
                ' rows="%(num_disks)s" columns="1" automatic_rebuild="0"'
                ' controller="%(controller_id)s"><disks>' % locals())
        for disk_id in disk_ids:
            xml += '<disk id="%s" />' % disk_id
        xml += '</disks></raid></add>'
        self.send(xml)
        return self.receive_element("raid")

    def raid_do(self, raid_id, action):
        """Perform an action ("start" or "rebuild") on a RAID.
        Return without waiting to confirm the result of that action.
        """
        xml = ('<edit><raid id="%s" action="%s"></raid></edit>'
                % (raid_id, {"start": 1, "rebuild": 3}[action]))
        self.send(xml)
        return self.receive_element("raid")

    def create_lv(self, store_id, cvol, recreate=False, soft_delete=False,
            reserved=None, threshold=None, auto_allocate=None, new_api=True):
        """
        Creates a logical volume, returning (SOMA id, LUN).
        If store_id is the SOMA id of a disk (rather than a RAID) then
        it will be a simple volume, in which case cvol's "size" value
        should be the size of the disk (SOMA allocates the whole disk anyway,
        but an incorrect size could lead to incorrect reported statistics).
        The cvol's "size" and "volume_name" must be set; its "io_mode",
        "io_throttle" and "bw_throttle" may optionally be set.
        Sizes (cvol's "size", reserved, auto_allocate) are in MiB.
        Bandwidth throttle is in MiB/s, IO throttle is in IOs/s.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        vals = {}
        for a in ("io_mode", "throttle_bw_rd", "throttle_bw_wr",
                "throttle_io_rd", "throttle_io_wr"):
            try:
                vals[a] = cvol.get_value(a)
            except KeyError:
                vals[a] = None
        # size must be a multiple of 1GB; rounding, if necessary, is down
        # (so that the volume will fit if the size is the size of the store)
        size = int(int(cvol.get_value("size"))/1024.)*1024
        cvol.set_value("size", size)
        xml = "<add>"
        xml += "<logical_volume "
        xml += "name='%s' " % cvol.get_value("volume_name")
        xml += "size='%s' " % size
        xml += "action='0' "
        if recreate:
            xml += "recreate='1' "
        if soft_delete:
            xml += "softdelete='1' "
        xml += "io_mode='%s' " % (vals["io_mode"] or 0)
        if new_api:
            for sattr, lattr in (
                    ("bandwidth_read_throttle", "throttle_bw_rd"),
                    ("bandwidth_write_throttle", "throttle_bw_wr"),
                    ("io_read_throttle", "throttle_io_rd"),
                    ("io_write_throttle", "throttle_io_wr")):
                xml += "%s='%s' " % (sattr, vals[lattr] or 0)
        xml += "access_policy='0' "
        xml += "write_protection='0' "
        soma_reserved = reserved
        if soma_reserved is None:
            xml += "volume_type='0' "
            soma_reserved = size
            type_data = "0"
        else:
            xml += "volume_type='1' "
            if threshold is None:
                threshold = "90"
            type_data = "%s;%s" % (threshold, auto_allocate or 0)
        xml += "reserved='%s' " % (soma_reserved)
        xml += "volume_type_data='%s'>" % (type_data)
        xml += "<space_reservations>"
        xml += "<space_reservation storage='%s' size='%s'/>" % (
                store_id, soma_reserved)
        xml += "</space_reservations>"
        xml += "</logical_volume>"
        xml += "</add>"
        self.send(xml)
        try:
            elem = self.receive_element("logical_volume")
        except baseclient.SomaErrorResponse, e:
            if new_api and all([phrase in str(e) for phrase in
                    "The attribute ", " is not valid for a logical_volume"]):
                return self.create_lv(store_id, cvol, recreate=recreate,
                        soft_delete=soft_delete, reserved=reserved,
                        threshold=threshold, auto_allocate=auto_allocate,
                        new_api=False)
            else:
                raise sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2]
        return elem["id"], elem["lun" in elem and "lun" or "vin"]

    def get_controller_time(self):
        """
        Get the local time on the controller.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        ctrl_id = self.get_local_controller_id()
        self.request_elements("system",
            "<filter attribute='controller' operator='eq' value='%s' />"
            % ctrl_id)
        return self.receive_element_attribute("system", "date")

    def schedule_snapshot(self, snap_name, raid_soma_id, src_vol_id, date,
            buffer_size, threshold, reprovision_size, backup):
        """
        Creates a snapshot element to snapshot the specified volume.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = '<add><snapshot name="%s" ' % snap_name
        xml += 'logical_volume="%s" ' % src_vol_id
        xml += 'start_date="%s" end_date="%s" ' % (date, date)
        xml += 'repetition_policy="0" '  # once
        xml += 'retention_policy="0" '   # locked
        xml += 'retention_period="1" '   # (arbitrary but avoids SOMA bug)
        xml += 'buffer_size="%s" ' % buffer_size
        xml += 'reprovision_size="%s" ' % reprovision_size
        xml += 'threshold="%s" ' % threshold
        if backup:
            xml += 'backup="%s" ' % backup
        xml += 'automatic_export="0" '   # no
        xml += 'windows_compat="0">'     # no
        xml += '<reservations><reservation raid="%s"/>' % raid_soma_id
        xml += '</reservations></snapshot></add>'
        self.send(xml)
        response = self.receive()
        xml_rx = minidom.parseString(response)
        self.check_error(xml_rx)

    def delete_lv(self, lv_id):
        """
        Deletes a logical_volume, given its SOMA ID.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.delete_element("logical_volume", lv_id)

    def delete_element(self, soma_class, soma_id):
        """
        Deletes a SOMA element, given its SOMA class name and ID.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.send("<delete><%s id='%s'/></delete>" % (soma_class, soma_id))
        response = self.receive()
        xml = minidom.parseString(response)
        self.check_error(xml)

    def eject_disk(self, soma_id):
        """
        Set a disk's ejected attribute to True.
        SOMA supports this only for disks not in a RAID.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.send("<edit><disk id='%s' ejected='1'/></edit>" % soma_id)
        return self.receive_elements("disk")

    def stop_disk(self, soma_id):
        """
        Puts a disk into state 'offline'. Note: SOMA does this asynchronously;
        it may be several seconds before the disk actually goes offline.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.send("<edit><disk id='%s' action='1'/></edit>" % soma_id)
        return self.receive_elements("disk")

    def set_disk_role(self, disk_id, role):
        """Change the 'role' attribute of a disk."""
        self.send("<edit><disk id='%s' role='%s'/></edit>" % (disk_id, role))
        return self.receive_elements("disk")

    def port_mapping(self, port, lvId, protocol, read_only=False):
        """
        Maps a volume to a port
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = "<add><export port='%s' " % port
        xml += "logical_volume='%s' " % lvId
        xml += "protocol='%s' " % SOMA_PROTOCOL[protocol]
        xml += "access_policy='%s'></export></add>" % (read_only and 2 or 0)
        self.send(xml)
        return self.receive_element_attribute("export", "id")

    def add_host(self, host_type, name, wwn, hostname):
        """
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = "<add><host host_type='%s' name='%s' wwn='%s' hostname='%s'" % (
                HOSTTYPE[host_type], name, wwn, hostname)
        xml += "></host></add>"
        self.send(xml)
        return self.receive_element_attribute("host", "id")

    def add_host_mapping(self, protocol, controller_id, host_id, lv_id,
            read_only=False):
        """
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = "<add><host_mapping host='%s' " % host_id
        xml += "logical_volume='%s' " % lv_id
        xml += "protocol='%s' " % SOMA_PROTOCOL[protocol]
        xml += "controller='%s' " % controller_id
        xml += "access_policy='%s'>" % (read_only and 2 or 0)
        xml += "</host_mapping></add>"
        self.send(xml)
        return self.receive_element_attribute("host_mapping", "id")

    def get_portals(self, ctrl_id, hostname):
        """
        Gets the iscsi_portal for a host.
        The controller SOMA ID must be specified: in a dual-controller
        node, each controller has its own portals.
        Should return a list length of 0 or 1.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = ("<refresh element_type='iscsi_portal'><filters>"
                "<filter attribute='controller' operator='eq' value='%s'/>"
                "<filter attribute='hostname' operator='eq' value='%s'/>"
                "</filters></refresh>" % (ctrl_id, hostname))
        self.send(xml)
        return self.receive_elements("iscsi_portal")

    def add_portal(self, ctrl_id, hostname):
        """
        adds an iscsi_portal for a target
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = ("<add><iscsi_portal name='' controller='%s' hostname='%s' "
                "port='3260' discovery_method='0' authentication='0' "
                "username='' password=''></iscsi_portal></add>"
                % (ctrl_id, hostname))
        self.send(xml)
        return self.receive_element_attribute("iscsi_portal", "id")

    def get_iscsi_initiators(self, vol_name=None, portal_soma_id=None,
            active=None, hostname=None):
        """Get the SOMA ISCSI initiator elements for a given volume,
        limited to a particualar portal if one is specified.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = "<select element_type='iscsi_initiator'><filters>"
        if vol_name:
            # volume name transformation: see RFC3722 (iSCSI names)
            xml += ("<filter attribute='name' operator='substr' value=':%s'"
                    " />" % ''.join([x for x in vol_name.lower()
                    if x.isalnum() or x in '-.:']))
        if portal_soma_id:
            xml += ("<filter attribute='portal' operator='eq' value='%s' />"
                    % portal_soma_id)
        if active is not None:
            xml += ("<filter attribute='active' operator='eq' value='%s' />"
                    % (active and 1 or 0))
        if hostname is not None:
            xml += ("<filter attribute='hostname' operator='eq' value='%s' />"
                    % hostname)
        xml += "</filters></select>"
        self.send(xml)
        return self.receive_elements("iscsi_initiator")

    def start_iscsi_initiator(self, soma_id, username, password):
        """Start an ISCSI initiator. (This should cause a disk to appear.)
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = ("<edit><iscsi_initiator id='%s' username='%s' password='%s' "
                "authentication='1' action='1'></iscsi_initiator></edit>"
                % (soma_id, username, password))
        self.send(xml)
        return self.receive_element("iscsi_initiator")

    def stop_iscsi_initiator(self, soma_id):
        """Stop an ISCSI initiator.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        xml = ("<edit><iscsi_initiator id='%s' action='2'>"
                "</iscsi_initiator></edit>" % soma_id)
        self.send(xml)
        return self.receive_element("iscsi_initiator")

    def get_volume_current_host(self, soma_id):
        """Return the SOMA "current_host" of the specified volume.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.request_elements("logical_volume", filters=
                '<filter attribute="id" operator="eq" value="%s"/>' % soma_id)
        return self.receive_element_attribute("logical_volume",
                "current_host")

    def get_local_controller_id(self):
        """Get the ID of the SOMA "local_controller" element.
        In the case of a dual controller system, the two controllers may
        have the same hostname, which means we don't necessarily know
        which one we're talking to (which one is active) unless we ask it.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.request_elements("local_controller")
        return self.receive_element_attribute("local_controller", "id")

    def get_initiator_iqn(self, controller_soma_id):
        """Get the initiator IQN of the specified controller.
        Raises: ConnectionLostException, SomaErrorResponse, SomaInvalidComms
        """
        self.request_elements("system", filters=
                "<filter attribute='controller' operator='eq' value='%s'/>"
                % controller_soma_id)
        return self.receive_element_attribute("system", "iqn")

    def get_init_ports(self, protocol):
        """
        Get initiator ports for SAS or FC
        Raises: ConnectionLostException, SomaErrorResponse
        """
        if protocol == 'fc':
            soma_type = 'fibre_port'
            # Currently, QLogic FC ports appear to be in target mode even
            # when the driver is started in initiator mode, so get them all.
            self.request_elements(soma_type)
        else:
            soma_type = '%s_port' % protocol
            # mode 0 = unknown, 1 = target, 2 = initiator, 3 = initiator/target
            self.request_elements(soma_type, filters=
                    "<filter attribute='mode' operator='gt' value='1'/>")
        ports = self.receive_elements(soma_type)
        return ports

    def rescan_ioc(self, sas_or_fc, ioc_id):
        """Rescans a SAS or FC IOC. sas_or_fc should be 'sas' or 'fc'.
        """
        # sas_io_controller or fc_io_controller
        soma_type = sas_or_fc + "_io_controller"
        xml = ('<edit><%s id="%s" action="1"></%s></edit>' %
                (soma_type, ioc_id, soma_type))
        self.send(xml)
        return self.receive_elements(soma_type)
