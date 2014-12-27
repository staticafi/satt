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
# On arran we have only python2, so use python2

import sys
import subprocess
import select
import fcntl
import os

from common import err, create_lockfile
from dispatcher import RunningTask, Dispatcher

BUFSIZE = 1024

def track_rsync_progress(stdout, msg):
    poll = select.poll()
    stdout_fd = stdout.fileno()

    flags = fcntl.fcntl(stdout_fd, fcntl.F_GETFL)
    fcntl.fcntl(stdout_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    poll.register(stdout_fd, select.POLLIN |
                  select.POLLERR | select.POLLHUP)

    def get_progress(str):
        sp = str.rindex(' ')
        r = str[sp:]
        vals = r.split('=', 1)
        if vals[0].strip() != 'to-check':
            raise ValueError('Not to-check line')

        return vals[1][:-2]

    done = False
    while not done:
        for fd, flags in poll.poll():
            if flags & select.POLLERR:
                err('Tracing rsync output')

            if flags & select.POLLIN:
                try:
                    data = stdout.readline()
                    while data:
                        try:
                            x = get_progress(data)
                            sys.stdout.write('\r{0}: {1} '. format(msg, x))
                            sys.stdout.flush()
                        except ValueError:
                            pass
                        data = stdout.readline()
                except IOError:
                    continue

            if flags & select.POLLHUP:
                poll.unregister(fd)
                print('... done')
                done = True

def rsync_runner_scripts(tasks, configs):
    print('[local] rsync symbiotic-benchmarks scripts')

    # XXX do it parallely (same as the tasks)
    for t in tasks:
        p = subprocess.Popen(['rsync', '-rRzEm', '--progress',
                             './run_on_benchmark.sh',
                             '{0}@{1}:{2}/symbiotic-benchmarks/'
                             .format(configs['ssh-user'], t.getMachine(),
                             configs['remote-dir'])],
                             bufsize = BUFSIZE, stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)

        track_rsync_progress(p.stdout, 'Synchronizing scripts (1) with {0}'
                             .format(t.getMachine()))

        p = subprocess.Popen(['rsync', '-rRzEm', '--progress',
                             './run_benchmark',
                             '{0}@{1}:{2}/symbiotic-benchmarks/'
                             .format(configs['ssh-user'], t.getMachine(),
                             configs['remote-dir'])],
                             bufsize = BUFSIZE, stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)

        track_rsync_progress(p.stdout, 'Synchronizing scripts (2) with {0}'
                             .format(t.getMachine()))

def do_sync(tasks, configs):
    try:
        if configs['sync'] == 'yes':
            rsync_runner_scripts(tasks, configs)
    except KeyboardInterrupt:
        print('Stopping...')
        sys.exit(0)
