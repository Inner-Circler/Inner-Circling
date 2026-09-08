# DREAM_HISTORY(1)

## NAME

dream_history_manager.py — DREAM_HISTORY: the bounded standing summary of what Self's dreaming corpus has concluded.

## SYNOPSIS

    python coordinator/dream_history_manager.py               state, writes nothing
    python coordinator/dream_history_manager.py --bootstrap   the one bootstrap derivation
    python coordinator/dream_history_manager.py --fold        fold every unfolded dream
    python coordinator/dream_history_manager.py --show        the current DREAM_HISTORY, whole
    python coordinator/dream_history_manager.py --selftest    the pure helpers, no model call

## DESCRIPTION

Self's dream corpus never shrinks. It is kept whole and never pruned, by ruling — which is right for a record and useless as a thing to read. This module gives that corpus a **bounded summary**: one standing account, under a thousand words, of what the dreaming has concluded.

The summary lives in the same file as the corpus, as records marked `section = "history"` rather than `section = "dream"`. **The newest history record is the current DREAM_HISTORY**; the older ones are the account of how it got there. Each record names the dream ids it folded, so a summary always sits beside its dated sources and can be re-derived and checked — that was the condition attached to allowing a summary at all.

**Nothing reads this into a prompt, and nothing should.** No part ever sees it. An earlier ruling had named a destination inside a part's identity block, and a later one struck that destination while keeping the derivation. There is no route into a prompt here; do not look for one and do not build one.

**The shape is one bootstrap, then one fold per dream.** The first derivation runs over the whole corpus at once. Every derivation after that takes the prior summary plus one new dream and produces the whole replacement summary — the production read literally, from the bootstrap forward. Batch-writing the record once per historic dream would have produced a truer-looking history and a false one; running it forward from a single bootstrap keeps the checkable property without pretending the summaries were written at the time.

**Each derivation asks for the WHOLE replacement, not an addition.** That is what keeps it bounded: a summary that only ever accumulates would grow with the corpus, which is the thing this exists to avoid.

**This module is the one writer, and it only ever adds history rows.** The dream corpus rows themselves are written by nothing, anywhere in the project, and this module preserves that.

**Three guards, each inherited from a mistake:**

    a reply that stopped at max_tokens is REFUSED, never written — the model's
        thinking spends from the same budget, so a capped reply is a document cut
        mid-sentence however long it looks
    a reply over 1000 words is truncated at a whitespace boundary and reported
    a bootstrap refuses outright when any history record already exists

## MAIN

    Parse the arguments.
    if (--selftest) then { run the pure-helper self-test; return its result. }
    if (--bootstrap) then { run the bootstrap; return its result. }
    if (--fold) then { fold every unfolded dream; return its result. }
    Load the register.
    if (--show) then {
        if (a history exists) then { print its content whole. }
        else { print "(no DREAM_HISTORY yet — run --bootstrap)". }
        return 0.
    }
    otherwise print the state — how many dream records the corpus holds, how many
        history records exist and which is newest, and how many dreams are not yet
        folded — and return 0.

The bare invocation writes nothing and makes no model call.

## COMMAND-LINE ARGUMENTS

    (none)        print the state. Writes nothing, calls nothing.
    --bootstrap   the one bootstrap derivation over the whole corpus. Makes a real
                  model call. Refuses if any history record already exists.
                  Default: off.
    --fold        fold every dream not yet covered by a history record, one
                  derivation each. Makes real model calls. Refuses if there is no
                  history to fold into. Default: off.
    --show        print the current DREAM_HISTORY in full. Default: off.
    --selftest    exercise the pure helpers against a fabricated register. No
                  model call, no file written. Default: off.

## DEPENDENCIES

`REGISTER_CLASS` for load and save (`self_schema` until 2026-09-03); `LLM_response_disassembler` for every read of a reply; `llm_client` for the model call itself (`stream_call_once`, which owns the client, the key resolution, the retry ladder and the meter — 2026-08-28). `pathlib`, `sys`, `datetime`, `copy`, `argparse`, `os`. It no longer imports `anthropic` at all.

## EXTERNAL FILES

    self/dreams.toml    READ by every verb. WRITTEN by --bootstrap and --fold, and
                        only ever by appending section="history" rows. ABSENT is
                        read as an empty corpus (`register = "self_dreams"`,
                        `next_id = 1`, no rows) since B111, 2026-09-06 — the file
                        never ships, and a fresh install's first run used to die on
                        file-not-found; a read never creates it, and --bootstrap on
                        an empty corpus reports so and exits 1.
    .env                READ only when ANTHROPIC_API_KEY is absent from the
                        environment, and only on a verb that calls the model.

## NETWORK ACCESS

One model call per derivation — one for `--bootstrap`, one per unfolded dream for `--fold`. Every other verb, including the bare invocation and `--selftest`, makes none.

## HUMAN I/O

Prints to stdout through a `say` parameter (default `print`), so a caller can capture the narration. Reads no input.

## OPERATION

### corpus(doc) / histories(doc) / latest_history(doc)
The `section = "dream"` rows, sorted by date then id; the `section = "history"` rows in file order; and the last of those, which is the current DREAM_HISTORY.

### dream_history_covered_read(doc) / dream_history_unfolded_read(doc)
(`covered_ids()`/`unfolded()` before the B99 re-homing, 2026-09-03.)
Every dream id named as a source by any history record; and the corpus rows not among them — the work `--fold` has left to do.

### truncate_words(text, cap) — MOVED
    LLM_response_disassembler.word_cap(text, cap), 2026-09-02: the same split
    on whitespace, the same (text, cut) answer, beside every other read of a
    reply. _derive() calls it on the Reply's text.

### dream_history_render(doc, content, sources, title) (`render_history()` before the B99 re-homing, 2026-09-03)
    Work on a deep COPY of the register.
    Mint "SD-" plus the register's next_id, four digits.
    Record today's UTC date, the title, section "history", the sorted source ids,
        and the stripped content.
    Append, advance next_id, return (the new register, the new record).

Pure. The corpus rows are not touched, which is this module's one-writer promise made mechanical.

### _call(user, client)
Sends the system prompt and one user message, returns the reply text and the stop reason. The client is injectable so no test reaches the network.

**Through `llm_client.stream_call_once()` since 2026-08-28** (stage 1 of the provider socket). It previously built its own client and resolved the key by hand-parsing `.env` for a line starting `ANTHROPIC_API_KEY` — which finds a key in the file even when the shell has set a different one, inverting this project's own precedence. A fold now rides the retry ladder and reaches the one meter; the injection contract is unchanged.

### _derive(prior, dreams, client, say)
    Build the message: the prior DREAM_HISTORY (or an explicit note that this is
        the bootstrap and there is none), then the dream record or records to fold.
    Call the model.
    if (it stopped at max_tokens) then { say REFUSED and return nothing. }
    if (the reply is empty) then { say REFUSED and return nothing. }
    Truncate to the word cap; if that cut anything, say so.
    Return the text.

### dream_history_bootstrap(client, say) (`bootstrap()` before the B99 re-homing, 2026-09-03)
    if (any history record exists) then { say REFUSED — the bootstrap runs once —
        and return 2. }
    if (the corpus is empty) then { say there is nothing to bootstrap; return 1. }
    Derive one history over every dream record.
    if (the derivation was refused) then { return 1. }
    Render and save it, naming every corpus id as a source.
    Say what was written, with its word count and source count; return 0.

### dream_history_fold(client, say) (`fold()` before the B99 re-homing, 2026-09-03)
    if (no history record exists) then { say REFUSED — bootstrap first — and
        return 2. }
    if (nothing is unfolded) then { say the history is current; return 0. }
    FOR EACH unfolded dream, oldest first:
        Re-load the register and take the newest history as the prior.
        Derive the whole replacement from (prior + this one dream).
        if (the derivation was refused) then { return 1. }
        Render and save a new history record naming this dream as its source.
        Say what was written.
    return 0.

Re-loading inside the loop is deliberate: each fold must see the record the previous fold just wrote, since that is the prior it derives from.

### selftest()
Ten checks over a fabricated register: corpus ordering, the absence of a history before a bootstrap, what counts as unfolded, that rendering mints the next id as a history record and leaves the corpus rows alone, that nothing is unfolded afterwards, that a newly added dream becomes the one unfolded row, which record `latest_history` picks, and both sides of the word cap.

## BUGS

None found. One behaviour worth naming so it is not read as a defect: `--fold` returns 1 and stops at the first refused derivation rather than continuing to the next dream. That is intentional — folds are sequential, each deriving from the one before, so continuing past a failure would produce a history with a hole in its chain.
