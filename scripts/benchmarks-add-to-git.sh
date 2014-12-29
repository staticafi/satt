#!/bin/sh

if [ "$#" != "1" ]; then
	echo "Usage: $0 dir_with_set_files" >/dev/stderr
	echo "Must be run from git directory"
	exit 1
fi

#if ! git rev-parse &>/dev/null; then
#	echo "This script must be run from git directory (with benchmarks)"
#	exit 1
#fi

git_add_set()
{
	SET="$1"
	DIRP="$2"

	cat "$SET" | while read LINE; do
		# skip commented lines
		echo "$LINE" | grep -q '^\s*#' && continue

		git add "$DIRP/$LINE"
	done
}

DIR="$1"
DIRPATH=`readlink -f $DIR`

for SET in $DIR/*.set; do
	git_add_set "$SET" "$DIRPATH"
done

# User will do this, specifying his own commit message
# git commit
