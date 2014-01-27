from .jenv import EnvFactory
from cheeseprism.auth import BasicAuthenticationPolicy
from cheeseprism.resources import App
from pyramid.config import Configurator
from pyramid.session import UnencryptedCookieSessionFactoryConfig
from pyramid.settings import asbool
import futures
import logging
import os


logger = logging.getLogger(__name__)


def main(global_config, **settings):
    settings = dict(global_config, **settings)
    settings.setdefault('jinja2.i18n.domain', 'CheesePrism')

    session_factory = UnencryptedCookieSessionFactoryConfig('cheeseprism')
    config = Configurator(root_factory=App, settings=settings,
                          session_factory=session_factory,
                          authentication_policy=\
                          BasicAuthenticationPolicy(BasicAuthenticationPolicy.noop_check))

    setup_workers(config.registry)

    config.add_translation_dirs('locale/')

    config.include('.request')
    config.include('.views')
    config.include('.index')

    tempspec = settings.get('cheeseprism.index_templates', '')
    config.registry['cp.index_templates'] = EnvFactory.from_str(tempspec)

    if asbool(settings.get('cheeseprism.pipcache_mirror', False)):
        config.include('.sync.pip')

    if asbool(settings.get('cheeseprism.auto_sync', False)):
        config.include('.sync.auto')

    tempfile_limit = int(settings.get('cheeseprism.temp_file_limit', 10*1024))
    config.add_request_method(lambda req: tempfile_limit,
                              name='request_body_tempfile_limit', reify=True)

    config.add_request_method(lambda req: asbool(settings.get('cheeseprism.disable.regenerate', False)),
                              name='disable_regen', reify=True)

    return config.make_wsgi_app()


def ping_proc(i):
    pid = os.getpid()
    logger.debug("worker %s up: %s", i, pid)
    return pid


def setup_workers(registry):
    """
    now thread only
    """
    settings = registry.settings

    registry['cp.executor_type'] = 'thread'

    executor = futures.ThreadPoolExecutor

    workers = int(settings.get('cheeseprism.futures.workers', 5))


    logging.info("Starting thread executor w/ %s workers", workers)
    executor = registry['cp.executor'] = executor(workers)

    # -- This initializes our threads
    workers = [str(pid) for pid in executor.map(ping_proc, range(workers))]
    logger.info("workers: %s", " ".join(workers))
