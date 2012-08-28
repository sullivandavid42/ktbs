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

from nose.tools import eq_

from ktbs.methods.filter import LOG as FILTER_LOG
from ktbs.namespace import KTBS

from .test_ktbs_engine import KtbsTestCase


class TestFilter(KtbsTestCase):

    def __init__(self):
        KtbsTestCase.__init__(self)
        self.log = FILTER_LOG
    
    def test_filter(self):
        base = self.my_ktbs.create_base("b/")
        model = base.create_model("m")
        otype = model.create_obsel_type("#ot")
        src = base.create_stored_trace("s/", model, default_subject="alice")
        ctr = base.create_computed_trace("ctr/", KTBS.filter,
                                         {"after": "10", "before": "20"},
                                         [src],)

        self.log.info(">strictly temporally monotonic change: add o00")
        o00 = src.create_obsel("o00", otype, 0)
        eq_(len(ctr.obsels), 0)
        self.log.info(">strictly temporally monotonic change: add o05")
        o05 = src.create_obsel("o05", otype, 5)
        eq_(len(ctr.obsels), 0)
        self.log.info(">strictly temporally monotonic change: add o10")
        o10 = src.create_obsel("o10", otype, 10)
        eq_(len(ctr.obsels), 1)
        self.log.info(">strictly temporally monotonic change: add o15")
        o15 = src.create_obsel("o15", otype, 15)
        eq_(len(ctr.obsels), 2)
        self.log.info(">strictly temporally monotonic change: add o20")
        o20 = src.create_obsel("o20", otype, 20)
        eq_(len(ctr.obsels), 3)
        self.log.info(">strictly temporally monotonic change: add o25")
        o25 = src.create_obsel("o25", otype, 25)
        eq_(len(ctr.obsels), 3)
        self.log.info(">strictly temporally monotonic change: add o30")
        o30 = src.create_obsel("o30", otype, 30)
        eq_(len(ctr.obsels), 3)

        self.log.info(">non-temporally monotonic change: add o27")
        o27 = src.create_obsel("o27", otype, 27)
        eq_(len(ctr.obsels), 3)
        self.log.info(">non-temporally monotonic change: add o17")
        o17 = src.create_obsel("o17", otype, 17)
        eq_(len(ctr.obsels), 4)
        self.log.info(">non-temporally monotonic change: add o07")
        o07 = src.create_obsel("o07", otype, 7)
        eq_(len(ctr.obsels), 4)

        self.log.info(">strictly temporally monotonic change: add o35")
        o35 = src.create_obsel("o35", otype, 35)
        eq_(len(ctr.obsels), 4)

        self.log.info(">non-monotonic change: removing o15")
        with src.obsel_collection.edit() as editable:
            editable.remove((o15.uri, None, None))
        eq_(len(ctr.obsels), 3)
        self.log.info(">non-monotonic change: removing o25")
        with src.obsel_collection.edit() as editable:
            editable.remove((o25.uri, None, None))
        eq_(len(ctr.obsels), 3)
        
          
        
