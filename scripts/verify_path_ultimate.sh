DIR="$1"
GRAPHML="$2"
PRPFILE="$3"
BENCHMARK="$4"
VERIFIER_RESULT="$GRAPHML.ultimate-result"

BENCHMARKDIR=`dirname "$BENCHMARK"`

test -z $UA && UA="$DIR/UltimateAutomizer/UltimateWitnessChecker.py"
UADIR=`dirname $UA`
cd $UADIR || exit 1

# Is '32bit simple' correct for all benchmarks?
python3 UltimateWitnessChecker.py \
    "$PRPFILE" \
    "$BENCHMARK" \
    32bit simple \
    "$GRAPHML" 1> "$VERIFIER_RESULT"

if [ $? -ne 0 ]; then
	echo "error"
elif grep -q 'FALSE' "$VERIFIER_RESULT"; then
	echo "confirmed"
else
	echo "unconfirmed"
fi

cat "$VERIFIER_RESULT"
rm "$VERIFIER_RESULT"
