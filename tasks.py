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

from common import err, dbg, expand
import configs

def expandVariables(cmd):
    c = cmd[:]
    for key, val in configs.configs.items():
        # params is not string, we cannot replace it like this
        # more over it has been replaced in expandSpecialVariables
        if key == 'params':
            continue

        c = c.replace('{{{0}}}'.format(key), val)

    return c

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
        self._count = 0

    def getParallel(self):
        return self._parallel_no

    def getMachine(self):
        return self._machine

    def getCount(self):
        return len(self._benchmarks)

    def add(self, test):
        """ Add new test to the task """
        self._benchmarks.append(test)
        self._count += 1

    def readd(self, rb):
        """ Add benchmark that already ran """
        self.add((rb.name, rb.category))

    def expandSpecialVariables(self, cmd, name, cat):
        # expand {params}
        par = configs.configs['params']
        if par.has_key(cat):
            ecmd = cmd.replace('{params}', '{0} {1}'.format(par['*'], par[cat]))
        else:
            ecmd = cmd.replace('{params}', par['*'])

        # expand {machine}
        ecmd = ecmd.replace('{machine}', self._machine)

        # expand {benchmark} and {file}
        ecmd = ecmd.replace('{benchmark}', name)
        # {file} is a synonym to {benchmarks}
        ecmd = ecmd.replace('{file}', name)

        # expand {benchmark-dirname} and {file-dirname}
        ecmd = ecmd.replace('{benchmark-dirname}', os.path.dirname(name))
        ecmd = ecmd.replace('{file-dirname}', os.path.dirname(name))

        return ecmd

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

        self._count -= 1
        name, cat = self._benchmarks.pop()

        ecmd = self.expandSpecialVariables(cmd, name, cat)
        ecmd = expandVariables(ecmd)
        dbg('running: {0}'.format(ecmd))

        p = subprocess.Popen(ecmd, Task.BUFSIZE, shell = True,
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)

        return RunningTask(cmd, p, self, name, cat)

def get_machines():
    path = configs.configs['machines']

    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening file with machines: {0}".format(e.strerror))

    parallel = 1
    tasks = []
    position = 1

    for line in f:
        line = line.strip()
        if not line or line[0] == '#':
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

def assign_set(dirpath, path, tasks, should_skip):
    # there is not so much of .set files, so there won't be
    # any significant time penalty if we parse the configs
    # here every time
    exclude = configs.configs['exclude'].split(',')

    old_dir = os.getcwd()
    epath = expand(dirpath)
    os.chdir(epath)

    bname = os.path.basename(path)
    if bname in exclude:
        dbg('Skiping {0} benchmarks'.format(bname))
        os.chdir(old_dir)
        return False

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
            bench = ('benchmarks/c/{0}'.format(it), cat)
            if should_skip(bench):
                dbg('Skipping benchmark {0}'.format(it))
            else:
                tasks[n % num].add(bench)
                n += 1

    f.close()
    os.chdir(old_dir)

    return n != 0

def assign_set_dir(dirpath, tasks, should_skip):
    dirpath = '{0}/c'.format(dirpath)
    edirpath = os.path.expanduser(dirpath)
    dbg('Looking for benchmarks in: {0}'.format(edirpath))

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
        gotany |= assign_set(dirpath, f, tasks, should_skip)

    if not gotany:
        sys.stderr.write('Warning: Haven\'t found any .set file\n')

def _should_skip_with_db(dbproxy, toolid, year_id, x):
    name, cat = x
    catid = dbproxy.getCategoryID(year_id, cat)
    if catid is None:
        return False

    taskid = dbproxy.getTaskID(catid, name)
    if taskid is None:
        return False

    return dbproxy.hasTaskResult(taskid, toolid)

def get_benchmarks(files, tasks):
    items = files.split(',')

    skip_known_id = configs.configs['skip-known-benchmarks']
    if skip_known_id != 'no':
        from database_proxy import DatabaseProxy
        dbproxy = DatabaseProxy()
        year_id = dbproxy.getYearID(configs.configs['year'])
        if year_id is None:
            err('Wrong year: {0}'.format(configs.configs['year']))

        try:
            toolid = int(skip_known_id)
        except ValueError:
            err('Invalid tool id for skip-known-benchmarks')

        should_skip = lambda x: _should_skip_with_db(dbproxy, toolid, year_id, x)
    else:
        should_skip = lambda x: False

    for it in items:
        paths = glob.glob(expand(it))
        if not paths:
            sys.stderr.write('Directory does not exist: {0}\n'.format(it))
            return

        for path in paths:
            # get folder or .set file
            if os.path.isdir(path):
                assign_set_dir(path, tasks, should_skip)
            elif os.path.isfile(path):
                dirpath = os.path.dirname(path)
                basename = os.path.basename(path)
                assign_set(dirpath, basename, tasks, should_skip)

    # return number of found benchmarks
    num = 0
    for t in tasks:
        num += t.getCount()

    return num

def git_checkout(repo_dir, tag):
    old_dir = os.getcwd()
    epath = expand(repo_dir)
    if os.path.isdir(epath):
        dirpath = epath
    else:
        dirpath = os.path.dirname(epath)

    os.chdir(dirpath)

    ret = subprocess.call(['git', 'checkout', tag])

    os.chdir(old_dir)

    return ret == 0
