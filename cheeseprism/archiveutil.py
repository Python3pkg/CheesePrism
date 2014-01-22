from .utils import path
import logging
import pkginfo
import re
import time
import traceback


logger = logging.getLogger(__name__)


class ArchiveUtil(object):
    """
    A pickeable object we can pass via mp queues
    """
    EXTS = re.compile(r'^.*(?P<ext>\.egg|\.gz|\.bz2|\.tgz|\.zip|\.whl)$')

    def read(self, (arch, data)):
        pkgdata = None
        if not arch.md5hex in data:
            pkgdata = self.arch_to_add_map(arch)
        return arch.md5hex, pkgdata
    __call__ = read

    def arch_to_add_map(self, arch, error_handler=None):
        pkgi = self.pkginfo_from_file(arch, handle_error=error_handler)
        if pkgi:
            return self.pkginfo_to_pkgdata(arch, pkgi)

    @staticmethod
    def move_on_error(error_folder, exc, path_):
        logger.error(traceback.format_exc())
        path_.rename(path(error_folder) / path_.basename())

    def extension_of(self, path):
        match = self.EXTS.match(str(path))
        if match:
            return match.groupdict()['ext']

    def pkginfo_to_pkgdata(self, arch, pkgi):
        start = time.time()
        return dict(name=pkgi.name,
                    version=pkgi.version,
                    filename=str(arch.name),
                    added=start)

    def pkginfo_from_file(self, path, handle_error=None):
        ext = self.extension_of(path)
        not_recognized = False
        try:
            if ext is not None:
                if ext in set(('.gz','.tgz', '.bz2', '.zip')):
                    return pkginfo.sdist.SDist(path)
                elif ext == '.egg':
                    return pkginfo.bdist.BDist(path)
                elif ext == '.whl':
                    return pkginfo.wheel.Wheel(path)
            not_recognized = True
        except Exception, e:
            if handle_error is not None:
                return handle_error(e, path)
            raise

        if not_recognized is True:
            msg = "Unrecognized extension: %s" %path
            e = RuntimeError("Unrecognized extension: %s" %path)
            if handle_error is not None:
                logger.error(msg)
                return handle_error(e, path)

            raise e
