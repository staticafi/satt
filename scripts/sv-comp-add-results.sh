#!/bin/sh

# take folder with .xml files that contain results of sv-comp
# and add the results into our database

if [ "$#" != "1" ]; then
	echo "Usage: $0 dir_with_xml_files" >/dev/stderr
	exit 1
fi

DIR="$1"

for FILE in $DIR/*.xml; do
	./sv-comp-xml-parser.py "$FILE"
done
