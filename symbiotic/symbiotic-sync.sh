#!/bin/sh

# Sync script that satt needs for running Symbiotic

sync_symbiotic()
{
	MACHINE="$1"
	REMOTE_DIR="$2"
	SYMBIOTIC_DIR="$3"

	USER=${MACHINE%%@*}
	HOST=`hostname`
	GIT_REP="ssh://$USER@$HOST/$SYMBIOTIC_DIR"

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
	rsync -r "$FILE" "$MACHINE":"$REMOTE_DIR"/satt/symbiotic/ || exit 1
}

MACHINE="$1"
REMOTE_DIR="$2"
SYMBIOTIC_DIR="$3"

sendfile symbiotic/run_benchmark

sync_symbiotic "$MACHINE" "$REMOTE_DIR" "$SYMBIOTIC_DIR" || exit 1

exit 0
