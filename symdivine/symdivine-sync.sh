#!/bin/sh

# Sync script that satt needs for running Symbiotic

sendfile()
{
	FILE="$1"
	TO="$2"
	scp -p "$FILE" "$MACHINE":"$TO"|| exit 1
}

MACHINE="$1"
REMOTE_DIR="$2"
SYMDIVINE_DIR="$3"

# create dir in the case it does not exists
ssh "$MACHINE" mkdir -p "$REMOTE_DIR/symdivine" "$REMOTE_DIR/satt/symdivine"

DIR=`dirname $0`
sendfile $SYMDIVINE_DIR/symdivine "$REMOTE_DIR"/symdivine/
sendfile $DIR/run_benchmark.py "$REMOTE_DIR"/satt/symdivine/
sendfile $DIR/lart "$REMOTE_DIR"/symdivine/
sendfile $SYMDIVINE_DIR/compile_to_bitcode.py "$REMOTE_DIR"/satt/symdivine/
#sendfile "$SYMDIVINE_DIR/libz3.so" "$REMOTE_DIR"/symdivine/

exit 0
