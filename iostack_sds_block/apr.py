#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Automatic Provisioning Requester
# Copyright (c) 2013-2015 MPSTOR Ltd mpstor.com
import optparse
import pybonjour
import select
import socket
import sys
import xml.etree.ElementTree as ElementTree

APR_APM_PROTOCOL_VERSION = "13"
VERSION = 15
APM_SERVICE_TYPE = "_HE_METASOMA._tcp"
APM_SERVICE_PORT = 7010
IQN_FILE_PATH = "/etc/iscsi/initiatorname.iscsi"
CONFIG_FILE = "/etc/apr.conf"

class _ServiceFinder(object):
    """Iterator over (host, port) tuples supplying an mDNS/DNS-SD service."""
    BROWSE_TIMEOUT = 1
    RESOLVE_TIMEOUT = 2

    def __init__(self, service):
        self.service = service

    def __iter__(self):
        found = []
        # (this is an array only so it can be set within the closure)
        resolved = []

        def resolve_callback(sdRef, flags, interfaceIndex, errorCode,
                fullname, hosttarget, port, txtRecord):
            # The same host can be found more than once (at different IPs),
            # but the (host, port) tuples returned should be unique.
            resolved.append(True)
            if errorCode == pybonjour.kDNSServiceErr_NoError:
                if (hosttarget, port) not in found:
                    found.append((hosttarget, port))

        def browse_callback(sdRef, flags, interfaceIndex, errorCode,
                serviceName, regtype, replyDomain):
            if errorCode != pybonjour.kDNSServiceErr_NoError:
                return
            resolver = pybonjour.DNSServiceResolve(0, interfaceIndex,
                    serviceName, regtype, replyDomain, resolve_callback)
            try:
                resolved[:] = []
                while not resolved:
                    ready = select.select([resolver], [], [],
                            _ServiceFinder.RESOLVE_TIMEOUT)
                    if resolver not in ready[0]:
                        break
                    pybonjour.DNSServiceProcessResult(resolver)
            finally:
                resolver.close()

        browser = pybonjour.DNSServiceBrowse(regtype=self.service,
                callBack=browse_callback)
        try:
            while True:
                next = len(found)
                while next == len(found):
                    ready = select.select([browser], [], [],
                            _ServiceFinder.BROWSE_TIMEOUT)
                    if browser in ready[0]:
                        pybonjour.DNSServiceProcessResult(browser)
                    else:
                        return
                # ('for' is defensive - exactly one should have been added)
                for i in range(next, len(found)):
                    yield found[i]
        finally:
            browser.close()


class _XmlMessage():
    def __init__(self):
        self._etree = ElementTree.Element("apr")
        self._etree.set("version", APR_APM_PROTOCOL_VERSION)
        self._cmd_node = ElementTree.SubElement(self._etree, "cmd")

    def set_val(self, k, v):
        val_node = ElementTree.SubElement(self._cmd_node, k)
        val_node.text = str(v)

    def to_xml(self):
        return ElementTree.tostring(self._etree)


class APRError(Exception):
    """General APR exception."""
    pass


class UsageError(APRError):
    """An error in the options passed to the APR."""
    def __init__(self, error, parser=None):
        super(UsageError, self).__init__(error)
        try:
            self.usage = parser.get_usage()
        except:
            self.usage = ""


class ActionFailure(APRError):
    """Raised when the request to the APM fails for any reason."""
    def __init__(self, error, response=None):
        """error: text indicating why the message is wrong or unexpected.
        response: XML ElementTree of the APM's response.
        """
        try:
            error = "%s: %s" % (error,
                    response.find("failure").find("reason").text)
        except:
            pass
        super(ActionFailure, self).__init__(error)


class ActionFailureNonExistent(ActionFailure):
    """Failure due to non-existence of referenced volume or snapshot."""
    pass


class _Parser(optparse.OptionParser):
    def error(self, msg):
        raise UsageError(msg, self)


class _Requester():
    def __init__(self, host, port, options):
        self.options = options
        self._host = host
        self._port = port
        self._sock = None

    def send(self):
        if self._sock:
            raise Exception("send() previously called")
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._sock.connect((self._host, self._port))
        except socket.error, se:
            raise ActionFailure("Cannot connect to APM: %s" % se)
        if self.options.create: self.create()
        elif self.options.delete: self.delete()
        elif self.options.snapshot: self.snapshot()
        elif self.options.connect: self.get_connection()
        elif self.options.disconnect: self.drop_connection()
        elif self.options.attach: self.attach()
        elif self.options.detach: self.detach()
        elif self.options.create_host: self.create_host()
        elif self.options.delete_host: self.delete_host()
        elif self.options.map_host: self.map_host()
        elif self.options.unmap_host: self.unmap_host()
        elif self.options.get_compute_groups: self.get_compute_groups()
        elif self.options.set: self.set()
        elif self.options.maintain: self.maintain()
        else: raise ActionFailure("Unknown action.")

    def receive(self):
        text = self._sock.recv(8096)
        try:
            etree = ElementTree.fromstring(text)
            versions = etree.attrib["version"].split(',')
            if APR_APM_PROTOCOL_VERSION not in versions:
                raise ActionFailure(
                        "APR protocol version (%s) not supported."
                        % APR_APM_PROTOCOL_VERSION)
            rsp = etree.find("ack")
            if rsp is None:
                raise ActionFailure("Request failed", etree)
            return dict([(e.tag, e.text) for e in rsp.getchildren()])
        except ActionFailure, e:
            if "No such" in str(e):
                raise ActionFailureNonExistent(e)
            raise
        except Exception:
            text = text or "(Empty response.)"
            raise ActionFailure("Error in the APM response: %s" % text)

    def create(self):
        msg = _XmlMessage()
        msg.set_val("action", "create")
        if self.options.id:
            msg.set_val("public_id", self.options.id)
        msg.set_val("storage_group", self.options.storage_group)
        msg.set_val("protocol", self.options.protocol)
        msg.set_val("vbs_termination", self.options.vbs_termination and 1 or 0)
        msg.set_val("size", self.options.size)
        if self.options.node_vol:
            msg.set_val("node_vol", self.options.node_vol)
        if self.options.reserved:
            msg.set_val("reserved", self.options.reserved)
        if self.options.threshold:
            msg.set_val("threshold", self.options.threshold)
        if self.options.auto_allocate:
            msg.set_val("auto_allocate", self.options.auto_allocate)
        self._sock.sendall(msg.to_xml())

    def delete(self):
        msg = _XmlMessage()
        msg.set_val("action", "delete")
        msg.set_val("public_id", self.options.id)
        self._sock.sendall(msg.to_xml())

    def snapshot(self):
        msg = _XmlMessage()
        msg.set_val("action", "snapshot")
        msg.set_val("src_id", self.options.src_id)
        msg.set_val("protocol", self.options.protocol)
        if self.options.quiesce:
            msg.set_val("quiesce", self.options.quiesce)
        if self.options.id:
            msg.set_val("public_id", self.options.id)
        if self.options.backup_store:
            msg.set_val("backup_store", self.options.backup_store)
        self._sock.sendall(msg.to_xml())

    def get_connection(self):
        msg = _XmlMessage()
        msg.set_val("action", "connect")
        msg.set_val("public_id", self.options.id)
        msg.set_val("consumer", self.options.consumer)
        msg.set_val("iqn", self.options.iqn)
        msg.set_val("wwn", self.options.wwn)
        msg.set_val("sas_ids", self.options.sas_ids)
        msg.set_val("storage_group", self.options.storage_group)
        self._sock.sendall(msg.to_xml())

    def drop_connection(self):
        msg = _XmlMessage()
        msg.set_val("action", "disconnect")
        msg.set_val("public_id", self.options.id)
        msg.set_val("consumer", self.options.consumer)
        msg.set_val("iqn", self.options.iqn)
        msg.set_val("wwn", self.options.wwn)
        msg.set_val("sas_ids", self.options.sas_ids)
        self._sock.sendall(msg.to_xml())

    def attach(self):
        msg = _XmlMessage()
        msg.set_val("action", "attach")
        msg.set_val("consumer", self.options.consumer)
        msg.set_val("public_id", self.options.id)
        self._sock.sendall(msg.to_xml())

    def detach(self):
        msg = _XmlMessage()
        msg.set_val("action", "detach")
        msg.set_val("public_id", self.options.id)
        msg.set_val("consumer", self.options.consumer)
        self._sock.sendall(msg.to_xml())

    def create_host(self):
        msg = _XmlMessage()
        msg.set_val("action", "create_host")
        if self.options.host_id:
            msg.set_val("host_id", self.options.host_id)
        if self.options.iqn:
            msg.set_val("iqn", self.options.iqn)
        if self.options.user:
            msg.set_val("user", self.options.user)
        if self.options.password:
            msg.set_val("password", self.options.password)
        if self.options.wwn:
            msg.set_val("wwn", self.options.wwn)
        if self.options.sas_ids:
            msg.set_val("sas_ids", self.options.sas_ids)
        self._sock.sendall(msg.to_xml())

    def delete_host(self):
        msg = _XmlMessage()
        msg.set_val("action", "delete_host")
        msg.set_val("host_id", self.options.host_id)
        self._sock.sendall(msg.to_xml())

    def map_host(self):
        msg = _XmlMessage()
        msg.set_val("action", "map_host")
        msg.set_val("public_id", self.options.id)
        msg.set_val("host_id", self.options.host_id)
        self._sock.sendall(msg.to_xml())

    def unmap_host(self):
        msg = _XmlMessage()
        msg.set_val("action", "unmap_host")
        msg.set_val("public_id", self.options.id)
        msg.set_val("host_id", self.options.host_id)
        self._sock.sendall(msg.to_xml())

    def get_compute_groups(self):
        msg = _XmlMessage()
        msg.set_val("action", "get_compute_groups")
        msg.set_val("public_id", self.options.id)
        msg.set_val("iqn", self.options.iqn)
        self._sock.sendall(msg.to_xml())

    def set(self):
        msg = _XmlMessage()
        msg.set_val("action", "set")
        msg.set_val("object_type", self.options.object_type)
        msg.set_val("object_id", self.options.object_id)
        msg.set_val("admin_state", self.options.admin_state)
        self._sock.sendall(msg.to_xml())

    def maintain(self):
        msg = _XmlMessage()
        msg.set_val("action", "maintain")
        msg.set_val("public_id", self.options.id)
        self._sock.sendall(msg.to_xml())


class _Responder():
    def __init__(self, requester):
        self._requester = requester

    def receive(self):
        return self._requester.receive()

    def get_socket(self):
        return self._requester._sock


def request(*request_args):
    """Send a request to the cloudmanager (a.k.a. APM) and wait for the
    response.
    To take the arguments from the command line, do request(*sys.argv[1:]).
    Otherwise, just pass the options as they would appear on the command
    line, e.g., request('--delete', '--id', 'vol-0000002').
    For a successful operation, returns a dict, e.g.,
    for a --delete operation, the dict is empty;
    for a --create or --snapshot, it has keys 'id', 'size_gb', 'volume_name'.
    On error, raises UsageError or ActionFailure.
    """
    responder = request_async(*request_args)
    return responder.receive()


def request_async(*request_args):
    """Asynchronous version of request(): sends a request to the APM
    without waiting for a response.
    On error, raises UsageError or ActionFailure.
    Returns a responder object which provides the following methods:
    receive(), which returns a dict as for request(), or raises ActionFailure;
    get_socket(), which returns a socket.
    To avoid blocking on receive(), the readiness of the socket can first be
    tested, e.g., in a select().
    """
    parser = _Parser(add_help_option=(__name__ == "__main__"),
            usage="\n%prog --help\n"
            "%prog --create --size SIZE_GB"
            " [--id VOL_ID]"
            " [--group GROUP_ID]"
            " [--protocol PROTOCOL] [--vbs-termination]"
            " [--node-volume]"
            " [--reserved RESERVED_GB] [--threshold THRESH]"
            " [--auto_allocate INCR_GB]\n"
            "%prog --delete --id ID\n"
            "%prog --snapshot [--quiesce QUIESCE]"
            " --src-id VOL_ID [--id SNAP_ID]\n"
            "%prog --connect --id ID [--consumer HOST] [--iqn IQN] "
            "[-wwn WWN] [--sas PORT] [--group GROUP_ID]\n"
            "%prog --disconnect --id ID\n"
            "%prog --attach --id ID --consumer HOST\n"
            "%prog --detach --id ID\n"
            "%prog --host-create [--host HOST_ID] --iqn IQN [--user USER "
            "--password PASS]\n"
            "%prog --host-create [--host HOST_ID] --wwn WWN\n"
            "%prog --host-create [--host HOST_ID] --sas PORT\n"
            "%prog --host-delete --host HOST_ID\n"
            "%prog --host-map --id ID --host HOST_ID\n"
            "%prog --host-unmap --id ID --host HOST_ID\n"
            "%prog --query-compute-groups\n"
            "%prog --set --object-type OBJ --object-id OBJ_ID "
            "--admin-state ADMIN_STATE\n"
            "If a file '" + CONFIG_FILE + "' can be read then options "
            "defined in it, one per line in the form \"--option=value\", "
            "will be read first. Command line options override these. ")
    actions = []
    actions.append(parser.add_option("-c", "--create",
            help="Create a logical volume.",
            action="store_true",
            dest="create"))
    actions.append(parser.add_option("--delete",
            help="Delete a logical volume or snapshot.",
            action="store_true",
            dest="delete"))
    actions.append(parser.add_option("--snapshot",
            help="Create a snapshot of a logical volume.",
            action="store_true",
            dest="snapshot"))
    actions.append(parser.add_option("--connect",
            help="Enable a connection to a volume or snapshot."
            " The additional parameters required depend on the type of"
            " connection supported by the volume: for a VBS connection,"
            " specify a consumer; for a direct ISCSI connection,"
            " specify the consumer's IQN; for direct SAS or Fibre Channel,"
            " specify the initiator port WWN(s). Outputs the details"
            " needed to attach the volume, e.g., ISCSI login credentials.",
            action="store_true",
            dest="connect"))
    actions.append(parser.add_option("--disconnect",
            help="Terminate a volume's connection, if it is connected,"
            " or undo the effect of a prior --attach.",
            action="store_true",
            dest="disconnect"))
    actions.append(parser.add_option("--attach",
            help="Attach a volume on one node to another storage node.",
            action="store_true",
            dest="attach"))
    actions.append(parser.add_option("--detach",
            help="Detach a volume."
                " (Currently, --detach is a synonym for --disconnect.)",
            action="store_true",
            dest="detach"))
    actions.append(parser.add_option("--host-create",
            help="Create a record of a host which may be given access"
            " to a volume. For iSCSI access without authentication, the"
            " username and password may be omitted.",
            action="store_true",
            dest="create_host"))
    actions.append(parser.add_option("--host-delete",
            help="Delete a host.",
            action="store_true",
            dest="delete_host"))
    actions.append(parser.add_option("--host-map",
            help="Give a host access to a volume.",
            action="store_true",
            dest="map_host"))
    actions.append(parser.add_option("--host-unmap",
            help="Deny a host access to a volume (remove host mapping).",
            action="store_true",
            dest="unmap_host"))
    actions.append(parser.add_option("--query-compute-groups",
            help=("Get the compute groups and their members."),
            action="store_true",
            dest="get_compute_groups"))
    actions.append(parser.add_option("--set",
            help=("Change the administrative state of a resource."),
            action="store_true",
            dest="set"))
    parser.add_option("--auto-allocate",
            help="For a thin-provisioned volume, the amount of space to add"
            " when it reaches its usage threshold (default: 0).",
            # (The default is implemented in the APM.)
            type="int",
            metavar="INCR_GB",
            dest="auto_allocate")
    parser.add_option("--admin-state",
            default="",
            help="Desired administrative state, e.g., 'locked'.",
            metavar="ADMIN_STATE",
            dest="admin_state")
    parser.add_option("--consumer",
            default="",
            help="The hostname of the node that is to use a volume."
            " This must be identical to that node's hostname field in the"
            " database.",
            metavar="HOST",
            dest="consumer")
    parser.add_option("-g", "--group",
            default="",
            help="Storage group (default: none). "
            "Determines the location and characteristics of a new volume, "
            "or, when connecting an IDA node volume, the ports on which "
            "the volume is exported when it is located on the consumer. "
            "Note: for the '--create' operation, the options in the policy "
            "for the specified storage group override all other options.",
            metavar="GROUP_ID",
            dest="storage_group")
    parser.add_option("--host",
            help="A string to uniquely identify a host record."
            " If unspecified for a new host then one will be generated.",
            metavar="HOST_ID",
            dest="host_id")
    parser.add_option("--id",
            help="The ID (a string) to assign to a new volume or snapshot,"
            " or to identify an existing volume or snapshot."
            " If an ID is not specified for a new volume then the ID "
            " will be the same as the (randomly generated) name.",
            metavar="ID",
            dest="id")
    parser.add_option("--iqn",
            default="",
            help="Initiator IQN (default: taken from %s, if readable)."
            % IQN_FILE_PATH,
            metavar="IQN",
            dest="iqn")
    parser.add_option("--node-volume",
            default=False,
            help="The volume is to be a node volume (operator volume).",
            action="store_true",
            dest="node_vol")
    parser.add_option("--object-type",
            default="",
            help="Object type, e.g., 'node'.",
            metavar="OBJ",
            dest="object_type")
    parser.add_option("--object-id",
            default="",
            help="Numeric object identifier.",
            metavar="OBJ_ID",
            dest="object_id")
    parser.add_option("--password",
            default="",
            help="The password for iSCSI initiator authentication.",
            dest="password")
    parser.add_option("-p", "--protocol",
            default="iscsi",
            help="Protocol to use to export volume (default: %default).",
            metavar="fc|iscsi|sas",
            dest="protocol")
    parser.add_option("--quiesce",
            help='Whether to suspend ("freeze") writes to the volume'
            " while making the snapshot. QUIESCE may be:"
            " 'omit': do not suspend writes (default);"
            " 'prefer': attempt to suspend writes, snapshot anyway;"
            " 'require': fail unless writes can be suspended.",
            metavar="QUIESCE",
            dest="quiesce")
    reserved_option = parser.add_option("--reserved",
            help="Create a thin-provisioned volume,"
            " initially reserving RESERVED_GB space for it.",
            type="int",
            metavar="RESERVED_GB",
            dest="reserved")
    parser.add_option("--sas",
            default="",
            help="SAS initiator port ID, or list of IDs separated by ','.",
            metavar="PORT",
            dest="sas_ids")
    parser.add_option("-s", "--size",
            type="int",
            help="The size of the volume to be created.",
            metavar="SIZE_GB",
            dest="size")
    src_id_option = parser.add_option("--src-id",
            help="The ID of the volume to snapshot.",
            metavar="VOL_ID",
            dest="src_id")
    parser.add_option("--threshold",
            help="For a thin-provisioned volume, the percentage usage of"
            " the currently reserved space which triggers more space to be"
            " reserved (default: 90).",
            # (The default is implemented in the APM.)
            type="int",
            metavar="THRESH",
            dest="threshold")
    parser.add_option("--user",
            default="",
            help="The username for iSCSI initiator authentication.",
            dest="user")
    parser.add_option("--vbs-termination",
            default=False,
            help="The volume is to be connected via a Virtual Block Store"
            " (only).",
            action="store_true",
            dest="vbs_termination")
    parser.add_option("--wwn",
            default="",
            help="FC initiator port WWN, or list of WWNs separated by ','.",
            metavar="WWN",
            dest="wwn")
    parser.add_option("--server",
            default=None,
            help=("Specify the hostname or IP of the APM server;"
            " skips DNS service discovery (specialized usage)."),
            dest="server")
    parser.add_option("--service-type",
            default=APM_SERVICE_TYPE,
            help=("Specify the APM's mDNS service type (default: %default)"
            " (specialized usage)."),
            metavar="SERVICE_TYPE",
            dest="service_type")
    # hidden options: expected to be used only by the APM itself
    actions.append(parser.add_option("--maintain",
            help=optparse.SUPPRESS_HELP,
            action="store_true",
            dest="maintain"))
    parser.add_option("--backup",
            help=optparse.SUPPRESS_HELP,
            #help="The backup store to which the snapshot is to copied.",
            metavar="STORE",
            dest="backup_store")

    option_file = None
    try:
        option_file = open(CONFIG_FILE)
    except:
        pass
    # initialize options with default values
    options, args = parser.parse_args([])
    if option_file:
        ln = 0
        for line in option_file:
            ln += 1
            clean = line.strip()
            if clean.startswith("#") or not clean:
                continue
            option_spec = [x.strip() for x in clean.split("=")]
            if "" in option_spec or " " in option_spec[0]\
                    or not option_spec[0].startswith('--'):
                parser.error("%s: line %s not in format '--option[=value]'."
                        % (CONFIG_FILE, ln))
            options, args = parser.parse_args(option_spec, options)
    # In case an argument (e.g., size) is passed in as a number:
    request_args = [str(x) for x in request_args]
    options, args = parser.parse_args(request_args, values=options)

    opts = [x for x in actions if options.__dict__[x.dest]]
    if len(opts) != 1:
        parser.error("Expected exactly one of these options: %s." \
            % (", ".join([str(x) for x in actions])))

    if options.create:
        if options.size is None:
            parser.error("Must specify the logical volume size.")

    if options.connect and not options.iqn:
        try:
            options.iqn = _get_local_iqn()
        except:
            # due to permissions, the above may succeed only for root
            # - but the IQN is needed only if it's an ISCSI volume.
            pass

    if options.attach or options.detach or options.connect \
            or options.disconnect or options.delete:
        if not options.id:
            parser.error("Must specify a volume ID.")

    if options.attach:
        if not options.consumer:
            parser.error("Must specify a storage consumer.")

    if options.snapshot and not options.src_id:
        parser.error("Must specify the volume to snapshot (option %s)."
                % src_id_option)
    elif options.src_id and not options.snapshot:
        parser.error("Option %s is used only for snapshots." % src_id_option)

    if options.reserved is None:
        for opt in (options.threshold, options.auto_allocate):
            if opt is not None:
                parser.error("The %s option is valid only with the %s "
                        "option." % (opt, reserved_option))
    else:
        if not options.create:
            parser.error("The %s option is valid only when creating a "
                    "volume." % reserved_option)
        if options.reserved > options.size:
            parser.error("The reserved space cannot exceed the volume size.")

    r = None
    if options.server:
        r = _Requester(options.server, APM_SERVICE_PORT, options)
    else:
        for host, port in _ServiceFinder(options.service_type):
            r = _Requester(host, port, options)
            break
        if not r:
            raise ActionFailure("Failed to find a running APM.")
    r.send()
    return _Responder(r)


def _get_local_iqn():
    """Return the IQN of the machine we're running on, or an empty string
    if we are unable to determine it.
    """
    iqn = ""
    try:
        iqn_file = open(IQN_FILE_PATH)
        for line in iqn_file:
            clean = line.strip()
            if clean.startswith("#"):
                continue
            assign = [x.strip() for x in clean.split("=")]
            if len(assign) == 2 and assign[0] == "InitiatorName":
                iqn = assign[1]
    except:
        pass
    return iqn


if __name__ == "__main__":
    try:
        result = request(*sys.argv[1:])
        if result:
            print "\n".join(["%s=%s" % (k, result[k])
                for k in sorted(result.keys())])
    except UsageError, e:
        sys.stderr.write(e.usage)
        sys.stderr.write("\nError: %s\n" % str(e))
        exit(1)
    except APRError, e:
        sys.stderr.write("Error: %s\n" % str(e))
        exit(1)
