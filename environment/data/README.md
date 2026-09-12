# PB-07 water level export

PB-07 is the compliance monitoring bore for the pumping station, about 300 m from the estuary
shoreline. Every figure is depth to water in metres, positive downward, so a deeper water table
is a larger number. The licence, the pump intake depth and the regulator's own record are all
depth below the top of the casing.

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

The compliance logger. `timestamp` is local standard time, `depth_m` to the millimetre. The
logger went to a 12 hour interval at the June battery change to get through the season, having run
at 10 minutes before that. That was well before this record opens, so the whole of this file is at
the one interval. Other bores are on their own intervals.

The well head was rebuilt on 12 August, in the middle of this record. Until then the logger hung
from the casing top. From the rebuild on it hangs from the new cover plate, 0.07 m above the casing
top, and the export is written as the logger measures it, so every reading from 2025-08-12T09:00 on,
a stamp that falls between the morning and evening readings, is 0.07 m deeper than the depth below
the casing top at that moment. Nothing in this file has been corrected for it. bore.json carries the
stamp and the offset as `measuring_point_moved_at` and `measuring_point_offset_m`.

## commissioning_10min.csv

Three days from the commissioning check run in the week before this record opens, at the 10 minute
interval, before the bore was put to work. This is the contractor's dump and is included for reference.
The contractor's check meter was set against its own reference peg for that run, not against the
casing top the compliance logger uses once it goes into service, so every reading in this file sits
about 0.04 m shallower than the same moment would read on the compliance logger. The two files are on
their own datums.

## bore.json

The licence settings for this abstraction period, and where the readings are taken from.

| key | meaning |
|---|---|
| `bore` | the bore |
| `abstraction_start` | when the pump went to continuous duty |
| `licence_limit_mm_per_day` | the maximum drawdown rate the licence allows, averaged over the abstraction period |
| `pump_intake_depth_m` | depth of the pump intake below the casing top |
| `projection_day` | the day of abstraction for which the licence asks the projected depth to water, counted as days elapsed from `abstraction_start`, so 90 means 90 days after abstraction began |
| `measuring_point_moved_at` | when the point the readings are taken from moved off the casing top, a stamp that falls between two readings |
| `measuring_point_offset_m` | how far above the casing top that point sits from the stamp on, so every reading from then on is that much deeper than the depth below the casing top at the same moment |

## How the last return was done

For the March period the drawdown rate was reported as the slope of a straight line through the
logger readings taken during abstraction, 5.1 mm/day, with no tidal term, and the projected depth
was that line carried forward. The regulator accepted the return.
