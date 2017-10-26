#!/bin/sh

# Sync script that satt needs for running Symbiotic

sendfile()
{
	FILE="$1"
	rsync -r "$FILE" "$MACHINE":"$REMOTE_DIR"/satt/symbiotic/ || exit 1
}

MACHINE="$1"
REMOTE_DIR="$2"
SYMBIOTIC_DIR="$3"

sendfile symbiotic/run_benchmark
exit 0
