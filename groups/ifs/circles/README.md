# circles/

**Written by the coordinator. Never by hand.**

One file per circle, `circle_<OT>.md`, where `<OT>` is the open time
`YYYY-MM-DD_HHMM`. It is the literal transcript: every statement, in the
order it was made, tagged with who made it.

```
[Soul]: ...
[Child] [To: Soul]: ...
[Self]: ...
```

`[Self]` is you, and the tag is fixed: every transcript writes `[Self]:`
for what you say, always. The display name you are asked for at first run
is for the console only — the `Self>` prompt, `/help` — and never reaches a
transcript or a model (`coordinator/docs/identity.md`). The code compares
on an internal id that never changes.

**No transcripts ship.** A system that has not held a circle has none, and
one that has held none is not broken. The coordinator creates what it needs
on first write.

**Four registers live here too, and they are not transcripts.** Each holds
one row per circle rather than one file per circle, which is why they sit
beside the transcripts rather than under `self/`:

```
circle_history.toml          one durable entry per circle, written at close
circle_journal.toml          the running entry every part reads at the top
                             of its prompt, revised each circle
circle_observation_log.toml  what the closing pass noticed about the CIRCLE
                             as a working body — addressed to you, about the
                             room, never about you
working_sets.toml            which issues each circle was shown
```

All four ship EMPTY, and each is the same document its own reader builds
when the file is absent — shipping them changes nothing except that you can
read the shape before there is anything in it. Written by the coordinator,
never by hand, exactly like the transcripts.

**A fifth file appears here only if you rule on the issue graph from inside
a circle.** `commands_<OT>.toml` records the `/issue-...` rulings one circle
made, beside the transcript that occasioned them. In the two-pane interface
they are typed in the command pane, and all but one are developer verbs:
`/issue-evidence-add`, which attaches a statement to an issue as evidence,
runs there without `--dev`, so any circle may produce one.
`coordinator/circle.py` run on its own runs every verb at its `Self>`
prompt, `--dev` or not.

**The transcript is the record.** Everything downstream — each part's
short_term, the close report, the safety net that backfills a lost
short_term — is derived from it. Do not edit these files. If a circle
went wrong, that is what the record should say.
