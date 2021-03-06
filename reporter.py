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
from time import time, strftime, strptime

import configs

from common import err, dbg
from dispatcher import RunningTask
from log import satt_log

def get_correct_result_from_name(name, true_spec, false_spec):
    """
    Returns 'true' or 'false' depending on what of these words
    occurrs earlier in the name. If none of these is contained
    in the name, return None
    """
    is_true = False
    is_false = False

    for x in true_spec:
        if x in name:
            is_true = True
            break;

    for x in false_spec:
        if x in name:
            is_false = True
            break;

    if is_true and is_false:
        return None

    if is_true:
        return 'TRUE'
    elif is_false:
        return 'FALSE'
    else:
        return None


class BenchmarkReport(object):
    """ Report results of benchmark. This is a abstract class """

    def __init__(self):
        self._progress = 0

        self._keywords = {
            'reach'     : (['true-unreach-call'], ['false-unreach-call']),
            'memsafety' : (['true-valid-memsafety'], ['false-valid-deref',
                                                      'false-valid-memtrack',
                                                      'false-valid-free']),
            'overflow'  : (['true-no-overflow'], ['false-no-overflow']),
            'undef'     : (['true-def-behavior'], ['false-def-behavior'])
        }

    def _changeState(self, rb, s):
        if s == '=== VERSIONS':
            rb._state = 'VERSIONS'
            return True
        elif s == '=== RESULT':
            rb._state = 'RESULT'
            return True
        elif s == '=== MEMORY USAGE':
            rb._state = 'MEMORY USAGE'
            return True
        elif s == '=== TIME CONSUMED':
            rb._state = 'TIME CONSUMED'
            return True
        elif s == '=== WITNESS':
            rb._state = 'WITNESS'
            return True
        elif s == '=== WITNESS OUTPUT':
            rb._state = 'WITNESS OUTPUT'
            return True
        elif s == '=== OUTPUT':
            rb._state = 'OUTPUT'
            return True

        return False

    def report(self, msg, rb):
        """
        Report what happens for one benchmark.

        \param msg      one line of the output of the benchmark
        \param rb       instance of RunningBenchmark
        """
        mach = rb.task.getMachine()
        name = rb.name
        s = msg.strip()

        if self._changeState(rb, s):
            return

        if rb._state is None or rb._state == 'OUTPUT':
            rb.storeOutput('{0}\n'.format(s))
        elif rb._state == 'VERSIONS':
            self.versions(rb, s);
        elif rb._state == 'RESULT':
            self.result(rb, s);
        elif rb._state == 'MEMORY USAGE':
            self.memoryUsage(rb, s);
        elif rb._state == 'TIME CONSUMED':
            self.timeConsumed(rb, s);
        elif rb._state == 'WITNESS':
            self.witness(rb, s);
        elif rb._state == 'WITNESS OUTPUT':
            self.witnessOutput(rb, s);

    def summary(self):
        "Give summary of the run"
        pass

    def done(self, rb):
        " The benchmark is done"
        raise NotImplementedError("Child class needs to override this method")

    def progress(self, progress):
        self._progress = progress

    def result(self, rb, msg):
        if msg == 'TIMEOUT':
            rb.result = 'TIMEOUT'
        elif msg.startswith('FALSE'):
            rb.result = 'FALSE'
        elif msg == 'ERROR':
            rb.result = 'ERROR'
        elif msg == 'TRUE':
            rb.result = 'TRUE'
        elif msg == 'UNKNOWN':
            rb.result = 'UNKNOWN'
        else:
            rb.storeOutput('RESULT: {0}\n'.format(msg))

    def versions(self, rb, msg):
            rb.versions += '{0}\n'.format(msg)

    def witness(self, rb, msg):
            rb.witness += '{0}\n'.format(msg)

    def witnessOutput(self, rb, msg):
            rb.witness_output += '{0}\n'.format(msg)

    def memoryUsage(self, rb, msg):
        try:
            if not rb.memory is None:
                raise ValueError('Memory usage already set')

            rb.memory = float(msg)
        except ValueError:
            rb.storeOutput('MEMORY USAGE: {0}\n'.format(msg))

    def timeConsumed(self, rb, msg):
        try:
            if not rb.time is None:
                raise ValueError('Time already set')

            rb.time = float(msg)
        except ValueError:
            rb.storeOutput('TIME CONSUMED: {0}\n'.format(msg))

    def sendEmail(self, server, from_addr, to_addrs):
        pass

    def _get_correct_result(self, name, rb):
        if 'Reach' in rb.category:
            keywords = self._keywords['reach']
        elif 'MemSafety' in rb.category:
            keywords = self._keywords['memsafety']
        elif 'Overflow' in rb.category:
            keywords = self._keywords['overflow']
        elif 'DefinedBehavior' in rb.category:
            keywords = self._keywords['undef']
        else:
            #FIXME
            print("UNKNOWN CATEGORY!");
            return None

        return get_correct_result_from_name(name, keywords[0], keywords[1])

class StdoutReporter(BenchmarkReport):
    """ Report results of benchmark to stdout """
    def __init__(self):
        BenchmarkReport.__init__(self)
        self._incorrect_results = []
        self._correct_true_results_num = 0
        self._correct_false_results_num = 0
        self._incorrect_true_results_num = 0
        self._incorrect_false_results_num = 0
        self._error_results_num = 0
        self._unknown_results_num = 0
        self._total_num = 0

    def done(self, rb):
        self._total_num += 1
        mach = rb.task.getMachine()
        name = rb.name

        color = None
        result = rb.result
        correct = self._get_correct_result(os.path.basename(name), rb)

        if rb.result == 'ERROR' or rb.result is None:
            color = 'red_bg'
            self._error_results_num += 1
        elif rb.result == 'UNKNOWN':
            color = 'yellow'
            self._unknown_results_num += 1
        elif correct is None:
            color = 'red_bg'
            rb.result = 'cannot_decide ({0})'.format(rb.result)
        elif rb.result == 'TRUE':
            # if there is not true or false is before true
            # in the name
            if correct != 'TRUE':
                color = 'red'
                self._incorrect_true_results_num += 1
                self._incorrect_results.append(rb.name)
            else:
                self._correct_true_results_num += 1
                color = 'green'
        elif rb.result == 'FALSE':
            if correct != 'FALSE':
                color = 'red'
                self._incorrect_false_results_num += 1
                self._incorrect_results.append(rb.name)
            else:
                color = 'green'
                self._correct_false_results_num += 1

            if color == 'green' and rb.witness != '':
                wtns = rb.witness.strip()
                result = '{0} ({1})'.format(rb.result, wtns)

                if wtns != 'confirmed':
                    color = 'green_yellow_bg'

        prefix = '[{0} | {1}%]  '.format(strftime('%H:%M:%S'), self._progress)
        satt_log('{0} - {1}: {2}'.format(rb.category,
                                         os.path.basename(name), result),
                                         color, prefix = prefix)

        if rb.result is None or rb.result == 'ERROR':
            satt_log('--- output <<{0}>>'.format(mach))
            out = rb.output.strip()

            if out:
                satt_log(out)
                satt_log('---')

        if rb.result is None:
            return False

        return True
    def summary(self):
        incorrect_results_num = self._incorrect_false_results_num + self._incorrect_true_results_num

        satt_log("-----------------------------------------------------------------------")
        satt_log(" -| Ran in total {0} benchmarks of which {1} were answered incorrectly"\
                 .format(self._total_num, incorrect_results_num))
        satt_log(" -|")
        satt_log(" -| Correct   TRUE  results: {0}".format(self._correct_true_results_num))
        satt_log(" -| Correct   FALSE results: {0}".format(self._correct_false_results_num))
        satt_log(" -| Incorrect TRUE  results: {0}".format(self._incorrect_true_results_num))
        satt_log(" -| Incorrect FALSE results: {0}".format(self._incorrect_false_results_num))
        satt_log(" -| UNKNOWN         results: {0}".format(self._unknown_results_num))
        satt_log(" -| ERROR           results: {0}".format(self._error_results_num))
        satt_log(" -|")
        if incorrect_results_num > 0:
            satt_log(" -| Incorrect results:")
            for b in self._incorrect_results:
                satt_log("   -- {0}".format(b))
        satt_log("-----------------------------------------------------------------------")

def no_witness_categ(categ):
    # we're missing the Termination and Concurrency
    return categ.endswith('-Arrays') or\
           categ.endswith('-Floats') or\
           categ.endswith('-Heap') or\
           'MemSafety' in categ

class RatingMethod(object):
    def __init__(self, query_func):
        res = query_func('SELECT unknown, false_correct, false_incorrect,'
                         'true_correct, true_incorrect '
                         'FROM rating_methods INNER JOIN years '
                         'ON rating_methods.year_id = years.id '
                         'WHERE year = \'{0}\';'.format(configs.configs['year']))
        if not res:
            err('Failed getting rating methods')

        res = res[0]

        self.unknown = res[0]
        self.false_correct = res[1]
        self.false_incorrect = res[2]
        self.true_correct = res[3]
        self.true_incorrect = res[4]

    def points(self, ok, res, witness = None, categ=None):
       if res is None:
           return 0

       res = res.lower()

       if res == 'unknown' or res == 'error' or res == 'timeout':
           return self.unknown
       elif res == 'false':
           if ok:
                if witness == 'confirmed' or no_witness_categ(categ):
                    return self.false_correct
                else:
                    return self.unknown
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

def get_name(name):
    return os.path.basename(name)

class MysqlReporter(BenchmarkReport):
    def __init__(self):
        BenchmarkReport.__init__(self)

        # use this to print out what is happening
        self._stdout = StdoutReporter()
        self.run_id = int(time())
        self.tool_params = '{0}'.format(configs.configs['params'])

        # replace apostrophes in tool_params
        self.tool_params = self.tool_params.replace('\'', '\\\'')

        from database import DatabaseConnection
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
        def choose_tag():
            if configs.configs.has_key('tool-tag'):
                return configs.configs['tool-tag']
            else:
                return configs.configs['tool']

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
                       ver, self.tool_params, choose_tag(),
                       Empty2Null(configs.configs['note']))
            self._db.query(q2)

            # get new tool_id
            res = self._db.query(q)
            assert len(res) == 1

        tool_id = res[0][0]

        return tool_id, year_id

    def save_task(self, rb, cat_id):
        """ Save unknown task into the database """

        name = get_name(rb.name)
        cr = self._get_correct_result(name, rb)
        if cr is None:
            msg = 'Couldn\'t infer if the result is correct or not, setting unkown'
            satt_log(msg)
            rb.output += msg
            rb.result = 'unknown ({0})'.format(rb.result)
        # create new task
        q = """
        INSERT INTO tasks
          (name, category_id, correct_result, property)
          VALUES('{0}', '{1}', '{2}', '{3}');
        """.format(name, cat_id, cr, None)
        self._db.query(q)

        q = """
        SELECT id, correct_result FROM tasks
        WHERE name = '{0}' and category_id = '{1}';
        """.format(name, cat_id)
        return self._db.query(q)

    def update_category(self, year_id, name):
        """ Create new category in the database """

        # create the a category in the database
        q = """
        INSERT INTO categories
          (year_id, name) VALUES ('{0}', '{1}');
        """.format(year_id, name)
        self._db.query(q)

        # return the new result
        q = """
        SELECT id, name FROM categories
        WHERE
            year_id = '{0}' and name = '{1}';
        """.format(year_id, name)

        return self._db.query(q)

    def done(self, rb):
        # print it after saving
        if not self._stdout.done(rb):
            # if there is a problem, the benchmark will run again, so do not
            # proceed further
            return False

        tool_id, year_id = self._updateDb(rb)

        q = """
        SELECT id, name FROM categories
        WHERE
            year_id = '{0}' and name = '{1}';
        """.format(year_id, rb.category)
        res = self._db.query(q)
        if not res:
            if configs.configs['save-new-tasks'] == 'yes':
                res = self.update_category(year_id, rb.category)
            else:
                rb.dumpToFile('Do not have given category')
                satt_log('^^ dumped to file (unknown category)')
                return True

        assert len(res) == 1
        if not len(res[0]) == 2:
            print(res[0])
        assert len(res[0]) == 2
        cat_id = res[0][0]
        cat_name = res[0][1]

        q = """
        SELECT id, correct_result FROM tasks
        WHERE name = '{0}' and category_id = '{1}';
        """.format(get_name(rb.name), cat_id)
        res = self._db.query(q)

        # we do not have such a task??
        if not res:
            if configs.configs['save-new-tasks'] == 'yes':
                res = self.save_task(rb, cat_id)
            else:
                rb.dumpToFile('Do not have given task')
                satt_log('^^ dumped to file (unknown task)')
                return True

        assert len(res) == 1
        task_id = res[0][0]
        correct_result = res[0][1]

        # replace ' by \' in output
        rb.output = rb.output.replace('\'', '\\\'')
        ic = is_correct(correct_result, rb.result)

        result= rb.result.lower()
        if rb.witness != '':
            wtns = rb.witness.strip()

            # replace ' even in witness, because it can contain
            # arbitrary text
            wtns = wtns.replace('\'', '\\\'')
        else:
            wtns = None

        if rb.witness_output != '':
            # FIXME we should limit the wintess_output size, otherwise we
            # get get some performance issues
            rb.witness_output = rb.witness_output.strip()
            rb.witness_output = rb.witness_output.replace('\'', '\\\'')

        q = """
        INSERT INTO task_results
        (tool_id, task_id, result, witness, is_correct, points, cpu_time,
         memory_usage, output, witness_output, run_id)
        VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}', {8}, '{9}', '{10}')
        """.format(tool_id, task_id, result, wtns, ic,
                   self._rating_methods.points(ic, rb.result, wtns, cat_name), None2Zero(rb.time),
                   None2Zero(rb.memory), Empty2Null(rb.output), rb.witness_output, self.run_id)

        def _exception_handler(args, data):
            q, tool_id, task_id = data

            if (args[1].startswith('Duplicate entry')):

                if configs.configs['ignore-duplicates'] == 'yes':
                    satt_log('Already has this result for this tool, ignoring.')
                else:
                    err('Already has result of this benchmark for this tool.\n'
                        'It is only supported to have one result for each '
                        'benchmark and particular tool\n'
                        'If want ignore this behaviour use --ignore-duplicates.\n'
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

        time_format = '%Y-%m-%d-%H-%S'
        raw_started_at = strptime(configs.configs['started_at'], time_format)
        started_at = strftime('%a %b %d %H:%M:%S %Y', raw_started_at)
        finished_at = strftime('%a %b %d %H:%M:%S %Y')

        text = """
This is automatically generated message. Do not answer.
=======================================================

Satt on tool {0} started at {1}, finished {2}
with parameters: {3}
on benchmarks from year {4}

Note: {5}

Results:

""".format(configs.configs['tool'],
           started_at,
           finished_at,
           configs.configs['params'],
           configs.configs['year'],
           configs.configs['note'])

        q = """
        SELECT result, is_correct, witness, count(*)
            FROM task_results
            WHERE run_id = {0}
            GROUP BY result, is_correct, witness""".format(self.run_id)

        res = self._db.query(q)
        if not res:
            err('No results stored to db after this run?')

        total = 0
        for row in res:
            result = row[0]
            if result == 'true' or result == 'false':
                if row[1] == 0:
                    result += ' incorrect'
                else:
                    result += ' correct'

            if not row[2] is None:
                text += '{0:<15} (witness {1}): {2}\n'.format(result, row[2], row[3])
            else:
                text += '{0:<15}: {1}\n'.format(result, row[3])

            total += row[3]

        text += '\nTotal number of benchmarks: {0}'.format(total)

        q = """SELECT tool_id FROM task_results
               WHERE run_id = {0}""".format(self.run_id)
        res = self._db.query(q)
        if not res:
            err('Failed querying db for tool\'s id')

        tool_id = res[0][0]

        text += '\n\nYou can check the results here:\n'
        text += 'http://macdui.fi.muni.cz:3000/tools/{0}'.format(tool_id)

        text += '\n\nHave a nice day!\n'

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
