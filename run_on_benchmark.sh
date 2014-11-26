#!/bin/sh

# Run symbiotic on given benchmark
# This script is used by symbiotic-benchmarks

# send to the runner versions of used libraries
echo "### VERSIONS"


# get absolute paths to the files
SYMBIOTIC_DIR="`readlink -f $1`"
BENCHMARK="`readlink -f $2`"

# use temporary directory for running
RUNDIR=`mktemp --directory --tmpdir="." symbiotic.XXXXXXXXXX`

# make runme script work in RUNDIR directory
# and write logs to this dir
export DIR="$RUNDIR"
export LOGSDIR="`readlink -f .`/logs"

clean_and_exit()
{
	rm -rf "$RUNDIR"
	exit $1
}

RUNME="$SYMBIOTIC_DIR/runme"

# make copy of the benchmark, so that we don't
# mess up the benchmarks directory
cd "$RUNDIR"
cp "$BENCHMARK" .

FILE="`basename $BENCHMARK`"

# run symbiotic
echo "### START"
RESULT="`${RUNME} ${FILE}`" || RESULT='ERROR'

# report result
echo "### RESULT"
echo "$RESULT"

# go back to the parent directory, so that
# we can delete the temporary one
cd ..

clean_and_exit 0
