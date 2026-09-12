# MW-22 water level export

MW-22 sits on the eastern arm of the same wellfield, cut into the bank of the tidal creek itself
and screened in the confined sand beneath the estuary clay. The confining layer passes the tide
straight through, so this bore breathes with the creek far harder than any of the others. Every figure is depth to water below the top of the casing, in metres, positive
downward, so a deeper water table is a larger number.

## What the readings carry

Two things move the level in this bore, and every reading carries both of them together.

The first is the water table the licence is about. It sits flat while the bore is not abstracting.
Once abstraction starts it falls at a steady rate, and it goes on falling at that rate for as long
as the abstraction continues, so the level on any day of the abstraction is that steady fall
carried forward from the start of it.

The second is the tide. The bore is close enough to the estuary to breathe with it, so every
reading also carries a sinusoid at the period this bore breathes at, with an amplitude and a
phase of its own at this bore. These are all estuary bores on a semidiurnal tide, so that period
is somewhere between 10 and 15 hours, near enough twice a day. That cycle is why the commissioning run below was logged every ten
minutes, before the pump went to work. A logger that reads less often than twice per tidal cycle
does not see the tide as a tide; it sees the same term, but sampled where each reading happens to
land in the cycle, which comes out as a slow swing across the record. The term is the same
sinusoid either way, evaluated at the reading times.

## levels.csv

The compliance record. `timestamp` is local standard time, `depth_m` to the millimetre. The logger on this
bore records twice a day through the abstraction period, and it was started on the afternoon shift,
so the record runs from an evening reading and stops on a morning one.

## commissioning_10min.csv

Three days from the commissioning check run in the week before this record opens, at the 10 minute
interval, before the bore was put to work. This is the contractor's dump and is included for reference.
The contractor's check meter was set against its own reference peg for that run, not against the
casing top the compliance logger uses once it goes into service, so every reading in this file sits
about 0.04 m shallower than the same moment would read on the compliance logger. The two files are on
their own datums.

## bore.json

The licence settings for this abstraction period.

| key | meaning |
|---|---|
| `bore` | the bore |
| `abstraction_start` | when the pump went to continuous duty |
| `licence_limit_mm_per_day` | the maximum drawdown rate the licence allows, averaged over the abstraction period |
| `pump_intake_depth_m` | depth of the pump intake below the casing top |
| `projection_day` | the day of abstraction for which the licence asks the projected depth to water, counted as days elapsed from `abstraction_start`, so 90 means 90 days after abstraction began |

## How the last return was done

For the previous period the drawdown rate was reported as the slope of a straight line through
the readings taken during abstraction, 2.9 mm/day, with no tidal term, and the projected depth was
that line carried forward. The regulator accepted the return.
