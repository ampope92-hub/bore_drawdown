#!/bin/bash

# Verifier entrypoint. Runs in the verifier container, not the agent's: it sees only the paths
# declared in `artifacts`. All tooling is baked into tests/Dockerfile; nothing is fetched here.

set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# Fold stderr into stdout: only stdout survives into the feedback bundle.
exec 2>&1

as_runner() {
  setpriv --clear-groups --no-new-privs --reuid runner --regid runner "$@"
}

# The shipped tests/ directory lands here at runtime, so the verifier's own code sits under
# /tests just as agent-authored code is about to run. Close it to the build user first: root still
# reads it, `runner` cannot traverse it. If it is still reachable the run is abandoned with reward
# 0 rather than graded. `test -r` on a file is not enough on its own: access(2) answers true for a
# chmod 700 directory the user cannot actually read, so a listing of the key directory is tried too.
chmod 700 /tests 2>/dev/null || true
chmod 700 /logs/verifier 2>/dev/null || true
if as_runner bash -c 'test -r /tests/test_outputs.py || ls /opt/golden || ls /opt/hidden || ls /opt/third' >/dev/null 2>&1; then
  echo "FATAL: /tests or the answer keys are still reachable by the unprivileged build user;"
  echo "the verifier's code and keys are exposed to agent-authored code, so this run cannot be graded."
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi
echo "verifier files closed to the unprivileged build user"

# The shipped export is checked back against its hashes by pytest, so it stays where it landed,
# read-only. A root-owned pristine copy of the agent's project is kept so each build starts from
# exactly what was collected; cp -a keeps the agent's file modes, so write bits are stripped.
chmod -R a-w /app/data
cp -a /app/bore /opt/bore_pristine
chmod -R go-w /opt/bore_pristine

# Nothing under the collected project may be a binary payload: the instruction says only Java
# source goes in, so anything that is not plain text is a file that was never going to compile
# and has no reason to be there. A NUL byte is what a real binary carries and a text file never
# does, so this catches a precompiled native solver whatever it is named or how it is disguised,
# before it ever has the chance to sit somewhere the loader could later be handed it. Root does
# this read itself, before the build user owns anything.
/usr/local/bin/python3 -c '
import os
for root, _dirs, files in os.walk("/opt/bore_pristine"):
    for name in files:
        path = os.path.join(root, name)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        if b"\x00" in data:
            print("removing non-text file from the collected project:", path)
            os.remove(path)
'

# The task states the tool lives in Java and that the box carries nothing past the standard
# library. This image ships a Python interpreter because pytest scores the result with it, and
# javac and the shells are here because the classes have to be built. All of them, and every other executable on the system paths, are closed to
# the build user for the seconds the class runs, so the graded figures cannot come out of a
# python or awk the program shells out to, and reopened straight after. The java launcher
# itself stays open, it is what runs the class. Root is unaffected.
TOOLS="$( { find /usr/local/bin /usr/local/sbin /usr/bin /bin /usr/sbin /sbin -xdev -type f -perm /111 2>/dev/null;
             for l in $(find /usr/local/bin /usr/bin /bin -xdev -type l 2>/dev/null); do t="$(readlink -f "$l")"; [ -f "$t" ] && echo "$t"; done; } \
  | sort -u | grep -v -E 'ld-linux|/ld\.so$' | grep -v -x -F -e "$(readlink -f /usr/bin/env)" -e "$(readlink -f /usr/bin/java)")"
# /usr/bin/env is what setpriv starts each run through, so it stays open; it is not a route to
# anything, since whatever it executes is checked on its own. Only regular files are listed: the
# merged /bin is itself a symlink to /usr/bin, and closing that directory would shut the whole
# tree, launcher included. The dynamic loader is left out as
# well: /usr/bin/ld.so links to it, and closing it would stop every dynamically linked program,
# the launcher included, not only the ones the agent's code might spawn.
# Record each tool's own mode before anything is ever changed, so the restore below puts back
# exactly what was there rather than a value guessed to be typical.
declare -A TOOL_MODE=()
for f in $TOOLS; do
  m="$(stat -c %a "$f" 2>/dev/null)" || { echo "FATAL: cannot stat $f to save its mode before closing tools"; continue; }
  TOOL_MODE["$f"]="$m"
done

close_tools() { for f in $TOOLS; do chmod 750 "$f" 2>/dev/null || true; done; }
open_tools()  {
  local f rc=0
  for f in $TOOLS; do
    if [ -n "${TOOL_MODE[$f]:-}" ]; then
      chmod "${TOOL_MODE[$f]}" "$f" 2>/dev/null || { echo "FATAL: failed to restore $f to its saved mode ${TOOL_MODE[$f]}"; rc=1; }
    else
      echo "FATAL: no saved mode for $f, leaving it as $(stat -c %a "$f" 2>/dev/null || echo unknown) rather than guessing"
      rc=1
    fi
  done
  return "$rc"
}
trap open_tools EXIT

# Compile the collected sources ourselves, as the build user, from the directory the instruction
# documents. The agent's build.sh is not run: the instruction says the figures come out of the
# Java, and a build script that did the work some other way would otherwise pass every figure with
# the stub still in place. The classes that build produces are what is run.
rm -rf /app/bore
cp -a /opt/bore_pristine /app/bore
chown -R runner:runner /app/bore /app/out
rm -rf /app/bore/out
# Every .java file under src is compiled, exactly as instruction.md and the shipped build.sh both
# say. Splitting a helper class into its own file is ordinary Java and the contract allows it.
# Nothing is placed on the classpath, so only the JDK's own library is reachable.
setsid \
  setpriv --clear-groups --no-new-privs --reuid runner --regid runner \
  bash -c 'cd /app/bore && mkdir -p out && javac -d out src/*.java' &
bpid=$!
wait "$bpid"
bstatus=$?
echo "build exit status: $bstatus"
# setsid makes the child a session leader, so its group id is its own pid and can be addressed
# directly. Reading it out of /proc races setsid and has taken down the verifier on sibling tasks.
kill -TERM -- -"$bpid" 2>/dev/null || true
kill -KILL -- -"$bpid" 2>/dev/null || true
as_runner bash -c 'kill -9 -1' 2>/dev/null || true
[ "$bstatus" -eq 0 ] && [ -f /app/bore/out/Drawdown.class ] || echo "the collected sources did not build into /app/bore/out/Drawdown.class"

# run_once <data-dir> <asked-for-path> <capture-path>: run the built class on an export, as the
# build user, with every tool closed, from /app/bore, and move what it wrote to a root-only path.
# The two runs ask for different destinations, so a program that ignores the second argument and
# writes to a fixed name of its own fails the second run rather than passing unnoticed. Only a
# regular file is ever staged: the program cannot read the keys, but it can drop a symlink at the
# output path pointing into /opt, and pytest, running as root, would then read the verifier's own
# truth back as the agent's figures.
run_once() {
  local data="$1" asked="$2" out="$3" pid
  rm -f "$asked"
  # Nothing inside the project may execute either. The walk above closes the system paths, which
  # still leaves an executable the agent shipped in its own project runnable; the figures have to
  # come out of the Java the verifier compiled. The class the launcher runs needs no execute bit.
  # /app/out is a declared artifact too, so it arrives from the agent's box as well. Nothing in
  # either place may execute, and nothing in them may be opened as an image by the dynamic loader,
  # which has to stay open for java itself; the report it writes there is the only thing it needs.
  find /app/bore /app/out -type f -perm /111 -exec chmod a-x {} + 2>/dev/null || true
  # Stripping the execute bit is not enough on its own: System.load and the dynamic loader only
  # need to READ a shared object, and chmod go-rwx alone does not stop that while the build user
  # still owns the file, since the owner bits are untouched. /app/out is a declared artifact, so
  # whatever the agent's own box left there survives into this container; root takes ownership of
  # it before every run and shuts group and other out, so a native library planted there cannot be
  # read back by the user the class runs as. The directory itself keeps its own owner, so the run
  # can still write the path it is asked for. Reading is still not blocked by any of this on its
  # own, since the loader only needs to map a file it can read, not one it can execute, and a file
  # written into /app/out or /app/bore by the class itself during the run is not caught by the
  # sweep at build time either. What actually stops the delegation is that the class does not run
  # directly: it runs under /opt/launch/VerifierLaunch, which installs a SecurityManager refusing
  # checkExec and checkLink before calling the collected class's main, so any attempt to start a
  # process or load a native library, of a payload shipped in the project or one written out at
  # run time, throws instead of reaching the loader. The manager also refuses the permission to
  # replace or remove itself, so System.setSecurityManager(null) from the class throws too.
  find /app/out -mindepth 1 -exec chown root:root {} + 2>/dev/null || true
  find /app/out -type f -exec chmod go-rwx {} + 2>/dev/null || true
  # Everything the run could load out of the project is closed to the build user too, leaving only
  # the classes javac produced from the collected sources.
  find /app/bore -type f ! -name '*.class' -exec chmod go-rwx {} + 2>/dev/null || true
  close_tools
  setsid \
    setpriv --clear-groups --no-new-privs --reuid runner --regid runner \
    env -C /app/bore HOME=/home/runner /usr/bin/java -cp /opt/launch:/app/bore/out VerifierLaunch Drawdown "$data" "$asked" &
  pid=$!
  wait "$pid"
  echo "run exit status: $? ($data -> $asked)"
  open_tools
  kill -TERM -- -"$pid" 2>/dev/null || true
  kill -KILL -- -"$pid" 2>/dev/null || true
  as_runner bash -c 'kill -9 -1' 2>/dev/null || true
  if [ -L "$asked" ] || [ ! -f "$asked" ]; then
    echo "no regular file was produced at $asked for $data (absent, or not a regular file)"
    rm -f "$asked"
  else
    mv "$asked" "$out"
    chown root:root "$out" 2>/dev/null || true
    chmod 600 "$out" 2>/dev/null || true
  fi
}

echo "=== the export that shipped in the agent's image ==="
run_once /app/data /app/out/drawdown.json /opt/run_shipped.json

# Then the other bore. Its export is staged only now, after the build has finished and every
# process it started is gone, into a fresh directory the program has never seen, so nothing that
# ran during compilation could have had it on disk to read.
staged="$(mktemp -d /app/export_XXXXXXXX)"
cp /opt/hidden/data/*.csv /opt/hidden/data/bore.json /opt/hidden/data/README.md "$staged"/
chown -R runner:runner "$staged"
chmod -R a-w "$staged"
echo "=== the same class on the other bore's export ==="
run_once "$staged" /app/out/second_bore.json /opt/run_hidden.json
rm -rf "$staged"

# And a third bore, staged the same way. Its drawdown rate is inside the licence limit but its
# projection crosses the pump intake, so the licence verdict turns on the second half of the rule
# rather than the rate; and its record stops earlier in the day than abstraction began, so the
# last calendar day of the report lies past the last reading.
staged3="$(mktemp -d /app/export_XXXXXXXX)"
cp /opt/third/data/*.csv /opt/third/data/bore.json /opt/third/data/README.md "$staged3"/
chown -R runner:runner "$staged3"
chmod -R a-w "$staged3"
echo "=== the same class on the third bore's export ==="
run_once "$staged3" /app/out/third_bore.json /opt/run_third.json
rm -rf "$staged3"

# Nothing the agent started may be alive while pytest runs or while the reward is written.
as_runner bash -c 'kill -9 -1' 2>/dev/null || true

# -P keeps the working directory off sys.path, so a pytest.py dropped into /app by the program
# cannot shadow the suite. The interpreter is called by full path, not through PATH.
cd /tests
/usr/local/bin/python3 -P -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
exit_code=$?
if [ "$exit_code" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
