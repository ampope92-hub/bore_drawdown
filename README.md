# Bore Drawdown: Licence Compliance from an Aliased Tidal Record in Java

A water utility owes a compliance return for monitoring bore PB-07. The agent gets the bore's level export (`levels.csv`), a 10-minute commissioning dump, licence settings in `bore.json`, and a README. It has to write a Java program (standard library only, offline) that outputs a JSON report with five fields: the mean depth to water for every day of the abstraction period, the projected depth on the day the licence names, the drawdown rate in mm/day, the bore's tidal period in hours, and whether the bore is within its licence (drawdown rate under the limit, projected depth above the pump intake). The same class is then run unchanged on exports from other bores.

## What makes it hard

- **Tidal aliasing.** The compliance logger reads every 12 hours, but the bore "breathes" with a 12.42-hour tide. Sampled at that interval, the tide folds into a slow swing of about 14.8 days and roughly a fifth of a metre that looks like a real trend. The fix is to measure the period from the commissioning dump and fit the sinusoid at the actual reading timestamps. A swing fitted at a period read by eye (14 or 15 days), or no swing at all, does not recover the level.
- **The site's own method is wrong.** The README says the last return used a straight line through the abstraction readings. On the shipped bore that is 85 mm out on the worst day (51 mm on another bore) against a 30 mm bar, and it calls the shipped bore a breach when the licence check found it compliant. A fit that carries the tide at the reading times stays within 9 mm of every daily mean.
- **Daily means must keep the tide in.** The tidal period does not divide 24 hours, so a whole day of tide leaves a residue. On the third bore (tidal amplitude about a metre) a tide-free trend is 40 mm out against the 30 mm bar.
- **Measuring point move.** Partway through each record the measuring point moved above the casing top (0.07 m, 0.05 m and 0.11 m on the three bores), and the export is not corrected for it. Using the readings as written puts the projected depth 0.43 / 0.36 / 0.86 m out against a 0.10 m bar, and gets the shipped verdict wrong.
- **Nothing can be hardcoded.** The three bores have different periods (12.42, 11.83 and 12.90 h), logger intervals, licence limits (9.8, 2.4 and 6.0 mm/day), intake depths and verdicts. Each half of the licence test is exercised by a bore that fails on that clause alone.

The implementation itself is small: a CSV reader, a period grid search, a 4x4 least squares, and a JSON line.

## How it's graded

The verifier runs in a separate, offline container. It compiles `src/*.java` itself as an unprivileged user (the build script is not run), then runs the class on three exports: the shipped bore and two held-back bores. The key for each bore is the daily means recorded by the licence check's own 10-minute logger. Per bore, the report must:

- have exactly the five keys, and one finite entry per day of the abstraction period
- have every daily level within 0.03 m of that day's mean
- have the projected depth within 0.10 m of the licence-day mean
- have a drawdown rate within the drift the depth bars allow over `projection_day`
- have a tidal period within 0.15 h of the one carried by the commissioning dump
- give the same verdict as the check

The shipped data files must also be unaltered (sha256).

Anti-cheat: anything under `src` that is not plain text is deleted before compiling. During the run, every system executable except `java` is closed and files in the project have their execute bits stripped. The class runs under a verifier-built launcher (`tests/VerifierLaunch.java`) with a SecurityManager that refuses process execution, native library loading, and attempts to remove the manager. Each run writes to a different output path. Keys are root-only, `/tests` is closed to the build user, and pytest runs with `-P`. Eight arms are documented in `task.toml` as scoring 0 through the real verifier, including the straight line, the trend-only report, the uncorrected readings, frozen results, a native-binary delegate, and a Python shim.

## Repository layout

- `instruction.md` - the task prompt given to the agent
- `task.toml` - metadata, limits, and the difficulty, solution and verification write-ups
- `environment/` - agent container: `Dockerfile`, `data/` (bore.json, levels.csv, commissioning dump, README), `bore/` (stub `Drawdown.java` and `build.sh`)
- `solution/` - `solve.sh`, reference `Drawdown.java`, `gen_bore.py` (regenerates all three exports and keys), `calibrate.py` (reproduces the route comparisons)
- `tests/` - verifier `Dockerfile`, `test.sh`, `test_outputs.py`, `VerifierLaunch.java`, and keys/data for the shipped (`golden/`), second (`hidden/`) and third (`third/`) bores

## Running it

Requires Docker and Harbor (`uv tool install harbor` or `pip install harbor`). From the repo root:

```
harbor run -p . -a oracle
```

runs the reference solution through the verifier (should score reward 1). To try an agent:

```
harbor run -p . -a <agent> -m <model>
```

for example `-a claude-code`.

---

Task design, data generators, reference solution and verifier by Audrey Pope.
