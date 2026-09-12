#!/usr/bin/env bash
# Compile the drawdown tool. Run it as: java -cp /app/bore/out Drawdown <data-dir> <output-json>
set -euo pipefail
cd /app/bore
mkdir -p out
javac -d out src/*.java
