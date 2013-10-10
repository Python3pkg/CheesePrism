from . import utils
from .index import IndexManager
from .index import notify_packages_added
from path import path
from pyramid.settings import asbool
from threading import Thread
import logging
import os
import time

logger = logging.getLogger(__name__)


def sync_folder(index, folder):
    with utils.benchmark("Sync packages"):
        EXTS = index.archive_tool.EXTS
        candidates = dict((x.read_md5().encode('hex'), x)\
                          for x in folder.files()\
                          if EXTS.match(x))

        current = dict((x.read_md5().encode('hex'), x)\
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
        pkg_added = list(notify_packages_added(index, new_pkgs, reg))

        if not any((index.datafile_path.exists(), index.home_file.exists())):
            index.write_index_home(index.projects_from_archives())

        return pkg_added


def sync_cache(index, registry):
    pdc = path(os.environ['PIP_DOWNLOAD_CACHE'])
    assert pdc.exists(), "Environmental var $PIP_DOWNLOAD_CACHE must be set to sync pip cache"
    sync_folder(index, pdc)
    update_index(index, registry)


def pip(config):
    index = IndexManager.from_registry(config.registry)
    thread = Thread(target=sync_cache, args=(index, config.registry))
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


def index_watch(index, reg, interval=3, failint=3, pdc=None):
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


def auto(config):
    index = IndexManager.from_registry(config.registry)
    thread = Thread(target=index_watch, args=(index, config.registry, path(os.environ['PIP_DOWNLOAD_CACHE'])))
    thread.start()
    #@@ configure additional folders?