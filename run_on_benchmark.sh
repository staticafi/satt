#!/bin/sh

# Run symbiotic on given benchmark
# This script is used by symbiotic-benchmarks

# get absolute paths to the files
SYMBIOTIC_DIR="`readlink -f $1`"
BENCHMARK="`readlink -f $2`"

# first, set environment. bens have some header files in
# weird path
export C_INCLUDE_PATH=$C_INCLUDE_PATH:$SYMBIOTIC_DIR/include:/usr/include/x86_64-linux-gnu/
export PATH=$HOME/local/bin:$PATH
export LD_LIBRARY_PATH=$HOME/local/lib64:$HOME/local/lib:$LD_LIBRARY_PATH

# use temporary directory for running
RUNDIR=`mktemp --directory --tmpdir="." symbiotic.XXXXXXXXXX`

# make runme script work in RUNDIR directory
# and write logs to this dir
export DIR="$RUNDIR"
export LOGSDIR="`readlink -f .`/logs"

clean_and_exit()
{
	# go back to the parent directory, so that
	# we can delete the temporary one
	cd ..

	rm -rf "$RUNDIR"
	exit $1
}

tmout()
{
	# the trap already printed a message
	clean_and_exit 1
}

trap tmout 14

RUNME="$SYMBIOTIC_DIR/runme"

# make copy of the benchmark, so that we don't
# mess up the benchmarks directory
cd "$RUNDIR"
cp "$BENCHMARK" .

FILE="`basename $BENCHMARK`"

# run symbiotic
RESULT="`${RUNME} ${FILE}`" || RESULT='ERROR'

# report result
echo "$RESULT"

clean_and_exit 0
