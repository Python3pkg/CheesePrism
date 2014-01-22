"""
Classes, subscribers and functions for dealing with index management
"""
from . import event
from .archiveutil import ArchiveUtil
from .desc import template
from .desc import updict
from .jenv import EnvFactory
from .utils import benchmark
from functools import partial
from more_itertools import chunked
from .utils import path
from pyramid import threadlocal
from pyramid.events import ApplicationCreated
from pyramid.events import subscriber
from pyramid.path import DottedNameResolver as dnr
from pyramid.settings import asbool
import json
import logging
import re
import threading
import time


logger = logging.getLogger(__name__)


class IndexManager(object):
    """
    Manages the static file index
    """

    root_index_file = 'index.html'
    EXTS = re.compile(r'^.*(?P<ext>\.egg|\.gz|\.bz2|\.tgz|\.zip)$')
    SDIST_EXT = re.compile(r'^.*(?P<ext>\.gz|\.bz2|\.tgz|\.zip)$')

    leaf_name = 'leaf.html'
    home_name = 'index.html'
    def_index_title = 'CheesePrism'
    leaf_data = updict()
    index_data = updict(title=def_index_title,
                        index_title=def_index_title,
                        description="Welcome to the CheesePrism")
    datafile_name = "index.json"
    index_data_lock = threading.Lock()

    leaf_template = template('leaf.html')
    home_template = template('home.html')

    at = archive_tool = ArchiveUtil()
    _move_on_error = at.move_on_error

    pkginfo_to_pkgdata = at.pkginfo_to_pkgdata
    pkginfo_from_file = at.pkginfo_from_file
    extension_of = at.extension_of


    def __init__(self, index_path, template_env=None,
                 arch_baseurl='/index/', urlbase='', index_data={},
                 leaf_data={}, error_folder='_errors', executor=None,
                 write_index_html=True):

        self.urlbase = urlbase
        self.write_index_html = write_index_html
        self.arch_baseurl = arch_baseurl
        self.template_env = template_env

        if not self.template_env:
            self.template_env = self.default_env_factory('')
        self.index_data = index_data.copy()
        self.leaf_data = leaf_data.copy()
        self.path = path(index_path).makedirs_p()
        self.home_file = self.path / self.root_index_file
        self.datafile_path = self.path / self.datafile_name

        self.error_folder = self.path / error_folder
        if not (self.error_folder.exists() and self.error_folder.isdir()):
            if self.error_folder.endswith('/') and not self.error_folder.isdir():
                self.error_folder.parent.remove_p()
            self.error_folder.makedirs()

        self.move_on_error = partial(self._move_on_error, self.error_folder)
        self.arch_to_add_map = partial(self.at.arch_to_add_map,
                                       error_handler=self.move_on_error)
        self.executor = executor

    @classmethod
    def from_registry(cls, registry):
        settings = registry.settings
        executor = registry['cp.executor']
        env = registry['cp.index_templates']
        return cls.from_settings(settings, executor, env)

    @classmethod
    def from_settings(cls, settings, executor=None, env=None):
        file_root = path(settings['cheeseprism.file_root'])
        if not file_root.exists():
            file_root.makedirs()

        urlbase = settings.get('cheeseprism.urlbase', '')
        write_index_html = asbool(settings.get('cheeseprism.write_index_html', 'true'))
        abu = settings.get('cheeseprism.archive.urlbase', '..')
        idx_tmplt = settings.get('cheeseprism.index_templates', '')
        env = EnvFactory.from_str(idx_tmplt)

        return cls(settings['cheeseprism.file_root'],
                   urlbase=urlbase,
                   arch_baseurl=abu,
                   template_env=env,
                   executor=executor,
                   write_index_html=write_index_html)

    @property
    def default_env_factory(self):
        return EnvFactory.from_str

    @property
    def files(self):
        return (x for x in self.path.files() if self.archive_tool.EXTS.match(x))

    def projects_from_archives(self):
        with benchmark('-- collected projects'):
            projects = {}
            paths = (self.path / item for item in self.files)
            arch_info = partial(pki_ff, handle_error=self.move_on_error)
            results = [info for info in self.executor.map(arch_info, paths)]
            for itempath, info in results:
                projects.setdefault(info.name, []).append((info, itempath))

        with benchmark('-- sorted projects'):
            return sorted(projects.items())

    def regenerate_leaf(self, leafname):
        files = self.path.files('%s-*.*' %leafname)
        
        pki_ff = partial(self.at.pkginfo_from_file, handle_error=self.move_on_error)
        versions = ((pki_ff(self.path / item), item) for item in files)

        return self.write_leaf(self.path / leafname, versions)

    def regenerate_all(self):
        items = self.projects_from_archives()
        if self.write_index_html is False:
            yield None
        else:
            with benchmark('-- wrote index.html'):
                yield self.write_index_home(items)

        with benchmark('-- regenerated index'):
            yield [self.write_leaf(self.path / key, value) for key, value in items]

    def write_index_home(self, items):
        logger.info('Write index home: %s', self.home_file)
        data = self.index_data.copy()
        data['packages'] = [dict(name=key, url=str(path(self.urlbase) / key )) \
                            for key, value in items]
        self.home_file.write_text(self.home_template.render(**data))
        return self.home_file

    def write_leaf(self, leafdir, versions, indexhtml="index.html", indexjson="index.json"):
        if not leafdir.exists():
            leafdir.makedirs()

        leafhome = leafdir / indexhtml
        leafjson = leafdir / indexjson

        versions = list(versions)
        title = "%s:%s" %(self.index_data['title'], leafdir.name)
        tversions = (self.leaf_values(leafdir.name, archive)\
                     for info, archive in versions)

        text = self.leaf_template\
               .render(package_title=leafdir.name,
                       title=title,
                       versions=tversions)

        leafhome.write_text(text)
        with self.index_data_lock: #@@ more granular locks
            with open(leafjson, 'w') as jsonout:
                leafdata = [dict(filename=str(fpath.name),
                                 name=dist.name,
                                 version=dist.version,
                                 mtime=fpath.mtime,
                                 ctime=fpath.ctime,
                                 atime=fpath.ctime,
                                 ) for dist, fpath in versions]
                json.dump(leafdata, jsonout)
        leafhome.utime((time.time(), time.time()))
        return leafhome

    def leaf_values(self, leafname, archive):
        url = str(path(self.arch_baseurl) / archive.name)
        return dict(url=url, name=archive.name)

    @staticmethod
    def data_from_path(datafile):
        datafile = path(datafile)
        if datafile.exists():
            with open(datafile) as stream:
                return json.load(stream)
        else:
            logger.error("No datafile found for %s", datafile)
            datafile.write_text("{}")
        return {}

    def _write_datafile(self, **data):
        if self.datafile_path.exists():
            newdata = data
            with open(self.datafile_path) as root:
                    data = json.load(root)
                    data.update(newdata)

        with open(self.datafile_path, 'w') as root:
            json.dump(data, root)
        return data

    def write_datafile(self, with_lock=True, **data):
        if with_lock is True:
            with self.index_data_lock:
                return self._write_datafile(**data)
        return self._write_datafile(**data)

    def reg_data(self, arch):
        pkgdata = self.arch_to_add_map(arch)
        return arch.md5hex, pkgdata,

    def register_archive(self, arch, registry=None):
        """
        Adds an archive to the master data store (index.json)
        """
        md5, pkgdata = self.reg_data(arch)
        self.write_datafile(**{md5:pkgdata})
        return pkgdata, md5

    @staticmethod
    def group_by_magnitude(collection):
        alen = len(collection)
        if alen > 1000:
            return chunked(collection, 100)
        if alen > 100:
            return chunked(collection, 10)
        return [collection]

    def update_data(self, datafile=None, pkgdatas=None):
        if datafile is None:
            datafile = self.datafile_path

        archs = self.files if pkgdatas is None else pkgdatas.keys()
        new = []

        archs_g = self.group_by_magnitude([x for x in archs])
        with benchmark("Rebuilt /index.json"):
            for archs in archs_g:
                with self.index_data_lock:
                    new.extend(self._update_data(archs, datafile))

        pkgs = len(set(x['name'] for x in new))
        logger.info("Inspected %s versions for %s packages" %(len(new), pkgs))
        return new

    def _update_data(self, archs, datafile):
        data = self.data_from_path(datafile)
        new = []
        exe = self.executor

        read = self.archive_tool
        archdata = [(arch, data) for arch in archs]
        for md5, pkgdata in exe.map(read, archdata):
            if pkgdata is not None:
                data[md5] = pkgdata
                new.append(pkgdata)

        self.write_datafile(with_lock=False, **data)
        return new


def pki_ff(path, handle_error=None, func=IndexManager.at.pkginfo_from_file):
    return path, func(path, handle_error=handle_error)


@subscriber(event.IPackageAdded)
def rebuild_leaf(event):
    reg = threadlocal.get_current_registry()
    logger.debug("Adding %s" %(event.path))
    event.im.register_archive(event.path, registry=reg)

    with benchmark("Rebuilt leaf for %s" %(event.name)):
        out = event.im.regenerate_leaf(event.name)
    return out


@subscriber(event.IIndexUpdate)
def bulk_update_index(event):
    new_pkgs = event.index.update_data(event.datafile, pkgdatas=event.pkgdatas)
    return bulk_add_pkgs(event.index, new_pkgs, register=False)


def bulk_add_pkgs(index, new_pkgs):
    """
    Sidestep the event system for efficiency

    @@ requires a prior update
    """
    with benchmark('') as bm:
        leaves = set()
        archs = []

        for data in new_pkgs:
            leaves.add(data['name'])
            archs.append(index.path / data['filename'])

        bm.name = "Bulk add >> register %s archives and rebuild %s leaves"\
           %(len(archs), len(leaves))

        for leaf in leaves:
            try:
                index.regenerate_leaf(leaf)
            except Exception:
                logger.exception('Issue building leaf for %s', leaf)

    return leaves, archs


def bulk_update_index_at_start(event):
    logger.info("--> Checking and updating index")
    reg = event.app.registry

    index = IndexManager.from_registry(reg)
    logger.info("-- %s pkg in %s", len([x for x in index.files]), index.path.abspath())

    new_pkgs = index.update_data()
    leaves, archs = bulk_add_pkgs(index, new_pkgs)

    home_file = index.path / index.root_index_file
    if index.write_index_html is True and (not home_file.exists() or len(leaves)):
        items = index.projects_from_archives()
        index.write_index_home(items)
    return leaves, archs


def async_bulk_update_at_start(event):
    from threading import Thread
    logger.info("Spawning thread to handle bulk update on start")
    Thread(target=bulk_update_index_at_start,
           args=(event,),
           name='bulk-update-on-start').start()


resolve = dnr(None).maybe_resolve
preup_key = 'cheeseprism.preupdate'

def noop(*args, **kw):
    return

def includeme(config):
    config.scan(__name__)
    preup = resolve(config.registry.settings.get(preup_key, 'cheeseprism.index.noop'))
    if preup:
        config.registry[preup_key] = preup
    if asbool(config.registry.settings.get('cheeseprism.async_restart', False)):
        config.add_subscriber(async_bulk_update_at_start, ApplicationCreated)
    else:
        config.add_subscriber(bulk_update_index_at_start, ApplicationCreated)
