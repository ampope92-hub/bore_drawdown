#!/usr/bin/env bash
set -euo pipefail

# Reference drawdown tool.
#
# The compliance logger reads the bore every twelve hours and the tide comes round every
# twelve hours and twenty-five minutes, so each reading lands a little later in the tidal
# cycle than the one before and the logger records the tide as a slow swing of about
# fifteen days. Over an abstraction period of a couple of weeks that swing passes for a
# trend, and a line through the readings gets the drawdown badly wrong in whichever
# direction the tide happened to be going. The tool measures the tidal period on the
# commissioning dump, fits the tide at the actual reading times alongside the trend, and
# reports the trend that is left. That is the drawdown.
#
# The implementation is solution/Drawdown.java, next to this script.
install -m 644 "$(dirname "$0")/Drawdown.java" /app/bore/src/Drawdown.java

mkdir -p /app/bore/out
javac -d /app/bore/out /app/bore/src/Drawdown.java
mkdir -p /app/out
java -cp /app/bore/out Drawdown /app/data /app/out/drawdown.json
