#!/usr/bin/env python2
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

import sys
import subprocess
import select
import fcntl
import os

BUFSIZE = 1024

def err(msg):
    sys.stderr.write(msg + '\n')
    sys.exit(1)

class RunningBenchmark(object):
    """ This class represents ont running task """
    def __init__(self, cmd, proc, task):
        # these are public, this is just a record in
        # a dictioary
        self.cmd = cmd
        self.proc = proc
        self.task = task

    def readOutput(self):
        return self.proc.stdout.readline()

class Task(object):
    """
    Class representing a task running on a remote computer
    The task is a set of benchmarks.
    """

    def __init__(self, mach, parallel_no = 1):
        """
        Create a task

        \param comp     computer (used by ssh)
        \paralel_no     number of tests that can run
                        parallely
        """
        self._machine = mach
        self._benchmarks = []
        self._parallel_no = parallel_no

    def add(self, test):
        """ Add new test to the task """
        self._benchmarks.append(test)

    def dump(self):
        """ Print task in human readable form """
        print("Task on {} (parallely {})".format(self._machine,
                                                 self._parallel_no))
        for t in self._benchmarks:
            print("\t -> {}".format(t))

    def getParallel(self):
        return self._parallel_no

    def getMachine(self):
        return self._machine

    def runBenchmark(self):
        """
        Run one benchmark.

        This includes creating ssh connection to the remote machine
        and running one benchmark. It will remove the benchmark from
        the benchmark list.
        """

        # nothing to run
        if not self._benchmarks:
            return None

        bench = self._benchmarks.pop()

        # this command will run on the remote machine
        cmd = '{}'.format(bench)

        p = subprocess.Popen(cmd, BUFSIZE, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)

        return RunningBenchmark(cmd, p, self)

class Dispatcher(object):
    """ Dispatch symbiotic instances between computers """

    def __init__(self):
        self._tasks = []
        self._poller = select.poll()
        self._fds = dict()

    def add(self, task):
        """ Add new task """

        self._tasks.append(task)

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

        bench = task.runBenchmark()
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
                            print('[{}]'.format(bench.task.getMachine()))
                            print('{}'.format(data))
                            data = bench.readOutput()
                    # While can be too fast and raise
                    # EBUSY
                    except IOError:
                        continue

                # is benchmark done?
                if flags & select.POLLHUP:
                    # remove the old benchmark
                    bench = self._unregisterFd(fd)
                    # run new benchmark
                    self._runBenchmark(bench.task)

    def run(self):
        """ Dispatch tasks over network and wait for outcomes """

        # take every task and call as many of benchmarks as
        # you are allowed. Later, when a task ends,
        # we will spawn only one new (one new for one done)
        for task in self._tasks:
            for n in range(0, task.getParallel()):
                if self._runBenchmark(task) is None:
                    break

        # monitor the tasks
        try:
            self._monitorTasks()
        except KeyboardInterrupt:
            self._killTasks()
            print('Stopping...')

def parse_tasks_file(path):
    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening file with tasks: {}".format(e.strerror))

    d = Dispatcher()

    paralel = 1
    machine = ""
    task = None
    line = f.readline()
    position = 1

    while line:
        stripped_line = line.strip()

        # empty line
        if not stripped_line:
            line = f.readline()
            continue

        # machine and paralelism
        if not line[0].isspace():
            # parse machine and number of parallel processes
            vals = line.split()
            l = len(vals)

            if l < 1 or l > 2:
                err('Wrong syntax of tasks file on line {}'.format(position))
            elif l == 2:
                paralel = int(vals[1])

            machine = vals[0]

            # add new task
            task = Task(machine, paralel)
            d.add(task)
        else:
            # this can happen only on line 1
            if task is None:
                err('Missing machine name on line {}'.format(position))

            task.add(stripped_line)

        position = position + 1
        paralel = 1
        line = f.readline()

    f.close()

    return d

def usage():
    sys.stderr.write("Usage: symbiotic-benchmarks tasks_file.txt\n")

if __name__ == "__main__":
    if len(sys.argv) == 2:
        dispatcher = parse_tasks_file(sys.argv[1])
    else:
        usage()
        sys.exit(1)

    dispatcher.run()
