from cheeseprism.auth import BasicAuthenticationPolicy
from cheeseprism.index import EnvFactory
from cheeseprism.resources import App
from pyramid.config import Configurator
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid_jinja2 import renderer_factory
import futures


def main(global_config, **settings):
    settings = dict(global_config, **settings)
    settings.setdefault('jinja2.i18n.domain', 'CheesePrism')

    session_factory = UnencryptedCookieSessionFactoryConfig('cheeseprism')

    config = Configurator(root_factory=App, settings=settings,
                          session_factory=session_factory,
                          authentication_policy=\
                          BasicAuthenticationPolicy(BasicAuthenticationPolicy.noop_check))

    executor_type = settings.get('cp.futures', 'thread')
    executor = executor_type != 'process' and futures.ThreadPoolExecutor \
      or futures.ProcessPoolExecutor
      
    workers = int(settings.get('cp.futures.workers', 0))
    if executor_type == 'process':
        workers = workers <= 0 and None or workers
    else:
        workers = workers <= 0 and 10 or workers

    config.registry['cp.executor'] = executor(workers)
    config.add_translation_dirs('locale/')
    config.include('pyramid_jinja2')
    config.add_renderer('.html', renderer_factory)

    config.add_static_view('static', 'static')
    config.include('.request')
    config.scan('.views')
    config.scan('.index')
    config.add_route('package', 'package/{name}/{version}')
    config.add_view('.views.from_pypi', route_name='package')
    settings['index_templates'] = EnvFactory.from_str(settings['cheeseprism.index_templates'])

    return config.make_wsgi_app()
