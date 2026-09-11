# self/

**Self's own registers.** Some are written by synthesis, some by you.

**Everything here is a DELEGATE — the live shape, none of the content.** Ruled
2026-08-18: every `self/` register the code depends on ships as an empty
template, never seeded. The project's own packaging tools — which are not in
this bundle — found heavy owner-name and part-name content throughout the
author's live `self/` in 2026-08-09, and nothing there is generic enough to
ship. What is worth shipping is the shape.

```
best_practices.toml      how the CIRCLE behaves, and
                         (R133) how YOU move
self.md                  who Self is for this
                         installation
topics.toml              synthesis's unvetted BLOCK 2
                         topics
remember.toml            Self's own reflexive record
proposals.toml           the PROPOSE-class register --
                         what parts proposed and Self
                         ruled on (added 2026-08-23,
                         R315)
coalesce.toml            the proposal coalesce register --
                         groups of pending proposals that
                         are one ask in different words
                         (added 2026-08-26, R356/B69)
redaction.toml           your curated redaction targets for
                         the CIRCLE pane's redacted view
                         (added 2026-08-31)
(FOUR REGISTERS ARE NOT HERE, and were until
 2026-09-07: circle_history.toml,
 circle_journal.toml, circle_observation_log.toml
 and working_sets.toml moved to `../circles/`,
 beside the transcripts. Each holds one row per
 CIRCLE rather than one about Self, which is what
 the move sorted on; `../circles/README.md`
 describes all four. They ship empty there.)

(groups.toml is NOT here, and no longer exists
 anywhere: it left every group's self/ on
 2026-09-07 (R467) and was RETIRED the same day
 (R468, B120). A group now describes itself —
 `../group.toml`, beside this self/ folder, and
 its presence is what makes the folder a group.
 That is where a group's roles, its reserved
 roles and its rulebook layer live. Which groups
 a bundle carries is packaging/groups.toml, on
 the publishing side.)
settings.toml            what you change when the code would
                         otherwise decide -- a cap, a budget,
                         a mode. Not shipped: it appears the
                         first time you change one
                         (/settings-update); absent means
                         every setting is at its default
instruments.toml         what a published, scored
                         psychological instrument measured
                         about you, read by
                         instrument_manager.py into ONE
                         part's Block 3 -- the part the
                         register itself names. Optional by
                         design and never shipped: absent
                         means that block is simply empty
dreams.toml              Self's own dream corpus and the
                         standing summary derived over it
                         (dream_history_manager.py, run by
                         hand: --bootstrap, --fold). Never
                         shipped -- one person's dreams --
                         and nothing at /close reads it. Absent
                         reads as an empty corpus; the file
                         appears when a derivation first
                         writes it
redaction_map.toml       the redacted view's reverse map:
                         each email, web address, phone
                         number or handle it has hidden,
                         beside the token shown in its place
                         (redaction_manager.py). Never
                         shipped: it appears the first time
                         the view hides one. It holds the
                         REAL text -- keep it as private as
                         your transcripts
```

**Each empty register is the document its reader builds anyway.** `topic_manager.py`,
`proposal_manager.py` and `redaction_manager.py` each construct their own
empty shape when their file is absent — a `next_id = 1` counter (four `next_*` counters for
`redaction_manager.py`) plus an empty table — and each
delegate here loads to that same document, allowing only a longer `[doc]` preamble ("SHIPPED
EMPTY ..." prose appended to the builder's own text). Three exceptions, named so nobody "fixes"
them: `remember_manager.py` builds only `remember = []` when the file is absent — no register
name, no counter — while its delegate carries both, which its reader neither needs nor minds;
and `best_practices.toml` and `coalesce.toml` each carry a preamble their builders
(`practice_manager.py`, `proposal_group_manager.py`) do not construct. In the project's own
tree a probe holds every delegate to exactly this rule at every commit
(`coordinator/tests/test_scaffold_delegates.py`, B109); the suites do not ship, so nothing in
this copy re-checks it. The delegates are not byte-for-byte what the code would write — some carry a header
comment — they are equivalent in what a fresh install *reads*. The delegate exists so the file
is *there*, valid and loadable, rather than conjured on first write.

The same rule and the same probe cover the four delegates in `../circles/`
(`circle_history_manager.py`, `circle_journal_manager.py`,
`circle_observation_manager.py`, `working_set_manager.py`) — they are not listed
above only because their registers are not Self's.

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
`groups/ifs/issues/issue_model.md` and the live graph directly
at every circle open, and the `split_briefing()` that routed the old document by
heading is gone from the code entirely. A delegate lingered here until
2026-08-18, correctly labelled vestigial, standing in for a file the live tree no
longer has. Removed — a stand-in for nothing is a thing to explain, not a thing
to ship.

---

**`circle_observation_log` is `.toml` since 2026-08-19** (R256). It
was the last `.md`-as-datastore on a live write path in the shipped product:
`inter_circle.py` appends to it at every `/close`, so it took the register
shape this directory uses. It has since moved out to `../circles/`, with the
other three one-per-circle registers. `self.md` deliberately did not —
synthesis reads it back as prompt input and replaces it whole, which is a
document, not a register.

**There is no `issues_narrative.md` delegate any more.** Dropped 2026-08-25,
on the same rule as the two below. The live `self/issues_narrative.md` was
retired 2026-08-14 once its entries were migrated into the issue graph, and
`issue_projection.narrative()` — the only thing that ever opened it — was
deleted at B46, 2026-08-17 (that module is `memory/issue_prompt_projection.py`
since 2026-09-03). The delegate outlived its reader by eight days,
and shipped a header that told every new user `circle_briefing_build()` concatenates
the file into BLOCK 2 at each circle open. It had not since B46. Worse, that
sentence was *written into it* on 2026-08-18, a day after the code went: the
edit corrected an older stale reference and replaced it with a fresher one.

The packaging tools that decide what ships — not part of this bundle — never
named this file, and could not reach it by following what live code depends
on, because no live code depended on it. It shipped purely as a passenger of
the wholesale scaffold copy, unexamined by the register that is supposed to
justify every shipped path.

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
