#!/bin/bash

if [ $# -ne 2 ]; then
	echo "Usage: $0 file.set category_id"
	exit 1
fi

WORKING_DIR="`dirname $1`"
cd $WORKING_DIR

S="`basename $1`"
CATEGORY_ID="$2"

for BENCH in `cat $S`; do
	NAME=`basename $BENCH`
	DIR=`dirname $BENCH`

	if echo $NAME | grep -q 'true.*false'; then
		CORRECT_RESULT='true'
	elif echo $NAME | grep -q 'false.*true'; then
		CORRECT_RESULT='false'
	elif echo $NAME | grep -q 'true'; then
		CORRECT_RESULT='true'
	elif echo $NAME | grep -q 'false'; then
		CORRECT_RESULT='false'
	else
		echo 'No correct result'
		exit 1
	fi

	echo "INSERT INTO tasks (name, category_id, correct_result) VALUES ('$DIR/$NAME', '$CATEGORY_ID', '$CORRECT_RESULT');"
done
