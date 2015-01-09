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

from common import err, dbg, colored, expand
from dispatcher import Dispatcher
from configs import configs
from reporter import BenchmarkReport
from log import satt_log

class SyncReporter(BenchmarkReport):
    def done(self, rb):
        mach = rb.task.getMachine()
        name = rb.name

        msg = '{0} {1} - {2}: Done'.format(rb.category, mach,
                                           os.path.basename(name))
        satt_log(msg)

        if rb.output:
            # if there's any output, it is probably an error,
            # so write it out in red color
            satt_log(colored(rb.output, 'red'))

        sys.stdout.flush()

class SyncDispatcher(Dispatcher):

    def __init__(self, tasks):
        Dispatcher.__init__(self, tasks, SyncReporter())

        # create remote directory if it does not exists
        # this create remote-dir and remote-dir/satt
        for t in tasks:
            m = '{0}@{1}'.format(configs['ssh-user'], t.getMachine())

            dbg('Creating remote directory on {0}'.format(t.getMachine()))
            subprocess.call(['ssh', m,
                            'mkdir', '-p',
                            '{0}/satt'.format(configs['remote-dir'])])

            # also we need synchronize benchmarks on remote directory,
            # so call sync-benchmarks.sh for this machine
            dbg('Synchronizing benchmarks on {0}'.format(t.getMachine()))
            ret = subprocess.call(['./sync-benchmarks.sh', m,
                                   configs['remote-dir'],
                                   expand(configs['benchmarks'])])

            # if syncing failed, remove the task from tasks
            if ret != 0:
                satt_log(colored('Removing machine {0} because'
                         ' syncing benchmarks failed'.format(t.getMachine()), 'red'))
                tasks.remove(t)

    # do the same as dispatcher, but run sync-cmd instead
    # of remote-cmd
    def _runBenchmark(self, task):
        cmd = self._expandVars(configs['sync-cmd'])
        bench = task.runBenchmark(cmd)
        if bench is None:
            return None

        self._registerBenchmark(bench)

        return bench

def add_tasks(tasks):
    for t in tasks:
        # we need to add at least one path so that
        # the dispatcher can dispatch something.
        t.add((configs['tool'], 'synchronizing'))

def rsync_tool_runner(tasks):
    satt_log('Synchronizing...')

    if not configs.has_key('sync-cmd'):
        dbg('No sync command')
        return

    add_tasks(tasks)

    d = SyncDispatcher(tasks)
    d.run()

def do_sync(tasks):
    try:
        if configs['sync'] == 'yes':
            rsync_tool_runner(tasks)
    except KeyboardInterrupt:
        satt_log('Stopping...')
        sys.exit(0)
