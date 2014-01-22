from .utils import path
import argparse
import sys


def mc(args=sys.argv[1:]):
    def_save = path('old-master/files')
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to index folder", type=path)
    parser.add_argument("--copydir", help="dir to co", type=path, action='store', default=def_save)

    pargs = parser.parse_args(args)
    index = pargs.path.abspath()
    copydir = pargs.copydir
    if copydir == def_save:
        copydir = index / copydir

    copydir.makedirs_p()

    files = index.files('*-master.tar.gz')

    print "%s files" %len(files)
    for fp in index.files('*-master.tar.gz'):
        np = fp.parent / fp.replace('-master', '')
        if np.exists():
            print "DUPE: %s" %np
        else:
            newfp = fp.rename(copydir / fp.basename())
            newfp.symlink(index / newfp.basename())
            newfp.copy(np)
