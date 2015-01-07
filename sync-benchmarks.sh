#!/bin/sh

# synchronize benchmarks repository
sync_benchmarks()
{
	MACHINE="$1"
	REMOTE_DIR="$2"
	BENCHMARKS_DIR="$3"

	USER=${MACHINE%%@*}
	HOST=`hostname`
	GIT_REP="ssh://$USER@$HOST/$BENCHMARKS_DIR"

	ssh "$MACHINE"\
		"cd ${REMOTE_DIR};\
		 if cd benchmarks &>/dev/null;\
			then git pull &>/dev/null;\
			else git clone $GIT_REP; fi"

	return $?
}

MACHINE="$1"
REMOTE_DIR="$2"
BENCHMARKS_DIR="$3"

sync_benchmarks "$MACHINE" "$REMOTE_DIR" "$BENCHMARKS_DIR" || exit 1

exit 0
