# -*- coding: utf-8 -*-

#    This file is part of RDF-REST <http://champin.net/2012/rdfrest>
#    Copyright (C) 2011-2012 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Françoise Conil <francoise.conil@liris.cnrs.fr> /
#    Universite de Lyon <http://www.universite-lyon.fr>
#
#    RDF-REST is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    RDF-REST is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with RDF-REST.  If not, see <http://www.gnu.org/licenses/>.

from pytest import mark

from StringIO import StringIO

from rdflib import Graph, Literal, RDF, RDFS, URIRef

#from subprocess import Popen, PIPE
from sys import stderr
from webob import Request

from example2 import Group2Implementation, Item2Implementation, \
    make_example2_service
from rdfrest.exceptions import SerializeError
from rdfrest.cores.factory import unregister_service
from rdfrest.http_server import HttpFrontend
from rdfrest.serializers import register_serializer
from rdfrest.util import urisplit
from rdfrest.util.config import get_service_configuration
from utest.example1 import EXAMPLE

URL = "http://localhost:8001/"

class TestHttpFront(object):

    service = None
    server = None

    def setup(self):
        service_config = get_service_configuration()
        self.service = make_example2_service(service_config)
        #root = self.service.get(URIRef(URL))
        root = self.service.get(self.service.root_uri, [EXAMPLE.Group2])
        assert isinstance(root, Group2Implementation)
        root.create_new_simple_item("foo")
        # max-age is now deprecated, cache_control="max-age=60")
        self.app = HttpFrontend(self.service, service_config)

    def teardown(self):
        if self.app is not None:
            del self.app
        if self.service is not None:
            unregister_service(self.service)
            del self.service

    def request(self, url, method="GET", body=None, headers=None):
        scheme, http_host, path_info, query_string, frag_id = urisplit(url)
        if frag_id is not None:
            raise ValueError("request should not include a fragment-id")
        if ":" in http_host:
            netloc, port = http_host.split(":")
        else:
            netloc = http_host
            port = "80" # should be different if scheme == 'https'
        environ = {
            "HTTP_ACCEPT": "test/turtle,*/*;q=.1",
            "HTTP_HOST": http_host,
            "HTTP_USER_AGENT": "unit-test",
            "PATH_INFO": path_info,
            "REMOTE_ADDR": "127.0.0.1",
            "REMOTE_HOST": "localhost.localdomain",
            "REQUEST_METHOD": method.upper(),
            "SCRIPT_NAME": "",
            "SERVER_NAME": netloc,
            "SERVER_PORT": port,
            "SERVER_PROTOCOL": "HTTP/1.1",
            "SERVER_SOFTWARE": "direct-access",
            "wsgi.errors": stderr,
            "wsgi.file_wrapper": body and [body] or [],
            "wsgi.input": StringIO(body or ""),
            "wsgi.multiprocess": "False",
            "wsgi.multithread": "False",
            "wsgi.run_once": "False",
            "wsgi.url_scheme": scheme,
            "wsgi.version": "(1, 0)"
            }
        if query_string is not None:
            environ["QUERY_STRING"] = query_string
        if body is not None:
            environ["CONTENT_LENGTH"] = str(len(body))
            environ["CONTENT_TYPE"] = "text/plain;charset=utf-8"
        if headers is not None:
            for key, val in headers.items():
                key = key.upper()
                key = key.replace("-", "_")
                if key not in ("CONTENT_LENGTH", "CONTENT_TYPE"):
                    key = "HTTP_" + key
                environ[key] = val

        req = Request(environ)
        res = req.get_response(self.app)
        return res, res.body


    def test_bad_method(self):
        resp, content = self.request(URL, "XXX")
        assert resp.status_int == 405


    def test_get_not_found(self):
        resp, content = self.request(URL+"not_there")
        assert resp.status_int == 404

    def test_get(self):
        resp, content = self.request(URL)
        assert resp.status_int == 200

    def test_get_valid_params(self):
        resp, content = self.request(URL+"?valid=a")
        assert resp.status_int == 200

    def test_get_invalid_params(self):
        resp, content = self.request(URL+"?invalid=a")
        assert resp.status_int == 404

    def test_get_not_allowed(self):
        resp, content = self.request(URL+"?notallowed=a")
        assert resp.status_int == 405

    def test_get_redirect(self):
        resp, content = self.request(URL+"?redirect=foo")
        assert resp.status_int == 303
        assert resp.location == URL+"foo"

    def test_get_proxy(self):
        resp, content = self.request(URL+"@proxy")
        assert resp.status_int == 303
        assert resp.location == URL



    def test_put_not_found(self):
        resp_put, content_put = self.request(URL+"not_there", "PUT",
                                                      "")
        assert resp_put.status_int == 404

    def test_put_without_etag(self):
        resp_get, content_get = self.request(URL)
        assert resp_get.content_type is not None
        reqhead = { "content-type": resp_get.content_type }
        resp_put, content_put = self.request(URL, "PUT", content_get,
                                                      reqhead)
        assert resp_put.status_int == 403

    def test_put_bad_content(self):
        resp_get, content_get = self.request(URL)
        assert resp_get.etag is not None
        assert resp_get.content_type is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": resp_get.content_type,
            # NB: content-type and etag must be kept consistent
            }
        new_content = ">" # illegal in most syntaxes (Turtle, XML, JSON, HTML)
        resp_put, content_put = self.request(URL, "PUT", new_content,
                                                      reqhead)
        assert resp_put.status_int == 400

    def test_put_bad_mediatype(self):
        resp_get, content_get = self.request(URL)
        assert resp_get.etag is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": "application/x-not-supported"
            }
        new_content = ""
        resp_put, content_put = self.request(URL, "PUT", new_content,
                                                      reqhead)
        #assert resp_put.status_int == 415 # no parser found
        # NB: in fact, the bad mediatype does not match the etag, so we get
        assert resp_put.status_int == 412 # pre-condition failed

    def test_put_idem(self, url=URL):
        resp_get, content_get = self.request(url)
        assert resp_get.etag is not None
        assert resp_get.content_type is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": resp_get.content_type,
            }
        resp_put, content_put = self.request(url, "PUT", content_get,
                                                      reqhead)
        assert resp_put.status_int == 200
        assert "etag" in resp_put.headers

    def test_put_legal_rdf(self):
        reqhead = { "accept": "text/nt" }
        resp_get, content_get = self.request(URL, headers=reqhead)
        graph = Graph()
        graph.parse(data=content_get, publicID=URL, format="nt")
        graph.set((URIRef(URL), RDFS.label, Literal("label has been changed")))
        new_content = graph.serialize(format="nt")
        assert resp_get.etag is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": "text/nt",
            }
        resp_put, content_put = self.request(URL, "PUT", new_content,
                                                      reqhead)
        assert resp_put.status_int == 200
        assert "etag" in resp_put.headers

    def test_put_illegal_rdf(self):
        # try to put a graph without any rdf:type for the resource
        reqhead = { "accept": "text/nt" }
        resp_get, content_get = self.request(URL, headers=reqhead)
        graph = Graph()
        graph.parse(data=content_get, publicID=URL, format="nt")
        graph.remove((URIRef(URL), RDF.type, None))
        new_content = graph.serialize(format="nt")
        assert resp_get.etag is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": "text/nt",
            }
        resp_put, content_put = self.request(URL, "PUT", new_content,
                                                      reqhead)
        assert resp_put.status_int == 403

    def test_put_valid_params(self):
        self.test_put_idem(URL+"?valid=a")

    def test_put_invalid_params(self):
        reqhead = { "content-type": "text/turtle" }
        resp_put, content_put = self.request(URL+"invalid=a", "PUT",
                                                 POSTABLE_TURTLE, reqhead)
        assert resp_put.status_int == 404



    def test_post_not_found(self):
        resp_put, content_put = self.request(URL+"not_there", "POST",
                                                      "")
        assert resp_put.status_int == 404

    def test_post_bad_content(self):
        new_content = "illegal xml"
        reqhead = { "content-type": "application/rdf+xml" }
        resp, content = self.request(URL, "POST", new_content, reqhead)
        assert resp.status_int == 400

    def test_post_bad_mediatype(self):
        new_content = ""
        reqhead = { "content-type": "application/x-not-supported" }
        resp, content = self.request(URL, "POST", new_content, reqhead)
        assert resp.status_int == 415

    def test_post_legal_rdf(self, url=URL):
        #graph = Graph()
        #graph.parse(data=POSTABLE_TURTLE, publicID=url, format="n3")
        #new_content = graph.serialize(format="nt")
        #reqhead = { "content-type": "text/nt" }
        reqhead = { "content-type": "text/turtle" }
        resp, content = self.request(url, "POST", POSTABLE_TURTLE,
                                              reqhead)
        assert resp.status_int == 201
        assert resp.location
        resp, content = self.request(resp.location)
        assert resp.status_int == 200

    def test_post_illegal_rdf(self):
        # try to post a graph without an rdf:type for the created element
        graph = Graph()
        graph.parse(data=POSTABLE_TURTLE, publicID=URL, format="n3")
        created = next(graph.triples((URIRef(URL), None, None)))[2]
        graph.remove((created, RDF.type, None))
        new_content = graph.serialize(format="nt")
        reqhead = { "content-type": "text/nt" }
        resp, content = self.request(URL, "POST", new_content, reqhead)
        assert resp.status_int == 403

    def test_post_valid_params(self):
        self.test_post_legal_rdf(URL+"?valid=a")

    def test_post_invalid_params(self):
        reqhead = { "content-type": "text/turtle" }
        resp, content = self.request(URL+"?invalid=a", "POST",
                                         POSTABLE_TURTLE, reqhead)
        assert resp.status_int == 404



    def test_delete_not_found(self):
        resp_put, content_put = self.request(URL+"not_there", "DELETE")
        assert resp_put.status_int == 404

    def test_delete(self):
        resp, content = self.request(URL + "foo", "DELETE")
        assert resp.status_int == 204

    def test_delete_conflict(self):
        # we create a non-empty group, then try to delete it
        reqhead = { "content-type": "text/turtle" }
        resp, _       = self.request(URL, "POST", POSTABLE_TURTLE,
                                              reqhead)
        url2 = resp.location
        assert url2 is not None
        _               = self.request(url2, "POST", POSTABLE_TURTLE,
                                              reqhead)
        resp, content = self.request(url2, "DELETE")
        assert resp.status_int == 409

    def test_delete_valid_params(self):
        resp, content = self.request(URL + "foo?valid=a", "DELETE")
        assert resp.status_int == 204

    def test_delete_invalid_params(self):
        resp, content = self.request(URL + "foo?invalid=a", "DELETE")
        assert resp.status_int == 404


    def test_cache_control(self):
        resp, _ = self.request(URL)
        assert resp.cache_control is not None
        resp, _ = self.request(URL + "foo")
        assert resp.cache_control is not None


    def test_serialize_error(self):
        # we use the fact that rdfrest_demo can "simulate" a serialize error
        resp, content = self.request(URL, headers={"accept": "text/errer"})
        assert resp.status_int == 550


    @mark.parametrize("ctype", [ "text/turtle",
                                 "application/rdf+xml",
                                 "text/nt",
    ])
    def test_ctype(self, ctype):
        self.teardown()
        self.setup()
        reqhead = { "accept": ctype }
        resp_get, content_get = self.request(URL, headers=reqhead)
        assert resp_get.status_int == 200
        assert resp_get.content_type == ctype
        assert resp_get.etag is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": ctype,
            }
        resp_put, content_put = self.request(URL, "PUT", content_get, reqhead)
        assert resp_put.status_int == 200



    def test_max_bytes_get_ok(self):
        self.app.max_bytes = 1000
        self.test_get()

    def test_max_bytes_get_ko(self):
        self.app.max_bytes = 1000
        foo = self.service.get(URIRef(URL + "foo"), [EXAMPLE.Item2])
        assert isinstance(foo, Item2Implementation)
        with foo.edit(_trust=True) as editable:
            editable.add((foo.uri, RDFS.label, Literal(1000*"x")))
        resp, content = self.request(URL + "foo")
        assert resp.status_int == 403

    def test_max_bytes_put_ok(self):
        self.app.max_bytes = 1000
        self.test_put_idem()

    def test_max_bytes_put_ko(self):
        self.app.max_bytes = 1000
        resp_get, content_get = self.request(URL)
        assert resp_get.etag is not None
        assert resp_get.content_type is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": resp_get.content_type,
            }
        content_get = content_get + "#"*1000
        resp_put, content_put = self.request(URL, "PUT", content_get, reqhead)
        assert resp_put.status_int == 413

    def test_max_bytes_post_ok(self):
        self.app.max_bytes = 1000
        self.test_post_legal_rdf()

    def test_max_bytes_post_ko(self):
        self.app.max_bytes = 1000
        reqhead = { "content-type": "text/turtle" }
        resp, content = self.request(URL, "POST", POSTABLE_TURTLE + "#"*1000,
                                     reqhead)
        assert resp.status_int == 413



    def test_max_triples_get_ok(self):
        self.app.max_triples = 10
        self.test_get()

    def test_max_triples_get_ko(self):
        self.app.max_triples = 10
        foo = self.service.get(URIRef(URL + "foo"))
        with foo.edit(_trust=True) as editable:
            for i in range(10):
                editable.add((foo.uri, RDFS.label, Literal("label%i" % i)))
        resp, content = self.request(URL + "foo")
        assert resp.status_int == 403

    def test_max_triples_put_ok(self):
        self.app.max_triples = 10
        self.test_put_idem()

    def test_max_triples_put_ko(self):
        self.app.max_triples = 10
        resp_get, content_get = self.request(URL)
        assert resp_get.etag is not None
        assert resp_get.content_type is not None
        reqhead = {
            "if-match": resp_get.etag,
            "content-type": resp_get.content_type,
            }
        content_get += ("<> <http://example.org/other#label>"
                        + ",".join('"%s"' % i for i in range(10))
                        + ".")
        resp_put, content_put = self.request(URL, "PUT", content_get, reqhead)
        assert resp_put.status_int == 413

    def test_max_triples_post_ok(self):
        self.app.max_triples = 10
        self.test_post_legal_rdf()

    def test_max_triples_post_ko(self):
        self.app.max_triples = 10
        reqhead = { "content-type": "text/turtle" }
        patch = ("<http://example.org/other#label> "
                 + ", ".join('"%s"' % i for i in range(10))
                 + "; ].")
        content = POSTABLE_TURTLE.replace("].", patch)
        resp, content = self.request(URL, "POST", content, reqhead)
        assert resp.status_int == 413



POSTABLE_TURTLE = """
    @prefix : <http://example.org/example/> .
    @prefix o: <http://example.org/other-ns/> .

    <> :contains [
        a :Group2 ;
        :label "created group" ;
    ].
"""

@register_serializer("text/errer", None, 01)
def serialize_error(graph, uri, _bindings=None):
    """I always raise an exception.

    I am used to test what happens on serialize errors.
    """
    raise SerializeError("just for testing")
