#!/usr/bin/env python
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

import sys
import os

from xml.dom import minidom as mdom

def err(msg):
    sys.stderr.write('ERR: {0}\n'.format(msg))
    sys.exit(1)

try:
    import MySQLdb as db
except ImportError:
    err('Do not have MySQLdb module')

def get_correct_result(name):
    """
    Returns 'true' or 'false' depending on what of these words
    occurrs earlier in the name
    """

    ti = name.find('true')
    fi = name.find('false')

    # we must have either one or the other
    assert ti != -1 or fi != -1

    if ti == -1:
        return 'false'
    elif fi == -1:
        return 'true'
    else: # both of the words are in the name
        if ti < fi:
            return 'true'
        else:
            return 'false'

class Result(object):
    def __init__(self, name):
        self.name = name

        self.tool = None
        self.params = None
        self.version = None
        self.year = None
        self.date = None
        self.category = None
        self.status = None
        self.correct = None
        self.cpuTime = None
        self.memUsage = None

        try:
            self._conn = db.connect('localhost', 'statica',
                                    'statica', 'statica')
            self._cursor = self._conn.cursor()
        except db.Error as e:
            err('{0}\n'.format(str(e)))

        # check if we're connected to the db
        # if not, the method will yield an error
        self._db('SELECT VERSION()')

    def __del__(self):
        self._cursor.close()
        self._conn.close()
        del self

    def check(self):
        assert not self.name is None
        err = False

        if self.tool is None:
            err = True
        elif self.version is None:
            err = True
        elif self.year is None:
            err = True
        elif self.date is None:
            err = True
        elif self.category is None:
            err = True
        elif self.status is None:
            err = True
        elif self.correct is None:
            err = True
        elif self.cpuTime is None:
            err = True
        elif self.memUsage is None:
            err = True
        # self.param can be None

        if err:
            print('Check error >>')
            self.dump()

        return not err

    def __str__(self):
        return """
name: {0} - {1}
tool: {2} {3}
date: {4} -- {5}
status: {6} [{7}]
resources: {8}, {9} MB
        """.format(self.category, self.name, self.tool, self.version,
                   self.year, self.date, self.status, self.correct,
                   self.cpuTime, self.memUsage)

    def dump(self):
        print(self.__str__())

    def _db(self, query):
        try:
            self._cursor.execute(query)
            ret = self._cursor.fetchall()
        except db.Error as e:
            err(str(e))

        return ret

    def updateDb(self):
        "Check if tool is in the database and put it there if it is not"

        assert self.check()

        ###
        # Update years table
        ###

        # I don't want to catch exceptions and check if we have duplicate rows
        # so just query the db and insert only if we do not have the row
        q = 'SELECT count(id) FROM years WHERE year = {0}'.format(self.year)
        res = self._db(q)
        if res[0][0] == 0:
            q = 'INSERT INTO years (year, created_at, updated_at) '\
            'VALUES(\'{0}\', \'{1}\',\'{2}\');'.format(self.year, self.date, self.date)

            # add year if we do not have this one
            self._db(q)

        res = self._db('SELECT id FROM years WHERE year = {0};'.format(self.year))
        year_id = res[0][0]

        ###
        # Update categories table
        ###

        category_id = None

        q = """
        SELECT id FROM categories
        WHERE name = '{0}' and year_id = {1};
        """.format(self.category, year_id)
        res = self._db(q)
        if not res:
            # add category if we do not have it
            q2 = """
            INSERT INTO categories (name, year_id, created_at)
            VALUES('{0}', '{1}', '{2}');
            """.format(self.category, year_id, self.date)
            self._db(q2)

            # get new category id
            # XXX use executemany instead?
            res = self._db(q)
            assert len(res) == 1
            category_id = res[0][0]

        else:
            assert len(res) == 1
            category_id = res[0][0]

        ###
        # Update tools table
        ###

        tool_id = None

        q = """
        SELECT id FROM tools WHERE name = '{0}' and version = '{1}' and params = '{2}' and year_id = '{3}';
        """.format(self.tool, self.version, self.params, year_id)
        res = self._db(q)
        # inconsistency in database (more rows for one version of a tool)
        assert len(res) < 2

        if not res:
            # no tool of this name and version, add it!
            q2 = """
            INSERT INTO tools (name, year_id, version, params, created_at, tag)
            VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}');
            """.format(self.tool, year_id, self.version, self.params,
                       self.date, 'svcomp')
            self._db(q2)

            res = self._db(q)
            assert len(res) == 1
            tool_id = res[0][0]

        else:
            tool_id = res[0][0]

        ###
        # Update tasks
        ###
        task_id = None
        assert not category_id is None

        q = """
        SELECT id FROM tasks WHERE name = '{0}' and category_id = '{1}'
        """.format(self.name, category_id)
        res = self._db(q)
        if res:
            task_id = res[0][0]
        else:
            correct_result = get_correct_result(self.name)
            q2 = """
            INSERT INTO tasks
            (name, category_id, correct_result, created_at)
            VALUES('{0}', '{1}', '{2}', '{3}', '{4}');
            """.format(self.name, category_id, correct_result,
                       self.date, self.date);
            self._db(q2)

            res = self._db(q)
            assert len(res) == 1
            task_id = res[0][0]

        return (tool_id, task_id)

    def store(self):
        "Store result in the database"
        tool_id, task_id = self.updateDb()
        assert self.check()

        def is_correct(x):
            if x == 'correct':
                return 1

            return 0

        def get_points(is_correct, status):
            # for sv-comp 2014
            if status == 'false':
                if is_correct == 1:
                    return 1
                else:
                    return -4
            elif status == 'true':
                if is_correct == 1:
                    return 2
                else:
                    return -8
            else:
                return 0

        q = """
        INSERT INTO task_results
        (tool_id, task_id, result, is_correct, points,
        cpu_time, memory_usage, created_at)
        VALUES('{0}', '{1}', '{2}', '{3}', '{4}', '{5}', '{6}', '{7}');
        """.format(tool_id, task_id, self.status, is_correct(self.correct),
                   get_points(is_correct(self.correct), self.status),
                   self.cpuTime, self.memUsage, self.date, self.date)
        self._db(q)

    def commit(self):
        print('Commited: {0} - {1} - {2}'.format(self.tool, self.category, self.name))
        self._conn.commit()

def parse_sourcefile(sf):
    #print('Not handled attrs: options')
    name = sf.getAttribute('name')
    # remove prefix (hardcode it at least for now)
    name = name.replace('../../sv-benchmarks/c/', '')
    r = Result(name)

    columns = sf.getElementsByTagName('column')
    assert columns

    for c in columns:
        title = c.getAttribute('title')
        value = c.getAttribute('value')

        if title == 'status':
            r.status = value
        elif title == 'cputime':
            r.cpuTime = value
        elif title == 'memUsage':
            r.memUsage = value
        elif title == 'category':
            r.correct = value

    if r.correct is None:
        assert not r.status is None
        if r.status == get_correct_result(r.name):
            r.correct = 'correct'
        else:
            r.correct = 'incorrect'

    return r

if __name__ == "__main__":
    f = sys.argv[1]
    basename = os.path.basename(f)
    parts = basename.split('.')

    tool = parts[0]
    tp = parts[2]

    if tp != 'results':
        print('Skipping witnesscheck file')
        sys.exit(0)
    # what the true and false files are at all?
    if tool == 'true':
        print('Skipping true file')
        sys.exit(0)
    if tool == 'false':
        print('Skipping false file')
        sys.exit(0)

    year = 2000 + int(parts[3][-2:])
    cat = parts[4]
    if cat == 'xml':
        print('Skipping overall category')
        sys.exit(0)

    doc = mdom.parse(f)
    res = doc.getElementsByTagName('result')[0]
    date = res.getAttribute('date')
    params = res.getAttribute('options')
    version = res.getAttribute('version')

    sfs = doc.getElementsByTagName('sourcefile')

    for sf in sfs:
        r = parse_sourcefile(sf)
        r.tool = tool
        r.year = year
        r.category = cat
        r.date = date
        r.version = version
        r.params = params

        r.check()
        r.store()

        # commit only if everything went well
        # (no error or exception aborted the script here)
        r.commit()
