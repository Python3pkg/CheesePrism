from cheeseprism.auth import BasicAuthenticationPolicy
from cheeseprism.index import EnvFactory
from cheeseprism.resources import App
from functools import partial
from pyramid.config import Configurator
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.settings import asbool
from pyramid_jinja2 import renderer_factory
import multiprocessing
import futures
import logging

logger = logging.getLogger(__name__)


def main(global_config, **settings):
    settings = dict(global_config, **settings)

    settings.setdefault('jinja2.i18n.domain', 'CheesePrism')

    session_factory = UnencryptedCookieSessionFactoryConfig('cheeseprism')

    config = Configurator(root_factory=App, settings=settings,
                          session_factory=session_factory,
                          authentication_policy=\
                          BasicAuthenticationPolicy(BasicAuthenticationPolicy.noop_check))

    executor_type = settings.get('cheeseprism.futures', 'thread')
    executor = executor_type != 'process' and futures.ThreadPoolExecutor \
      or futures.ProcessPoolExecutor

    workers = int(settings.get('cheeseprism.futures.workers', 0))
    if executor_type == 'process' and workers <= 0:
        workers = multiprocessing.cpu_count() + 1
    else:
        workers = workers <= 0 and 10 or workers

    logging.info("using %s executor with %s workers", executor_type, workers)
    config.registry['cp.executor'] = partial(executor, workers)

    if asbool(settings.get('cheeseprism.pipcache_mirror', False)):
        config.include('.sync.pip')

    if asbool(settings.get('cheeseprism.auto_sync', False)):
        config.include('.sync.auto')

    config.add_translation_dirs('locale/')
    config.include('pyramid_jinja2')
    config.add_renderer('.html', renderer_factory)

    config.add_static_view('static', 'static')
    config.include('.request')
    config.scan('.views')
    config.scan('.index')
    config.add_route('package', 'package/{name}/{version}')
    config.add_view('.views.from_pypi', route_name='package')
    tempspec = settings.get('cheeseprism.index_templates', '')
    config.registry['cp.index_templates'] = EnvFactory.from_str(tempspec)

    if asbool(settings.get('cheeseprism.pipcache_mirror', False)):
        config.include('.sync.pip')

    if asbool(settings.get('cheeseprism.auto_sync', False)):
        config.include('.sync.auto')
    
    return config.make_wsgi_app()
