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
import os

from common import err
from dispatcher import RunningTask

class BenchmarkReport(object):
    """ Report results of benchmark. This is a abstract class """

    def report(self, msg, rb):
        """
        Report what happens for one benchmark.

        \param msg      one line of the output of the benchmark
        \param rb       instance of RunningBenchmark
        """
        mach = rb.task.getMachine()
        name = rb.name
        s = msg.strip()

        if s == '=== VERSIONS':
            rb._state = 'VERSIONS'
            return
        elif s == '=== RESULT':
            rb._state = 'RESULT'
            return
        elif s == '=== MEMORY USAGE':
            rb._state = 'MEMORY USAGE'
            return
        elif s == '=== TIME CONSUMED':
            rb._state = 'TIME CONSUMED'
            return

        if rb._state is None:
            rb.output += '{0}\n'.format(s)
        elif rb._state == 'VERSIONS':
            self.versions(rb, s);
        elif rb._state == 'RESULT':
            self.result(rb, s);
        elif rb._state == 'MEMORY USAGE':
            self.memoryUsage(rb, s);
        elif rb._state == 'TIME CONSUMED':
            self.timeConsumed(rb, s);

    def done(self, rb):
        " The benchmark is done"
        raise NotImplementedError("Child class needs to override this method")

    def result(self, rb, msg):
        if msg == 'TIMEOUT':
            rb.result = 'TIMEOUT'
        elif msg == 'FALSE':
            rb.result = 'FALSE'
        elif msg == 'ERROR':
            rb.result = 'ERROR'
        elif msg == 'TRUE':
            rb.result = 'TRUE'
        elif msg == 'UNKNOWN':
            rb.result = 'UNKNOWN'
        else:
            rb.output += 'RESULT: {0}\n'.format(msg)

    def versions(self, rb, msg):
            rb.versions += '{0}\n'.format(msg)

    def memoryUsage(self, rb, msg):
        try:
            if not rb.memory is None:
                raise ValueError('Memory usage already set')

            rb.memory = int(msg)
        except ValueError:
            rb.output += 'MEMORY USAGE: {0}\n'.format(msg)

    def timeConsumed(self, rb, msg):
        try:
            if not rb.time is None:
                raise ValueError('Time already set')

            rb.time = int(msg)
        except ValueError:
            rb.output += 'TIME CONSUMED: {0}\n'.format(msg)


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

class StdoutReporter(BenchmarkReport):
    """ Report results of benchmark to stdout """

    def done(self, rb):
        mach = rb.task.getMachine()
        name = rb.name

        color = None
        t = rb.name.find('true')
        f = rb.name.find('false')

        if rb.result == 'ERROR' or rb.result is None:
            color = 'red'
        elif rb.result == 'UNKNOWN':
            color = 'yellow'
        elif rb.result == 'TRUE':
            # if there is not true or false is before true
            # in the name
            if t == -1 or (f != -1 and f < t):
                color = 'red'
            else:
                color = 'green'
        elif rb.result == 'FALSE':
            if f == -1 or (t != -1 and t < f):
                color = 'red'
            else:
                color = 'green'

        print(colored('{0} - {1}: {2}'.format(rb.category,
                                              os.path.basename(name),
                                              rb.result), color))


        if rb.result is None:
            print(colored(rb.output, 'blue'))

        sys.stdout.flush()

class MysqlReporter(BenchmarkReport):

    def __init__(self, configs):
        # use this to print out what is happening
        self._stdout = StdoutReporter()

        try:
            self._conn = db.connect('localhost', 'statica',
                                    'statica', 'statica')
            self._cursor = self._conn.cursor()
        except _mysql.Error as e:
            sys.stderr.write('{0}\n'.format(str(e)))
            sys.exit(1)

        self._db('SELECT VERSION()')
        ver = self._db_fetchone()
        print('Connected to database: MySQL version {0}'.format(*ver))

    def _db(self, query):
        try:
            self._cursor.execute(query)
        except db.Error as e:
            sys.stderr.write('Failed querying db {0}\n'.format(e.args[1]))
            sys.exit(1)

    def _db_fetchone(self):
        return self._cursor.fetchone()

    def _db_fetchall(self):
        return self._cursor.fetchall()

    def __del__(self):
        self._conn.close()

    def done(self, rb):
        # print it after saving
        self._stdout.done(rb)

        #query = 'SELECT id, category_id from tasks where name = \'{0}\''.format(
        #        rb.name[pos + 1:])
        #self._db(query)
