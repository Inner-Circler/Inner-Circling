# coordinator — the local Coordinator

A local Python coordinator that runs a circle as direct Messages API calls.
Successor to `spike_asyncio/`. **The agent-teams mechanism is retired, not
"untouched and fully operational"** as this line said for weeks — its
team-teardown checks in `circle_close_verify.py` are vestigial (self-skipping when
their subject is absent; "nothing schedules them and no live path runs
them", per `coordinator/docs/circle_close_verify.md`), and `scripts/*.py` cannot be
"neither modified nor read" because `scripts/` itself no longer exists
(retired 2026-08-19). Nothing in this checkout still runs the agent-teams
path.

(The windowed way in is the Ticker flavor — `ui/ticker/`, manual at
`ui/docs/bridge.md`; `ui/circling.py` remains the two-pane terminal. Both
run this directory underneath.)
Either mechanism can be used for any given circle.

---

## A RECORD PATH IS RELATIVE TO ITS GROUP'S TREE

**`parts/`, `self/`, `issues/` and `circles/` do not exist at the repository root.** They
are the four kinds inside a GROUP's tree, and a group's tree is `groups/<name>/` — R466/R467,
B117, 2026-09-07. So every record path written in this file and in the man pages —
`self/best_practices.toml`, `circles/working_sets.toml`, `parts/<p>/remember.toml`,
`issues/issue_model.md` — is shorthand for `groups/<group>/…`, resolving to `groups/ifs/…`
for the default group.

**Stated here once rather than rewritten at forty sites** (audit-register.md #27, 2026-09-08).
The convention was already how every document wrote these paths and was declared nowhere: a
reader who tried one against the tree found nothing there, and `record_paths.py`'s own account
of the shape (`:18`, `:144`) is a comment inside code, not something a reader of prose meets.

`coordinator/record_paths.py` is the one lookup either way — `record_rel("self/topics.toml")`
for the ROOT-relative string git and the hook take, `SELF_DIR / "topics.toml"` for the
absolute path — and both follow `--group`.

---

## What it does differently

| | agent-teams (retired) | coordinator |
|---|---|---|
| statement delivery | `SendMessage` reply + `statement_temp.md` fallback (#43706) | the HTTP return value |
| file writes | teammate writes lost to the mount (#69866) | one local process, direct to `D:\` |
| turn rules | prose in `process_core.md`, model asked to obey | enforced in the round loop |
| caching | opaque | 4 explicit 1h breakpoints, metered per call |
| round shape | broadcast | sequential, shuffled — parts hear each other *within* a round |
| console | CLI operational chatter | statements only |

Unchanged and still authoritative: `process_core.md`, each part's
`long_term.md` (`part_relationships.toml` RETIRED 2026-08-22), `issues/issue_model.md`
(circle_objectives' source — `self/circle_briefing.md` retired 2026-08-11 and
`self/issues_narrative.md` at B46 2026-08-17, see `docs/BNF.md` BLOCK 2),
the transcript format, the four-section short_term format,
`coordinator/circle_close_verify.py`, and dreaming/synthesis — no longer nightly
tasks (R228 removed the batch shape 2026-08-18 — this line said 2026-07-28, the
date ifs-nightly last ran, until 2026-09-04); they run automatically,
synchronously, inside every completing live `/close`, via
`coordinator/inter_circle.py`.
(`self/open_concerns.md`/`.toml`, the OC register, retired outright
2026-08-13 — vestigial.)

## Interop with the existing pipeline

- Transcript lines are written as `[Tag]:` / `[Tag] [To: X]:` — verified
  against `circle_close_verify.py::parts_that_spoke()`.
- short_terms carry the four canonical sections — verified against
  `circle_close_verify.py::short_term_status()`.
- At close, `--live` shells out to
  `coordinator/circle_close_verify.py --short-term-only --open-time <OT> --write-report`,
  so `work/logs/close_<OT>.json` is produced by **the same verifier as today**
  and the audit's `--reconcile` guard (`circle_audit.py` phase 2) keeps working
  with no changes.

## Write safety

`WriteGuard` refuses everything not on an explicit allow-list.

- **`--dry-run` (the test rig)** — no model calls, every part passes; writes
  only under `work/sandbox/`. `circles/`, `parts/`, `self/`, `work/` are
  unwritable. (A bare invocation refuses since R360 — the old bare default,
  real calls with sandboxed writes, was the practice mode R250 deprecated;
  practice lives in the lab.)
- **`--live`** — additionally permits exactly two shapes:
  `circles/circle_<OT>.md` and `parts/<name>/short_term_<OT>.toml` (`.md` before
  2026-09-04, R434 — a resumed pre-B96 close still writes it), where `<OT>`
  is *this run's* open time. It cannot overwrite a prior circle, cannot touch
  `long_term.md` or any other per-part file, cannot write `self/`.

Identity files are opened read-only in both modes.

---

## Setup — nothing to install

`.venv` already has both dependencies (`anthropic 0.109.2`, `python-dotenv
1.2.2`, pinned in `requirements.txt`) and `ANTHROPIC_API_KEY` is already in
`.env`. Just use the venv's interpreter. Two equivalent ways, from
this checkout's own root:

**`.env` IS ONLY READ WHEN THE VARIABLE IS UNSET.** `load_dotenv` is
reached only if `os.environ` has no `ANTHROPIC_API_KEY`, so a stale key in
the environment silently beats a fresh one in the file — rotating the key
in `.env` alone then changes nothing. That is what 401'd
`circle_2026-08-09_1507` out of existence. `circle.py` now prints both,
masked, whenever they differ:

```
!! ANTHROPIC_API_KEY is set in the
   ENVIRONMENT and differs from .env.
   environment  sk-ant-api03...5gAA <- IN USE
   .env         sk-ant-api03...igAA <- IGNORED
```

Reconcile them or clear the variable; the warning is telling you which key
is actually in play.

**THE COMMON CAUSE IS A LONG-LIVED PROCESS HOLDING A STALE SNAPSHOT.** A
process keeps the environment it was handed at launch; clearing the variable
afterwards corrects the registry and every new shell, and cannot reach a
process that started before you did it. That process then serves the old
value to every child it spawns, for as long as it lives. Measured
2026-08-09: a `claude.exe` open for days was still handing out a circling
key rotated out that morning, while `HKCU\Environment` and the machine
environment carried nothing — both readings true at once.

So if this warning fires, the fix is usually **restart whatever launched the
shell**, not edit anything. And when it fires it means *you are not using
the project's key*, which is worth knowing before a live circle that costs
money and goes on the record.

**A disabled key is a dead key.** Measured the same day: the rotated key
returned `401 authentication_error` while `.env`'s key worked. Disabling
without deleting keeps it visible and auditable in the console; it does not
keep it operable for anything already holding it. Which is the good failure
mode — a stale snapshot fails loudly at the API check instead of drifting.

```
.venv\Scripts\python.exe coordinator\circle.py --dry-run
```

or activate once per shell, then use plain `python`:

```
.venv\Scripts\activate
python coordinator\circle.py --dry-run
```

PowerShell uses `.venv\Scripts\Activate.ps1`. Every `python` in this README
means the venv's python.

To confirm before a paid run:

```
.venv\Scripts\python.exe -c "import anthropic,dotenv;print(anthropic.__version__)"
```

Expect `0.109.2`. If that errors, and only then:

```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use `-m pip` rather than bare `pip` so the install cannot land in a different
interpreter.

## Commands at the `Self>` prompt

These four (plus plain speech) are the whole circle-pane verb set —
`command_surface.py`'s PANE_OF classifies every other verb (including
`/status`, corrected out of this list) as command-pane only, reachable at
`cmd>` in the dual-pane UI, not here. There are 55 verbs total across both
panes (`len(command_surface.COMMANDS)`, 2026-09-04; 43 when this line was
written); see `docs/BNF.md`'s USER_SUBSET_COMMANDS / DEV_SUBSET_COMMANDS for
the rest.

```
<text>    speak as Self — resets every part's since-Self counter, runs a round
/round    let the parts take another round without a Self statement
/pass     an alias for /round, same operation
/close    collect short_terms, verify, print the usage report
/abort    end the circle without a close — no short_terms, transcript kept
```

---

# 1. Dry run — free, no network

Proves the scheduler, transcript writer, limit enforcement and short_term
writer without spending anything.

```
python coordinator\circle.py --dry-run --seed 7 --parts philosopher,judge,mourner
```

At the prompts: type a topic, then `/round`, then `/status`, then `/close`.

**Expect:** three canned statements per round in shuffled order; after the
second round a `[... at the two-statement limit — holding until Self
re-engages.]` line; three short_terms written under
`work\sandbox\parts\`; `$0.0000`.

**Check:** no part speaks twice in a row within or across rounds, and the
holding note appears only once every part has reached 2.

Delete `work\sandbox\` freely — nothing there matters.

---

# 2. Test round — real models, in the lab, ~$0.30

Three parts, real API — run it in a LAB checkout, a full copy kept
specifically for churn like this whose record never merges back (R249). A
lab is optional local infrastructure, not something this repository ships
— set one up as a separate clone if you want one. The old way — a bare
invocation here, real calls with sandboxed writes — refuses since R360.

```
cd <your lab checkout>
.venv\Scripts\python.exe coordinator\circle.py --live --parts philosopher,judge,mourner
```

Topic: something low-stakes — `testing a new way of holding the circle; how
does this feel from your side?`

Then:

1. Read the opening round. Watch whether later speakers in the round respond
   to earlier ones — that is the thing sequential scheduling buys.
2. Type one Self statement. Confirm `/status` shows all counters back at `0/2`.
3. `/round` twice more, until parts start holding at the limit.
4. `/close`.

**What to verify**

- **Cache is working.** In the usage report, `hit rate` should be **≥ 85%**
  after two or three rounds. If it is near 0%, the prefix is changing between
  calls — stop and investigate rather than running a full circle.
- **Pre-warm.** Each `warmed <part>` line should show ~18,000 tokens written.
  On the *next* call those become reads at 1/20th the price.
- **No truncation.** `[<part> ran long — asking again, shorter]` should be
  rare; `truncated twice` should never appear. If it does, the run now says so
  loudly and exits non-zero — see §Exit codes below.
- **Voice.** Read the transcript at the LAB's
  `circles\circle_<OT>.md`. Compare it to
  `circles\circle_2026-07-26_1112.md` from this morning's agent-teams circle.
  This is the real question the test round answers: do the parts still sound
  like themselves without the CLI wrapper? If a part feels flat, the cause is
  almost always its `long_term.md`, not the transport.
- **short_terms.** Open one under the LAB's `parts\<name>\`. Four sections,
  substantive, about *this* circle.

Cost check against the report: expect roughly `$0.22` warm + `$0.02`/round +
`$0.03` close. If it is materially higher, the cache missed.

---

# 3. Full circle — live, all seven parts, ~$1.30 for 15 rounds

Only after the test round passes. Do not run this concurrently with an
agent-teams circle — two circles sharing one open-time minute would collide.

```
python coordinator\circle.py --live
```

**Sequence**

1. Confirm the banner reads `LIVE` and the transcript path is
   `...\circles\circle_<OT>.md`. (A bare invocation refuses since R360, so a
   wrong-mode run cannot happen silently.)
2. Type your opening topic exactly as you would after `CIRCLE:` today.
3. Pre-warm runs for all seven parts (~125,000 tokens, ~$0.50). This is the
   whole circle's identity cost, paid once.
4. Hold the circle. `/round` to let parts continue; type to speak as Self.
5. `/close` when done.

**At close, in order**

- one short_term call per part that spoke, written straight to
  `parts\<name>\short_term_<OT>.toml` (`.md` before 2026-09-04, R434; the
  reply's four sections become four named keys, prose verbatim, and the
  record is read back before it counts as written). A part that never spoke writes nothing —
  correct, and dreaming (`coordinator/inter_circle.py`, run automatically at
  close) exempts it as SILENT rather than treating it as no-engagement.
  For the Soul this will often be the case;
- `coordinator/circle_close_verify.py --short-term-only --open-time <OT> --write-report`
  runs and prints its own verdict;
- every `[proposed: <command>]` annotation — a practice is
  `[proposed: /practice-add ...]`, a better option
  `[proposed: /better-option-add ...]`, an edge
  `[proposed: /issue-relationship-add ...]` — is staged into
  `self/proposals.toml` by proposal_stage(), then an
  a)pprove/d)eny/s)kip screen shows every currently pending row — this
  circle's and any skipped earlier — and approving one RUNS the command;
  see `docs/BNF.md`'s PROPOSE LIFECYCLE. (The six practice bracket
  spellings, their revise/delete forms and the best_practices.toml
  staging path went with B60, 2026-08-20.);
- the usage report.

**Verifier exit 0 is the success condition.** It writes
`work\logs\close_<OT>.json` exactly as the agent-teams close did, so the
automatic dreaming/synthesis pass that runs synchronously at the end of this
same `/close` (`coordinator/inter_circle.py`) reconciles and dreams normally
with no changes.

If the verifier exits non-zero it will name the failing part(s) as
`MISSING-SHORT-TERM`. Re-run just the close for that part by hand, or backfill
from the transcript as today — the existing remedy applies unchanged.

**Right after `/close` returns:** check `self\narrative_<date>.md` and the
part's `long_term.md` picked up the circle — dreaming/synthesis already ran,
synchronously, before the close command exited. That confirms the
coordinator's output flows through `coordinator/inter_circle.py` end to end.
That check is the real acceptance test.

---

## Desync risks in the dry run and test round

**Neither run can desync THIS tree's durable records.** The dry run writes
only under `work/sandbox/`; the lab test round writes the LAB's own record,
which never merges back (R249). Here, `parts/*/long_term.md` and
`short_term_*.toml` (`.md` before 2026-09-04, R434) are unwritable and are opened read-only. The guard is
tested. What follows is everything that *is* live.

**1. Self–part desync, not part–part.** The test round is a real experience
that is then discarded. You will remember it; no part will. If you later
reference something a part said in a test round, it is blank — and worse, it
may confabulate agreement rather than say so. *Mitigation:* make the test topic
disposable and about the mechanism, not about content you care about.

**2. Briefing content gets engaged, then engaged again.** `circle_objectives`
carries the live issues (constructed fresh from `issues/*.toml` at circle
open — no file behind it since `self/circle_briefing.md` retired 2026-08-11),
and the parts read it in a test round like any other. A part may raise one at
you. Because nothing is written, it surfaces again in the next real circle
exactly as before. The failure mode is repetition, not loss — but do not
treat an issue as engaged on the strength of a test round.

**3. RETIRED — there is no longer a 1:11 AM run to avoid.** R228
(2026-07-28) removed the scheduled nightly task this risk was about; the
coordinator reads each part's `long_term.md` once at circle open, and the
only writer of that file — dreaming/synthesis — now runs synchronously
inside the SAME live `/close` that produced the circle, never as an
independent background process a later open could race against.

**4. RETIRED — there is no agent-teams circle to collide with.** Nothing in this
checkout can open one (see the head of this file). When it could, the same part
would have been animated in two places, and the agent-teams close would have
written a short_term describing only its own half.

**5. Open-time collision (`--live` only).** Two circles opened in the same
minute would both claim `circles/circle_<OT>.md`. Not reachable from a sandbox
run; noted for live use.

### Not desync, though it looks like it

- **Parts polled later in a round see more than parts polled earlier.** That is
  the intended async model — parts speak when ready, and every view is derived
  from one canonical transcript, so no part can see something another cannot.
- **`circle_objectives` is frozen at startup** for the whole run — constructed
  once by `group_attention.circle_briefing_build()`. Editing `issues/*.toml` mid-circle does not
  propagate. Same as the agent-teams path, where parts read their briefing at
  circle start. All parts in a run share one identical copy.
- **Long circles lose the message-level cache.** Merged role-blocks alternate
  each time a part speaks; past ~20 statements by one part the 20-block lookback
  window is exceeded. The three system breakpoints are separate windows and
  still hit, so the ~18,000-token identity prefix stays cached and only the
  transcript is re-paid. Cost degradation, not desync.

### Fixed 2026-07-26

Statements were rendered to listeners as bare `Judge: …` while the transcript
recorded `[Judge] [To: Child]: …` — the parts could not see who a statement was
addressed to, desyncing perception from the durable record. `prompt_messages_render()`
now carries the addressing.

## Opening a circle — the order, and why it is that order

Ruled 2026-08-09: *"Test the API as early as practical and error out
gracefully on fail; do not write circle records of any sort until after the
check passes."*

```
1  key source reported if env and
   .env disagree
2  API CHECK — one real
   messages.create, max_tokens=1,
   against the circle's own model
3  open circles reported; confirm
   to open a new one anyway
4  working set prompt
5  topic prompt
6  OPEN TIME MINTED, path checked,
   transcript written
7  pre-warm, prompt capture
8  opening round
```

Steps 1-3 come before anything is typed, so a bad key costs a retry rather
than a re-pasted topic. Nothing under `circles/` or `self/` is written
before step 6.

**Transient failures retry on Self's ladder** — 3 attempts, 5 seconds after
the first failure and 15 after the second, for 429, any 5xx, and connection
or timeout errors. Fatal ones (401, 403, 404, 400) do not wait. The SDK's
own `max_retries` is set to 0 for these calls so the ladder is the only
retry behaviour there is.

**An unspoken circle leaves no trace.** If the run dies between step 6 and
step 8, the transcript and its `circles/working_sets.toml` entry are removed. The
test is the bytes: if a single statement landed, the file differs from what
`open_transcript` wrote and nothing is touched — a partial transcript is a
real record and is resumable.

**A transcript at this open time is REFUSED, not overwritten.** Two `--live`
opens in the same clock minute used to mean the second silently truncated
the first.

## Exit codes

`circle.py` exits **0 only when the circle produced a complete record.** Any of
the following puts an entry in the failure record, prints a banner at the end of
the run, and makes the exit code **1**:

- a part truncated twice (`MAX_TOKENS` in `circle_rounds.py`, now 2500) — see below
- a `short_term` that failed twice and was not written
- `coordinator/circle_close_verify.py` exiting non-zero at close

**Exit 2 means the circle never opened** — a bad key, a failed pre-warm, a
malformed `--resume`, a closed circle asked to reopen, a transcript already
at this open time, or either confirmation prompt declined. Nothing was
written, or what was written has been withdrawn. Exit 1 means a circle ran
and its record is incomplete; the two are not interchangeable. Both cancels
returned 1 until 2026-08-09, when writing this sentence down was what found
them.

**Truncation is never downgraded to a pass.** Before 2026-07-26 a part that
overran twice was recorded as having passed. That was the one data-loss path in
the pipeline with no net: the transcript safety net deliberately
exempts genuinely silent parts, so a part that *tried* to speak and was cut off
looked identical to one that chose silence, and nothing downstream would ever
catch it. Now:

- if any text came back, it is **kept** and marked in the transcript with a
  line-*trailing* `[statement truncated at the token ceiling -- incomplete]`.
  The marker is trailing on purpose — `circle_close_verify.py::parts_that_spoke()`
  anchors on the leading `[Tag]:`, so the part still counts as having spoken,
  still writes a `short_term`, and dreaming still sees engagement.
- if nothing came back, the statement is genuinely lost and the record says so
  in those words. That part may read as silent to dreaming — check the
  transcript before the next circle.

An interrupted run (`/abort`) prints an explicit reminder that no
`short_term`s were collected and that nothing backfills them
automatically — `/abort` never reaches dreaming, unlike a completing close.
The reminder names the repair: `circle_audit.py --backfill --commit`.

## Rollback

Stop using it. A bare `python coordinator\circle.py` is REFUSED (R360) and writes
nothing; `--dry-run` writes only under `work\sandbox\`; `--live` writes only this
run's two file shapes. To revert a live circle: delete `circles\circle_<OT>.md`,
`parts\*\short_term_<OT>.toml` (`.md` before 2026-09-04, R434), and `work\logs\close_<OT>.json`. Nothing else
was touched. There is no other path to fall back to — the agent-teams mechanism is
retired.

## The briefing SPLIT — there is no file, and no filter, any more

Renamed and restructured 2026-08-06, then rebuilt twice more since. What
`self/circle_briefing.md` used to be one file for, filtered per part at a
cost of seven cache writes of ~34,000 characters to withhold at most 136
characters each, is now two independent things, neither of them a filter
over a rendered document:

```
best practices / better options  self/best_practices.toml, read
                                 directly by practice_manager.py's
                                 practice_broadcast() (-> circle_identity) and
                                 practice_narrowcast(part_tag) (-> part_identity),
                                 by `addressee` field, rendered by the two
                                 projections. R133-137, 2026-08-11; the
                                 register left check_best_practices.py (now
                                 practice_verify.py) 2026-09-03.
circle_objectives                group_attention.py's circle_briefing_build() — issue_model.md
                                 + the live issues/*.toml graph, constructed
                                 fresh at every circle open.
                                 self/circle_briefing.md retired the same day;
                                 issues_narrative.md was a third source until
                                 B46, 2026-08-17. See docs/BNF.md BLOCK 2.
```

An addressed practice was formerly its `**Part** —` marker line PLUS every
line to the next blank line — that was E09: the original filter took only the
marker and leaked the continuation of every wrapped entry to all six other
parts. That whole marker-and-filter mechanism is gone with the file; routing
is the TOML's own `addressee` field now.

`prompt_capture --verify` asserts that no SHARED block carries a
practice addressed to one part alone. Since R277 (2026-08-21) blocks 1
and 2 are captured ONCE per circle — `Block1_circle_identity.md`,
`Block2_circle_objectives.md` — and `prompt_capture.prompt_capture_write()` refuses a
capture in which they differ between parts.

## Known cost levers

Each part's cached prefix is ~18,000 tokens. (There is no filter any more —
see "The briefing SPLIT" above; this matches the pre-warm figure quoted
under "What to verify".)

**Correction to an earlier estimate.** I previously said trimming the briefing
would "roughly halve" per-circle cost. That was wrong. The briefing is 34% of
the *prefix*, but the prefix is warmed once and re-read at 0.1x, so its true
share of a 15-round circle is ~23%. A full trim saves ~$0.20 of ~$1.20 —
about **17%**. Worth doing for how it affects the parts' attention; not a
cost emergency. (This paragraph used to cite `proposed_step6_briefing.md`
for that trim; no such file exists anywhere in the tree.)

`long_term.md` is NOT a remaining lever — it no longer grows automatically
at all (measured directly: 1,649-4,260 bytes per part, mean 2,796; this
section previously said "~28 KB per part and growing", ~7x off, and
self-contradicted "The three part files" section below, which correctly
says "It no longer grows — dreams go to short_terms"). A resolved chain of
3+ can reach `self/topics.toml` as a LONG_TERM CANDIDATE for Self to review,
but nothing auto-writes `long_term.md` itself (`inter_circle.py`'s own
comment says so directly).

## Flags

Regenerated against `coordinator/circle.py`'s own argparse definitions
(this section previously listed 6 of the real 13, with defaults stated for
only one).

```
--live              write to circles/ and parts/<name>/short_term_<OT>.toml (R434),
                    run circle_close_verify.py at close. Default: off.
--dry-run           no network, no API key needed; every part passes.
                    Default: off. A bare invocation with neither --live nor
                    --dry-run REFUSES (R360) — one is required.
--parts a,b,c       comma-separated part dirs — TESTING ONLY, see "Roster"
                    below (a reduced roster leaves the omitted parts
                    unaware of the circle). Default: every member of the
                    DEFAULT GROUP — the `ifs` row resolved through
                    group_manager.group_resolve() (B117 stage 1,
                    R466/R467), never the parts/ scan; the scan is the
                    fallback only where no group row exists. The Soul is
                    among them (see "The Soul" below — it IS a
                    participant; process_core.md's own §The Soul
                    disagrees with the record, not this default).
--group NAME        open on a NAMED group (coordinator/group_manager.py,
                    groups/<name>/group.toml — R468) instead of --parts — a deliberately
                    different roster, not a reduced one, so the REDUCED
                    LIVE ROSTER warning above does not fire for it.
                    Mutually exclusive with --parts (landed `6fe45f4`,
                    2026-09-02). Default: unset.
--recall-arm ARM    tier A recall (remember_expand.py, docs/MEMORY_DESIGN.md):
                    expand topic-matched seeds into each part's BLOCK 4.
                    ARM is off | delivered | withheld. Default: off.
--no-prewarm        skip llm_client.stream_prewarm(), the sequential
                    zero-output-token calls that write each part's cached
                    prompt prefix before the opening round. Default: off
                    (the prewarm runs).
--no-blind          run the PRIOR protocol: a sequential opening round,
                    instead of the default BLIND round. Default: off.
--seed N            see "Seed" below. Default: unset (a fresh shuffle
                    every round).
--yes               skip the reduced-live-roster confirmation prompt.
                    Default: off.
--resume OPEN_TIME  reopen an unclosed circle, e.g. --resume
                    2026-08-02_1259; the transcript must round-trip
                    byte-for-byte or the resume is refused. Default: unset.
--dev[=BOOL]        open with dev mode on — DEV-table verbs, the help
                    hierarchy, and progress lines all answer at this
                    terminal's Self> prompt. Bare --dev means --dev=true.
                    Default: off.
--list-resumable    show circles that have a transcript but no close
                    report, then exit. Default: off.
--dev-cmd VERB ...  run ONE always-available command directly from the
                    shell, no circle needed (the ic.py replacement).
                    Bypasses dev_mode entirely. Default: unset.
```

## Seed

`--seed N` calls `random.seed(N)`, which fixes the one place randomness is
used: `random.shuffle(order)` in `circle_round_run()` — the order parts are **polled**
within a round. Same seed, same polling order every run.

It does **not** make the parts' statements deterministic. Model sampling is
server-side and unaffected. Its only purpose is to remove one variable when
comparing two test runs, or to reproduce a scheduler bug.

**Omit it for real circles.** A fresh shuffle each round is the point — a fixed
seed means the same part is asked first every round, which quietly biases who
sets the agenda.

## Roster

**No, parts do not need to be named.** The default is **every member of the
default group**, the Soul included — the `ifs` row resolved through
`group_manager.group_resolve()`, never a `parts/` scan (B117 stage 1,
R466/R467). `--parts` exists for cheap test rounds.

### The Soul — a doctrine discrepancy that has since been resolved

This section quoted `process_core.md` §The Soul as saying it "does not speak
directly in circles… may graduate to speech if a circle specifically calls
for it" and described a `STANDING_OVERRIDE["injured_soul"]` symbol in
`circle.py` as a workaround. Neither is accurate today: no such symbol
exists anywhere in the tree, and `process_core.md` §The Soul now reads
**"It is present in every circle and it does speak — rarely, and on its own
terrain"** (R303, 2026-08-22) — already matching the empirical record below
rather than contradicting it.

The record: it has spoken in **21 circles between 2026-06-24 and 2026-08-09** (measured
directly against circles/*.md, matching every historical spelling — "Soul"
and "Injured Soul"/"injured_soul", since the two are the same part across a
rename), including this morning's `circle_2026-07-26_1112`, and it keeps its
own short_term records of having done so (`2026-07-05_1308`: *"Spoke three
times."*). It is a participant, in `DEFAULT_PARTS`, and excluding it would
silently drop a part the live path includes.

**Where the per-part addendum mechanism actually lives:** `identity_tail`
in `part.toml` (R246, R304) — per-part, per-installation, landing in BLOCK
3. A stricter addendum ("default to `[pass]`...") sat in the Soul's
`part.toml` for a few hours on 2026-08-22 before R304 deleted it outright,
not as a workaround kept in place: it duplicated (and was stricter than)
`parts/soul/long_term.md`'s own "My role in circles" section, and deleting
it delivered a softening Self had separately asked for. No part declares an
`identity_tail` today — the mechanism is built; nothing installs one yet.

**Your inference is correct, and it matters.** An omitted part is not a quiet
attendee — it is absent. Trace it through:

- It never appears in the transcript, so it writes no short_term.
- `coordinator/part_dreaming.py`'s `part_dream()` (inter_circle's until 2026-09-03) reads that via
  `short_term_manager.short_term_locate()` (B96/R434, 2026-09-04, either `.md` or `.toml` suffix): no
  short_term file means treated as no engagement for that circle. Absent and present-but-silent are
  recorded identically.
- The transcript safety net (`inter_circle.short_term_backfill_step()`, run automatically before
  dreaming at every live close) explicitly **exempts** a part that did not
  speak — absence for a non-speaking part is correct, not a loss — so nothing
  alarms and nothing is backfilled.
- Result: no dream entry, no `long_term.md` change
  from that circle. The part's memory has a hole it cannot detect.

The one channel back in is Self. SYNTHESIS reads the **transcript**,
not the short_terms, so Self sees the whole circle regardless; whatever the
circle changed in `issues/*.toml` reaches every part's `circle_objectives` at
the next circle start. So an absent part learns of the circle secondhand, from
the issue graph's state, without a memory of its own. That is coherent IFS —
Self is the one present at everything — but it is not the same as having
been there.

Two practical consequences:

1. **Use the full roster for any circle you want to count.** `--live` with a
   reduced roster now prints the absent parts and requires you to type `yes`.
2. **A reduced dry-run test is invisible to the parts entirely** — it makes
   no model calls and writes nothing to `parts/`, so no part carries any
   memory of it. Free, and traceless by design; a LAB test round is
   remembered by the lab's own parts and by nothing here.

Tunables, none of them actually in `circle.py` (this line said "at the top of
circle.py" until audit-register.md #21 found otherwise): `MODEL`, `CACHE_TTL`
and the four rate constants live in `llm_client.py`; `MAX_SINCE_SELF` and
`MAX_TOKENS` (2500, not the 600 an earlier line in this file also had wrong)
live in `circle_rounds.py`. **The rates are still $2/$10 per MTok, verified
2026-07-26 and re-verified 2026-09-01** (audit-register.md #27) — this line
warned of a rise to $3/$15 on 2026-09-01 that Anthropic cancelled on
2026-08-10/11, making the $2/$10 introductory rate permanent
(platform.claude.com/docs/en/about-claude/pricing). Nothing to update.


## The three part files, and which one reaches a prompt

Ruled 2026-08-07 (R113, R114). The names now describe what they hold.

```
long_term.md      the RECORD. Identity plus the
                  historic dream corpus. It no
                  longer grows — dreams go to
                  short_terms.
short_term_<OT>   one circle, and its dreams —
                  `[[dreamt]]` in the .toml (since
                  2026-09-04, R434), `## Dreamt` in
                  a legacy .md. Append-only.
mid_term.md       the DISTILLATE. The only
                  per-part file a prompt carries.
```

`part_mid_term_manager.py` derives the third from the first two plus every `## Dreamt`
section, and `part_identity` reads it. A part with no distillate falls back to
the raw record — losing an identity to a missing cache file is the worst
failure available here.

**Staleness is a content hash over all sources plus the prompt version.** A new
circle's dream invalidates that part's distillate on its own; an unchanged day
costs nothing and makes no call.

`part_mid_term_project.py` (`midterms_project.py` until 2026-09-04) is the runbook: survey, pack, derive, write, verify. It
carries Self's prompt verbatim, the operational form actually run, and the
improvements still proposed. It cannot be imported — the hyphen is deliberate,
because everything importable belongs in `part_mid_term_manager.py`.

Measured across seven parts on the first full run: **230,324 characters of raw
`part_identity` became 46,515** — $0.230 of cache write per circle open became
$0.047, against $0.179 for a derivation run.

### Where a guard can be anchored, and where it cannot

Ruled 2026-08-07, denying a verifier I proposed for the distillate:

> *"The checkable claim would verify the presence of origins that large
> themselves carry the authority of an LLM derivation at circle time. The entire
> system is placing substantial trust in LLM derivations."*

```
ANCHORED    an ask fragment's backing quote
            sits in a part's STATEMENT — an
            event that happened in a room,
            recorded as said. Outside the
            derivation.
NOT         a mid_term's sources are
            long_term.md and `## Dreamt`
            sections. Both derivations.
```

Locating a phrase in a derivation proves two derivations agree, not that either
is true. **A guard that checks derivation against derivation is theatre with a
passing exit code.** So the distillate carries no verifier, deliberately, and
says so — what it carries instead is the hash of its sources, the model and
prompt version that made it, and an untouched record to read behind it.
