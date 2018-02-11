# -*- coding: utf-8 -*-
"""HTTP Server ("REST API").

Architecture:

The Server class starts a ThreadingWSGIServer thread which in turn
creates a RequestHandler on a new thread for each request.
There is only one instance of the application (Middleware + Api)
for all threads, but it uses thread local variables where necessary.
The objectapi is also thread-aware.

 +--------------------------+
 | Server                   |          /  one instance of each
 |  .start() / .terminate() |          \  object on the left
 +--------------------------+
                                          objects on the right are
      +                                   instantiated per request
      | has on .thread                              \/
      v

 +----------------------------------+
 | ThreadingWSGIServer              |
 | wsgiref.simple_server.WSGIServer |
 |  .set_app(app) / .get_app()      |
 | BaseHTTPServer.HTTPServer        |      calls
 | SocketServer.TCPServer           |   +---------+
 | SocketServer.BaseServer          |             |
 |  .RequestHandlerClass            |             |
 +----------------------------------+             v

      +                      +------------------------------------------+
      | has                  | RequestHandler                           |
      | .application         | wsgiref.simple_server.WSGIRequestHandler |
      |                      | BaseHTTPServer.BaseHTTPRequestHandler    |
      |                      | SocketServer.StreamRequestHandler        |
      |                      | SocketServer.BaseRequestHandler          |
      |                      +------------------------------------------+
      |
      v                                           +
                                                  |    calls
 +--------------------+                           v
 | Middleware         |
 |                    |           +-------------------------------------+
 | +----------------+ |   calls   | wsgiref.simple_server.ServerHandler |
 | | Api            | |           | wsgiref.handlers.SimpleHandler      |
 | | bottle.Bottle  | |  <-----+  | wsgiref.handlers.BaseHandler        |
 | +----------------+ |           |  .run(app)                          |
 +--------------------+           +-------------------------------------+

           +
           |  calls
           v

     +------------+
     | objectapi  |
     +------------+

 [diagram created using asciiflow.com]


References:

HATEOS:
http://martinfowler.com/articles/richardsonMaturityModel.html
Endless arguments, but in practice APIs are not written in a way that
allows clients to deal automatically with all changes, and if even if
they were, clients might fail to deal with such changes.
However, including hyperlinks does at least make for an API that is
partly self-documenting for developers of REST API clients.

Supported media types:
The data format returned by default is JSON (application/json).
JSON Hypertext Application Language (HAL):
http://stateless.co/hal_specification.html
https://tools.ietf.org/html/draft-kelly-json-hal-06
(Curies not used here.)
For now, HAL is also supported as a JSON extension for hyperlinks.
Note that this support may be discontinued.
Of the many alternatives considered, Collection+JSON was another
contender but is more verbose, e.g., every {"volname":"my vol"}
becomes {"name":"volname", "value":"my vol"} in Collection+JSON.
JSON-API (jsonapi.org) is appealing, but more complex than HAL.
For link relations types ('self', 'item', etc.):
http://www.iana.org/assignments/link-relations/link-relations.xhtml

Error body format:
http://tools.ietf.org/html/draft-nottingham-http-problem-07
(The specified Content-Type is not used here.)

Versioning:
Among the most useful of many references are:
http://www.troyhunt.com/2014/02/your-api-versioning-is-wrong-which-is.html
http://barelyenough.org/blog/2008/05/resthttp-service-versioning-reponse-to-jean-jacques-dubray/
where Jean-Jacques Dubray explains the use of major and minor versions
to manage compatibility (note that many discussions assume there is only
one server - a website - and no clients newer than the server).
"""
import bottle
import httplib
import json
import eskimo
import logging
import SocketServer
import sys
import threading
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler
from functools import partial

__copyright__ = "Copyright (c) 2015 MPSTOR mpstor.com"
__license__ = "See LICENSE.txt"
__author__ = "Michael Breen"

# Maps major API version numbers to the current supported minor version.
# Minor version increments are used for additions which should not
# break existing clients.
# Where a client specifies X.Y, the application is free to reply using
# an API version X.Z where Z >= Y.
VERSIONS = {0:0}

THREAD = threading.local()

TYPE_2_RESOURCE = {
        "node": "/nodes",
        "controller": "/controllers",
        "disk": "/disks",
        "volume":"/volumes",
        "initiator": "/initiators",
        "connection": "/connections",
        "policy": "/policies",
        "group": "/groups",
        }

CONTENT_ANY = "*/*"
CONTENT_DEFAULT = CONTENT_JSON = "application/json"
CONTENT_HAL = "application/hal+json"
SUPPORTED_MEDIA = (CONTENT_JSON, CONTENT_HAL)

class Api(bottle.Bottle):
    """Respond to HTTP client requests.
    A single instance of this class deals with all requests,
    which may be processed concurrently in different threads.
    """
    def __init__(self, objectapi):
        super(Api, self).__init__()
        self.objectapi = objectapi

        self.route('/nodes',
                callback=partial(self.get_resources, 'node'))
        self.route('/nodes/<id:int>',
                callback=partial(self.get_resources, 'node'))

        self.route('/controllers',
                callback=partial(self.get_resources, 'controller'))
        self.route('/controllers/<id:int>',
                callback=partial(self.get_resources, 'controller'))

        self.route('/disks',
                callback=partial(self.get_resources, 'disk'))
        self.route('/disks/<id:int>',
                callback=partial(self.get_resources, 'disk'))

        self.route('/volumes', method='POST',
                callback=partial(self.create_resource, 'volume'))
        self.route('/volumes',
                callback=partial(self.get_resources, 'volume'))
        self.route('/volumes/<id:int>',
                callback=partial(self.get_resources, 'volume'))
        self.route('/volumes/<id:int>', method='DELETE',
                callback=partial(self.delete_resource, 'volume'))

        self.route('/volumes/<snapshot_of:int>/snapshots',
                callback=partial(self.get_resources, 'volume'))
        self.route('/volumes/<snapshot_of:int>/snapshots/<id:int>',
                callback=partial(self.get_resources, 'volume'))
        self.route('/volumes/<snapshot_of:int>/snapshots', method='POST',
                callback=partial(self.create_resource, 'volume'))
        self.route('/volumes/<snapshot_of:int>/snapshots/<id:int>',
                method='DELETE',
                callback=partial(self.delete_resource, 'volume'))

        self.route('/volumes/<volume:int>/connections',
                callback=partial(self.get_resources, 'connection'))
        self.route('/volumes/<volume:int>/connections/<id:int>',
                callback=partial(self.get_resources, 'connection'))
        self.route('/volumes/<volume:int>/connections', method='POST',
                callback=partial(self.create_resource, 'connection'))
        self.route('/volumes/<volume:int>/connections/<id:int>',
                method='DELETE',
                callback=partial(self.delete_resource, 'connection'))

        self.route('/initiators', method='POST',
                callback=partial(self.create_resource, 'initiator'))
        self.route('/initiators',
                callback=partial(self.get_resources, 'initiator'))
        self.route('/initiators/<id:int>',
                callback=partial(self.get_resources, 'initiator'))
        self.route('/initiators/<id:int>', method='DELETE',
                callback=partial(self.delete_resource, 'initiator'))

        self.route('/connections', method='POST',
                callback=partial(self.create_resource, 'connection'))
        self.route('/connections',
                callback=partial(self.get_resources, 'connection'))
        self.route('/connections/<id:int>',
                callback=partial(self.get_resources, 'connection'))
        self.route('/connections/<id:int>', method='DELETE',
                callback=partial(self.delete_resource, 'connection'))

        self.route('/policies', method='POST',
                callback=partial(self.create_resource, 'policy'))
        self.route('/policies',
                callback=partial(self.get_resources, 'policy'))
        self.route('/policies/<id:int>',
                callback=partial(self.get_resources, 'policy'))
        self.route('/policies/<id:int>', method='DELETE',
                callback=partial(self.delete_resource, 'policy'))
        self.route('/policies/<id:int>', method='PATCH',
                callback=partial(self.modify_resource, 'policy'))

        self.route('/groups', method='POST',
                callback=partial(self.create_resource, 'group'))
        self.route('/groups',
                callback=partial(self.get_resources, 'group'))
        self.route('/groups/<id:int>',
                callback=partial(self.get_resources, 'group'))
        self.route('/groups/<id:int>', method='DELETE',
                callback=partial(self.delete_resource, 'group'))
        self.route('/groups/<id:int>', method='PATCH',
                callback=partial(self.modify_resource, 'group'))

        self.route('/groups/<groups:int>/nodes',
                callback=partial(self.get_resources, 'node'))
        self.route('/groups/<groups:int>/nodes/<id:int>',
                callback=partial(self.get_resources, 'node'))
        self.route('/groups/<group:int>/nodes/<node:int>', method='PUT',
                callback=self.add_node_to_group)
        self.route('/groups/<group:int>/nodes/<node:int>', method='DELETE',
                callback=partial(self.delete_resource, 'node_group_link'))

        # Non-Bottle exceptions are caught by Middleware.
        self.catchall = False

    def get_resources(self, type_, **args):
        """Get an object or a collection of objects as a Resource.
        """
        rows = self.objectapi.get_objects(type_, **args)
        if "id" in args:
            if len(rows) == 1:
                return resource(rows[0])
            else:
                raise bottle.HTTPError(404)
        else:
            return resource(rows)

    def create_resource(self, type_, **attrs):
        args = request_dict()
        for attr in attrs:
            if args.setdefault(attr, attrs[attr]) != attrs[attr]:
                raise bottle.HTTPError(400, "Inconsistent values for '%s'."
                        % attr)
        obj = self.objectapi.create_object(type_, **args)
        created("%s/%s" % (TYPE_2_RESOURCE[type_], obj["id"]))
        return resource(obj)

    def modify_resource(self, type_, id):
        args = request_dict()
        if args.setdefault("id", id) != id:
            raise bottle.HTTPError(400, "Attribute 'id' cannot be changed.")
        obj = self.objectapi.modify_object(type_, **args)
        return resource(obj)

    def delete_resource(self, type_, **args):
        self.objectapi.delete_object(type_, **args)

    def add_node_to_group(self, group, node):
        self.objectapi.create_object('node_group_link', group=group,
                node=node)
        created("/groups/%s/node/%s" % (group, node))

    def default_error_handler(self, response):
        """Override default_error_handler to return JSON instead of HTML.
        """
        if response.status_code == 404:
            return json.dumps({'detail':"Not found: %s" %
                    bottle.request.path})
        if response.body:
            return json.dumps({'detail':response.body})


def resource(obj):
    """Return the object(s) converted to the format expected by the client.
    This function may be passed a single object or a sequence of objects.
    """
    single = isinstance(obj, dict)
    content = get_medium()
    if content == CONTENT_HAL:
        if single:
            result =  HalResource(obj)
        else:
            # HalResource() needs _type, but for nested resource collections,
            # e.g., /groups/X/nodes, the "self" link derived from it will
            # not include the nesting - so set it arbitrarily to "volume"
            # and then set the correct link from the path.
            doc = HalResource({"_type":"volume"})
            doc.links['self'] = path_prefix() +\
                    bottle.request.environ['PATH_INFO']
            doc.links['item'] = []
            items = []
            for one in obj:
                items.append(HalResource(one))
                link = Link(one)
                doc.links['item'].append(link)
            doc.embedded['item'] = items
            result =  doc
    else:
        if single:
            result =  {k: v for k, v in obj.items() if not k.startswith("_")}
        else:
            result =  [{k: v for k, v in one.items() if not k.startswith("_")}
                    for one in obj]
    return json.dumps(result)

def get_medium():
    """Return the content type expected by the client if it's supported,
    otherwise raise an exception.
    """
    # accept = environ.get("HTTP_ACCEPT", CONTENT_ANY).split()
    accept = bottle.request.headers.get("Accept", CONTENT_DEFAULT)
    # basic parsing (parameters, including quality parameter, disregarded)
    media = [medium.split(";")[0].strip() for medium in accept.split(",")]
    for medium in media:
        if medium in SUPPORTED_MEDIA:
            return medium
    if "*/*" in media:
        return CONTENT_DEFAULT
    raise bottle.HTTPError(415)

def created(path):
    """Set Bottle's response to "201 Created" with a Location header.
    A version prefix is added to the path if appropriate.
    """
    bottle.response.set_header('Location', path_prefix() + path)
    bottle.response.status = 201

def path_prefix():
    """Return '/vX.Y' if the requested path had a version prefix,
    where X is the requested major version number and
    Y is the latest supported minor version; otherwise return ''.
    """
    environ = bottle.request.environ
    prefix = environ['sds.path_prefix']
    if prefix:
        major = environ['sds.version']
        return '/v%d.%d' % (major, VERSIONS[major])
    else:
        return ''


class HalDict(dict):
    def items(self):
        """Override dict.items() (used by json.dumps()) to make ordering
        of HAL+JSON output human-friendly and deterministic.
        """
        # (1) In a Resource dict, '_links' comes first, '_embedded' last.
        # (2) In a Link dict, 'href' comes first.
        # (3) In a dict of Links, 'self' comes first.
        # We assume that the keys above occur only in the corresponding
        # dictionaries and so just use a single ordering in this class.
        items = super(HalDict, self).items()
        return sorted(((k,v) for k,v in items), key=lambda (x,y):
                {'self': '1', 'href': '1', '_links': '1',
                '_embedded': '9'}.get(x, '5' + str(x)))


class HalResource(HalDict):
    """A HAL resource object.
    See http://stateless.co/hal_specification.html
    """
    def __init__(self, attrs):
        """HalResource("/path/to/resource")
        """
        super(HalResource, self).__init__(_links=HalDict(self=Link(attrs)))
        self.links = self['_links']
        link_attrs = attrs.pop("_refs", {})
        for key in attrs:
            # exclude _type, id (id becomes the "self" link)
            if not key.startswith('_') and key != "id":
                _type = link_attrs.get(key)
                if _type:
                    # In _links, include only non-empty links:
                    # https://tools.ietf.org/html/draft-kelly-json-hal-06
                    # "The reserved "_links" property ... is an object whose
                    # ... values are either a Link Object or an array
                    # of Link Objects."
                    # That implies null is not allowed as a value, and while
                    # it does not state whether arrays may be empty (it's a
                    # rather poor spec.), consistency suggests that null
                    # links and empty arrays are both excluded from _links.
                    # This means that external query-string filters based on
                    # the link attributes (e.g., /volumes?snapshot_of=null)
                    # cannot be supported.
                    # (But filtering is not currently supported anyway.)
                    if attrs[key]:
                        if isinstance(attrs[key], list):
                            self.links[key] = [Link({"_type": _type,
                                    "id": oid}) for oid in attrs[key]]
                        else:
                            self.links[key] = Link({"_type": _type,
                                    "id": attrs[key]})
            if not key.startswith('_'):
                self[key] = attrs[key]

    @property
    def embedded(self):
        return self.setdefault('_embedded', {})


class Link(HalDict):
    """A HAL link.
    """
    def __init__(self, attrs):
        """Link({"_type": "resource-type", "id": "resource_id", ...})
        where the "id" key is optional.
        Other keys are ignored, but could be needed in future if objects
        are located in a hierarchy, e.g., /nodes/X/raids/Y requires
        the node ID X as well as the RAID ID Y.
        (However it may be better to avoid hierarchy.)
        """
        href = TYPE_2_RESOURCE[attrs["_type"]]
        _id = attrs.get("id")
        if _id:
            href += "/%s" % _id
        super(Link, self).__init__(href=path_prefix() + href)


def request_dict():
    """Return the JSON object body of the current request as a dict.
    """
    body = bottle.request.body.getvalue()
    body = body.strip()
    if not body:
        raise bottle.HTTPError(400, "Missing request body.")
    try:
        args = json.loads(body)
    except:
        raise bottle.HTTPError(400, "Request body is not valid JSON: %r"
                % body)
    if isinstance(args, dict):
        return args
    raise bottle.HTTPError(400, "Request body is not a JSON object: %r"
            % body)


class Middleware(object):
    """WSGI middleware.
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, org_start_response):
        """Check the API version, handle exceptions, and do any other
        actions common to all requests.
        """
        headers = {"Content-Type": CONTENT_DEFAULT}

        def start_response(status, response_headers, exc_info=None):
            new_headers = [(k, v) for k, v in response_headers
                    if k.lower() not in [h.lower() for h in headers]]
            try:
                headers["Content-Type"] = get_medium()
            except Exception, e:
                pass
            new_headers += headers.items()
            org_start_response(status, new_headers, exc_info)

        class ErrorLogger(object):
            def write(self, message):
                THREAD.logger.error(message)

        environ['wsgi.errors'] = ErrorLogger()

        # Anything stripped from the beginning of the path.
        environ['sds.path_prefix'] = ''
        # Treat /X/Y/ as /X/Y and make the latter canonical.
        environ['PATH_INFO'] = '/' + environ['PATH_INFO'].strip('/')

        def version_error(title):
            start_response("400 Bad Request", [])
            detail = ("Use a HTTP header 'API-Version: X.Y' or a "
                    "path prefix /vX.Y where X.Y is "
                    + " or ".join(["%s.%s" % (x, y) for (x, y) in
                    sorted(VERSIONS.items())]) + ".")
            return [json.dumps({'title': title, 'detail': detail})]

        top = environ['PATH_INFO'].split('/')[1]
        versions = None
        if top.startswith('v') and top.count('.') < 2:
            try:
                versions = [int(x) for x in top[1:].split('.')]
            except ValueError:
                # It might be '/volumes' or something else.
                pass
            else:
                environ['sds.path_prefix'] += '/' + top
                environ['PATH_INFO'] = (environ['PATH_INFO'].split(top, 1)[1]
                        or '/')
        if 'HTTP_API_VERSION' in environ:
            try:
                h_versions = [int(x) for x in
                        environ['HTTP_API_VERSION'].split('.', 1)]
            except:
                return version_error("Invalid API-Version.")
            if versions:
                if h_versions != versions:
                    return version_error("API-Version does not match path.")
            else:
                versions = h_versions
        elif not versions:
            return version_error("No API version specified.")
        if len(versions) == 1:
            versions.append(0)
        major = versions[0]
        if major not in VERSIONS or versions[1] > VERSIONS[major]:
            return version_error("Unsupported API version.")
        environ['sds.version'] = major
        headers['API-Version'] = '%d.%d' % (major, VERSIONS[major])
        try:
            with eskimo.Lock(self, shared=True, timeout=0):
                return self.app(environ, start_response)
        except eskimo.Timeout:
            # Server is shutting down.
            start_response("503 Service Unavailable", [])
            return []
        except Exception, e:
            exc_info = sys.exc_info()
            try:
                status = e.fields.get('status', 500)
                status_name = httplib.responses.get(status, '')
                start_response("%s %s" % (status, status_name), [])
                return [json.dumps(e.fields)]
            except:
                raise exc_info[0], exc_info[1], exc_info[2]


class ThreadingWSGIServer(SocketServer.ThreadingMixIn, WSGIServer):
    '''Version of WSGIServer that spawns a thread to handle each request.
    '''
    pass


class RequestHandler(WSGIRequestHandler):
    '''Handler for individual client requests with customized logging.
    '''
    def log_error(self, format, *args):
        """Override BaseHTTPRequestHandler logging to use our logger.
        """
        THREAD.logger.error(self.formatted_message(format, *args))

    def log_message(self, format, *args):
        """Override BaseHTTPRequestHandler logging to use our logger.
        """
        THREAD.logger.info(self.formatted_message(format, *args))

    def formatted_message(self, format, *args):
        """Return a log message formatted the BaseHTTPRequestHandler way.
        """
        return "%s - - [%s] %s" % (self.address_string(),
                self.log_date_time_string(),
                format % args)


class Server():
    """Runs the top-level server thread.
    """
    def __init__(self, objectapi, config):
        address = config.HTTP_IP, config.HTTP_PORT
        rest_api = Api(objectapi)
        self.logger = logging.getLogger(__name__)
        self.stack = Middleware(rest_api)
        class MyRequestHandler(RequestHandler):
            def handle(self):
                """Set up logging labelled by the request thread.
                Use the same label as objectapi uses for this thread.
                """
                THREAD.logger = logging.getLogger(__name__ + ':%s' %
                        objectapi.thread_label())
                return RequestHandler.handle(self)
        server = ThreadingWSGIServer(address, MyRequestHandler)
        server.set_app(self.stack)
        self.thread = threading.Thread(target=server.serve_forever)
        self.thread.daemon = True

    def start(self):
        self.thread.start()
        self.logger.info("Running.")

    def terminate(self, timeout=3):
        """timeout: maximum time in seconds allowed to shutdown cleanly.
        If the server cannot complete existing client requests within the
        specified time then this method will return anyway, after which
        processing of incomplete requests will continue on a daemon thread, i.e., only for as long as the program runs.
        """
        self.logger.info("Terminating.")
        try:
            eskimo.Lock(self.stack, timeout=timeout).acquire()
        except eskimo.Timeout:
            pass
