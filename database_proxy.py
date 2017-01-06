#!/usr/bin/env python
#
# Copyright (c) 2015 Marek Chalupa
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

import configs

from os.path import basename
from common import err, dbg
from dispatcher import RunningTask
from log import satt_log
from database import DatabaseConnection

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

    def points(self, ok, res, witness = None):
       if res is None:
           return 0

       res = res.lower()

       if res == 'unknown' or res == 'error' or res == 'timeout':
           return self.unknown
       elif res == 'false':
           if ok:
                if witness == 'confirmed':
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

def get_name(name):
    return basename(name)

class DatabaseProxy(object):
    def __init__(self, conffile = None):
        self._db = DatabaseConnection(conffile)

        # self check
        ver = self._db.query('SELECT VERSION()')[0][0]
        satt_log('Connected to database: MySQL version {0}'.format(ver))

        self._rating_methods = RatingMethod(self._db.query)

    def connection(self):
        return self._db

    def commit(self):
        self._db.commit()

    def getYearID(self, year):
        q = """
        SELECT id FROM years WHERE year = '{0}';
        """.format(year);

        res = self._db.query(q)
        if not res:
            return None

        return res[0][0]

    def getToolID(self, tool, version, tool_params, year_id):
        q = """
        SELECT id FROM tools
        WHERE name = '{0}' and version = '{1}'
              and params = '{2}' and year_id = '{3}';
        """.format(tool, version, tool_params, year_id)
        res = self._db.query(q)
        if not res:
            return None

        assert len(res) == 1
        return res[0][0]

    def getCategoryID(self, year_id, category_name):
        q = """
        SELECT id FROM categories
        WHERE
            year_id = '{0}' and name = '{1}';
        """.format(year_id, category_name)
        res = self._db.query(q)
        if not res:
            return None

        return res[0][0]

    def getTaskID(self, category_id, name):
        q = """
        SELECT id FROM tasks
        WHERE name = '{0}' and category_id = '{1}';
        """.format(get_name(name), category_id)
        res = self._db.query(q)
        if not res:
            return None

        return res[0][0]

    def getTaskWithCorrectResult(self, category_id, name):
        q = """
        SELECT id, correct_result FROM tasks
        WHERE name = '{0}' and category_id = '{1}';
        """.format(get_name(rb.name), cat_id)
        res = self._db.query(q)
        if not res:
            return None

        return (res[0][0], res[0][1])

    def hasTaskResult(self, task_id, tool_id):
        q = """
        SELECT count(*) FROM task_results
        WHERE task_id = '{0}' and tool_id = '{1}';
        """.format(task_id, tool_id)
        res = self._db.query(q)
        if not res:
            return False

        return res[0][0] != 0

