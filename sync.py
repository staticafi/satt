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

class SyncReporter(BenchmarkReport):
    def done(self, rb):
        mach = rb.task.getMachine()
        name = rb.name

        print('{0} {1} - {2}: Done'.format(rb.category, mach,
                                           os.path.basename(name)))

        if rb.output:
            print(colored(rb.output, 'blue'))

        sys.stdout.flush()

class SyncDispatcher(Dispatcher):

    def __init__(self, tasks):
        Dispatcher.__init__(self, tasks, SyncReporter())
        self.cmd = self._expandVars('rsync {file} '
                                    '{ssh-user}@{machine}:{remote-dir}/satt')

        # create remote directory if it does not exists
        for t in tasks:
            m = '{0}@{1}'.format(configs['ssh-user'], t.getMachine())

            dbg('Creating remote directory on {0}'.format(t.getMachine()))
            subprocess.call(['ssh', m,
                            'mkdir', '-p',
                            '{0}/satt'.format(configs['remote-dir'])])

    # do the same as dispatcher, but run cmd instead
    # of remote-cmd
    def _runBenchmark(self, task):
        bench = task.runBenchmark(self.cmd)
        if bench is None:
            return None

        self._registerBenchmark(bench)

        return bench

    def changeCmd(self, cmd):
        self.cmd = self._expandVars(cmd)

def add_files_from_dir(task, dirpath):
    edirpath = expand(dirpath)

    try:
        files = os.listdir(edirpath)
    except OSError as e:
        err('Failed opening dir with benchmarks ({0}): {1}'
            .format(edirpath, e.strerror))

    for f in files:
        if f == 'config':
            continue

        task.add(('{0}/{1}'.format(dirpath, f), 'Syncing'))

def assign_tasks(tasks):
    for t in tasks:
        # look for files in directory named the same as
        # the tool
        add_files_from_dir(t, configs['tool'])

def rsync_tool_runner(tasks):
    dbg('local: rsync satt scripts')

    assign_tasks(tasks)

    d = SyncDispatcher(tasks)
    d.run()

    # run user's custom command if he wants
    if configs.has_key('sync-cmd'):
        dbg('Running sync-cmd')
        d.changeCmd(configs['sync-cmd'])

        for t in tasks:
            t.add(('sync-cmd', 'Syncing'))

        d.run()

def do_sync(tasks):
    try:
        if configs['sync'] == 'yes':
            rsync_tool_runner(tasks)
    except KeyboardInterrupt:
        print('Stopping...')
        sys.exit(0)
