#!/usr/bin/env python

import sys
import subprocess
import os

from tempfile import mkdtemp

def move_symbiotic(path, tmpdir):
    """
    Move symbiotic into a tmp directory (if it is not there yet)
    so that we do not create too much trafic on NFS
    """
    symbdir = '{0}/symbiotic'.format(tmpdir)
    # clean previous symbiotic
    ret = subprocess.call(['rm', '-rf', symbdir])
    assert ret == 0

    ret = subprocess.call(['cp', '-r', path, symbdir])
    assert ret == 0

    assert os.path.isfile('{0}/bin/symbiotic'.format(symbdir))
    return symbdir

if __name__ == "__main__":
    tmpdir = '/var/tmp/symbiotic-{0}'.format(os.getenv('USER'))
    if not os.path.isdir(tmpdir):
        os.mkdir(tmpdir)

    if len(sys.argv) == 2:
        symbiotic_dir = move_symbiotic(os.path.abspath(sys.argv[1]), tmpdir)
        assert os.path.isfile('{0}/bin/symbiotic'.format(symbiotic_dir))
    else:
        print('ERROR: invalid arguments')
        sys.exit(1)

