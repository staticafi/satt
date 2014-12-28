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

class Result(object):
    def __init__(self, name):
        self.name = name

        self.tool = None
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
        except db.Error as e:
            err('{0}\n'.format(str(e)))

        # check if we're connected to the db
        # if not, the method will yield an error
        self._db('SELECT VERSION()')

    def __del__(self):
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

        if err:
            print('Check error >>')
            self.dump()

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
        print(query)
        try:
            cur = self._conn.cursor()
            cur.execute(query)
            ret = cur.fetchall()
            cur.close()
        except db.Error as e:
            err(str(e))

        return ret

    def updateDb(self):
        "Check if tool is in the database and put it there if it is not"

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

        q = """
        SELECT year_id FROM categories
        WHERE name = '{0}' and year_id = {1};
        """.format(self.category, year_id)
        res = self._db(q)
        if not res:
            # add category if we do not have it
            q = """
            INSERT INTO categories (name, year_id, created_at, updated_at)
            VALUES('{0}', '{1}', '{2}', '{3}');
            """.format(self.category, year_id, self.date, self.date)
            self._db(q)

        self._conn.commit()

    def store(self):
        "Store result in the database"
        self.updateDb()

        pass
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
        cat == 'Overall'

    doc = mdom.parse(f)
    res = doc.getElementsByTagName('result')[0]
    date = res.getAttribute('date')
    version = res.getAttribute('version')

    sfs = doc.getElementsByTagName('sourcefile')

    for sf in sfs:
        r = parse_sourcefile(sf)
        r.tool = tool
        r.year = year
        r.category = cat
        r.date = date
        r.version = version

        r.check()
        r.store()
