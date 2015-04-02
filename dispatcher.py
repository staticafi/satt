#!/usr/bin/env python
#
# This script distributes task between computers. The task
# is to be run the Symbiotic tool on given benchark.
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

import subprocess
import select
import fcntl
import os
from time import strftime

from common import err, dbg
from tasks import Task
from configs import configs
from log import satt_log

class RunningTask(object):
    """ This class represents ont running task """
    def __init__(self, cmd, proc, task, name, cat):
        # these are public, this is just a record in
        # a dictioary
        self.cmd = cmd
        self.proc = proc
        self.task = task
        self.name = name
        self.category = cat

        # here the reporter can save result of benchmark and
        # arbitrary auxiliary output
        self.result = None
        self.output = ''
        self.versions = ''
        self.memory = None
        self.time = None

        self._state = None # what are we just reading?

    def readOutput(self):
        return self.proc.stdout.readline()

    def dumpToFile(self, msg = None):
        # XXX make this a method of RunningTask
        d = 'unknown-benchmarks'
        if not os.path.exists(d):
            os.mkdir(d)

        d = '{0}/{1}-{2}'.format(d, configs['tool'],
                                 configs['started_at'])
        if not os.path.exists(d):
            os.mkdir(d)

        fname = '{0}/{1}-{2}.log'.format(d, self.category,
                                         os.path.basename(self.name))
        try:
            f = open(fname, 'w')
        except IOError as e:
            err('Failed dumping benchmark to file: {0}'.format(str(e)))

        if msg:
            f.write('Reason: {0}\n'.format(msg))
        f.write('category: {0}\n'.format(self.category))
        f.write('name: {0}\n\n'.format(self.name))
        f.write('cmd: {0}\n'.format(self.cmd))
        f.write('machine: {0}\n'.format(self.task.getMachine()))
        f.write('params: {0}\n'.format(configs['params']))
        f.write('versions: {0}\n'.format(self.versions))
        f.write('result: {0}\n'.format(self.result))
        f.write('memUsage: {0}\n'.format(self.memory))
        f.write('cpuUsage: {0}s\n\n'.format(self.time))
        f.write('other output:\n{0}\n\n'.format(self.output))

        f.write(str(configs))

        f.close()

class Dispatcher(object):
    """ Dispatch symbiotic instances between computers """

    def __init__(self, tasks = [], report = None):
        self._tasks = tasks
        self._poller = select.poll()
        self._fds = dict()
        self._benchmarks_count = 0
        self._benchmarks_done = 0

        # initialize benchmarks_count
        for t in tasks:
            self._benchmarks_count += t.getCount()

        # we must import it only localy, otherwise we get
        # cyclic dependency
        import reporter

        if report is None:
            if configs['no-db'] == 'yes':
                self._report = reporter.StdoutReporter()
            else:
                self._report = reporter.MysqlReporter()
        else:
            self._report = report

        self._dontSendResults = False

    def sendResults(self):
        """ Send results by e-mail to given people """

        if self._dontSendResults:
            return

        emails = []

        try:
            f = open('emails.txt')
            for email in f:
                emails.append(email.strip())
            f.close()
        except IOError as e:
            dbg('Not sending email with results, because'
                ' error occured while processing file with emails')

        # if we don't have any e-mail, we don't have to send anything
        if not emails:
            return

        self._report.sendEmail('localhost',
                               'statica@fi.muni.cz', emails)
    def add(self, task):
        """ Add new task """

        self._tasks.append(task)
        self._benchmarks_count += task.getCount()

    def _registerFd(self, fd, data):
        """ Add new fd to the poller """

        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

        self._fds[fd] = data
        self._poller.register(fd, select.POLLIN |
                              select.POLLERR | select.POLLHUP)

    def _unregisterFd(self, fd):
        """ Remove fd from the poller """

        bench = self._fds[fd]

        self._fds.pop(fd)
        self._poller.unregister(fd)

        return bench

    def _registerBenchmark(self, bench):
        """ Set running benchmark to be tracked down by poller """

        fd = bench.proc.stdout.fileno()
        self._registerFd(fd, bench)

    def _runBenchmark(self, task):
        """ Run another benchmark from task """

        bench = task.runBenchmark(configs['remote-cmd'])
        if bench is None: # no more tests to run
            return None

        self._registerBenchmark(bench)

        return bench

    def _getBenchmark(self, fd):
        return self._fds[fd]

    def _is_running(self):
        return self._fds != {}

    def _poll_wait(self):
        return self._poller.poll()

    def _killTasks(self):
        for bench in self._fds.values():
            bench.proc.terminate()
            # for sure
            bench.proc.kill()

    def _monitorTasks(self):
        assert self._is_running()

        while self._is_running():
            for fd, flags in self._poll_wait():
                if flags & select.POLLERR:
                    self._killTasks()
                    err('Waiting for benchmark failed')

                if flags & select.POLLIN:
                    bench = self._getBenchmark(fd)
                    try:
                        data = bench.readOutput()
                        while data:
                            self._report.report(data, bench)
                            data = bench.readOutput()
                    # While can be too fast and raise
                    # EBUSY
                    except IOError:
                        continue

                # is benchmark done?
                if flags & select.POLLHUP:
                    # remove the old benchmark
                    bench = self._unregisterFd(fd)
                    if not self._report.done(bench):
                        # something went wrong - queue this one again
                        satt_log('Running benchmark again');
                        # we must take this one as it was not running yet
                        self._benchmarks_done -= 1

                        # XXX we do not have a mechanism how to track
                        # how many times the benchmark ran, so it may happen
                        # that it will run indifinetly many times.
                        # It seems we don't need to care about that atm, so let's
                        # ignore it for now.
                        #
                        # P. S message for future me: If you read this, we probably hit
                        # this error and you hate me and my wickidness - just sorry.
                        bench.task.readd(bench)

                    self._benchmarks_done += 1
                    # set progress
                    if self._benchmarks_done != 0:
                        prgs = float(self._benchmarks_done) / self._benchmarks_count
                        self._report.progress(int(prgs * 100))

                    # run new benchmark
                    self._runBenchmark(bench.task)

    def run(self):
        """ Dispatch tasks over network and wait for outcomes """

        dbg('[local] Started dispatching benchmarks')

        # take every task and call as many of benchmarks as
        # you are allowed. Later, when a task ends,
        # we will spawn only one new (one new for one done)
        try:
            for task in self._tasks:
                for n in range(0, task.getParallel()):
                    if self._runBenchmark(task) is None:
                        break

            # monitor the tasks
            self._monitorTasks()
        except KeyboardInterrupt:
            self._dontSendResults = True
            self._killTasks()
            satt_log('Stopping...')
