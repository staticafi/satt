#!/usr/bin/env python
#
# Copyright (c) 2014 Marek Chalupa
# E-mail: statica@fi.muni.cz
#
# Permission to use, copy, modify, distribute, and sell this software and its
# documentation for any purpose is hereby granted without fee, provided that
# the above copyright notice appear in all copies and that both that copyright
# notice and this permission notice appear in supporting documentation, and
# that the name of the copyright holders not be used in advertising or
# publicity pertaining to distribution of the software without specific,
# written prior permission. The copyright holders make no representations
# about the suitability of this software for any purpose. It is provided "as
# is" without express or implied warranty.
#
# THE COPYRIGHT HOLDERS DISCLAIM ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS, IN NO
# EVENT SHALL THE COPYRIGHT HOLDERS BE LIABLE FOR ANY SPECIAL, INDIRECT OR
# CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
# DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
# TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#

import sys
import os
import errno
import atexit
import time

from configs import configs

LOCKFILE = '.satt-running.lock'

def colored(msg, c = None):
    isatty = os.isatty(sys.stdout.fileno())
    if isatty and not c is None:
        if c == 'red':
            c = '\033[0;31m'
        elif c == 'green':
            c = '\033[0;32m'
        elif c == 'gray':
            c = '\033[0;30m'
        elif c == 'blue':
            c = '\033[1;34m'
        elif c == 'yellow':
            c = '\033[0;33m'

        return "{0}{1}{2}".format(c, msg, '\033[0m')
    else:
        return msg

def err(msg):
    sys.stderr.write(colored('ERR: {0}\n'.format(msg), 'red'))
    sys.exit(1)

def dbg(msg):
    if msg and configs['debug'] == 'yes':
        print('DBG: {0}'.format(msg))

def expand(path):
    return os.path.expanduser(os.path.expandvars(path))

def create_lockfile():
    try:
        fd = os.open(LOCKFILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError as e:
        if e.errno == errno.EEXIST:
            return False
        else:
            err('Failed taking lock: {0}'.format(e.strerror))

    os.write(fd, time.ctime())
    os.close(fd)

    atexit.register(lambda: os.unlink(LOCKFILE))

    return True
