# MIDTERMS_PROJECT.PY(1)

## NAME
midterms_project.py — runbook documenting and driving the process by which each part's mid-term distillate gets produced: survey staleness, pack sources, derive via one call per stale part, write with provenance stamped, and verify structural soundness.

## SYNOPSIS
    python coordinator/midterms_project.py           the plan, and what is stale
    python coordinator/midterms_project.py --prompt  the derivation, verbatim
    python coordinator/midterms_project.py --pack Part#
    python coordinator/midterms_project.py --verify

## DESCRIPTION
This script documents and automates "THE RUN" — the ordered process by which the seven parts' mid-term distillates get produced. The docstring records that the first seven distillates were made by hand, in conversation, because the sandbox at that time had no route to the API; that worked once but is not repeatable, since a process that lives only in a transcript cannot be re-run, checked, or handed to a nightly job. This file is that process written down: the ordered steps, the prompt they use, and the checks that confirm a run was sound.

THE RUN, as laid out in the docstring, proceeds in five stages: (1) SURVEY — `mid_term.py` reports which parts are stale, absent, legacy, or locked, and how many source characters each has; a `locked` part belongs to Self and is skipped. (2) PACK — per part, assemble `long_term.md` (with settled content stripped), `dreams.toml`, every `## Dreamt` section newest-first, and the part's `remember.toml` chain: exactly the bytes the staleness hash covers (`part_relationships.toml` DROPPED as a source 2026-08-22, `mid_term.py` PROMPT v7). (3) DERIVE — one API call per stale part, using the SYSTEM prompt defined in `mid_term.py`. (4) WRITE — `mid_term.write()` stamps the source hash, model, and prompt version into the front matter. (5) VERIFY — confirms every part reads `fresh`, that the prompt block carries the distillate rather than the raw corpus, and that a part with no distillate still has an identity block.

The docstring records a cost measurement taken 2026-08-07 across all seven parts (roughly 54,479 input tokens / $0.109, roughly 7,000 output tokens / $0.070, total roughly $0.179, saving roughly $0.116 per circle opened), and states the design intent plainly: the run "should almost never run," because staleness is a content hash — an unchanged day costs nothing and makes no call. The practical trigger is a source moving, which in practice means a circle closed and dreaming wrote a fresh `## Dreamt` section.

The script also carries, verbatim in a module constant, Self's own preferred derivation prompt as given on 2026-08-07 (the second, tightened form, after seeing the first output), plus the added constraint that prior relationship and dreaming semantics must not be lost — the relationship half is superseded 2026-08-22 (`mid_term.py` PROMPT v7 drops relationships as a source entirely; the quote is kept as the record of what was first asked for). The change log of proposed prompt revisions moved to `coordinator/improvements.toml` on 2026-08-09 (it was a hardcoded data list with no code shape to it — the file's own `_improvements()` helper reads it at `--prompt` time). Each entry is tagged LANDED (now in `mid_term.SYSTEM`), DENIED (Self ruled it out, with the reasoning preserved so it is not re-proposed), or DEFERRED (real but unmeasured, awaiting evidence). One DENIED entry records Self's own reasoning at length: a proposal to make every claim traceable to a source phrase was rejected because checking a derivation's claim against another derivation ("the entire system is placing substantial trust in LLM derivations") only proves two derivations agree, not that either is true — summarized in the entry as "a guard that checks derivation against derivation is theatre with a passing exit code."

## MAIN
    read the command-line arguments after the script's own path;
    if (the first argument is "--prompt") then {
        import mid_term;
        print Self's own prompt verbatim;
        print mid_term.SYSTEM (the prompt as actually run, with its
            budget placeholder filled in) alongside its prompt version;
        print the IMPROVEMENTS log, each entry's status, title, and
            word-wrapped rationale;
        return 0
    } else if (the first argument is "--pack") then {
        print pack(<second argument>) — the exact packed source text for
            that one part; return 0
    } else if (the first argument is "--verify") then {
        return verify()'s exit code
    } else {
        import mid_term;
        compute survey() — one row per part: tag, staleness state,
            source character count, dreamt-section count;
        print a table of those rows;
        compute `todo`: the parts whose state is stale, absent, or
            legacy;
        print how many parts need deriving (listing them if any, else
            "nothing to do"), the total source character count and an
            estimated input-token count, and the active prompt version
            and character budget;
        if (todo is non-empty) then {
            print the five-stage pipeline summary and a reminder that
                --pack <part> emits the exact source text for one call
        }
        return 0
    }

## COMMAND-LINE ARGUMENTS
- `--prompt` (optional flag, mutually exclusive with the others by virtue of first-argument dispatch): prints Self's own verbatim derivation prompt, the operational SYSTEM prompt actually run (with its version), and the full IMPROVEMENTS change log.
- `--pack PART` (optional; requires a part tag as the next argument): prints the exact packed source text — the same bytes the staleness hash covers — for the named part, ready to paste into a manual call.
- `--verify` (optional flag): runs structural verification across all parts and returns a nonzero process exit code if any structural failure is found.
- No arguments (default): prints the survey table (per-part staleness state, source size, dreamt-section count) and a summary of how many parts need deriving.

## DEPENDENCIES
Standard library: `pathlib`, `sys`, `textwrap`, `__future__.annotations`, and `tomllib` (falling back to the third-party `tomli` on Python 3.10 and older — same fallback pattern used throughout this project's other TOML readers). Sibling modules, imported lazily inside functions rather than at module load: `mid_term` (for `state()`, `sources()`, `write()` semantics, `SYSTEM`, `PROMPT`, `BUDGET`) and `circle` (as `C`, for `PART_TAGS`, `load_shared()`, `block_order()`, `shared_block()`, `system_blocks()`). No third-party packages beyond that fallback, and no external programs are invoked directly by this script.

## EXTERNAL FILES
Read: `coordinator/improvements.toml`, directly, by `_improvements()` — the suggested-improvements change log, moved out of a hardcoded module constant 2026-08-09. Also, indirectly, whatever `mid_term.state()`, `mid_term.sources()`, and `circle.load_shared()` read from each part's directory (`long_term.md`, `dreams.toml`, `## Dreamt` sections, and `remember.toml`; NOT `part_relationships.toml` as of 2026-08-22, PROMPT v7).

Written: none directly by this script. `--pack` only prints to stdout; deriving and writing a distillate (stage 4, `mid_term.write()`) is not invoked from any code path in this file — the docstring frames the actual derive/write calls as made by hand, outside this script, using the packed text this script emits.

## NETWORK ACCESS
None made directly by this script. It documents and prepares for API calls (the derivation step) but does not itself place any network call; deriving a distillate is described as a separate, manual step using the text `--pack` emits.

## HUMAN I/O
No stdin. All output is to stdout: the survey table, the prompt/version/improvements dump under `--prompt`, the raw packed text under `--pack`, and the pass/fail report under `--verify`. Exit codes: `main()` returns 0 on every dispatch path except `--verify`, which returns `verify()`'s own result (1 if any structural failure was found, else 0).

## OPERATION

### `survey()`
    {
        for each part tag in circle.PART_TAGS, ask mid_term.state() for
        its staleness state and source-size info, and return one row per
        part: (tag, state, source character count, dreamt-section
        count).
    }

### `pack(part)`
    { return mid_term.sources(part)'s "text" value — exactly the bytes
      the staleness hash covers for that one part, ready to paste into a
      manual derivation call. }

### `verify()`
    {
        load the shared prompt blocks (core, briefing, conclusion) and
        the canonical block order once via circle.load_shared() and
        circle.block_order().
    }
    for each part tag in circle.PART_TAGS {
        get its staleness state via mid_term.state();
        if (state is stale, absent, or legacy) then {
            add it to the pending-derivation list — NOT treated as a
            failure, per the docstring's explicit design note that
            staleness is a queue, not a defect
        }
        build that part's shared block and its part_identity prompt
            section;
        if (the part_identity section is empty after stripping
            whitespace) then {
            record a structural failure: EMPTY part_identity
        }
        if (the part_identity section contains the raw "## Dream
            entries" heading AND the part's state is not "absent") then {
            record a structural failure: raw dream corpus reached the
            prompt
        }
    }
    print how many parts were checked, each recorded failure, the
        pending-derivation list if non-empty, and a final PASS or
        FAILURE(S) line;
    return 1 if any structural failure was recorded, else 0.

## BUGS
None found. `verify()`'s own docstring explicitly documents and defends the design choice most likely to look like a bug at a glance — treating "stale" as a queue state rather than a failure — with the historical note that the first version reported every deliberately-staged part as a failure, which would have made a healthy tree look broken on every prompt-version bump.
