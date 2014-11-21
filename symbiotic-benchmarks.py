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

import sys
import subprocess
import select
import fcntl
import os
import time
import errno
import glob
import atexit
import getopt

BUFSIZE = 1024

def err(msg):
    sys.stderr.write(msg + '\n')
    sys.exit(1)

class RunningBenchmark(object):
    """ This class represents ont running task """
    def __init__(self, cmd, proc, task, name, cat):
        # these are public, this is just a record in
        # a dictioary
        self.cmd = cmd
        self.proc = proc
        self.task = task
        self.name = name
        self.category = cat

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
        print("Task on {0} (parallely {1})".format(self._machine,
                                                   self._parallel_no))
        for t in self._benchmarks:
            print("\t -> {0}".format(t))

    def getParallel(self):
        return self._parallel_no

    def getMachine(self):
        return self._machine

    def runBenchmark(self, cmd = 'echo "NO COMMAND GIVEN"'):
        """
        Run one benchmark.

        This includes creating ssh connection to the remote machine
        and running one benchmark. It will remove the benchmark from
        the benchmark list.
        """

        # nothing to run
        if not self._benchmarks:
            return None

        name, cat = self._benchmarks.pop()

        # if the command contains variables {machine} and {benchmark}
        # expand them
        ecmd = cmd.replace('{machine}', self._machine)
        ecmd = ecmd.replace('{benchmark}', name)

        print('[local] Running task {0}:{1}'.format(self._machine, name))
        p = subprocess.Popen(ecmd, BUFSIZE, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)

        return RunningBenchmark(cmd, p, self, name, cat)

class BenchmarkReport(object):
    """ Report results of benchmark. This is a abstract class """

    def report(self, msg, rb):
        """
        Report what happens for one benchmark.

        \param msg      one line of the output of the benchmark
        \param rb       instance of RunningBenchmark
        """

        raise NotImplementedError("Child class needs to override this method")


class StdoutReporter(BenchmarkReport):
    """ Report results of benchmark to stdout """

    def report(self, msg, rb):
        """
        Report what happens for one benchmark.

        \param msg      one line of the output of the benchmark
        \param rb       instance of RunningBenchmark
        """
        mach = rb.task.getMachine()
        name = rb.name

        sys.stdout.write('[{0}:{1}] '.format(mach, os.path.basename(name)))
        print(msg.rstrip())
        sys.stdout.flush()

class Dispatcher(object):
    """ Dispatch symbiotic instances between computers """

    def __init__(self, tasks = [], configs = dict()):
        self._tasks = tasks
        self._poller = select.poll()
        self._fds = dict()
        self._report = StdoutReporter()
        self._configs = configs

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

    def _expandVars(self, cmd):
        c = cmd[:]
        for key, val in self._configs.items():
            c = c.replace('{{{0}}}'.format(key), val)

        return c

    def _runBenchmark(self, task):
        """ Run another benchmark from task """

        cmd = self._expandVars(self._configs['remote-cmd'])
        bench = task.runBenchmark(cmd)
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
                    # run new benchmark
                    self._runBenchmark(bench.task)

    def run(self):
        """ Dispatch tasks over network and wait for outcomes """

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
            self._killTasks()
            print('Stopping...')

def get_machines(configs):
    path = configs['machines']

    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening file with machines: {0}".format(e.strerror))

    parallel = 1
    tasks = []
    position = 1

    for line in f:
        line = line.strip()
        if not line:
            continue

        # parse machine and number of parallel processes
        vals = line.split()
        l = len(vals)

        if l < 1 or l > 2:
            err('Wrong syntax of tasks file on line {0}'.format(position))
        elif l == 2:
            parallel = int(vals[1])

        machine = vals[0]

        # add new task
        tasks.append(Task(machine, parallel))

        parallel = 1
        position = position + 1

    return tasks

def assign_set(dirpath, path, tasks):
    relpath = os.path.join(os.path.expanduser(dirpath), path)
    try:
        f = open(relpath, 'r')
    except OSError as e:
        err("Failed opening set of benchmarks ({0}): {1}"
            .format(relpath, e.strerror))

    num = len(tasks)
    assert num > 0

    cat = path[:-4]

    for line in f:
        line = line.strip()
        if not line:
            continue

        # this is shell path, we need to expand it
        item = '{0}/{1}'.format(dirpath, line).strip()

        n = 0
        for it in glob.iglob(item):
            tasks[n % num].add((it, cat))
            n +=1

    f.close()

def parse_sets(dirpath, tasks):
    try:
        files = os.listdir(os.path.expanduser(dirpath))
    except OSError as e:
        err('Failed opening dir with benchmarks ({0}): {1}'
            .format(dirpath, e.strerror))

    for f in files:
        if f[-4:] != '.set':
            continue

        assign_set(dirpath, f, tasks)

def usage():
    sys.stderr.write(
"""
Usage: symbiotic-benchmarks OPTS

OPTS can be:
    --machines=file.txt             File with machines
    --benchmarks-dir=dir_with_sets  Directory with sets of benchmarks
    --no-sync                       Do not sync Symbiotic on remote machines
    --sync=[yes/no]                 Whether to sync Symbiotic on remote machines

For configuration is searched in symbiotic-benchmarks.conf file.
Command-line argument have higher priority
""")

LOCKFILE = '.symbiotic-benchmarks-running'
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

def rsync_symbiotic(tasks, configs):
    print('[local] rsync Symbiotic ({0})'.format(configs['rsync-dir']))

    epath = os.path.expanduser(configs['rsync-dir'])

    for t in tasks:
        subprocess.call(['rsync', '-rz', '--progress' , '--delete',
                        epath, '{0}@{1}:{2}'
                        .format(configs['ssh-user'], t.getMachine(),
                        configs['rsync-remote-dir'])])

def rsync_symbiotic_benchmarks(tasks, configs):
    print('[local] rsync symbiotic-benchmarks')

    for t in tasks:
        subprocess.call(['rsync', '-rRz', '--progress', './symbiotic',
                         '{0}@{1}:{2}/symbiotic-benchmarks/'
                         .format(configs['ssh-user'], t.getMachine(),
                         configs['rsync-remote-dir'])])

def do_sync(tasks, config):
    if configs['sync'] != 'yes':
        return
    try:
        rsync_symbiotic_benchmarks(tasks, configs)
        rsync_symbiotic(tasks, configs)
    except KeyboardInterrupt:
        print('Stopping...')
        sys.exit(0)

def parse_configs(path = 'symbiotic-benchmarks.conf'):
    # fill in default values
    conf = {'sync':'yes', 'ssh-user':'', 'rsync-remote-dir':'',
            'remote-cmd':'echo "ERROR: No command specified"'}

    if os.path.exists(path):
        print('Using config file {0}'.format(path))
    else:
        return conf

    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening configuration file ({0}): {1}"
            .format(path, e.strerror))

    allowed_keys = ['rsync-dir', 'rsync-remote-dir', 'benchmarks-dir',
                    'machines', 'ssh-user', 'remote-cmd', 'sync']

    for line in f:
        line = line.strip()
        if not line or line[0] == '#':
            continue

        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()

        if key in allowed_keys:
            conf[key] = val
        else:
            err('Unknown config key: {0}'.format(key))

    return conf

def parse_command_line(configs):
    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                  ['help', 'machines=', 'benchmarks-dir=',
                                   'no-sync', 'sync='])
    except getopt.GetoptError as e:
        err('{0}'.format(str(e)))

    for opt, arg in opts:
        if opt == '--help':
            usage()
            sys.exit(1)
        elif opt == '--machines':
            configs['machines'] = arg
        elif opt == '--benchmarks-dir':
            configs['benchmarks-dir'] = arg
        elif opt == '--no-sync':
            configs['sync'] = 'no'
        elif opt == '--sync':
            configs['sync'] = arg
        else:
            err('Unknown switch {0}'.format(opt))

    if args:
        usage()
        sys.exit(1)

if __name__ == "__main__":
    if not create_lockfile():
        err('Another instance of benchmarks is running')

    configs = parse_configs()
    # command line has higher priority
    parse_command_line(configs)

    # we need at least machines and dir now
    if not configs.has_key('machines'):
        usage()
        err('\nERROR: Need file with machines!')
    if not configs.has_key('benchmarks-dir'):
        usage()
        err('\nERROR: Need directory with benchmarks sets!')



    tasks = get_machines(configs)
    do_sync(tasks, configs)

    parse_sets(configs['benchmarks-dir'], tasks)

    dispatcher = Dispatcher(tasks, configs)
    dispatcher.run()
