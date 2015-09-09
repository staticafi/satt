#!/bin/bash

sync_slicer()
{
	MACHINE="$1"
	REMOTE_DIR="$2"
	SLICER_DIR="$3"

	USER=${MACHINE%%@*}
	HOST=`hostname`
	GIT_REP="ssh://$USER@$HOST/$SLICER_DIR"

	ssh "$MACHINE"\
		"cd ${REMOTE_DIR};\
		 if cd symbiotic &>/dev/null;\
			then git pull &>/dev/null;\
			else git clone $GIT_REP; fi"

	return $?
}

sendfile()
{
	FILE="$1"
	rsync -r "$FILE" "$MACHINE":"$REMOTE_DIR"/satt/slicer/ || exit 1
}

MACHINE="$1"
REMOTE_DIR="$2"
SLICER_DIR="$3"

sendfile slicer/run_benchmark

sync_slicer "$MACHINE" "$REMOTE_DIR" "$SLICER_DIR" || exit 1

exit 0
