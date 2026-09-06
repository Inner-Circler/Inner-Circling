# self/

**Self's own registers.** Some are written by synthesis, some by you.

**Everything here is a DELEGATE — the live shape, none of the content.** Ruled
2026-08-18: every `self/` register the code depends on ships as an empty
template, never seeded. `packaging/sanitize.py`'s 2026-08-09 run found heavy
owner-name and part-name content throughout the live `self/`, and nothing there
is generic enough to ship. What is worth shipping is the shape.

```
best_practices.toml      how the CIRCLE behaves, and
                         (R133) how YOU move
self.md                  who Self is for this
                         installation
topics.toml              synthesis's unvetted BLOCK 2
                         topics
remember.toml            Self's own reflexive record
circle_history.toml      one durable entry per circle
circle_journal.toml      the circle's own evolving
                         identity, folded into Block 1
                         every close (added 2026-09-04,
                         B94)
proposals.toml           the PROPOSE-class register --
                         what parts proposed and Self
                         ruled on (added 2026-08-23,
                         R315)
working_sets.toml        which issue nodes each circle
                         was shown
self_observation_log.toml  what synthesis
                         noticed about the room, one
                         record per circle
coalesce.toml            the proposal coalesce register --
                         groups of pending proposals that
                         are one ask in different words
                         (added 2026-08-26, R356/B69)
redaction.toml           your curated redaction targets for
                         the CIRCLE pane's redacted view
                         (added 2026-08-31)
groups.toml              your named rosters of parts, so
                         `--group <name>` can invoke a whole
                         circle by name (added 2026-09-03)
settings.toml            what you change when the code would
                         otherwise decide -- a cap, a budget,
                         a mode. Not shipped: it appears the
                         first time you change one
                         (/settings-update); absent means
                         every setting is at its default
```

**Each empty register is the document its reader builds anyway.** `topic_manager.py`,
`circle_history_manager.py`, `circle_journal_manager.py`, `remember_manager.py`,
`self_observation_manager.py`, `proposal_group_manager.py`,
`redaction_manager.py` and `group_manager.py` each construct their own empty shape — `next_id = 1` (or,
for `redaction_manager.py`, four separate `next_*` counters) plus an empty table —
when their file is absent, and these delegates are byte-equivalent to that.
So a fresh install reads the same document whether it received the delegate or no
file at all — the delegate exists so the file is *there*, valid and loadable,
rather than conjured on first write.

`self.md` is the one exception: it is prose, so it ships hand-genericized rather
than empty — the two sections synthesis expects, with a note in each saying what
belongs there.

**`best_practices.toml` lives here, not in `coordinator/`.** It moved to
`coordinator/` on 2026-08-11 (best practices are circle-scoped) and back on
2026-08-16 by ruling — user-owned content lives with the user-owned record. Its
delegate followed on 2026-08-18; it had been sitting under
`packaging/scaffold/coordinator/` describing the reversed layout for two days.

**This directory arrives nearly empty.** The registers start empty and fill as
you rule things into them.

---

**There is no `circle_briefing.md` delegate, and there should not be one.**
`self/circle_briefing.md` was retired 2026-08-11: `group_attention.circle_briefing_build()` now reads
`issues/issue_model.md`, the live graph and `self/best_practices.toml` directly
at every circle open, and the `split_briefing()` that routed the old document by
heading is gone from the code entirely. A delegate lingered here until
2026-08-18, correctly labelled vestigial, standing in for a file the live tree no
longer has. Removed — a stand-in for nothing is a thing to explain, not a thing
to ship.

---

**`self_observation_log` is `.toml` since 2026-08-19** (R256). It
was the last `.md`-as-datastore on a live write path in the shipped product:
`inter_circle.py` appends to it at every `/close`, so it moved to the register
shape the rest of this directory already uses. `self.md` deliberately did not —
synthesis reads it back as prompt input and replaces it whole, which is a
document, not a register.

**There is no `issues_narrative.md` delegate any more.** Dropped 2026-08-25,
on the same rule as the two below. The live `self/issues_narrative.md` was
retired 2026-08-14 once its entries were migrated into the issue graph, and
`issue_projection.narrative()` — the only thing that ever opened it — was
deleted at B46, 2026-08-17. The delegate outlived its reader by eight days,
and shipped a header that told every new user `build_briefing()` concatenates
the file into BLOCK 2 at each circle open. It had not since B46. Worse, that
sentence was *written into it* on 2026-08-18, a day after the code went: the
edit corrected an older stale reference and replaced it with a fresher one.

Nothing in `packaging/` ever named this file. `scan.py::resolve()` could not
reach it either — resolution is driven by the paths live code depends on, and
no live code depended on it — so it shipped purely as a passenger of
`_clone_scaffold()`'s wholesale copy, unexamined by the register that is
supposed to justify every shipped path.

**There is no `leads.md` delegate any more.** Dropped 2026-08-19
(R257), for the same reason `circle_briefing.md`'s went:
nothing in the shipped code opens it. `self/leads.md`'s only writer was
`transcript_store.py`'s `marks_file` handling, removed 2026-08-14 with MARK's
wholesale retirement, and the file has been frozen since. The operator's own
`self/leads.md` is untouched — it is real history. A seed file for a store
nothing will ever write promises a mechanism the recipient does not have.

**There is no `marks/<OT>.toml` any more either — MARK was RETIRED WHOLESALE
2026-08-14, code included.** This document's own register table named it as a
live register (*"your ratifications, written at close"*) for weeks past that
date, even after the `leads.md` paragraph above already cited the same
retirement as the reason `leads.md`'s writer disappeared. `self/marks/` is not
a directory the shipped code creates or reads at all; the old records are in
git, at their own paths, for anyone who held them before the retirement.
