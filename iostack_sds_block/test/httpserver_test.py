# -*- coding: utf-8 -*-
"""
Test httpserver.py
"""
import eskimo
import httpserver
import json
import logging
import mox
import socket
import threading
import unittest

__copyright__ = "Copyright (c) 2015 MPSTOR mpstor.com"
__license__ = "See LICENSE.txt"
__author__ = "Michael Breen"

CONTENT_HEADER = [("Content-Type", "application/json")]
MAX_MAJOR = max(httpserver.VERSIONS.keys())
DEFAULT_VERSION = "%d.%d" % (MAX_MAJOR, httpserver.VERSIONS[MAX_MAJOR])
DEFAULT_VERSION_HEADER = [("API-Version", DEFAULT_VERSION)]

# if tests fail then change the following line
DEBUG = 0
if DEBUG:
    logging.basicConfig()
else:
    logging.basicConfig(filename="/dev/null")
logging.getLogger().setLevel(logging.DEBUG)


class TuplesComparator(mox.Comparator):
    """Checks that all the tuples in a list are equal, ignoring order.
    """
    def __init__(self, ref):
        self.ref = ref
    def equals(self, rhs):
        return sorted(self.ref) == sorted(rhs)


class HTTPServerTest(unittest.TestCase):
    """Test httpserver.
    """
    def setUp(self):
        self.mox = mox.Mox()

    def tearDown(self):
        pass

    def test_version_errors(self):
        """Use of unsupported, missing, or inconsistent API versions.
        """
        detail = ("Use a HTTP header 'API-Version: X.Y' or a "
                "path prefix /vX.Y where X.Y is "
                + " or ".join(["%s.%s" % (x, y) for (x, y) in
                sorted(httpserver.VERSIONS.items())]) + ".")
        missing = "No API version specified."
        unsupported = "Unsupported API version."
        inconsistent = "API-Version does not match path."
        invalid = "Invalid API-Version."
        major = MAX_MAJOR
        newer_major = '%d.%d' % (major + 1, 0)
        newer_minor = '%d.%d' % (major, httpserver.VERSIONS[major] + 1)
        for apiv, path, title in ((None, '/resource', missing),
                (major + 1, '/resource', unsupported),
                (newer_major, '/resource', unsupported),
                (newer_minor, '/resource', unsupported),
                (newer_minor, '/v%s/resource' % newer_minor, unsupported),
                (newer_minor, '/v%s/resource' % newer_major, inconsistent),
                ('a.1', '/resource', invalid),
                ('1.2.3', '/resource', invalid),
                (None, '/v%s/resource' % newer_minor, unsupported),
                (None, '/v%s/resource' % newer_major, unsupported),
                (None, '/v%d/resource' % (major + 1), unsupported),
                ):
            environ = {'PATH_INFO': path}
            if apiv:
                # key for "API-Version" HTTP header is 'HTTP_API_VERSION'
                environ['HTTP_API_VERSION'] = str(apiv)
            start_response = self.mox.CreateMockAnything()
            start_response("400 Bad Request", CONTENT_HEADER, None)

            self.mox.ReplayAll()
            app = None
            mw = httpserver.Middleware(app)
            body = mw(environ, start_response)
            content = json.loads(''.join(body))
            self.assertEqual(content, {'title': title, 'detail': detail})
            self.mox.VerifyAll()

    def test_version_conversion(self):
        """A server responds to a vX.Y request with vX.Z response,
        where Z is the latest supported minor version and Y < Z.
        """
        older = '%d.%d' % (MAX_MAJOR, httpserver.VERSIONS[MAX_MAJOR] - 1)
        for apiv, path in ((older, '/'), (None, '/v%s' % older)):
            environ = {'PATH_INFO': path}
            if apiv:
                environ['HTTP_API_VERSION'] = str(apiv)
            exp_environ = environ.copy()
            exp_environ['sds.version'] = MAX_MAJOR
            exp_environ['PATH_INFO'] = '/'
            exp_environ['sds.path_prefix'] = not apiv and path or ''
            exp_environ['wsgi.errors'] = mox.IsA(object)
            self.assertNotEqual(environ, exp_environ)  # sanity
            def app(environ, start_response):
                self.assertEqual(environ, exp_environ)
                start_response("200 OK", [])
                return ['{"a": "ok"}']
            start_response = self.mox.CreateMockAnything()
            start_response("200 OK", TuplesComparator(
                    CONTENT_HEADER + DEFAULT_VERSION_HEADER), None)

            self.mox.ReplayAll()
            mw = httpserver.Middleware(app)
            body = mw(environ, start_response)
            content = json.loads(''.join(body))
            self.assertEqual(content, {"a": "ok"})
            self.mox.VerifyAll()

    def test_shutting_down(self):
        """A terminating server should return a 503 to any new request.
        """
        environ = std_environ()
        start_response = self.mox.CreateMockAnything()
        start_response("503 Service Unavailable", TuplesComparator(
                CONTENT_HEADER + DEFAULT_VERSION_HEADER), None)
        self.mox.ReplayAll()
        app = None
        mw = httpserver.Middleware(app)
        with eskimo.Lock(mw):
            body = mw(environ, start_response)
        self.assertEqual(body, [])
        self.mox.VerifyAll()

    def test_request(self):
        """End-to-end test from Server() through to objectapi.
        The full functionality provided through the REST API is tested
        separately at the objectapi level, not here.
        This exercises the HAL and JSON media types.
        """
        objectapi = self.mox.CreateMockAnything()
        config = self.mox.CreateMockAnything()
        sock = socket.socket()
        sock.bind(('', 0))
        config.HTTP_IP, config.HTTP_PORT = sock.getsockname()
        sock.close()
        del sock
        # print("Serving http://%s:%s/" % (config.HTTP_IP, config.HTTP_PORT))
        server = httpserver.Server(objectapi, config)
        server.start()
        # Two request should be handled on separate threads.
        threads = []
        def sew():
            threads.append(threading.current_thread())
        for medium in "hal+json", "json":
            objectapi.thread_label().WithSideEffects(sew).AndReturn(medium)
            objectapi.get_objects("group", id=7).AndReturn([{
                    "id": 7, "created_at": "2015-09-18T13:10:40Z",
                    "name": "sg1..", "policy": 5, "nodes": [2, 4],
                    "_type": "group",
                    "_refs": {"policy": "policy", "nodes": "node"},
                    }])
            self.mox.ReplayAll()
            csock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            csock.settimeout(2)
            csock.connect((config.HTTP_IP, config.HTTP_PORT))
            request = "\r\n".join([
                    "GET /groups/7 HTTP/1.1",
                    "Host: %s:%s" % (config.HTTP_IP, config.HTTP_PORT),
                    "Accept: application/%s" % medium,
                    "API-Version: %s" % DEFAULT_VERSION,
                    "", ""])
            csock.sendall(request)
            response = ""
            while True:
                chunk = csock.recv(4096)
                if chunk:
                    response += chunk
                else:
                    break
            first_line = response.split("\r\n")[0]
            self.assertEqual(first_line, "HTTP/1.0 200 OK")
            last_line = response.split("\r\n")[-1]
            data = json.loads(last_line)
            exp_data = {"_links": {"self": {"href": "/groups/7"},
                    "nodes": [{"href": "/nodes/2"}, {"href": "/nodes/4"}],
                    "policy": {"href": "/policies/5"}},
                    "created_at": "2015-09-18T13:10:40Z",
                    "id": 7, "name": "sg1..", "nodes": [2, 4], "policy": 5}
            if medium == "json":
                del exp_data["_links"]
            self.assertEqual(data, exp_data)
            self.mox.VerifyAll()
            self.mox.ResetAll()
        self.assertNotEqual(*threads)
        server.terminate()

    def test_exception(self):
        """Test handling of exceptions thrown by application."""
        environ = std_environ()
        start_response = self.mox.CreateMockAnything()
        start_response("410 Gone", TuplesComparator(
                CONTENT_HEADER + DEFAULT_VERSION_HEADER), None)
        app = self.mox.CreateMockAnything()
        class TestException(Exception):
            def __init__(self, **args):
                self.fields = args

        app.__call__(mox.IgnoreArg(), mox.IgnoreArg()).AndRaise(
                TestException(**{"status": 410, "detail": "Oops."}))
        self.mox.ReplayAll()
        mw = httpserver.Middleware(app)
        body = mw(environ, start_response)
        data = json.loads(body[0])
        self.assertEqual(data, {"status": 410, "detail": "Oops."})
        self.mox.VerifyAll()


def std_environ(path='/', method='GET', environ=None):
    environ = environ or {}
    environ['PATH_INFO'] = path
    environ['REQUEST_METHOD'] = method
    environ['HTTP_API_VERSION'] = str(MAX_MAJOR)
    return environ


if __name__ == "__main__":
    unittest.main()
