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

import os
from time import time, strftime

import configs

from common import err, dbg
from dispatcher import RunningTask
from log import satt_log
from database import DatabaseConnection

class BenchmarkReport(object):
    """ Report results of benchmark. This is a abstract class """

    def __init__(self):
        self._progress = 0

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

    def progress(self, progress):
        self._progress = progress

    def result(self, rb, msg):
        m = msg.upper()

        if m == 'TIMEOUT':
            rb.result = 'TIMEOUT'
        elif m == 'FALSE':
            rb.result = 'FALSE'
        elif m == 'ERROR':
            rb.result = 'ERROR'
        elif m == 'TRUE':
            rb.result = 'TRUE'
        elif m == 'UNKNOWN':
            rb.result = 'UNKNOWN'
        else:
            rb.output += 'RESULT: {0}\n'.format(msg)

    def versions(self, rb, msg):
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

    def sendEmail(self, server, from_addr, to_addrs):
        pass

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

        prefix = '[{0} | {1}%]  '.format(strftime('%H:%M:%S'), self._progress)
        satt_log('{0} - {1}: {2}'.format(rb.category,
                                         os.path.basename(name),
                                         rb.result), color, prefix = prefix)


        if rb.result is None or rb.result == 'ERROR':
            satt_log('--- output <<{0}>>'.format(mach))
            out = rb.output.strip()

            if out:
                satt_log(out)
                satt_log('---')

        if rb.result is None:
            return False

        return True

class RatingMethod(object):
    def __init__(self, query_func):
        res = query_func('SELECT unknown, false_correct, false_incorrect,'
                         'true_correct, true_incorrect '
                         'FROM rating_methods INNER JOIN years '
                         'ON rating_methods.year_id = years.id '
                         'WHERE year = {0};'.format(configs.configs['year']))
        if not res:
            err('Failed getting rating methods')

        res = res[0]

        self.unknown = res[0]
        self.false_correct = res[1]
        self.false_incorrect = res[2]
        self.true_correct = res[3]
        self.true_incorrect = res[4]

    def points(self, ok, res):
       if res is None:
           return 0

       res = res.lower()

       if res == 'unknown' or res == 'error' or res == 'timeout':
           return self.unknown
       elif res == 'false':
           if ok:
               return self.false_correct
           else:
               return self.false_incorrect
       elif res == 'true':
           if ok:
               return self.true_correct
           else:
               return self.true_incorrect
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

    return '\'{0}\''.format(x.strip())

def is_correct(res1, res2):
    if res1 is None or res2 is None:
        return 0

    if res1.upper() == res2.upper():
        return 1

    return 0

class MysqlReporter(BenchmarkReport):
    def __init__(self):
        BenchmarkReport.__init__(self)

        # use this to print out what is happening
        self._stdout = StdoutReporter()
        self.run_id = int(time())
        self.tool_params = '{0}'.format(configs.configs['params'])

        # replace apostrophes in tool_params
        self.tool_params = self.tool_params.replace('\'', '\\\'')

        self._db = DatabaseConnection()

        ver = self._db.query('SELECT VERSION()')[0][0]
        satt_log('Connected to database: MySQL version {0}'.format(ver))

        self._rating_methods = RatingMethod(self._db.query)

    def progress(self, progress):
        # we must redirect progress to stdout
        self._stdout.progress(progress)

    def _commit(self):
        self._db.commit()

    def _updateDb(self, rb):
        ver = rb.versions.strip()

        q = """
        SELECT id FROM years WHERE year = '{0}';
        """.format(configs.configs['year']);
        res = self._db.query(q)
        if not res:
            err('Do not have year {0}. If this is not typo, '
                'update the database and benchmarks'.format(configs.configs['year']))

        year_id = res[0][0]

        # If tool that runs in this run is not known to database, add it
        q = """
        SELECT id FROM tools
        WHERE name = '{0}' and version = '{1}'
              and params = '{2}' and year_id = '{3}';
        """.format(configs.configs['tool'], ver, self.tool_params, year_id)
        res = self._db.query(q)
        if not res:
            q2 = """
            INSERT INTO tools
            (name, year_id, version, params, tag, note)
            VALUES('{0}', '{1}', '{2}', '{3}', '{4}', {5});
            """.format(configs.configs['tool'], year_id,
                       ver, self.tool_params, configs.configs['tool'],
                       Empty2Null(configs.configs['note']))
            self._db.query(q2)

            # get new tool_id
            res = self._db.query(q)
            assert len(res) == 1

        tool_id = res[0][0]

        return tool_id, year_id

    def done(self, rb):
        # print it after saving
        if not self._stdout.done(rb):
            # if there is a problem, the benchmark will run again, so do not
            # proceed further
            return False

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

        tool_id, year_id = self._updateDb(rb)

        q = """
        SELECT id FROM categories
        WHERE
            year_id = '{0}' and name = '{1}';
        """.format(year_id, rb.category)
        res = self._db.query(q)
        if not res:
            rb.dumpToFile('Do not have given category')
            satt_log('^^ dumped to file (unknown category)')
            return True

        assert len(res) == 1
        cat_id = res[0][0]

        q = """
        SELECT id, correct_result FROM tasks
        WHERE name = '{0}' and category_id = '{1}';
        """.format(get_name(rb.name), cat_id)
        res = self._db.query(q)

        # we do not have such a task??
        if not res:
            rb.dumpToFile('Do not have given task')
            satt_log('^^ dumped to file (unknown task)')
            return True

        assert len(res) == 1
        task_id = res[0][0]
        correct_result = res[0][1]

        # replace ' by \' in output
        rb.output = rb.output.replace('\'', '\\\'')
        ic = is_correct(correct_result, rb.result)

        q = """
        INSERT INTO task_results
        (tool_id, task_id, result, is_correct, points, cpu_time,
         memory_usage, output, run_id)
        VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', {7}, '{8}')
        """.format(tool_id, task_id, rb.result.lower(),
                   is_correct(correct_result, rb.result),
                   self._rating_methods.points(ic, rb.result), None2Zero(rb.time),
                   None2Zero(rb.memory), Empty2Null(rb.output), self.run_id)

        def _exception_handler(args, data):
            if (args[1].startswith('Duplicate entry')):
                q, tool_id, task_id = data

                err('Already has result of this benchmark for this tool.\n'
                    'It is only supported to have one result for each '
                    'benchmark and particular tool\n'
                    '(tool + version + params). You can delete the old result:\n'
                    '  $ ./db-cli \'DELETE from task_results WHERE tool_id={0}'
                    ' and task_id={1}\'\n'
                    'or you can delete all results for this tool:\n'
                    '  $ ./db-cli \'DELETE from tools WHERE id={0}\'\n'
                    .format(tool_id, task_id, tool_id))
            else:
                err('Failed querying db: {0}\n\n{1}'.format(args[1], q))

        self._db.query_with_exception_handler(q, _exception_handler,
                                              (q, tool_id, task_id))

        self._commit()

        return True


    def sendEmail(self, server, from_addr, to_addrs):
        import smtplib
        from email.mime.text import MIMEText

        started_at = configs.configs['started_at']

        text = """
This is automatically generated message. Do not answer.
=======================================================

Satt on tool {0} started at {1}, finished {2}
with parameters: {3}

Results:

""".format(configs.configs['tool'],
           started_at,
           strftime('%Y-%m-%d-%H-%S'),
           configs.configs['params'])

        q = """
        SELECT result, is_correct, count(*)
            FROM task_results
            WHERE run_id = {0}
            GROUP BY result, is_correct""".format(self.run_id)

        res = self._db.query(q)
        if not res:
            err('No results stored to db after this run?')

        for row in res:
            if row[1] == 0:
                text += '{0} {1}: {2}\n'.format(row[0],
                                              'incorrect', row[2])
            else:
                text += '{0} {1}: {2}\n'.format(row[0],
                                              'correct', row[2])

        msg = MIMEText(text)
        msg['Subject'] = 'Satt results from {0}'.format(started_at)
        msg['From'] = from_addr
        msg['To'] = 'statica@fi.muni.cz'

        s = smtplib.SMTP(server)
        ret = s.sendmail(from_addr, to_addrs, msg.as_string())
        s.quit()

        for r in ret:
            dbg('Failed sending e-mail to {0},'
                'err: {1}'.format(r[0], r[1]))
