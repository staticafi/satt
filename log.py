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

import atexit
import time
import sys

from common import colored

log_file = None

def satt_log_init(lfile):
    global log_file
    assert log_file is None

    try:
        log_file = open(lfile, 'w')
    except OSError as e:
        from common import err
        err('Failed creating log: {0}'.format(str(e)))

    atexit.register(lambda: log_file.close())

def satt_log(msg, color = None, stdout = True, prefix = None):
    global log_file
    assert not log_file is None

    # prefix None means time
    if prefix is None:
        prefix = '[{0}]  '.format(time.strftime('%H:%M:%S'))
    log_file.write(prefix)
    log_file.write(msg)
    log_file.write('\n')
    log_file.flush()

    if stdout:
        sys.stdout.write(prefix)

        if color is None:
            print(msg)
        else:
            print(colored(msg, color))

        sys.stdout.flush()
