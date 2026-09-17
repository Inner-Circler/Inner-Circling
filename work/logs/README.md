# work/logs/

Ships with one empty file, `circle_audit.log`, so the directory exists; git does
not track empty directories. Everything else here is written by the program as
you use it, one file per circle, named by the circle's open time (`<OT>`):

```
open_<OT>.json          the open verifier's report — whether the open left
                        behind what it should: a transcript headed with its
                        own open time, one working-set entry, and a whole
                        prompt capture covering every part. Written at the
                        end of every live open; it reports, and never stops
                        a circle. The close commits it with the circle, and
                        `circle_audit.py` reads it back.
closing_<OT>.json       the start-of-close marker, written the moment a live
                        /close begins and never deleted — a close that died
                        part-way leaves this file with no close_<OT>.json
                        beside it, which is how the next open tells the two
                        apart.
close_<OT>.json         the close verifier's report — a size and a sha256 for
                        each part that spoke. Written at every /close, before
                        dreaming runs, so it never carries a dreaming finding.
spend_<OT>.json         what the circle's own model calls cost.
delta_<OT>.json         what this one circle changed across the registers —
                        `circle_delta.py`'s memo. Written only while the
                        `circle_stats` setting is on.
dream_<OT>.json         the dreaming/synthesis run's own record.
dream_error_<OT>.json   written only when that run fails. The close names this
                        file; read it first. `rerun_safe` true: nothing was
                        written, and the printed re-run is clean. False: the
                        parts' new memory already landed — do NOT re-run; the
                        note carries the repair by hand.
command_suggest_<OT>.json
                        the commands a live close found the circle's words
                        suggesting — each line as you would type it, who
                        said it, and in which statement. Each line is also
                        staged as a proposal for your next ruling.
circle_audit.log        the audit's own log (`circle_audit.py`), appended to
                        each time you run it.
```

Nothing here reaches a part's prompt. These are records for you.
