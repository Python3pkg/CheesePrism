from . import utils
from .index import IndexManager
from .index import bulk_add_pkgs
from .utils import path
from threading import Thread
import logging
import os
import time

logger = logging.getLogger(__name__)


def sync_folder(index, folder):
    with utils.benchmark("Sync packages"):
        EXTS = index.archive_tool.EXTS
        candidates = dict((x.md5hex, x)\
                          for x in folder.files()\
                          if EXTS.match(x))

        current = dict((x.md5hex, x)\
                       for x in index.files)

        new = set(candidates) - set(current)
        for md5 in new:
            cpath = candidates.get(md5, None)
            if cpath is None:
                logger.error("missing md5: %s", md5)
                break
            _, name = cpath.rsplit('%2F', 1)
            cpath.copy(index.path / name)


def update_index(index, reg):
    with utils.benchmark('Update index after sync'):
        new_pkgs = index.update_data()
        if index.path.exists(): #for testing
            with utils.benchmark("New packages notifier: %s" %new_pkgs):
                leaves, archs = bulk_add_pkgs(index, new_pkgs, register=False)

            if index.write_index_html is True \
              and not all((index.datafile_path.exists(), index.home_file.exists())):
                index.write_index_home(index.projects_from_archives())

            return leaves, archs


def wait_for_file(fp, sleep=0.2, max_tries=5):
    fp = path(fp)
    if not fp.exists():
        logger.info('Waiting for base dir: %s' %fp)
        for x in range(max_tries):
            if not fp.exists():
                time.sleep(0.5)
                logger.info('bueller?')
            else:
                logger.info('Found based dir: %s' %fp)
                yield fp
    raise RuntimeError('%s not found in %ss' %(fp, max_tries * sleep))


def sync_cache(index, registry):
    pdc = path(os.environ.get('PIP_DOWNLOAD_CACHE'))
    if not pdc.exists():
        logger.error("Environmental var $PIP_DOWNLOAD_CACHE not set or %s not yet created" %pdc)
        return pdc

    wait_for_file(index.path)
    wait_for_file(index.datafile_path)
    sync_folder(index, pdc)
    try:
        update_index(index, registry)
    except :
        logger.exception("sync_cache:update_index failed")



def pip(config):
    index = IndexManager.from_registry(config.registry)
    thread = Thread(target=sync_cache, args=(index, config.registry), name='pip-updater')
    thread.start()


def dowatch(index, reg, pdc):
    dfexists = index.datafile_path.exists()

    assert dfexists
    data = index.data_from_path(index.datafile_path)

    index_reg = set()
    for md5, info in data:
        arch = path(info['filename'])
        assert arch.exists(), "index.json: %s missing" %arch
        index_reg.add((arch, arch.stat()))

    fsreg = set()
    for arch in index.files:
        # this assertion should rarely fail unless someone is sleeping out
        assert arch.exists(), "fs: %s missing" %arch
        fsreg.add((arch, arch.stat()))

    assert fsreg == index_reg, "index.json and filesystem do not match: %s" % index_reg ^ fsreg


def index_watch(index, reg, interval=3, failint=3, pdc=None, dowatch=dowatch):
    time.sleep(10)
    while True:
        try:
            dowatch(index, reg, pdc)
        except AssertionError:
            logger.exception("Index fails consistency tests")
            index.regenerate_all()
        except KeyboardInterrupt:
            raise
        except Exception:
            logger.exception("Who watches the watchman's exceptions?")
            time.sleep(3)
        finally:
            time.sleep(interval)

from pyramid.path import DottedNameResolver as dnr
resolve = dnr(None).maybe_resolve


def auto(config):
    dowatch = resolve(config.registry.settings.get('cheeseprism.dowatch', 'cheeseprism.sync.dowatch'))
    index = IndexManager.from_registry(config.registry)
    thread = Thread(target=index_watch, args=(index, config.registry, path(os.environ['PIP_DOWNLOAD_CACHE'])), kwargs=dict(dowatch=dowatch))
    thread.start()
    #@@ configure additional folders?
