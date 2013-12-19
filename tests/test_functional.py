from ConfigParser import ConfigParser
from cheeseprism.utils import resource_spec
from itertools import count
from mock import patch
from path import path
from pprint import pformat as pprint
from pyramid.decorator import reify
import logging
import unittest
import time


logger = logging.getLogger(__name__)
here = path(__file__).parent


class FunctionalTests(unittest.TestCase):
    testdir = here / 'test-indexes'
    dummy = here / "dummypackage/dist/dummypackage-0.0dev.tar.gz"
    counter = count()
    index_parent = "egg:CheesePrism#tests/test-indexes"
    pipcache = "egg:CheesePrism#tests/pipcache"
    devini = "egg:CheesePrism#development.ini"

    dummy = here / "dummypackage/dist/dummypackage-0.0dev.tar.gz"

    @classmethod
    def get_base(cls):
        return path(resource_spec(cls.index_parent))

    base = reify(lambda self: self.get_base())

    def setUp(self):
        self.count = next(self.counter)
        self.dummy.copy(self.testdir)
        self.dummypath = self.testdir / self.dummy.name

    def makeone(self, xtra=None, index_name='test-func-index', count=None):
        from cheeseprism.wsgiapp import main
        cp = ConfigParser(dict(here=self.base))

        with open(resource_spec(self.devini)) as fp:
            cp.readfp(fp)

        defaults = dict((x, cp.get('DEFAULT', x)) for x in cp.defaults())

        count = count is None and self.count or count
        self.idxpath = index_path = self.base / ("%s-%s" %(count, index_name))

        settings = {
            'cheeseprism.file_root': index_path,
            'cheeseprism.data_json': 'data.json'
            }

        settings = xtra and dict(settings, **xtra) or settings
        app = main(defaults, **settings)

        from webtest import TestApp
        return TestApp(app)

    def test_async_bulkupdate(self):
        idxname = 'async_bulk_up'
        idxpath = self.base / "0-" + idxname
        idxpath.mkdir_p()

        self.dummy.copy(idxpath)

        testapp = self.makeone({'cheeseprism.async_restart':'true'},
                               index_name=idxname, count=0)
        time.sleep(0.02)
        res = testapp.get('/index', status=200)
        assert 'dummy' in res.body

    def test_root_thead_pip_sync(self):
        with patch.dict('os.environ', {'PIP_DOWNLOAD_CACHE': resource_spec(self.pipcache)}):
            testapp = self.makeone({'cheeseprism.futures':'thread',
                                    'cheeseprism.pipcache_mirror':'true'})
            res = testapp.get('/index', status=200)
        assert 'WUT' in res.body

    def test_root_thread(self):
        testapp = self.makeone()
        res = testapp.get('/', status=200)
        self.failUnless('Cheese' in res.body)

    def tearDown(self):
        logger.debug("teardown: %s", self.count)
        if self.base.exists():
            dirs = self.base.dirs()
            logger.debug(pprint(dirs))
            time.sleep(0.02)
            logger.debug(pprint([x.rmtree() for x in dirs]))


