from cheeseprism import index
from cheeseprism import utils
from cheeseprism.resources import App
from cheeseprism.utils import path
from contextlib import contextmanager
from mock import Mock
from mock import patch
from pyramid import testing
from pyramid.decorator import reify
from pyramid.events import subscriber
from pyramid.httpexceptions import HTTPFound
from stuf import stuf
from test_pipext import PipExtBase
import futures
import itertools
import unittest

here = path(__file__).parent


def test_instructions():
    from cheeseprism.views import instructions
    assert instructions(None, None)


class ViewTests(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def setup_event(self):
        self.event_results = {}
        from cheeseprism.event import IPackageEvent

        @subscriber(IPackageEvent)
        def test_event_fire(event):
            self.event_results.setdefault(event.__class__.__name__, []).append(event)

        self.config.add_subscriber(test_event_fire)

    def tearDown(self):
        self.event_results = None
        testing.tearDown()
        CPDummyRequest._namer = None
        if CPDummyRequest.test_dir is not None:
            CPDummyRequest.test_dir.rmtree()
            CPDummyRequest.test_dir = None
        CPDummyRequest._index_data = {}
        for d in CPDummyRequest.cleanup:
            d.rmtree_p()
        CPDummyRequest.cleanup = []

    @patch('cheeseprism.rpc.PyPi.search')
    def test_find_package(self, search_pypi):
        search_pypi.return_value = ['1.3a2']
        from cheeseprism.views import find_package
        request = testing.DummyRequest()
        request.POST['search_box'] = 'pyramid'
        out = find_package(App(request), request)
        assert out['releases'] == None
        assert out['search_term'] == None

        request.method = 'POST'
        out = find_package(App(request), request)
        assert out['releases'] == ['1.3a2'], "%s != %s" %(out['releases'], ['1.3a2'])
        assert out['search_term'] == 'pyramid'

    @patch('cheeseprism.rpc.PyPi.release_urls')
    def test_package_no_details(self, pd):
        """
        pypi doesn't know anything about our package
        """
        from cheeseprism.views import from_pypi
        pd.return_value = None
        request = testing.DummyRequest()
        request.matchdict.update(dict(name='boto',
                                      version='1.2.3'))
        out = from_pypi(request)
        assert isinstance(out, HTTPFound)
        assert out.location == '/find-packages'

    @patch('cheeseprism.rpc.PyPi.release_urls')
    def test_package_md5_matches(self, pd):
        """
        package is already in index
        """
        from cheeseprism.views import from_pypi
        td = dict(name='boto',
                  version='1.2.3',
                  md5_digest='12345',
                  filename='boto-1.2.3.tar.gz')
        pd.return_value = [td]
        request = CPDummyRequest()
        request.matchdict.update(td)
        request.index_data.update({'12345':True})
        out = from_pypi(request)
        assert isinstance(out, HTTPFound)
        assert out.location == '/index/boto'

    @patch('cheeseprism.rpc.PyPi.release_urls')
    def test_package_httperror(self, pd):
        """
        from_pypi: test catching httperror
        """
        request = self.package_request(pd)
        with patch('requests.get') as get:
            from cheeseprism import views; reload(views)
            get.side_effect = views.HTTPError('http://boto', 500, 'KABOOM', dict(), None)
            out = views.package(request)
        assert isinstance(out, HTTPFound)

    @patch('cheeseprism.rpc.PyPi.release_urls')
    def test_package_urlerror(self, pd):
        """
        from_pypi: test catching urlerror
        """
        request = self.package_request(pd)
        with patch('requests.get') as get:
            from cheeseprism import views; reload(views)
            get.side_effect = views.URLError('kaboom')
            out = views.package(request)
        assert isinstance(out, HTTPFound)
        assert out.location == '/find-packages'

    @patch('cheeseprism.rpc.PyPi.release_urls')
    def test_package_good(self, pd):
        """
        from_pypi: test catching urlerror
        """
        request = self.package_request(pd)
        with patch('requests.get') as get:
            resp = get.return_value = Mock('response')
            resp.content = PipExtBase.dists['dp'].bytes()
            from cheeseprism import views; reload(views)
            out = views.package(request)
        assert isinstance(out, HTTPFound)
        assert out.location == '/index/boto'

    @patch('cheeseprism.rpc.PyPi.release_urls')
    def test_package_downloads_ok_but_bad(self, pd):
        """
        from_pypi: test catching urlerror
        """
        request = self.package_request(pd)
        with patch('requests.get') as get:
            resp = get.return_value = Mock('response')
            resp.content = PipExtBase.dists['dp'].bytes()
            from cheeseprism import views; reload(views)
            with patch('cheeseprism.index.IndexManager.pkginfo_from_file') as pkff:
                pkff.side_effect = ValueError("KABOOM")
                out = views.package(request)
        assert isinstance(out, HTTPFound)
        assert out.location == '/find-packages'

    def package_request(self, pd, td=None):
        if td is None:
            td = dict(name='boto',
                      version='1.2.3',
                      md5_digest='12345',
                      url='http://boto',
                      filename='boto-1.2.3.tar.gz')
        pd.return_value = [td]
        request = CPDummyRequest()
        request.matchdict.update(td)
        return request

    def test_index_view(self):
        from cheeseprism.views import upload as index
        request = testing.DummyRequest()
        assert index(App(request), request) == {}

    @property
    def base_cr(self):
        self.curreq = request = CPDummyRequest()
        return App(request), request

    def test_regenerate_index(self):
        """
        Basic regeneration of entire index
        """
        from cheeseprism.views import regenerate_index
        context, request = self.base_cr
        out = regenerate_index(context, request)
        assert out['disabled'] == False
        assert isinstance(out, dict)

        context, req = self.base_cr
        req.method = "POST"

        out = regenerate_index(context, req)
        assert isinstance(out, HTTPFound)
        assert req.file_root.exists(), "index not created at %s" %req.file_root
        assert len(req.file_root.files()) == 2
        assert set([x.name for x in req.file_root.files()]) == set(('index.html', 'index.json'))

    def test_upload_raises(self):
        from cheeseprism.views import upload
        context, request = self.base_cr
        request.POST['content'] = ''
        request.method = 'POST'
        with self.assertRaises(RuntimeError):
            upload(context, request)

    def test_upload_raises_packageadded(self):
        """
        If adding the package raises an error, an exception should be logged
        """
        from cheeseprism.views import upload
        self.setup_event()
        context, request = self.base_cr
        request.method = 'POST'
        request.POST['content'] = FakeFS(path('dummypackage2/dist/dummypackage-0.1.tar.gz'))
        with patch('cheeseprism.views.event.PackageAdded',
                   side_effect=RuntimeError('Kaboom')):
            with patch('path.path.write_bytes'):
                with self.assertRaises(RuntimeError):
                    upload(context, request)

    @patch('path.path.write_bytes')
    def test_upload(self, wb):
        from cheeseprism.views import upload
        self.setup_event()
        context, request = self.base_cr
        request.method = 'POST'
        request.POST['content'] = FakeFS(path('dummypackage/dist/dummypackage-0.0dev.tar.gz'))
        with patch('cheeseprism.index.IndexManager.pkginfo_from_file',
                   return_value=stuf(name='dummycode', version='0.0dev')) as pkif:
            res = upload(context, request)
            assert pkif.called
            assert 'PackageAdded' in self.event_results
            assert self.event_results['PackageAdded'][0].name == pkif.return_value.name
        assert res.headers == {'X-Swalow-Status': 'SUCCESS'}

    def test_upload_w_rename(self):
        from cheeseprism.views import upload
        self.setup_event()
        context, request = self.base_cr

        request._namer = utils.strip_master
        request.method = 'POST'
        request.POST['content'] = FakeFS(path('mastertest-0.0-master.tar.gz'))

        def test_pkif(p, moe):
            assert p.basename() == u'mastertest-0.0.tar.gz'
            return stuf(name='mastertest', version='0.0-master')

        with patch('cheeseprism.index.IndexManager.pkginfo_from_file',
                   side_effect=test_pkif) as pkif:

            res = upload(context, request)
            assert pkif.called

        assert res.headers == {'X-Swalow-Status': 'SUCCESS'}

    def test_from_requirements_GET(self):
        from cheeseprism.views import from_requirements
        context, request = self.base_cr
        assert from_requirements(context, request) == {}

    def test_from_requirements_POST(self):
        from cheeseprism.views import from_requirements
        context, request = self.base_cr
        flash = request.session.flash = Mock('flash')
        notify = request.registry.notify = Mock('notify')
        request.method = 'POST'
        reqfile = here / 'req-1.txt'
        request.POST['req_file'] = FakeFS(reqfile, body=reqfile.text())
        with mock_downloader():
            out = from_requirements(context, request)
            assert out
            assert flash.called
            assert notify.called


@contextmanager
def mock_downloader():
    with patch('cheeseprism.pipext.RequirementDownloader') as dl:
        dler = dl.return_value = Mock(name='downloader')
        pkgi, outf = Mock(name='pkginfo'), Mock(name='outfile')
        outf.filename = 'outfile'
        pkgi.name = "dummyfile"
        dler.download_all.return_value = (pkgi, outf),
        dler.skip = (outf,)
        dler.errors = ('error',)
        dl.req_set_from_file.return_value = (dl, Mock(name='finder'))
        yield dl


class DummyResponse(object):
    def __init__(self):
        self.headers = {}


class FakeFS(object):
    def __init__(self, path, body="Some gzip binary"):
        self.filename = path.name
        self.file = Mock()
        self.file.read.return_value = body


class CPDummyRequest(testing.DummyRequest):
    test_dir = None
    counter = itertools.count()
    env = None
    _index_data = {}
    _namer = None
    cleanup = []
    disable_regen = False

    @reify
    def namer(self):
        if self._namer is None:
            from cheeseprism.utils import secure_filename
            return secure_filename
        return self._namer

    @property
    def userid(self):
        return 'bob'

    @property
    def settings(self):
        return {}

    @property
    def file_root(self):
        test_dir = getattr(self, 'test_dir')
        if test_dir is None:
            test_dir = '%s-view-tests' %next(self.counter)
            self.test_dir = test_dir = path(__file__).parent / "test-indexes" / test_dir
            self.test_dir.mkdir_p()
            self.cleanup.append(test_dir)
        return self.test_dir

    @property
    def index_templates(self):
        if self.env is None:
            self.env = index.EnvFactory.from_str()
        return self.env

    @property
    def index(self):
        return index.IndexManager(self.file_root,
                                  template_env=self.index_templates,
                                  executor=futures.ThreadPoolExecutor(max_workers=4))

    @reify
    def response(self):
        return DummyResponse()

    @reify
    def index_data_path(self):
        return self.file_root / 'index.json'

    @reify
    def index_data(self):
        return self._index_data
