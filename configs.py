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
#
# On arran we have only python2, so use python2

import sys
import os
import getopt

def usage():
    sys.stderr.write(
"""
Usage: satt OPTS tool

OPTS can be:
    --machines=file.txt             File with machines
    --benchmarks=dir_with_sets      Directory with sets of benchmarks
    --no-sync                       Do not sync tool on remote machines
    --sync=[yes/no]                 Whether to sync tool on remote machines

For configuration is searched in name_of_tool.conf file.
Command-line argument have higher priority. Tool defaults to 'symbiotic'
""")

allowed_keys = ['tool-dir', 'remote-dir', 'benchmarks', 'machines',
                'ssh-user', 'ssh-cmd', 'remote-cmd', 'sync', 'timeout',
                'no-db', 'sync-cmd']

# fill in default values
configs = {'sync':'yes', 'ssh-user':'', 'remote-dir':'',
           'remote-cmd':'echo "ERROR: No command specified"',
           'no-db':'no', 'debug':'no', 'tool':'symbiotic'}

def parse_configs(path = 'symbiotic.conf'):
    from common import err, dbg

    if os.path.exists(path):
        print('Using config file {0}'.format(path))
    else:
        return configs

    try:
        f = open(path, 'r')
    except IOError as e:
        err("Failed opening configuration file ({0}): {1}"
            .format(path, e.strerror))

    for line in f:
        line = line.strip()
        if not line or line[0] == '#':
            continue

        key, val = line.split('=', 1)
        key = key.strip()
        val = val.strip()

        if key in allowed_keys:
            configs[key] = val
        else:
            err('Unknown config key: {0}'.format(key))

    return configs

def parse_command_line():
    from common import err, dbg

    try:
        opts, args = getopt.getopt(sys.argv[1:], '',
                                  ['help', 'machines=', 'benchmarks=',
                                   'no-sync', 'no-db', 'sync=', 'debug'])
    except getopt.GetoptError as e:
        err('{0}'.format(str(e)))

    for opt, arg in opts:
        if opt == '--help':
            usage()
            sys.exit(1)
        elif opt == '--machines':
            configs['machines'] = arg
        elif opt == '--benchmarks':
            configs['benchmarks'] = arg
        elif opt == '--no-sync':
            configs['sync'] = 'no'
        elif opt == '--sync':
            configs['sync'] = arg
        elif opt == '--no-db':
            configs['no-db'] = 'yes'
        elif opt == '--debug':
            configs['debug'] = 'yes'
        else:
            err('Unknown switch {0}'.format(opt))

    if len(args) > 1:
        usage()
        sys.exit(1)
    elif len(args) == 1:
        configs['tool'] = args[0]

    # print debug
    for l, r in configs.items():
        dbg('{0} = {1}'.format(l, r))
