from cheeseprism.utils import path
from cheeseprism.utils import resource_spec
from itertools import count
from mock import Mock
from mock import patch
from pprint import pformat as pprint
from stuf import stuf
import json
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

    def make_one(self, pkg='dummy', index_path=None):
        from cheeseprism import index
        executor = futures.ThreadPoolExecutor(1)
        if index_path is None:
            index_path = self.new_path('test-index')
        idx = index.IndexManager(index_path, executor=executor)
        pkg = getattr(self, pkg)
        pkg.copy(idx.path)
        self.dummypath = idx.path / pkg.name
        return idx

    def new_path(self, index_name):
        count = self.count = next(self.counter)
        return self.base / ("%s-%s" %(count, index_name))

    def test_index_init_baderrorfolder(self):
        bfp = self.new_path('badfolder')
        bfp.mkdir()
        (bfp / '_errors').touch()
        idx = self.make_one(index_path=bfp)
        assert '_errors' in {x.name for x in idx.path.dirs()}
        assert '_errors.bak' in {x.name for x in idx.path.files()}

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

    def test_regenerate_index_write_html_false(self):
        im = self.make_one()
        im.write_html = False
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
        assert leaves[0].name == 'index.json'
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



    def test_leafdata(self):
        self.im = self.make_one()
        fpath = here / path('dummypackage2/dist/dummypackage-0.1.tar.gz')
        dist = Mock(name='dist')
        distinfo = dist.name, dist.version = 'distname', 'version'
        data = self.im.leafdata(fpath, dist)
        assert distinfo == (data['name'], data['version'])
        assert data['md5'] == fpath.md5hex
        assert data['size'] == fpath.size
        assert data['filename'] == fpath.name
        assert 'mtime' in data
        assert data['ctime'] == fpath.ctime
        assert 'atime' in data

    def test_rebuild_leaf_subscriber(self):
        """
        Cover event subscriber
        """
        from cheeseprism.event import PackageAdded
        from cheeseprism.index import rebuild_leaf
        self.im = self.make_one()
        event = PackageAdded(self.im,  here / path('dummypackage2/dist/dummypackage-0.1.tar.gz'))

        with patch('cheeseprism.index.IndexManager.regenerate_leaf') as rl:
            out = rebuild_leaf(event)
        assert out is not None
        assert rl.call_args == (('dummypackage',), {})

    def test_rebuild_leaf_subscriber_existing_leaf(self):
        from cheeseprism.event import PackageAdded
        from cheeseprism.index import rebuild_leaf
        self.im = self.make_one()

        self.im.regenerate_leaf('dummypackage')

        distpath = here / path('dummypackage2/dist/dummypackage-0.1.tar.gz')
        event = PackageAdded(self.im, path=distpath)
        out = rebuild_leaf(event)

        assert len(out) == 2

    def test_html_free_remove_index(self):
        idx = self.make_one()
        home, leaves = idx.regenerate_all()
        free_gen = idx._leaf_html_free(idx.path / 'dummypackage', idx.path.files("*.gz"))
        linkout = next(free_gen)
        assert 'index.html' not in {f.name for f in linkout.parent.files()}

    def test__html_free_leafdir_disappears(self):
        idx = self.make_one()
        home, leaves = idx.regenerate_all()
        leafdir = idx.path / 'dummypackage'
        free_gen = idx._leaf_html_free(leafdir, idx.path.files("*.gz"))
        leafdir.rmtree()
        with self.assertRaises(StopIteration):
            next(free_gen)

    def test__html_free_version_disappears(self):
        idx = self.make_one()
        home, leaves = idx.regenerate_all()
        leafdir = idx.path / 'dummypackage'
        versions = idx.path.files('*.gz')
        [x.remove() for x in versions]
        free_gen = idx._leaf_html_free(leafdir, versions)
        with self.assertRaises(StopIteration):
            next(free_gen)

    def test_add_version_to_leaf_html_free(self):
        idx = self.make_one()
        idx.write_html = False

        name = 'dummypackage'
        idx.regenerate_leaf(name)

        distpath = here / path('dummypackage2/dist/dummypackage-0.1.tar.gz')
        data = idx.add_version_to_leaf(distpath, name)
        assert len(data) == 2
        assert all(x.islink() for x in (idx.path / name).files("*.gz"))

    def test_cleanup_links_version_removed(self):
        idx = self.make_one()
        idx.write_html = False

        name = 'dummypackage'
        idx.regenerate_leaf(name)

        leafdir = idx.path / name
        leafjson = leafdir / 'index.json'

        rem, miss = idx.cleanup_links(leafdir, leafjson, [])
        assert len(rem) == 1
        assert rem[0].name == 'dummypackage-0.0dev.tar.gz'

    def test_cleanup_links_archive_missing(self):
        idx = self.make_one()
        idx.write_html = False

        name = 'dummypackage'
        idx.regenerate_leaf(name)

        leafdir = idx.path / name
        leafjson = leafdir / 'index.json'

        badpath = Mock()
        badpath.name = 'dummypackage-0.0dev.tar.gz'
        badpath.exists.return_value = False

        rem, miss = idx.cleanup_links(leafdir, leafjson, [badpath])
        assert len(miss) == 1
        assert miss[0] == badpath.name
        assert leafjson.text() == '[]'

    def test_add_version_to_leaf_nodups(self):
        self.im = self.make_one()

        name = 'dummypackage'
        self.im.regenerate_leaf(name)

        distpath = here / path('dummypackage2/dist/dummypackage-0.1.tar.gz')

        data = self.im.add_version_to_leaf(distpath, name)
        data = self.im.add_version_to_leaf(distpath, name)
        assert len(data) == 2

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

    def test_no_leaf_index_write_html_false(self):
        """
        leaf index should not exist if index.write_html is False
        """
        self.im = self.make_one()
        self.im.write_html = False
        [x for x in self.im.regenerate_all()]

        leafindex = self.im.path / 'dummypackage/index.html'
        assert not leafindex.exists()

    def test_regenerate_leaf_html_free(self):
        self.im = self.make_one()
        self.im.write_html = False
        [x for x in self.im.regenerate_all()]

        new_arch = here / path('dummypackage2/dist/dummypackage-0.1.tar.gz')
        new_arch.copy(self.im.path)
        added = self.im.path / new_arch.name

        info = self.im.pkginfo_from_file(added)
        out = self.im.regenerate_leaf(info.name)
        with open(out) as fd:
            data = json.load(fd)
        assert new_arch.name in set([x['filename'] for x in data])
        symlink = out.parent / new_arch.name
        assert symlink.exists() is True

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

    @patch('pyramid.threadlocal.get_current_registry')
    def test_bulk_add_pkg_regen_error(self, getreg):
        with patch('cheeseprism.index.IndexManager.regenerate_leaf') as rl:
            rl.side_effect = ValueError('BAAAAAAD')
            from cheeseprism.index import bulk_add_pkgs

            idx = self.make_one()
            pkg = stuf(name='dummypackage', version='0.1',
                       filename=self.dummy.name)
            pkgs = pkg,
            assert bulk_add_pkgs(idx, pkgs)

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


def test_async_bulk_update_at_start():
    from cheeseprism.index import async_bulk_update_at_start as func
    event = Mock()
    thread_ctor = Mock()
    func(event, thread=thread_ctor)


def test_bulk_update_subscriber():
    from cheeseprism.index import bulk_update_index
    from cheeseprism.event import IndexUpdate
    event = Mock(name='event', spec=IndexUpdate(Mock(), Mock()))
    idx = event.index = Mock(name='idx')
    idx.attach_mock(Mock(return_value=[]), 'update_data')

    with patch('cheeseprism.index.bulk_add_pkgs', return_value=True):
        assert bulk_update_index(event) == True
