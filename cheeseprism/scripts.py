from path import path
import argparse
import sys


def mc(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument("path", help="Path to index folder", type=path)
    parser.add_argument("--cp", help="copy rather than move", type=bool, action='store_true', default=False)
    pargs = parser.parse_args(args)
    index = pargs.path.abspath()

    for fp in index.files('*-master.tar.gz'):
        np = fp.parent / fp.replace('-master', '')
        print("%s -> %s" %(fp, np))
        if not np.exists():
            fp.copy(np)
