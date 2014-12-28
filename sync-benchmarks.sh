#!/bin/sh

# synchronize benchmarks repository
function sync_benchmarks()
{
	MACHINE="$1"
	REMOTE_DIR="$2"
	BENCHMARKS_DIR="$3"

	USER=${MACHINE%%@*}
	HOST=`hostname`
	GIT_REP="ssh://$USER@$HOSTNAME/$BENCHMARKS_DIR"

	ssh "$MACHINE"\
		"cd ${REMOTE_DIR};\
		 if cd benchmarks &>/dev/null;\
			then git pull;\
			else git clone $GIT_REP; fi"
}

MACHINE="$1"
REMOTE_DIR="$2"
BENCHMARKS_DIR="$3"

sync_benchmarks "$MACHINE" "$REMOTE_DIR" "$BENCHMARKS_DIR"

exit 0
