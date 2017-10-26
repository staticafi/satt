#!/bin/sh

# synchronize benchmarks repository

exit 0

sync_benchmarks()
{
	MACHINE="$1"
	REMOTE_DIR="$2"
	BENCHMARKS_DIR="$3"
	YEAR="$4"

	GIT_REP="https://github.com/dbeyer/sv-benchmarks"

	ssh "$MACHINE"\
		"cd ${REMOTE_DIR};\
		 if cd benchmarks &>/dev/null;\
			then (git fetch origin master &&\
			      git reset --hard origin/master &&\
			      git clean -xdf &&\
			      git checkout $YEAR)&>/dev/null;\
			else git clone $GIT_REP benchmarks &&
				git checkout $YEAR;\
		 fi"

	return $?
}

MACHINE="$1"
REMOTE_DIR="$2"
BENCHMARKS_DIR="$3"
YEAR="$4"

#sync_benchmarks "$MACHINE" "$REMOTE_DIR" "$BENCHMARKS_DIR" "$YEAR" || exit 1

exit 0
