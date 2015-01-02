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
import time

import configs

from common import err, colored, dbg
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
        msg = msg.upper()

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
            if rb.versions is None:
                rb.versions = ''

            rb.versions += '{0}\n'.format(msg)

    def memoryUsage(self, rb, msg):
        try:
            if not rb.memory is None:
                raise ValueError('Memory usage already set')

            rb.memory = float(msg)
        except ValueError:
            rb.output += 'MEMORY USAGE: {0}\n'.format(msg)

    def timeConsumed(self, rb, msg):
        try:
            if not rb.time is None:
                raise ValueError('Time already set')

            rb.time = float(msg)
        except ValueError:
            rb.output += 'TIME CONSUMED: {0}\n'.format(msg)

class StdoutReporter(BenchmarkReport):
    """ Report results of benchmark to stdout """

    def done(self, rb):
        mach = rb.task.getMachine()
        name = rb.name

        color = None
        t = rb.name.find('true')
        f = rb.name.find('false')

        if rb.result == 'ERROR' or rb.result is None:
            color = 'red_bg'
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

try:
    import MySQLdb as db
except ImportError:
    dbg('Do not have MySQLdb module')

class MysqlReporter(BenchmarkReport):
    def __init__(self):
        # use this to print out what is happening
        self._stdout = StdoutReporter()

        try:
            self._conn = db.connect('localhost', 'statica',
                                    'statica', 'statica')
            self._cursor = self._conn.cursor()
        except NameError: # we do not have MySQLdb module
            err('Do not have MySQLdb module')
        except db.Error as e:
            err('{0}\n'.format(str(e)))

        ver = self._db('SELECT VERSION()')[0][0]
        print('Connected to database: MySQL version {0}'.format(ver))

    def _db(self, query):
        ret = None

        try:
            self._cursor.execute(query)
            ret = self._cursor.fetchall()
        except db.Error as e:
            err('Failed querying db {0}\n'.format(e.args[1]))

        return ret

    def __del__(self):
        try:
            self._conn.close()
        except AttributeError:
            # this means that we do not have MySQLdb module
            pass

    def _commit(self):
        self._conn.commit()

    def _updateDb(self, rb):
        def get_params(p):
            if p is None:
                return ''

            return p

        ver = rb.versions.strip()

        # If tool that runs in this run is not known to database, add it
        q = """
        SELECT id FROM tools WHERE name = '{0}' and version = '{1}';
        """.format(configs.configs['tool'], ver)
        res = self._db(q)
        if not res:
            tm = time.strftime('%y-%m-%d %H:%M')
            q2 = """
            INSERT INTO tools
            (name, year_id, version, params, created_at, updated_at)
            VALUES('{0}', '(SELECT id FROM years WHERE year = {1})',
                   '{2}', '{3}', '{4}', '{5}');
            """.format(configs.configs['tool'], configs.configs['year'],
                       ver, get_params(rb.params), tm, tm)
            self._db(q2)

            # get new tool_id
            res = self._db(q)
            assert len(res) == 1

        tool_id = res[0][0]

        return tool_id

    def done(self, rb):
        # print it after saving
        self._stdout.done(rb)

        def get_name(name):
            n = 0
            i = len(name) - 1
            while i  >= 0:
                if name[i] == '/':
                    n += 1

                    if n == 2:
                        break

                i -= 1

            return name[i + 1:]

        def dumpToFile(rb, msg = None):
            fname = '{0}.{1}.{2}.log'.format(
                     configs.configs['tool'], os.path.basename(rb.name),
                     time.strftime('%y-%m-%d-%H-%M-%s'))
            f = open(fname, 'w')

            if msg:
                f.write('Reason: {0}'.format(msg))
            f.write('category: {0}\n'.format(rb.category))
            f.write('name: {0}\n\n'.format(rb.name))
            f.write('cmd: {0}\n'.format(rb.cmd))
            f.write('params: {0}\n'.format(rb.params))
            f.write('versions: {0}\n'.format(rb.versions))
            f.write('result: {0}\n'.format(rb.result))
            f.write('memUsage: {0}\n'.format(rb.memory))
            f.write('cpuUsage: {0}s\n\n'.format(rb.time))
            f.write('other output:\n{0}\n'.format(rb.output))

            f.close()

        def is_correct(res1, res2):
            if res1.upper() == res2.upper():
                return 1

            return 0

        def points(ok, res):
            res = res.lower()

            if res == 'unknown' or res == 'error' or res == 'timeout':
                return 0
            elif res == 'false':
                if ok:
                    return 1
                else:
                    return -6
            elif res == 'true':
                if ok:
                    return 2
                else:
                    return -12
            else:
                dbg('Unknown result, skipping points')
                return 0

        def None2Zero(x):
            if x is None:
                return 0
            return x

        def Empty2Null(x):
            if x == '':
                return 'NULL'

            return '\'{0}\''.format(x)

        tool_id = self._updateDb(rb)

        q = """
        SELECT id FROM categories
        WHERE
            year_id = (SELECT id FROM years WHERE year = {0}) and
            name = '{1}';
        """.format(configs.configs['year'], rb.category)
        res = self._db(q)
        if not res:
            dumpToFile(rb, 'Do not have given category')
            return

        assert len(res) == 1
        cat_id = res[0][0]

        q = """
        SELECT id, correct_result FROM tasks WHERE name = '{0}' and category_id = '{1}';
        """.format(get_name(rb.name), cat_id)
        res = self._db(q)

        # we do not have such a task??
        if not res:
            dumpToFile(rb, 'Do not have given task')
            return

        assert len(res) == 1
        task_id = res[0][0]
        correct_result = res[0][1]

        ic = is_correct(correct_result, rb.result)
        tm = time.strftime('%y-%m-%d %H:%M')

        q = """
        INSERT INTO task_results
        (tool_id, task_id, result, is_correct, points, cpu_time,
         memory_usage, created_at, updated_at, output)
        VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}', '{8}', {9})
        """.format(tool_id, task_id, rb.result.lower(),
                   is_correct(correct_result, rb.result),
                   points(ic, rb.result), None2Zero(rb.time),
                   None2Zero(rb.memory), tm, tm, Empty2Null(rb.output))
        self._db(q)

        self._commit()

