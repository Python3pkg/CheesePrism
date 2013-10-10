"""
Classes, subscribers and functions for dealing with index management
"""
from . import event
from .desc import template
from .desc import updict
from .utils import benchmark
from functools import partial
from path import path
from pyramid import threadlocal
from pyramid.events import ApplicationCreated
from pyramid.events import subscriber
import jinja2
import json
import logging
import pkginfo
import re
import threading
import time
import traceback

logger = logging.getLogger(__name__)


class ArchiveUtil(object):
    """
    A pickeable object we can pass via mp queues
    """
    EXTS = re.compile(r'^.*(?P<ext>\.egg|\.gz|\.bz2|\.tgz|\.zip)$')

    def read(self, (arch, data)):
        md5 = arch.read_md5().encode('hex')
        pkgdata = None
        if not md5 in data:
            pkgdata = self.arch_to_add_map(arch)
        return md5, pkgdata
    __call__ = read

    def arch_to_add_map(self, arch):
        pkgi = self.pkginfo_from_file(arch, self.move_on_error)
        if pkgi:
            return self.pkginfo_to_pkgdata(arch, pkgi)

    def pkginfo_to_pkgdata(self, arch, pkgi):
        start = time.time()
        return dict(name=pkgi.name,
                    version=pkgi.version,
                    filename=str(arch.name),
                    added=start)

    def move_on_error(self, error_folder, exc, path):
        logger.error(traceback.format_exc())
        path.rename(error_folder)

    def extension_of(self, path):
        match = self.EXTS.match(str(path))
        if match:
            return match.groupdict()['ext']

    def pkginfo_from_file(self, path, handle_error=None):
        ext = self.extension_of(path)
        try:
            if ext is not None:
                if ext in set(('.gz','.tgz', '.bz2', '.zip')):
                    return pkginfo.sdist.SDist(path)
                elif ext == '.egg':
                    return pkginfo.bdist.BDist(path)
        except Exception, e:
            if handle_error is not None:
                return handle_error(e, path)
            raise
        raise RuntimeError("Unrecognized extension: %s" %path)


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
    move_on_error = at.move_on_error
    arch_to_add_map = at.arch_to_add_map
    pkginfo_to_pkgdata = at.pkginfo_to_pkgdata
    pkginfo_from_file = at.pkginfo_from_file
    extension_of = at.extension_of


    def __init__(self, index_path, template_env=None, arch_baseurl='/index/', urlbase='',
                 index_data={}, leaf_data={}, error_folder='_errors/', executor=None):
        self.urlbase = urlbase
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

        self.move_on_error = partial(self.move_on_error, self.error_folder)
        self.executor = executor

    @classmethod
    def from_registry(cls, registry):
        settings = registry.settings
        executor = registry['cp.executor']
        return cls.from_settings(settings, executor)

    @classmethod
    def from_settings(cls, settings, executor=None):
        file_root = path(settings['cheeseprism.file_root'])
        if not file_root.exists():
            file_root.makedirs()

        urlbase = settings.get('cheeseprism.urlbase', '')
        abu = settings.get('cheeseprism.archive.urlbase', '..')
        return cls(settings['cheeseprism.file_root'],
                   urlbase=urlbase,
                   arch_baseurl=abu,
                   template_env=settings['cheeseprism.index_templates'],
                   executor=executor)

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
            with self.executor() as exe:
                results = [info for info in exe.map(pki_ff, paths)]
                for itempath, info in results:
                    projects.setdefault(info.name, []).append((info, itempath))

        with benchmark('-- sorted projects'):
            return sorted(projects.items())

    def regenerate_leaf(self, leafname):
        files = self.path.files('%s-*.*' %leafname)
        versions = ((self.pkginfo_from_file(self.path / item), item) for item in files)
        return self.write_leaf(self.path / leafname, versions)

    def regenerate_all(self):
        items = self.projects_from_archives()
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

    def write_datafile(self, **data):
        with self.index_data_lock:
            if self.datafile_path.exists():
                newdata = data
                with open(self.datafile_path) as root:
                    data = json.load(root)
                    data.update(newdata)
            with open(self.datafile_path, 'w') as root:
                json.dump(data, root)
            return data

    def register_archive(self, arch, registry=None):
        """
        Adds an archive to the master data store (index.json)
        """
        pkgdata = self.arch_to_add_map(arch)
        md5 = arch.read_md5().encode('hex')

        self.write_datafile(**{md5:pkgdata})
        return pkgdata, md5

    def update_data(self, datafile=None, pkgdatas=None):
        if datafile is None:
            datafile = self.datafile_path

        archs = self.files if pkgdatas is None else pkgdatas.keys()
        with benchmark("Rebuilt /index.json"):
            with self.index_data_lock:
                data = self.data_from_path(datafile)
                new = []
                with self.executor() as exe:
                    read = self.archive_tool
                    for md5, pkgdata in exe.map(read,
                                                ((arch, data) for arch in archs)):

                        if pkgdata is not None:
                            data[md5] = pkgdata
                            new.append(pkgdata)

                pkgs = len(set(x['name'] for x in data.values()))
                logger.info("Inspected %s versions for %s packages" %(len(data), pkgs))
                with open(datafile, 'w') as root:
                    json.dump(data, root)
        return new


def pki_ff(path, handle_error=None, func=IndexManager.pkginfo_from_file):
    return path, func(path, handle_error=handle_error)


@subscriber(event.IPackageAdded)
def rebuild_leaf(event):
    logger.info("Rebuilding leaf for %s, adding %s" %(event.name, event.path))
    reg = threadlocal.get_current_registry()
    event.im.register_archive(event.path, registry=reg)
    out = event.im.regenerate_leaf(event.name)
    return out


@subscriber(event.IIndexUpdate)
def bulk_update_index(event):
    new_pkgs = event.index.update_data(event.datafile, pkgdatas=event.pkgdatas)
    return list(notify_packages_added(event.index, new_pkgs))


def notify_packages_added(index, new_pkgs, reg=None):
    if reg is None:
        reg = threadlocal.get_current_registry()
    for data in new_pkgs:
        yield reg.notify(event.PackageAdded(index,
                                            name=data['name'],
                                            version=data['version'],
                                            path=index.path / data['filename']))

@subscriber(ApplicationCreated)
def bulk_update_index_at_start(event):
    reg = event.app.registry

    index = IndexManager.from_registry(reg)
    logger.info("-- %s pkg in %s", len([x for x in index.files]), index.path.abspath())
    start = time.time()
    new_pkgs = index.update_data()
    pkg_added = list(notify_packages_added(index, new_pkgs, reg))
    index.write_index_home(index.projects_from_archives())

    logger.info('-- Package inspection finished in %ss', time.time() - start)
    return pkg_added


class EnvFactory(object):
    env_class = jinja2.Environment
    def __init__(self, config):
        self.config = config

    @property
    def loaders(self):
        if self.config:
            loaders = self.config.split(' ')
            for loader in loaders:
                spec = loader.split(':')
                if len(spec) == 1:
                    yield jinja2.FileSystemLoader(spec); continue

                type_, spec = spec
                if type_ == "file":
                    yield jinja2.FileSystemLoader(spec); continue

                if type_ == 'pkg':
                    spec = spec.split('#')
                    if len(spec) == 1: yield jinja2.PackageLoader(spec[0])
                    else: yield jinja2.PackageLoader(*spec)
                    continue
                raise RuntimeError('Loader type not found: %s %s' %(type_, spec))

    @classmethod
    def from_str(cls, config=None):
        factory = cls(config)
        choices = [jinja2.PackageLoader('cheeseprism', 'templates/index')]
        if config: [choices.insert(0, loader) for loader in factory.loaders]
        return factory.env_class(loader=jinja2.ChoiceLoader(choices))
