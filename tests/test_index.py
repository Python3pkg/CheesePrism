from cheeseprism.utils import path
from cheeseprism.utils import resource_spec
from itertools import count
from mock import Mock
from mock import patch
from pprint import pformat as pprint
from stuf import stuf
import futures
import logging
import textwrap
import unittest

logger = logging.getLogger(__name__)
here = path(__file__).parent


def test_data_from_path():
    from cheeseprism import index
    datafile = here / 'index.json'
    assert index.IndexManager.data_from_path(datafile) == {}
    datafile.write_text("{}")
    assert index.IndexManager.data_from_path(datafile) == {}


class IndexTestCase(unittest.TestCase):
    counter = count()
    index_parent = here / "test-indexes"

    dummy = here / "dummypackage/dist/dummypackage-0.0dev.tar.gz"
    dum_whl = here / "dummypackage/dist/dummypackage-0.0dev-py27-none-any.whl"

    @classmethod
    def get_base(cls):
        return path(resource_spec(cls.index_parent))

    @property
    def base(self): return self.get_base()

    def make_one(self, index_name='test-index', pkg='dummy'):
        from cheeseprism import index
        self.count = next(self.counter)
        executor = futures.ThreadPoolExecutor(1)
        index_path = self.base / ("%s-%s" %(self.count, index_name))
        idx = index.IndexManager(index_path, executor=executor)
        pkg = getattr(self, pkg)
        pkg.copy(idx.path)
        self.dummypath = idx.path / pkg.name
        return idx

    def test_register_archive(self):
        self.im = self.make_one()
        pkgdata, md5 = self.im.register_archive(self.dummypath)
        assert md5 == '3ac58d89cb7f7b718bc6d0beae85c282'
        assert pkgdata

        idxjson = self.im.data_from_path(self.im.datafile_path)
        assert md5 in idxjson
        assert idxjson[md5] == pkgdata

    def test_write_datafile(self):
        """
        create and write archive data to index.json
        """
        self.im = self.make_one()
        data = self.im.write_datafile(hello='computer')
        assert 'hello' in data
        assert self.im.datafile_path.exists()
        assert 'hello' in self.im.data_from_path(self.im.datafile_path)

    def test_write_datafile_w_existing_datafile(self):
        """
        write data to an existing datafile
        """
        self.im = self.make_one()
        data = self.im.write_datafile(hello='computer')
        assert self.im.datafile_path.exists()

        data = self.im.write_datafile(hello='operator')
        assert data['hello'] == 'operator'
        assert self.im.data_from_path(self.im.datafile_path)['hello'] == 'operator'

    def test_regenerate_index_write_index_html_false(self):
        im = self.make_one()
        im.write_index_html = False
        home, leaves = im.regenerate_all()
        pth = im.path
        assert home is None
        assert not (pth / im.root_index_file).exists()

    def test_regenerate_index(self):
        self.im = self.make_one()
        home, leaves = self.im.regenerate_all()
        pth = self.im.path
        file_structure = [(x.parent.name, x.name) for x in pth.walk()]
        index_name = u'%s-test-index' %self.count
        expected = [(index_name, u'dummypackage'),
                    (u'dummypackage', u'index.html'),
                    (path(u'dummypackage'), path(u'index.json')),
                    (index_name, u'dummypackage-0.0dev.tar.gz'),
                    (index_name, u'index.html')]

        assert len(leaves) == 1
        assert leaves[0].exists()
        assert leaves[0].name == 'index.html'
        assert leaves[0].parent.name == 'dummypackage'

        etxt = pprint(sorted(str(x) for x in expected))
        fstxt = pprint(sorted(str(x) for x in file_structure))
        assert set(expected).issubset(file_structure), \
               textwrap.dedent("""
               Expected not a subset of result::

               expected:

                %s

               actual:

                %s""") %(etxt, fstxt)

    @patch('cheeseprism.index.IndexManager.regenerate_leaf')
    def test_regenerate_leaf_event(self, rl):
        """
        Cover event subscriber
        """
        from cheeseprism.event import PackageAdded
        from cheeseprism.index import rebuild_leaf
        self.im = self.make_one()
        event = PackageAdded(self.im, here / path('dummypackage2/dist/dummypackage-0.1.tar.gz'))
        out = rebuild_leaf(event)
        assert out is not None
        assert rl.call_args == (('dummypackage',), {})

    def test_regenerate_leaf(self):
        self.im = self.make_one()
        [x for x in self.im.regenerate_all()]
        leafindex = self.im.path / 'dummypackage/index.html'
        new_arch = here / path('dummypackage2/dist/dummypackage-0.1.tar.gz')
        new_arch.copy(self.im.path)
        added = self.im.path / new_arch.name

        before_txt = leafindex.text()
        info = self.im.pkginfo_from_file(added)
        out = self.im.regenerate_leaf(info.name)
        assert before_txt != out.text()

    @patch('pyramid.threadlocal.get_current_registry')
    def test_bulk_add_pkg(self, getreg):
        from cheeseprism.index import bulk_add_pkgs
        self.im = self.make_one()
        pkg = stuf(name='dummypackage', version='0.1',
                   filename=self.dummy.name)
        pkgs = pkg,
        index = Mock(name='index')
        index.path = self.im.path
        leaves, archs = bulk_add_pkgs(index, pkgs)

        assert len(archs) == 1
        assert len(leaves) == 1
        assert 'dummypackage' in leaves
        assert archs[0].basename() == u'dummypackage-0.0dev.tar.gz'
        assert index.regenerate_leaf.called

    def tearDown(self):
        logger.debug("teardown: %s", self.count)
        if self.base.exists():
            dirs = self.base.dirs()
            logger.info(pprint(dirs))
            logger.info(pprint([x.rmtree() for x in dirs]))

def test_group_by_magnitude():
    from cheeseprism.index import IndexManager
    fiver = range(5)
    assert IndexManager.group_by_magnitude(fiver)[0] == fiver
    assert next(IndexManager.group_by_magnitude(range(101))) == range(10)
    assert next(IndexManager.group_by_magnitude(range(1001))) == range(100)


class ClassOrStaticMethods(unittest.TestCase):

    def test_move_on_error(self):
        from cheeseprism.index import ArchiveUtil
        exc, path = Mock(), Mock()
        path.basename.return_value = '_path_'
        ArchiveUtil.move_on_error('errors', exc, path)
        assert path.rename.called
        assert path.rename.call_args[0][0] == 'errors/_path_'

    def test_pkginfo_from_file_whl(self):
        """
        .pkginfo_from_file: wheel
        """
        from cheeseprism.index import IndexManager
        with patch('pkginfo.wheel.Wheel', new=Mock(return_value=True)):
            assert IndexManager.pkginfo_from_file('blah.whl') is True

    @patch('pkginfo.bdist.BDist', new=Mock(return_value=True))
    def test_pkginfo_from_file_egg(self):
        """
        .pkginfo_from_file: bdist
        """
        from cheeseprism.index import IndexManager
        assert IndexManager.pkginfo_from_file('blah.egg') is True

    @patch('pkginfo.sdist.SDist', new=Mock(return_value=True))
    def test_pkginfo_from_file_sdist(self):
        """
        .pkginfo_from_file: sdist
        """
        from cheeseprism.index import IndexManager
        for ext in ('.gz','.tgz', '.bz2', '.zip'):
            assert IndexManager.pkginfo_from_file('blah.%s' %ext) is True

    def test_pkginfo_from_bad_ext(self):
        """
        .pkginfo_from_file with unrecognized extension
        """
        from cheeseprism.index import IndexManager
        with self.assertRaises(RuntimeError):
            IndexManager.pkginfo_from_file('adfasdkfha.adkfhalsdk')

    def test_pkginfo_from_bad_ext_handled(self):
        """
        .pkginfo_from_file with unrecognized extension
        """
        from cheeseprism.index import IndexManager
        handler = Mock(name='handler')
        IndexManager.pkginfo_from_file('adfasdkfha.adkfhalsdk', handle_error=handler)
        assert handler.call_args[0][1] == 'adfasdkfha.adkfhalsdk'
        assert isinstance(handler.call_args[0][0], RuntimeError)


    def test_pkginfo_from_no_ext(self):
        """
        .pkginfo_from_file with no extension
        """
        from cheeseprism.index import IndexManager
        with self.assertRaises(RuntimeError):
            IndexManager.pkginfo_from_file('adfasdkfha')


    def test_pkginfo_from_file_exc_and_handler(self):
        """
        .pkginfo_from_file with exception and handler
        """
        from cheeseprism.index import IndexManager
        exc = Exception("BOOM")
        with patch('pkginfo.bdist.BDist', side_effect=exc):
            eh = Mock(name='error_handler')
            IndexManager.pkginfo_from_file('bad.egg', handle_error=eh)
        assert eh.called
        assert eh.call_args[0] == (exc, 'bad.egg'), eh.call_args[0]

    def test_pkginfo_from_file_exc(self):
        """
        .pkginfo_from_file with exception and no handler
        """
        from cheeseprism.index import IndexManager
        exc = ValueError("BOOM")
        with self.assertRaises(ValueError):
            with patch('pkginfo.bdist.BDist', side_effect=exc):
                IndexManager.pkginfo_from_file('bad.egg')

def test_cleanup():
    assert not IndexTestCase.get_base().dirs()

    
def test_noop():
    from cheeseprism.index import noop
    assert noop() is None
    
