# INTER_CIRCLE(1)

## NAME

inter_circle.py — what happens between circles: each part dreams, then one pass looks at the circle as a whole.

## SYNOPSIS

    python coordinator/inter_circle.py --ot 2026-08-15_1900 --live    process it
    python coordinator/inter_circle.py --ot 2026-08-15_1900           rehearse it
    python coordinator/inter_circle.py --ot <OT> --group band --live  a named group's re-run

`--group <name>`: process a circle of `groups/<name>/`'s record. Parsed from argv by hand, not by
argparse (`:910-911`), which is why a flag scan that reads `add_argument` calls alone will miss it.
Default: unset — the DEFAULT GROUP, which is a rule and not a name (R468, B120 stage 4).

## DESCRIPTION

A circle ends, and then the work that makes the next one different begins. Each part revisits what it has just been through and lets its own sense of itself move — that is **dreaming**. Then one pass looks at the whole circle rather than at any part in it, and writes what it noticed — that is **synthesis**.

This module is both, for **one** circle. The name is precise about it: this is what happens *between* circles, not *across* them.

**You do not normally run this.** It is the second phase of `/close`, run in the same process, immediately after the circle itself is already safely committed. What you would type this for is the **re-run** after a failure — the command line above is exactly that, the same code the close calls, pointed at a circle that has already closed.

**The bare form rehearses.** Real model calls, real staging, the real gate — and then a report instead of a commit, with the staged material kept where you can look at it. `--live` is what commits.

### The shape

    1  DREAMING     one model call per part, all parts at once. Each returns a
                    payload — at most one memory — and writes nothing itself.
    2  SYNTHESIS    one circle-wide call over EIGHT inputs: the transcript; each
                    part's fresh dreaming record; that material narrowed to its
                    high-salience rows, for the CIRCLE JOURNAL; the proposals Self
                    confirmed; the current account of Self; the previous circle's
                    history entry; the previous circle's journal entry; and the
                    closing instruction. This said FIVE and named none of the
                    journal three until 2026-09-09 (audit-register 2026-09-09 #56);
                    circle_synthesis.py builds all eight.
    3  VALIDATE     every payload against the writer-scope matrix and each
                    register's own rules — caps refuse, required headings must hold.
    4  RENDER+STAGE each register renders its own new material using the same code
                    the ordinary direct writers use; the bytes are staged, not
                    written.
    5  GATE         the register gate judges the staged tree against the current
                    one. Any failure leaves the tree untouched and the staging kept.
    6  COMMIT       the staged bytes land, the parts whose sources moved have their
                    distillate re-derived, and one commit records all of it.

**Nothing in phases 1 to 5 writes anything.** That is the design, not an implementation detail: staging is all-or-nothing, so a failed run wrote nothing at all, which is what makes a re-run clean by construction. There is no automated catch-up and no partial state to reconcile.

**Privacy is mechanical here.** Synthesis is handed each part's one fresh dreaming record in memory, from the dreaming payloads. It never reads any part's private remember register, and the writer-scope matrix means only what a payload actually grants can be staged. The gate then verifies it after the fact.

**A part that spoke never reaches dreaming as though it had been silent.** Before anything else on a live run, a backfill step repairs any speaking part whose note went missing, from the transcript. The order matters: repair first, then dream, or the file is fixed and the dream is not.

**Every call this module makes that writes the record is on record itself — R412 (2026-08-30), R413 (2026-08-31).** Each dreaming request, the synthesis and its insisted re-ask, a safety-net reconstruction, and the mid_term refresh it triggers are written to the circle's own capture, `work/prompts/<OT>/`, as they are sent — the string system prompt, the one user message, the raw reply and its thinking — in the same per-request files the parts' own turns use, under the contract's second shape. The synthesis speaks for no one part, so its file is named by kind. The failure diagnostic is not recorded: it writes nothing. Under a live `/close` the capture is already open (circle.py's); a hand re-run opens it itself and closes it after. Those files land after the close commit took the directory, so the dream commit carries them — and is made for them even when no register moved.

**Running twice is refused.** A completed run leaves a durable marker, and the guard consults it. There are two forms of that marker, and either one refuses a re-run: a file under `work/logs/`, written last by a successful run, and a git tag. The file exists because version control is optional here — a tree with no history has nowhere to keep a tag.

The guard is careful in one specific direction: it must never answer "not processed" because the check itself failed, since that answer causes a circle to be dreamt twice. So where a history exists and git cannot answer, it raises rather than guessing. Where there is no history at all, no tag could exist, so the file is the whole record and its answer stands.

**On failure** it writes `work/logs/dream_error_<OT>.json`, makes one diagnostic model call (surviving that call's own failure), prints the diagnosis and the exact re-run line, and exits non-zero.

**This is live-only.** A practice circle never reaches it, because synthesis writes to Self's own files, which no practice run may touch.

**One register is inert by ruling.** The relationships each part kept about the others is no longer written or read — a part's last converged record simply stopped updating. Nothing in the dreaming prompt or its output spends attention on it any more.

## MAIN

    Read the command line.
    if ("--ot" is absent) then {
        print the usage line and return 1.
    }
    Take the open time that follows it.
    Run circle_process for that circle, live only if "--live" is present.

## COMMAND-LINE ARGUMENTS

    --ot <OPEN_TIME>   required. The circle to process, as YYYY-MM-DD_HHMM.
    --live             commit the result. Default: off — the bare form makes the
                       same real model calls and stages the same material, then
                       reports instead of committing.

## DEPENDENCIES

Every register module it writes through — `remember_manager`, `topic_manager`, `circle_history_manager`, `circle_observation_manager`, `practice_manager` — plus `part_mid_term_manager` for the re-derivation, `TRANSACTION_CLASS` for staging, `backfill` for step 0, `part_dreaming` and `circle_synthesis` for the two model passes, `llm_client` and `LLM_response_disassembler`, `setting_manager`, `phase_clock`, `prompt_capture`, `part_roster`, `REGISTER_CLASS`, and `gitrepo` for the marker tag. `concurrent.futures` runs the parts in parallel. The issue-graph code under `memory/` is on the import path.

## EXTERNAL FILES

    circles/circle_<OT>.md               READ — the transcript, the primary input
    parts/<name>/short_term_<OT>.toml    READ, and repaired by the backfill step
                                         (.md before 2026-09-04, R434)
    parts/<name>/remember.toml           WRITTEN — one memory per part, at most
    parts/<name>/mid_term.md             RE-DERIVED for the parts whose sources moved
    self/topics.toml                     WRITTEN — synthesis's candidates
    circles/circle_history.toml             WRITTEN — one entry for this circle
    circles/circle_observation_log.toml       WRITTEN — one observation
    self/best_practices.toml             WRITTEN — confirmed practices
    work/logs/dream_<OT>.json            WRITTEN last by a successful run: the marker
    work/logs/dream_error_<OT>.json      WRITTEN on failure, with the diagnosis

## NETWORK ACCESS

One model call per part for dreaming, all in parallel; one circle-wide call for synthesis; one more only if a run fails, for the diagnosis. Nothing else.

## HUMAN I/O

Narrates to stdout through a `say` parameter (default `print`), so the close can route it into the command pane. Reads no input — there is nothing to answer here; every decision was made before this phase began.

Per part it reports the character counts of what it was given, what it produced, whether anything was truncated or looked suspect, and — on every line since the truncation lessons of 2026-08-21 — the two numbers that explain a truncation: how many output tokens the call spent, thinking included, and why it stopped.

## OPERATION

### circle_is_processed(ot) (`already_processed()` before the B99 re-homing, 2026-09-03)
    if (the marker file for this circle exists) then { return processed. }
    if (there is no version-control history in this tree at all) then {
        return not processed — the file was the whole record, and it said no.
    }
    Ask git for this circle's tag, using the same namer the writer uses (so a lab
        tree asks about the lab-stamped name a lab run actually writes).
    if (git cannot answer) then { RAISE — never guess, because guessing "no" here
        dreams the same circle twice. }
    return whether the tag exists.

### short_term_backfill_step(ot, say) (`backfill_step()` before the B99 re-homing, 2026-09-03)
Step 0 of every live run: any part that spoke but has no well-formed note is rebuilt from the transcript, so it reaches dreaming as a part that participated rather than one that had nothing to say.

### part_dream(part, ot, transcript, capsule="") — MOVED to part_dreaming.py, 2026-09-03 (stage 11)
One part's dreaming call. Returns a payload describing at most one memory — with its salience, and whether it continues an earlier one — plus the character counts, anything truncated or suspect, the output token count and the stop reason. It writes nothing. Since 2026-09-04 (R451, D86 a) its prompt reads the part's own lines from the transcript, not the whole thing, plus `capsule` — the one shared paragraph `circle_capsule_build()` builds once per circle, below.

### circle_capsule_build(ot, transcript, say) — part_dreaming.py, R451 (D86 a), 2026-09-04
ONE model call per circle, made before the seven parallel dreaming calls: a short shared paragraph covering what happened in the room, the same text every part reads alongside its own lines. Best-effort — a failed or unparseable call degrades to an empty capsule and a diagnostic line, never a refusal to the run.

### circle_synthesise(ot, transcript, payloads, ...) — MOVED to circle_synthesis.py, 2026-09-03 (stage 11)
The one circle-wide call, over the five inputs named above. Returns the material for the circle-level registers; like dreaming, it writes nothing.

### circle_process(ot, live, confirmed, say) (`process_circle()` before the B99 re-homing, 2026-09-03)
    if (this circle was already processed) then {
        say so, name the marker, and return 1 — re-running would double-dream it.
    }
    if (there is no transcript for that open time) then {
        say so and return 1.
    }
    if (live) then { run the backfill step; if it fails, stop here. }
    Build the shared room capsule, once (R451, D86 a, 2026-09-04).
    Dream every part in parallel, collecting payloads and reporting each as it
        lands.
    Synthesise over the transcript and those payloads.
    Validate, render, stage.
    Gate the staged tree against the current one; any failure stops here with the
        tree untouched and the staging kept.
    Re-derive the distillate for the parts whose sources moved; commit the staged
        files, the distillates, and every file in the circle's capture (the turns
        recorded since the close commit took it — made even when nothing was
        staged); record the marker.
    Return 0.
    (Around all of it: a live run with no turn log open — the hand re-run — opens
        the circle's own capture first and closes it after; under /close the log
        is circle.py's and is left as found.)

## BUGS

None found.
