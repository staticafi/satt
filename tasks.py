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
import errno
import glob
import atexit
import getopt

from common import err, dbg
import configs

class Task(object):
    """
    Class representing a task running on a remote computer
    The task is a set of benchmarks.
    """
    BUFSIZE = 1024

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

    def getParallel(self):
        return self._parallel_no

    def getMachine(self):
        return self._machine

    def getCount(self):
        return len(self._benchmarks)

    def add(self, test):
        """ Add new test to the task """
        self._benchmarks.append(test)

    def runBenchmark(self, cmd):
        """
        Run one benchmark.

        This includes creating ssh connection to the remote machine
        and running one benchmark. It will remove the benchmark from
        the benchmark list.
        """

        from dispatcher import RunningTask

        # nothing to run
        if not self._benchmarks:
            return None

        name, cat = self._benchmarks.pop()

        # if the command contains variables {machine} and {benchmark}
        # expand them
        ecmd = cmd.replace('{machine}', self._machine)
        ecmd = ecmd.replace('{benchmark}', name)

        dbg('local: running {0}:{1}'.format(self._machine,
                                            os.path.basename(name)))
        p = subprocess.Popen(ecmd, Task.BUFSIZE, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)

        return RunningTask(cmd, p, self, name, cat)

def expand(path):
    return os.path.expanduser(os.path.expandvars(path))

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
    old_dir = os.getcwd()
    epath = expand(dirpath)
    os.chdir(epath)

    try:
        f = open(path, 'r')
    except OSError as e:
        err("Failed opening set of benchmarks ({0}): {1}"
            .format(path, e.strerror))

    num = len(tasks)
    assert num > 0

    cat = path[:-4]

    for line in f:
        line = line.strip()
        if not line:
            continue

        n = 0
        for it in glob.iglob(line):
            tasks[n % num].add(('benchmarks/{0}'.format(it), cat))
            n += 1

    f.close()
    os.chdir(old_dir)

def assign_set_dir(dirpath, tasks):
    edirpath = os.path.expanduser(dirpath)

    try:
        files = os.listdir(edirpath)
    except OSError as e:
        err('Failed opening dir with benchmarks ({0}): {1}'
            .format(edirpath, e.strerror))

    gotany = False

    for f in files:
        if f[-4:] != '.set':
            continue

        # this path needs to be relative, since it can appear
        # on remote computer
        assign_set(dirpath, f, tasks)
        gotany = True

    if not gotany:
        sys.stderr.write('Warning: Haven\'t found any .set file\n')

def get_benchmarks(files, tasks):
    items = files.split(',')

    for it in items:
        paths = glob.glob(expand(it))
        if not paths:
            sys.stderr.write('Directory does not exist: {0}\n'.format(it))
            return

        for path in paths:
            # get folder or .set file
            if os.path.isdir(path):
                assign_set_dir(path, tasks)
            elif os.path.isfile(path):
                dirpath = os.path.dirname(path)
                basename = os.path.basename(path)
                assign_set(dirpath, basename, tasks)
