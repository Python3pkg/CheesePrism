from path import path
from mock import Mock

here = path('.')
testdir = here / 'test-indexes/test-main'

def test_main():
    """
    sanity check for code that creates wsgi app
    """
    from cheeseprism.wsgiapp import main
    globconf = dict()
    app = main(globconf, **{'cheeseprism.index_templates':'',
                            'cheeseprism.file_root': testdir,
                            'cheeseprism.data_json': 'data.json'})
    assert app

def test_sig_handler():
    from cheeseprism.wsgiapp import sig_handler
    exe = Mock(name='exe')
    sig_handler(exe, 1, None)
    assert exe.shutdown.called

def teardown():
    if testdir.exists():
        testdir.rmtree()
