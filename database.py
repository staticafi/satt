#!/usr/bin/env python
#
# This script distributes task between computers. The task
# is to be run the Symbiotic tool on given benchark.
#
# (c)oded 2015, Marek Chalupa
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

from common import err

def get_db_credentials(path = 'database/config'):
    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening file with database configuration: {0}".format(e.strerror))

    host = None
    user = None
    db = None
    pw = None

    for l in f:
        l = l.lstrip()
        if l[0] == '#':
            continue

        k,v = l.split('=', 1)
        k = k.strip()
        v = v.strip()

        if k == 'host':
            host = v
        elif k == 'user':
            user = v
        elif k == 'password':
            pw = v
        elif k == 'db':
            db = v
        else:
            err('Unknown key in {0}: \'{1}\''.format(path, k))

    f.close()

    return host, user, pw, db

def check_db_credentials(host, user, passwd, db):
    if host is None or host == '':
        err('Missing \'host\' for database')
    if user is None or user == '':
        err('Missing \'user\' for database')
    if passwd is None or passwd == '':
        err('Missing \'password\' for database')
    if db is None or db == '':
        err('Missing \'database\' for database')

