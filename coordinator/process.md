# IFS Inner Circle — Process Rules (operations)
Version: 2026-09-01

Part-facing rules — what you are, circle start, speaking, challenge, signals,
dual-mirror, common good, short-term write-up, Soul, new parts, goals,
honesty mandate, mutual knowing — live in `process_core.md`, which is sent to
every part as its system prompt. This file is the operations rulebook and is not
sent to parts.

Superseded versions are in git. `git log --follow -- <path>` lists every
version a document has had; `git show <rev>:<path>` prints one.

---

## Orchestration — local coordinator

A circle is a single local Python process, `coordinator/circle.py`, talking to
the Messages API. Read `coordinator/README.md` for how to run one.

**How delivery works.** Each part is a stateless API call. Its statement is the
HTTP return value — there is no inbox, no polling, no message that can be
dropped, and no separate session that could hold state the coordinator cannot
see. The coordinator holds the single canonical transcript and, for each part,
reconstructs that part's view of it: the part's own lines become assistant turns,
everyone else's become user turns, addressing included.

**Parts write nothing.** Every file — transcript, short_terms, close report — is
written by the coordinator process. This is the property that removed the whole
class of lost writes that cost six short_terms on `circle_2026-07-11_1644` and
four on `circle_2026-07-26_1112`.

**Rounds.** Within a round, parts are polled sequentially in shuffled order, and
each statement is appended to the transcript before the next part is asked. Parts
therefore respond to one another within a round, not to a snapshot taken at its
start. Order is random per round; `--seed` fixes it for a repeatable test and has
no effect on what parts say.

**Enforced in code, not by discipline** (`circle_round_run`):

- max 2 statements per part since Self last spoke; every Self statement resets
  the counters
- never speak twice in a row
- a part at the limit is held, and the hold is recorded in the transcript

**Truncation is an error, never a pass.** `circle_rounds.MAX_TOKENS` is the ceiling and
the length rule is `prompt_build.LENGTH_MAX_WORDS` — **no number is written here,
deliberately**: both are settings since 2026-08-28, and a rulebook that restated
them would be a fourth literal to go stale. This paragraph carried two at once
("`MAX_TOKENS` is 600", "the 100-word cap") long after the ceiling had been
raised to 2500 and while the room's own rule said something else again.

The ceiling sits far above the word rule ON PURPOSE, so reaching it means
runaway generation rather than a slightly long thought — and because this model
bills its THINKING against the same ceiling, most of what a statement spends
there is reasoning, not words. Measured on circle 2026-08-21_1139: thinking was
49% of a statement's output tokens at the median, and the longest turn reached
86% of the ceiling. A part that truncates is
asked again, shorter. If it truncates twice the statement is *kept* and marked in
the transcript with a trailing `[statement truncated at the token ceiling --
incomplete]`, and the run is failed. The marker is trailing so the part still
counts as having spoken and still writes a short_term. Before 2026-07-26 a double
truncation was silently downgraded to a pass, which made a part that was cut off
indistinguishable from a part that chose silence — the one data-loss path in the
pipeline with no safety net.

**Write guard.** In `--live` mode `WriteGuard` admits exactly five things:
this circle's own transcript `circles/circle_<OT>.md`;
`parts/<name>/short_term_<OT>.toml` (and the `.md` a resumed pre-2026-09-04 close
still writes — R434); `parts/<name>/remember.toml`;
`self/remember.toml`; and this circle's prompt captures under
`work/prompts/<OT>/`, plus its `<OT>_resume_<k>` siblings. Anything else
RAISES — it refuses rather than warns, because a refused write should be a
crash. Without `--live` the only admitted path is under `work/sandbox/`, and
that branch admits in live mode too.

**The guard is not the whole story, and reading it as one is the mistake this
paragraph used to invite.** It said the coordinator may write "exactly" the
transcript and the short_terms, "nothing else, ever" — short by three file
classes, and silent about the registers that never reach it. These are written
during a live circle WITHOUT passing through the guard at all, each live-gated
in its own writer instead: `self/best_practices.toml` (`/practice-add`,
`/practice-delete`), `self/topics.toml` (`/topic-close`),
`self/proposals.toml`, and `circles/working_sets.toml`.

`long_term.md` is genuinely unwritable in-circle. `part_relationships.toml`
used to be unwritable *by the guard* but staged by `inter_circle.py` at
`/close` instead — "structurally unwritable during a circle" was true of the
mechanism and false of the run. RETIRED 2026-08-22 (rulings/, after R308): the register,
its module, and the seven files are deleted; the write this paragraph
describes stopped before that, the same day.

`coordinator/tests/test_write_guard.py` is the probe, added 2026-08-19 after the
audit found that nothing in the tree had ever imported this module.
`ui/tests/test_circle_engine.py` looks like it covers it and cannot: `CircleEngine`
forces `--dry-run`, so every run takes the sandbox branch and never reaches
rule two. The probe is falsifiable, which is the point — a guard loosened to
admit everything fails 15 of its checks, one tightened to refuse everything
fails 9.

**Roster.** All seven parts attend every circle. A reduced roster (`--parts`) is a
testing affordance: an omitted part is absent from the transcript, writes no
short_term, and dreaming records no engagement for it. In `--live` mode this
requires explicit confirmation.

---

## Coordinator constraints

The coordinator is not a part and has no therapeutic standing.

**Relay verbatim.** Self's words reach parts unchanged. No editing, paraphrasing,
or framing.

**Present statements in arrival order. Never curated.**

**No content commentary** — with one exception: bare factual convergence may be
noted after all statements are in, in the form
`[Convergence: Judge and Learner both named X.]` No interpretation, no direction.
A convergence note is not an invitation to respond.

**Rule enforcement is mechanical.** Count statements; do not weigh them.

**Silent coordination.** Do not narrate reading files, waiting, or relaying. Speak
only when there is substantive content or a real exception.

**Dual-mirror.** The coordinator is also subject to the dual-mirror. Self's parts
may speak through this voice; parts may surface it.

---

## Close

`/close` at the `Self>` prompt runs the close sequence:

1. Each part is asked for its four-section short_term and the coordinator writes
   `parts/<name>/short_term_<OT>.toml` (`.md` before 2026-09-04, R434), then reads
   it back and refuses a record any of whose four sections is missing or empty.
   A part that never spoke is not asked and correctly writes nothing.
2. `coordinator/circle_close_verify.py --short-term-only --open-time <OT> --write-report`
   verifies every speaking part has a well-formed record and emits the durable
   close report `work/logs/close_<OT>.json` — each part's size and sha256.
3. The circle is committed to git: transcript, short_terms, close report, and the
   open report `work/logs/open_<OT>.json` the open wrote, tagged `circle/<OT>`.
   Only those paths.

`circle.py` exits non-zero if the record is incomplete: a double truncation, a
short_term that failed twice, or a non-zero verifier. `/abort` keeps the
transcript, collects no short_terms, and says so.

### short_term backfill from the transcript

When a part spoke but its `short_term_<OT>.toml` (or legacy `.md`) is missing or malformed,
reconstruct it from the transcript — the authoritative account of what was said —
rather than leave the circle reading as no-engagement for that part.

Build the part from the same material `circle.py` uses (`process_core.md`, its
`long_term.md`, circle_objectives as `group_attention.circle_briefing_build()`
constructs it from `issues/issue_model.md` + `issues/*.toml` —
`self/circle_briefing.md` retired 2026-08-11, `self/issues_narrative.md` at
B46 2026-08-17)
plus `circles/circle_<OT>.md`, and have it produce the
four-section record with *What I said* and *What I observed* grounded in its own
transcript lines. **Write only** `parts/<part>/short_term_<OT>.toml` — or `.md`
when the circle's other parts are `.md`, the repair matching the circle it lands in; never
`long_term.md` or any other per-part file. If processing already read the circle
as no-engagement for that part, re-consolidate afterwards and correct the
affected `self/` files.

`coordinator/circle_audit.py` (reconcile + backfill phases) automates this — see
below. (First applied 2026-07-11 for Child and Learner, `circle_2026-07-10_1223`.)

---

## Nightly

**THIS HEADING IS LOAD-BEARING — `memory/record_verify.py`'s
PROCESS_ANCHORS names it literally as a truncation-guard anchor** (audit-
register.md #12). The guard does not care that the section is retired; it
only checks the heading is present, at circle open and in `circle_audit.py`
phase 0. Renaming or deleting this heading without updating PROCESS_ANCHORS
would make the guard fire on every future commit touching this file — the
exact "worse than none" failure PROCESS_ANCHORS' own comment warns about,
citing the 2026-08-07 incident that taught it. Update both together.

RETIRED — R228 removed the batch shape, and the scheduled tasks are gone from
the scheduler. Dreaming and synthesis now run synchronously, as `/close`'s
phase 2: `coordinator/inter_circle.py` (design: `docs/INTER_CIRCLE_DESIGN_V2.md`).
The old prompts are in git at their own paths,
`scripts/ifs-nightly-dreaming-SKILL.md` and
`scripts/ifs-nightly-synthesis-SKILL.md`.

`coordinator/circle_audit.py` (renamed from `nightly.py` 2026-08-19, same
ruling) is NOT the successor — it is the independent audit: preflight, survey
of unprocessed circles (by `dream/<OT>` git tag; circles older than the oldest
tag are out of scope, and the dreaming manifests are dead records), reconcile +
transcript safety net, and the invariant gate over `parts/` and `self/`. It
cannot write to the live tree except `--backfill --commit`, which writes
short_terms and nothing else. Design history: `docs/NIGHTLY_DESIGN.md`.

### Durability guards, in order

1. **Reconcile.** `coordinator/circle_close_verify.py --reconcile --open-time <OT>` re-reads
   each short_term recorded present at close and compares size + sha256.
   `RECONCILE-DRIFT` means a write was lost or altered after a clean close;
   backfill those parts from the transcript before dreaming.
2. **Transcript safety net.** Runs whether or not a close report exists: any part
   that spoke (`[Part]:` or `[Part] [To: …]:` lines) with no well-formed
   short_term is backfilled first. A genuinely silent part is exempt — absence
   for a non-speaking part is correct, not a loss.
3. **Invariant gate** (`memory/register_gate.py`, judging with
   `coordinator/record_model.py`'s file model). Structural checks over the
   memory files: identity sections cannot vanish, content above `## Dream
   entries` is frozen, dream history is append-only, existing entry bodies are
   immutable, historic weights are frozen, and every `### ` line in `## Dream
   entries` must parse as an entry. The observation log's own rule is
   `circle_observation_manager.py`'s.

### Recency model

Dream entries are tracked by **recency, not weight**. Historic `### [N]` weight
numbers are frozen record and are never updated. An entry may carry several
markers at once — `### [review] [15] Dream …` is a flagged entry that also holds
its historic weight.

- Each entry carries a `*Last mentioned:*` field — the most recent circle in
  which its core theme was **substantially engaged** (developed, confirmed, or
  challenged; not a passing reference).
- An entry with no `*Last mentioned:*` field anchors to **its own dream date**.
  Self-report entries written outside any circle carry no circle reference;
  without this rule they would sit outside the recency model permanently.
  (Settled 2026-07-26 — `docs/NIGHTLY_DESIGN.md` §10.)
- **The threshold is circles, not days.** An entry that goes **≥ 5 circles**
  without substantial engagement is flagged `[review]` — a DIFFERENT, earlier
  stage than `quote_verify.py`'s own **≥ 12 circles** SETTLE threshold (that
  one moves a review-flagged entry on to `## Settled`, below); this line read
  as contradicting that one until audit-register.md #41 clarified the two are
  sequential, not competing numbers for the same event. **NEITHER IS
  MECHANICALLY ENFORCED TODAY** — `parts/*/dreams.toml` has been READ-ONLY
  since R178 (`register_gate.py`'s own REGISTERS entry: `"frozen": True`, "nothing
  writes it"), so no writer currently applies either threshold; both describe
  the intended rule, not code that runs. Counting is over circle
  files in `circles/`, so a fortnight with no circle ages nothing.
- After a review circle passes: if the topic was engaged, the flag clears; if
  not, the entry moves to `## Settled` at the bottom of `long_term.md` — frozen
  as history, never deleted.
- Any part may reintroduce a settled theme in a live circle; if it gains genuine
  engagement, the next dream entry re-creates it fresh.

### Dream entry format

```
### Dream YYYY-MM-DD — brief title

*Last mentioned: circle_YYYY-MM-DD_HHMM*

content (100–200 words, first-person voice)
```

Two field spellings are both canonical and both parsed:
`*Last mentioned: circle_…*` (value inside the emphasis) and
`*Review flagged:* YYYY-MM-DD_HHMM` (label emphasised, value outside).

New entries carry no weight number and go at the top of `## Dream entries`.
Content above that header is not subject to recency tracking or settling.

### Self's synthesis

Reads all parts' `long_term.md` (`part_relationships.toml` dropped, RETIRED
2026-08-22 per :84-89 above — this line said "and part_relationships.toml"
until audit-register.md #41), plus **all circle
transcripts since the last synthesis — transcripts are ground truth** and take
precedence over dream-compressed summaries when facts conflict. Then:

1. Rewrites `self/self.md` (system state, parts table, dated dream-synthesis
   bullets)
2. Appends one `CO-` record to `circles/circle_observation_log.toml` (TOML
   since 2026-08-19; was `self_observation_log.md`. `CO-` since R481,
   2026-09-07 — `SO-` ids written before it keep their prefix, forward-only)
3. STEP RETIRED 2026-08-11: used to rewrite `self/circle_briefing.md` with
   resolved questions, which `circle.py` split per part. That file is gone —
   circle_objectives is now built directly by `group_attention.circle_briefing_build()` at prompt
   time (see `docs/BNF.md` BLOCK 2), and nothing today gives
   "resolved questions" a home; a synthesis redesign that wants to keep
   surfacing them needs a new destination, not this rewrite.
4. STEP RETIRED, though never marked so until audit-register.md #41: used to
   write the narrative layer, a phase bullet appended to `self/narrative_arc.md`
   only on a genuine phase transition, plus a fresh `self/narrative_YYYY-MM-DD.md`.
   R165 (2026-08-15) moved the one job this did — the cross-circle phase
   bullet — into `circles/circle_history.toml`; R256 (2026-08-19) confirmed
   "no writer since R165" for the arc file. `record_model.py` calls the
   dependency "A PHANTOM": nothing writes either file today, and the operator's
   own `self/narrative_arc.md` is untouched, frozen history since 2026-07-27.

---

## Changing a description or a name

**The old name goes to Description history when it changes.** An explanation may
be attached and is **not required.** Ruled by Self, 2026-08-01.

Left to discipline rather than gated: the gate requires Description history to be
non-empty, and does not require a rewrite to cite the words that caused it. That
was offered as a check and declined — *"leave it to discipline."*

The rule is nonetheless checkable if it is ever wanted: the previous Description
string must appear somewhere in Description history after a change. Recorded here
so the option is a decision already made rather than one never noticed.

## Marks — RETIRED WHOLESALE, 2026-08-14

MARK — `self/marks/<OT>.toml`, `/mark`, the `[mark ...]` annotation, its five
kinds (`lands`/`stings`/`denied`/`lead`/`platitude`), the `· TEST` convention,
and PROPOSE MARK (`[propose mark]`, `self/mark_proposals.toml`) — is retired
outright, code included (docs/BNF.md). Self's reflexive record is REMEMBER
now, surfaced on demand by `/remember-list` (built 2026-08-18, R224, as
`/recall`; that alias retired 2026-09-11, R557). The
old `self/marks/<OT>.toml` records are in git, not lost —
`git log --all -- self/marks/` finds them. `self/leads.md` is left in place,
frozen: its writer
(`append_leads()`) is gone but the historical content stays.

Not carried forward: MARK's `kind`/`test` fields have no home in REMEMBER's
record shape, and PROPOSE MARK's capability — a part flagging its own
statement for Self's SAME-CIRCLE attention — has no designed replacement.
Full history of both mechanisms is preserved verbatim in the last version of
`docs/Circle BNF.txt`, in git.

## Editing memory files by hand

Use a plain-text editor. A markdown-aware editor may normalise a file on save —
escaping `[` and `_`, merging emphasis across lines. On 2026-07-26 that made 14
of 22 dream entries in `parts/mourner/long_term.md` unparseable while the file
still read correctly to a human, and it was committed before anyone noticed.

Run `python coordinator\circle_audit.py --selfcheck` after any manual edit. Every
`### ` line that fails to parse is now a hard failure.
