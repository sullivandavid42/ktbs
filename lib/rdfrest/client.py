# -*- coding: utf-8 -*-

#    This file is part of RDF-REST <http://liris.cnrs.fr/sbt-dev/ktbs>
#    Copyright (C) 2011 Françoise Conil /
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

"""
RDF-REST Client module.

I implement an rdflib store that acts as a proxy to a RESTful RDF graph.
"""

import types
from StringIO import StringIO
import httplib
import httplib2
from tempfile import mkdtemp 

#http://docs.python.org/howto/logging-cookbook.html
import logging
LOG = logging.getLogger(__name__)

from rdflib.store import Store, VALID_STORE
  #, CORRUPTED_STORE, NO_STORE, UNKNOWN
from rdflib.graph import Graph
#from rdflib.term import URIRef

# TODO We should scan rdflib registered parsers : rdflib/plugin.py
#      rdflib has a turtle serializer but no turtle parser
#from rdflib.parser import Parser
#from rdflib.serializer import Serializer
#from rdflib.plugin import plugins

CACHE_DIR = mkdtemp("http_cache")

_CONTENT_TYPE_PARSERS = {}
_CONTENT_TYPE_SERIALIZERS = {}

FORMAT_N3   = "n3"
FORMAT_XML  = "xml"
FORMAT_RDFA = "rdfa"
FORMAT_NT   = "nt"
FORMAT_TRIX = "trix"

PS_CONFIG_URI = "uri"
PS_CONFIG_USER = "username"
PS_CONFIG_PWD = "password"
PS_CONFIG_HTTP_CACHE = "path"
PS_CONFIG_HTTP_RESPONSE = "httpresponse"

def _get_rdflib_parsers():
    """ Try to get rdflib registered Parsers.
        TODO But how to make an automatic match Content-Type / rdflib parser ?
    """
    # parsers = plugins(name=None, kind=Parser) ## parsers in not used
    # lp = [ p.name for p in parsers ] ## lp is not used
    # ['n3', 'trix', 'xml', 'application/xhtml+xml', 'text/html', 'nt',  
    #  'application/rdf+xml', 'rdfa']

    # rdflib
    _CONTENT_TYPE_PARSERS["text/rdf+n3"] = FORMAT_N3
    # http://www.w3.org/TeamSubmission/turtle/
    _CONTENT_TYPE_PARSERS["text/turtle"] = FORMAT_N3
    # A accepter car historique
    _CONTENT_TYPE_PARSERS["application/x-turtle"] = FORMAT_N3
    # Acceptés par KTBS
    _CONTENT_TYPE_PARSERS["text/x-turtle"] = FORMAT_N3
    _CONTENT_TYPE_PARSERS["application/turtle"] = FORMAT_N3

    _CONTENT_TYPE_PARSERS["application/rdf+xml"] = "application/rdf+xml"

def _get_rdflib_serializers():
    """ Try to get rdflib registered Serializers.
        TODO Automate ?
    """
    _CONTENT_TYPE_SERIALIZERS[FORMAT_N3] = "text/turtle"
    _CONTENT_TYPE_SERIALIZERS[FORMAT_XML] = "application/rdf+xml"

# Build rdflib parsers list from content-type
_get_rdflib_parsers()

# Build rdflib serializers list 
_get_rdflib_serializers()

class ProxyStore(Store):
    """
    A Proxy store implemention.
    See http://www.rdflib.net/store/ for the detail of a store.
    Take store.py for the squeletton.

    The real store is on a server accessed with a REST protocol.
    """

    # Already define in the Store class
    context_aware = False
    formula_aware = False
    transaction_aware = False

    def __init__(self, configuration=None, identifier=None):
        """ ProxyStore initialization.
            Creates an empty Graph, intializes the HTTP client.
            Use the defaut for internal graph storage, i.e IOMemory.
            The URIref of the graph must be supplied either in identifier or
            in configuration parameter. It will be checked by open().
            The cache file path could be given in the configuration dictionary
            (__init__ only). We have to search about the memory cache.

            :param configuration: Can be a string or a dictionary. May be 
            passed to __init__() or to open(). Specified as a configuration 
            string (store database connection string). For KTBS, it is 
            preferably a dictionary which may contain credentials for HTTP 
            requests, the URI of the graph and an httpresponse supplied by the
            client (contains an RDF serialized graph already posted with 
            HTTPLIB2 and the header of the response). If the parameters are 
            in a string, the format should be "key1:value1;key2:value2". 
            May be passed to __init__() or to open().  Optionnal.
            :param identifier: URIRef identifying the graph to cache in the 
            store. 
        """

        LOG.debug("-- ProxyStore.init(configuration=%s, identifer=%s) --\n",
                  configuration, identifier)


        self._identifier = identifier
        self._format = None
        self._etags = None

        self.configuration = None
        configuration = self._configuration_extraction(configuration)

        self._graph = Graph()

        # Most important parameter : identifier and graph address
        # If not given, we can not go further
        if (identifier is not None) and len(identifier) > 0:
            if len(configuration) == 0:
                configuration = {PS_CONFIG_URI: identifier}

        # Show the network activity
        #httplib2.debuglevel = 1

        # File path for HTTPLIB2 cache
        # As it is a file cache, it is conserved between two executions
        # Should we delete the directory on application end (i.e close()) ?
        if PS_CONFIG_HTTP_CACHE in configuration.keys():
            self.httpserver = httplib2.Http(configuration[PS_CONFIG_HTTP_CACHE])
        else:
            self.httpserver = httplib2.Http(CACHE_DIR)

        # Store will call open() if configuration is not None
        Store.__init__(self, configuration)

    def open(self, configuration, create=False):
        """ Opens the store specified by the configuration string. 
            For the ProxyStore, the identifier is the graph address.

            :param configuration: Usually a configuration string of the store 
            (for database connection). May contain credentials for HTTP 
            requests. Can be a string or a dictionary. May be passed to 
            __init__() or to open(). 
            :param create: True to create a store. This not meaningfull for the
            ProxyStore. Optionnal.

            :returns: VALID_STORE on success
                      UNKNOWN No identifier or wrong identifier
                      NO_STORE
        """
        LOG.debug("-- ProxyStore.open(configuration=%s, create=%s), "
                  "identifier: %s --\n",
                  configuration, create, self._identifier)

        self.configuration = self._configuration_extraction(configuration)

        if (self._identifier is None) or len(self._identifier) == 0:
            if PS_CONFIG_URI in self.configuration.keys():
                self._identifier = self.configuration[PS_CONFIG_URI]
            else:
                raise StoreIdentifierError(identifier=self._identifier)
        else:
            if (PS_CONFIG_URI in self.configuration.keys()) and \
               (self._identifier != self.configuration[PS_CONFIG_URI]):
                raise StoreIdentifierError(identifier=self._identifier)

        if PS_CONFIG_USER in self.configuration.keys() and \
           PS_CONFIG_PWD  in self.configuration.keys():
            self.httpserver.add_credentials(self.configuration[PS_CONFIG_USER],
                                            self.configuration[PS_CONFIG_PWD])

        if PS_CONFIG_HTTP_RESPONSE in self.configuration.keys():
            # Serialized graph already sent by the client to the server
            # Populated the graph with the server response, no need to pull
            # the data from the server again
            if len(self.configuration[PS_CONFIG_HTTP_RESPONSE]) == 2:
                self._parse_header(\
                        self.configuration[PS_CONFIG_HTTP_RESPONSE][0])
                self._parse_content(\
                        self.configuration[PS_CONFIG_HTTP_RESPONSE][1])
        else:
            self._pull()

        return VALID_STORE

    @staticmethod
    def _configuration_extraction(configuration):
        """ Extract configuration data passed to ProxyStore.

            What do we do if configuration is passed twice (once in __init__
            and again in open) ? For the moment, overwrite.

            For the moment, ignore invalid configuration parameters (no
            StoreInvalidConfigurationError exception).

            :param configuration: Usually a configuration string of the store 
            (for database connection). May contain credentials for HTTP 
            requests. Can be a string or a dictionary. May be passed to 
            __init__() or to open(). Optionnal.
            :returns: A dictionnary with the extracted configuration.
        """

        extracted_configuration = {}
        
        # TODO ? if self.configuration is not None:
        if isinstance(configuration, types.DictType):
            extracted_configuration = configuration

        elif isinstance(configuration, types.StringTypes):

            if len(configuration) > 0:

                # Expect to get a key1:value1;key2:value2;.... string
                # If not formatted like this, nothing should be extracted
                for item in configuration.split(";"):
                    elems = item.split(":")

                    if len(elems) == 2:
                        extracted_configuration[elems[0]] = elems[1]

        return extracted_configuration

    def _parse_header(self, header):
        """ Parses the header of the HTTP request or response.
            TODO Analyse Content-Type HTTP header to determine
                 the serialization used
            TODO The serialization must be stored

            :param header: Header of the HTTP request or response.
        """
        # TODO Arbitrary default value to be decided
        self._format = FORMAT_N3

        # Extract Content-Type
        content_type = header['content-type']

        if len(content_type) > 0:
            content_type = content_type.split(";", 1)[0].strip()
            # Format contains corresponding rdflib format
            self._format = _CONTENT_TYPE_PARSERS[content_type]

        LOG.debug("-- ProxyStore._parse_header(), "
                  "content-type=%s, self._format=%s --",
                  content_type, self._format)

        self._etags = header.get('etag')

    def _parse_content(self, content):
        """ Parses the data in the content parameter to build the graph to 
            cache.

            :param content: HTTP received data either got by ProxyStore or
            passed by RDFREST Client.
        """
        # Creates the graph
        LOG.debug("-- ProxyStore._parse_content() using %s format", 
                  self._format)

        self._graph.parse(StringIO(content), format=self._format,
                          publicID=self._identifier)

    def _pull(self):
        """Update cache before an operation.
           This method must be called before each get-type request.
        """
        LOG.debug("-- _pull() ... start ...")

        assert self._identifier is not None, "The store must be open."

        # TODO - If there is a problem to get the graph (wrong address, ....)
        # Set an indication to notify it
        header, content = self.httpserver.request(self._identifier)

        LOG.debug("[received header]\n%s", header)

        # TODO Refine, test and define use-cases
        # httplib2 raises a httplib2.ServerNotFoundError exception when ...
        # Throw a ResourceAccessError exception in case of HTTP 404 as we have
        # no better mean at the moment
        if header.status == httplib.NOT_FOUND:
            raise ResourceAccessError(header.status)

        if not header.fromcache or self._format is None:
            LOG.debug("[received content]\n%s", content)

            if self._format is None:
                LOG.debug("Creating proxy graph  ....")
            else:
                LOG.debug("Updating proxy graph  ....")

            self._parse_header(header)
            self._parse_content(content)
            
        else:
            LOG.debug("Proxy graph is up to date ...")

        LOG.debug("-- _pull() ... stop ...")

    def _push(self):
        """ Send data to server.
            Apply the modifications on the cache, trigger an exception if data
            has already been modified on the server.
        """

        LOG.debug("-- _push() ... start ... --")

        assert self._identifier is not None, "The store must be open."

        # TODO : How to build the "PUT" request ?
        # Which data in the header ? 
        # Which serialization ? The same as we received but does rdflib supply
        # all kind of parsing / serialization ?
        headers = {'Content-Type': '%s; charset=UTF-8'
                   % _CONTENT_TYPE_SERIALIZERS[self._format],}
        if self._etags:
            headers['If-Match'] = self._etags
        data = self._graph.serialize(format=self._format)

        LOG.debug("[sent headers]\n%s", headers)
        LOG.debug("[sent data]\n%s", data)

        # TODO : Analyze the server response
        #        The server will tell if the graph has changed
        #        The server will supply new ETags ... update the data with the
        # response
        rheader, rcontent = self.httpserver.request(self._identifier,
                                                    'PUT',
                                                    data,
                                                    headers=headers)

        LOG.debug("[response header]\n%s", rheader)
        LOG.debug("[response content]\n%s", rcontent)

        if rheader.status in (httplib.OK,):
            self._parse_header(rheader)
        else:
            raise GraphChangedError(url=self._identifier, msg=rheader.status)

        LOG.debug("-- _push() ... stop ... --")

    def add(self, triple, context=None, quoted=False):
        """ Add a triple to the store.
            Apply the modifications on the cache, trigger an exception if data
            has already been modified on the server.
            
            :param triple: Triple (subject, predicate, object) to add.
            :param context: 
            :param quoted: The quoted argument is interpreted by formula-aware
            stores to indicate this statement is quoted/hypothetical. It should
            be an error to not specify a context and have the quoted argument
            be True. It should also be an error for the quoted argument to be
            True when the store is not formula-aware. 

            :returns: 
        """

        LOG.debug("-- ProxyStore.add(triple=%s, context=%s, quoted=%s) --", 
                  triple, context, quoted)

        assert self._identifier is not None, "The store must be open."

        # TODO : Wrong, assert is made to test bugs
        assert self._format is not None, "The store must be open."
        assert quoted == False, "The store -proxyStore- is not formula-aware"

        Store.add(self, triple, context, quoted)

        # Instruction suivant extraite du plugin Sleepycat
        # Store.add(self, (subject, predicate, object), context, quoted)
        self._graph.add(triple)


    def remove(self, triple, context):
        """ Remove the set of triples matching the pattern from the store

            :param triple: Triple (subject, predicate, object) to remove.
            :param context: 

            :returns: 
        """
        # pylint: disable-msg=W0222
        # Signature differs from overriden method
        LOG.debug("-- ProxyStore.remove(triple=%s, context=%s) --", 
                  triple, context)

        Store.remove(self, triple, context)

        self._graph.store.remove(triple)


    def triples(self, triple, context=None):
        """ Returns an iterator over all the triples (within the conjunctive
        graph or just the given context) matching the given pattern.

            :param triple: Triple (subject, predicate, object) to remove.
            :param context: ProxyStore is not context aware but it's internal
            cache IOMemory store is. Avoid context parameter.

            :returns: An iterator over the triples.
        """
        LOG.debug("-- ProxyStore.triples(triple=%s, context=%s) --", 
                  triple, context)

        Store.triples(self, triple) #, context=None)

        self._pull()

        return self._graph.store.triples(triple) #, context=None)

    def __len__(self, context=None):
        """ Number of statements in the store.

            :returns: The number of statements in the store.
        """
        self._pull()
        ret = len(self._graph)
        LOG.debug("******** __len__ : ProxyStore, nb statements %d", ret)
        return ret

    # ---------- Formula / Context Interfaces ---------- 
    #def contexts(self, triple=None):
    # Generator over all contexts in the graph. If triple is specified, a
    # generator over all contexts the triple is in.
    #def remove_context(self, identifier)
    # ---------- Formula / Context Interfaces ---------- 

    # ---------- Optional Transactional methods ---------- 
    def commit(self):
        """ Sends the modifications to the server.
        """
        self._push()

    def rollback(self):
        """ Cancel the modifications. Get the graph from the server.
        """
        self._pull()

    # ---------- Optional Transactional methods ---------- 

    def close(self, commit_pending_transaction=False):
        """ This closes the database connection. 
            :param commit_pending_transaction: Specifies whether to commit all
            pending transactions before closing (if the store is
            transactional). 
        """
        LOG.debug("******** close (%s) ", commit_pending_transaction)

        self._identifier = None
        self._etags = None
        self.configuration = None

        self._format = None
        self._graph.close()

        self.httpserver.clear_credentials()

    def destroy(self, configuration):
        """ This destroys the instance of the store identified by the
        configuration string.

            :param configuration: Configuration string identifying the store
        """
        LOG.debug("******** destroy (%s) ", configuration)

class GraphChangedError(Exception):
    """ Exception to be raised when the user tries to change graph data
        but the graph has already changed on the server.
    """
    def __init__(self, url=None, msg=None):
        self.url = url
        message = ("The graph has already changed on the server at %s,"
                   " the cache is not up to date. HTTP error %s") % (url, msg)
        Exception.__init__(self, message)

class StoreIdentifierError(Exception):
    """ Exception to be raised when the user tries to create a ProxyStore
        and to use it immediately with a wrong identifier. 
    """
    def __init__(self, identifier=None):
        message = ("The identifier is empty or invalid %s") % (identifier,)
        Exception.__init__(self, message)

class ResourceAccessError(Exception):
    """ Exception to be raised when the user tries to create a ProxyStore
        but the URI (identifier) is not valid ot the configuration 
        (e.g credentials) is not valid.
    """
    def __init__(self, retcode=None):
        self.retcode = retcode
        message = ("The graph can not be accessed check identifier and "
                   "configuration. retcode : %s") % (retcode,)
        Exception.__init__(self, message)