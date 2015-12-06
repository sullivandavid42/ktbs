# -*- coding: utf-8 -*-

#    This file is part of KTBS <http://liris.cnrs.fr/sbt-dev/ktbs>
#    Copyright (C) 2011-2012 Pierre-Antoine Champin <pchampin@liris.cnrs.fr> /
#    Françoise Conil <francoise.conil@liris.cnrs.fr> /
#    Universite de Lyon <http://www.universite-lyon.fr>
#
#    KTBS is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    KTBS is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with KTBS.  If not, see <http://www.gnu.org/licenses/>.

from json import dumps, loads
from nose.tools import assert_set_equal, eq_, raises
from unittest import skip

from ktbs.engine.resource import METADATA
from ktbs.methods.fsa import LOG as FSA_LOG
from ktbs.namespace import KTBS, KTBS_NS_URI

from .test_ktbs_engine import KtbsTestCase

def get_custom_state(computed_trace, key=None):
        jsonstr = computed_trace.metadata.value(computed_trace.uri,
                                                METADATA.computation_state)
        jsonobj = loads(jsonstr)
        ret = jsonobj.get('custom')
        if ret is not None and key is not None:
            ret = ret.get(key)
        return ret

def assert_obsel_type(obsel, obsel_type):
    eq_(obsel.obsel_type.uri, obsel_type.uri)

def assert_source_obsels(obsel, source_obsels):
    assert_set_equal(set(obsel.iter_source_obsels()), set(source_obsels))




class TestFSA(KtbsTestCase):

    def setUp(self):
        KtbsTestCase.setUp(self)
        self.log = FSA_LOG
        self.base = self.my_ktbs.create_base("b/")
        self.model = self.base.create_model("m")
        self.otypeA = self.model.create_obsel_type("#otA")
        self.otypeB = self.model.create_obsel_type("#otB")
        self.otypeC = self.model.create_obsel_type("#otC")
        self.otypeD = self.model.create_obsel_type("#otD")
        self.otypeE = self.model.create_obsel_type("#otE")
        self.otypeX = self.model.create_obsel_type("#otX")
        self.otypeY = self.model.create_obsel_type("#otY")
        self.otypeZ = self.model.create_obsel_type("#otZ")
        self.base_structure = {
            "states": {
                "start": {
                    "transitions": [
                        {
                            "condition": self.otypeA.uri,
                            "target": "s1"
                        },
                        {
                            "condition": "#otA",
                            "target": "s2"
                        },
                        {
                            "condition": self.otypeE.uri,
                            "target": "s3"
                        },
                    ]
                },
                "s1": {
                    "max_noise": 1,
                    "transitions": [
                        {
                            "condition": self.otypeB.uri,
                            "target": "s1"
                        },
                        {
                            "condition": "#otC",
                            "target": self.otypeX.uri,
                        },
                    ]
                },
                "s2": {
                    "max_noise": 1,
                    "transitions": [
                        {
                            "condition": self.otypeC.uri,
                            "target": "s2"
                        },
                        {
                            "condition": self.otypeD.uri,
                            "target": "#otY",
                        },
                    ]
                },
                "s3": {
                    "max_noise": 1,
                    "transitions": [
                        {
                            "condition": self.otypeD.uri,
                            "target": "#otZ"
                        },
                    ]
                },
                self.otypeX.uri: {
                    "terminal": True,
                },
                "#otY": {
                    "terminal": True,
                },
                "#otZ": {
                    "terminal": True,
                },
            }
        }
        self.src = self.base.create_stored_trace("s/", self.model, default_subject="alice")

    def test_base_structure(self):
        ctr = self.base.create_computed_trace("ctr/", KTBS.fsa,
                                         {"fsa": dumps(self.base_structure)},
                                         [self.src],)
        oA = self.src.create_obsel("oA", self.otypeA, 0)
        eq_(len(ctr.obsels), 0)
        oB = self.src.create_obsel("oB", self.otypeB, 1)
        eq_(len(ctr.obsels), 0)
        oC = self.src.create_obsel("oC", self.otypeC, 2)
        eq_(len(ctr.obsels), 1)
        assert_obsel_type(ctr.obsels[0], self.otypeX)
        assert_source_obsels(ctr.obsels[0], [oA, oB, oC])
        oD = self.src.create_obsel("oD", self.otypeD, 3)
        eq_(len(ctr.obsels), 1) # no overlap, so no new obsel

    def test_allow_overlap(self):
        self.base_structure['allow_overlap'] = True
        ctr = self.base.create_computed_trace("ctr/", KTBS.fsa,
                                         {"fsa": dumps(self.base_structure)},
                                         [self.src],)
        oA = self.src.create_obsel("oA", self.otypeA, 0)
        eq_(len(ctr.obsels), 0)
        oB = self.src.create_obsel("oB", self.otypeB, 1)
        eq_(len(ctr.obsels), 0)
        oC = self.src.create_obsel("oC", self.otypeC, 2)
        eq_(len(ctr.obsels), 1)
        assert_obsel_type(ctr.obsels[0], self.otypeX)
        assert_source_obsels(ctr.obsels[0], [oA, oB, oC])
        oD = self.src.create_obsel("oD", self.otypeD, 3)
        eq_(len(ctr.obsels), 2)
        assert_obsel_type(ctr.obsels[1], self.otypeY)
        assert_source_obsels(ctr.obsels[1], [oA, oC, oD])

    def test_simultaneaous_matches(self):
        self.base_structure['allow_overlap'] = True
        ctr = self.base.create_computed_trace("ctr/", KTBS.fsa,
                                         {"fsa": dumps(self.base_structure)},
                                         [self.src],)
        oA = self.src.create_obsel("oA", self.otypeA, 0)
        eq_(len(ctr.obsels), 0)
        oE = self.src.create_obsel("oE", self.otypeE, 1)
        eq_(len(ctr.obsels), 0)
        oD = self.src.create_obsel("oD", self.otypeD, 2)
        eq_(len(ctr.obsels), 2)
        assert_set_equal(set([self.otypeY.uri, self.otypeZ.uri ]), set(
            obs.obsel_type.uri for obs in ctr.obsels
        ))