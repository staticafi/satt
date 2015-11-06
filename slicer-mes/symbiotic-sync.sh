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
}

MACHINE="$1"
REMOTE_DIR="$2"
SYMBIOTIC_DIR="$3"

ssh "$MACHINE" mkdir -p "$REMOTE_DIR/satt/slicer-mes"
scp slicer-mes/run_slicer "$MACHINE":"$REMOTE_DIR"/satt/slicer-mes/run_slicer || exit 1
sync_symbiotic "$MACHINE" "$REMOTE_DIR" "$SYMBIOTIC_DIR" || exit 1

exit 0
