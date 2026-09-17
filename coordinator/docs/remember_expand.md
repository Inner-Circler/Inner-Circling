# REMEMBER_EXPAND.PY(1)

## NAME

remember_expand.py — tier A of seed-anchored recall: at circle open, a part's own seeds that match the
day's topic, each quoted into BLOCK 4 beside a short excerpt of the circle that minted it.

## SYNOPSIS

    python coordinator/remember_expand.py "<topic>"                      the dry report, whole roster
    python coordinator/remember_expand.py "<topic>" --issues n9999   ...with a focus issue's Label

(As a library: `remember_expand_apply(parts, topic, chosen, ot, arm=...)` returns `{part: pack_text}`.
Its one call site is `role_attention.part_attention_finalize()`, which does the write. The arm is
`circle.py --recall-arm`, not a flag of this file.)

## DESCRIPTION

RULED 2026-08-29, the module name and the go both. At circle open, any seed in a part's own REMEMBER
register whose text overlaps the day's topic or focus issues is quoted in that part's BLOCK 4 with a
short excerpt of the circle that minted it — found by the seed's own `circle` field, a deterministic
dereference, never a search and never a model call. `docs/MEMORY_DESIGN.md`, "Tier A, detailed", is the
design.

**What it reaches past.** `remember_prompt_projection` shows a part a RECENCY window of its register, so
an evicted memory returns only when newer ones age past it. This is a second axis, not a second lever on
that door: candidates are the FULL register, deliberately, and the selection is topic-conditional,
per-circle and expiring. Because the pack QUOTES the seed beside its excerpt, all three visibility cases
— settled in BLOCK 3, tail in BLOCK 4, or out of view entirely — are served uniformly with no special
casing. The IFS consequence is named in the design and is close to the point of the work: an unresolved
`charged` seed will resurface whenever its topic returns.

**PLACEMENT (R387).** Content decides the block, and this content is each part's own private seeds — so
BLOCK 4 only, the uncached per-part tail. A pack is never cached and never survives its circle.

**READ-ONLY, WITH ONE NAMED EXCEPTION.** Nothing here touches a register, a transcript, or a part file.
The one write is the TRIAL LOG, `work/recall_trial/recall_<OT>.json`, one file per circle while the arm
is on — coordinator-written like a close report, gitignored, never shipped. The dry report below writes
nothing at all.

**NOTHING HERE MAY COST AN OPEN.** Every failure degrades rather than raising: a seed whose minting
circle is missing, unparseable, or has no close report contributes nothing; a blank topic with no
working set yields no terms and an empty pack; any exception anywhere in `remember_expand_apply()` is
caught, reported on the command channel, and the circle opens without packs.
`coordinator/tests/test_remember_expand.py` drives every row of that degrade table.

**The arm is a flag, not a file.** `circle.py --recall-arm off|delivered|withheld` decides whether packs
are computed, and whether a computed pack is delivered. Default: delivered (on), since R526, 2026-09-10;
off from R400 until then. `delivered` computes and delivers;
`withheld` computes and logs without delivering; `off` computes nothing. Anything unrecognized coerces to
off, the degrade direction. A flag per invocation cannot be forgotten in a settings file between a trial
and ordinary use, and it rides argv into the record. R460 (2026-09-06) closed the recall trial: recall is
a plain on/off feature now — the Ticker's Full Recall sends `delivered`, No Recall sends `off` — and
`withheld`, the control arm, is kept for a future trial with no UI that sends it.

**The write moved out, 2026-09-02.** `remember_expand_apply()` used to reach into `sysblocks` itself;
asked why a different file was touching a block it does not own, and with no ruling requiring it (R387
named the PLACEMENT, never the mechanism), it was changed to RETURN `{part: pack_text}` and hand it back.
`role_attention.part_attention_finalize()` is now the one and only writer of `sysblocks[p][3]["text"]`,
matching Block 1/2/3's own shape: an ingredient returns text, only the assembler touches the block. The
old confinement probe (apply may touch no index but 3) is moot — apply no longer receives `sysblocks` at
all, so the guarantee holds by construction rather than by a check.

**The dry report is this file's whole command-line interface**, and it is lab instrumentation a person
runs by hand between circles: what WOULD match for each part in the roster, given a topic. It builds
every pack through exactly the code an open uses, prints the matched-record log, and delivers nothing.
One difference from a live open, deliberate: it excludes no circle (`exclude_ot=""`), because there is no
circle being opened. A live pack always excludes the circle it is opening — that transcript already rides
every request through `prompt_messages_render()`, so quoting it back would be paying twice for the same
text.

### The constants

    PACK_HEADING     "## From your record, on today's matter" — the operator's default, accepted
                     2026-08-29 with the module name. Part-facing prose: theirs to reword.
    SEED_QUOTE_CAP   300. Characters of the seed's own text quoted above its excerpt.
    EXPAND_N         2. Seeds expanded per part per circle.
    EXPAND_CAP       1200. Characters of excerpt per seed — what ONE recall delivery may put in front
                     of a part. `recall_index.py` imports it as its whole-reply budget, SHARED
                     KNOWINGLY under the one-home rule (2026-08-30): both were sized by the same
                     question, and a future resize should move both.
    ARMS             ("off", "delivered", "withheld").

## MAIN

    read the command line: the topic (positional) and --issues.
    split --issues on commas, discarding empty pieces.
    if (any issue ids survived) then {
        read each one's Label through memory/issue_schema — remember_labels_read()
    } else {
        no labels; the terms come from the topic alone
    }
    for each part in the roster {
        build that part's pack from its whole register, with no circle excluded;
        print the part, how many seeds matched, and the pack's size in characters;
        for each matched seed {
            print its circle, its overlap count, its salience, and whether it dereferenced
                to an excerpt
        }
    }
    fall off the end — exit 0. (argparse exits 2 on a missing topic.)

## COMMAND-LINE ARGUMENTS

- `topic` (positional) — the topic text to match seeds against, as though it were the day's topic. It is
  lowercased and split into terms of four characters or more. **Required; there is no default** — argparse
  refuses a bare invocation with its usage line and exit 2.
- `--issues <ids>`: comma-separated ISSUE ids, each `n9999`-shaped, whose Labels join the topic's terms
  and whose ids are matched verbatim as well. **Default: none** — with no `--issues`, terms come from
  the topic alone. (`issue ids`, not `node ids`: R279, 2026-08-21, *"'node' is graph speak … do not
  surface 'node'."*)
- `-h` / `--help`: argparse's own; prints the usage and exits 0.

There is no `--arm` here and there should not be: the arm belongs to a circle, and this report neither
delivers nor logs.

## DEPENDENCIES

`seam` (the command channel, for `remember_expand_apply()`'s one-line summary and its failure notice);
`remember_manager` as `RM` for `remember_read()` and `SALIENCE_WEIGHT`; `part_roster` as `R` for
`ROSTER`; `transcript_store` as `TS` for `circle_transcript_parse()`; `record_paths` for `ROOT` and
`record_dir()`. `memory/issue_schema` is imported function-locally inside `remember_labels_read()`, after
putting `memory/` on `sys.path` — the same hop `circle.py` makes. Standard library: `json`, `re`, `time`,
and `argparse` in `__main__`. No third-party packages.

## EXTERNAL FILES

READ:

    parts/<part>/remember.toml       every record on file, through remember_manager.remember_read().
                                     Only roster parts are ever passed, so that module's "self" path
                                     rule — self/remember.toml — is never reached from here.
    issues/*.toml                    only when focus ids are given, through memory/issue_schema — the
                                     one reader. A node that cannot be found or loaded contributes
                                     nothing rather than raising.
    work/logs/close_<OT>.json        the read gate on a seed's minting circle: no close report, no
                                     excerpt. A partial transcript is well-formed, so this is the test
                                     that keeps a circle still in flight out of any pack. Root-level,
                                     not group-scoped.
    circles/circle_<OT>.md           the minting circle itself, through record_dir(ROOT, "circles") —
                                     the group's own tree — parsed by transcript_store.

WRITTEN:

    work/recall_trial/recall_<OT>.json   the trial log: the arm, the topic, the chosen focus ids, and
                                         per part the matched-record rows, the pack's size, whether it
                                         was delivered, and the pack text. Written only by
                                         remember_expand_apply(), only with the arm on, LF newlines.
                                         Gitignored; never shipped.

## NETWORK ACCESS

None. No model calls, ever — the whole mechanism is keyword and node-id overlap plus one deterministic
dereference, which is what makes it affordable at every open.

## HUMAN I/O

No stdin. The dry report prints to stdout. `remember_expand_apply()` prints nothing directly: it emits
one summary line on the `command` channel (`recall: arm=… — packs for n/m part(s), N chars`), or, on any
failure, one notice saying the pre-fetch was skipped and the circle opens without packs.

## OPERATION

### remember_terms_read(topic, labels)
    lowercase the topic and every label, joined;
    return (the words of four characters or more, the nNNNN ids found).

Words shorter than four characters are noise, not signal.

### remember_labels_read(chosen)
```
if (nothing was chosen) then {
    return no labels.
} else {
    put memory/ on sys.path and import issue_schema;
    for each node file in the graph {
        if (its id is in the chosen set) then { keep its label }
        (any failure reading one node is swallowed — it contributes nothing)
    }
    return the non-empty labels.
}
```

### remember_overlap_read(body, words, nids) / remember_qualifies(body, words, nids)
The count of distinct terms present in the seed's text, and the design's deterministic match rule over
it: a seed qualifies on one exact node-id hit, or on two or more distinct word hits.

### _chain_depth(records)
    id -> how many records this one's chain walks back through, memoised, cycle-guarded by the set of
    ids already on the walk.

Local and cheap rather than reaching into `remember_manager`'s private helper.

### remember_select(records, words, nids, exclude_ot, cap)
```
for each record {
    if (it carries a class, or has no circle field) then { skip — a migration row is not a seed }
    else if (its circle is the one being excluded) then { skip }
    else if (it does not qualify) then { skip }
    else { score it: overlap, then salience weight plus chain depth, then date }
}
sort by that triple, descending; return the first `cap` of them.
```

The rank is the design's: overlap first, then the mechanical salience score the 2026-08-22 salience work
already defines, then recency. No in-view-versus-omitted tiebreak — the score already says what the
register thinks matters.

### _closed(ot)
Whether `work/logs/close_<OT>.json` exists.

### remember_span_read(entries, seed_text, part_tag, char_cap)
```
draw terms from the SEED's own text;
drop the topic row; if (nothing is left) then { return the empty excerpt }
find the statement with the most term hits.
if (one was found) then {
    take two statements before it and one after.
} else {
    # dream-authored seeds paraphrase, so nothing need match
    find the minting part's own last statement; if (it never spoke) then { return the empty excerpt }
    take one neighbour either side of it.
}
render each as "[<display>]: <text>", truncating at the character cap and stopping when it is spent;
return them joined by newlines.
```

Pure over already-parsed entries, which is why the probe can drive it directly.

### remember_dereference(ot, seed_text, part_tag, char_cap)
    OT -> transcript -> span.
    if (that circle has no close report) then { return the empty excerpt }
    if (its transcript file is absent) then { return the empty excerpt }
    parse it and return the span.
    (any exception returns the empty excerpt — a damaged record is the audit's to report, not this
    module's to raise on at an open)

### remember_pack_build_from(records, part_tag, topic, labels, exclude_ot) / remember_pack_build(part, …)
```
if (the topic and labels yield no terms at all) then { return an empty pack and an empty log. }
select up to EXPAND_N seeds;
for each of them {
    dereference it to an excerpt;
    log the circle, date, salience, overlap, and whether it expanded;
    if (there is no excerpt) then { contribute no section }
    else { a section: the seed quoted to SEED_QUOTE_CAP, then the excerpt }
}
if (no section survived) then { return an empty pack, with the log }
else { return PACK_HEADING followed by the sections, with the log }
```

The log row is written whether or not the seed expanded, which is what makes the trial log able to
distinguish "nothing matched" from "matched but could not be dereferenced".

### remember_expand_apply(parts, topic, chosen, ot, arm=None)
```
coerce an unrecognized arm to "off".
if (the arm is off) then { return no packs — nothing is computed, nothing is logged. }
read the chosen focus nodes' labels;
for each part {
    build its pack;
    it is DELIVERED only if the pack is non-empty and the arm is "delivered";
    record its matched rows, its size, whether it was delivered, and the pack text;
    if (delivered) then { add it to what is returned }
}
write the trial log; emit the one-line summary on the command channel.
(any exception anywhere above: emit the skipped notice and return whatever was collected — NEVER raise)
```

Returns `{part: pack_text}` for every part whose pack should reach BLOCK 4 this circle. The withheld arm
therefore returns nothing while still logging every computed pack in full — the control arm costs nothing
and the comparison is against identical machinery.

## BUGS

None found. Three characteristics that read as defects and are not:

**Term matching is substring, not word-boundary.** `remember_overlap_read()` asks whether each term
appears anywhere in the seed's text, so a topic term matches inside a longer word. It widens the match
set slightly in the generous direction, which is the right direction for a mechanism whose failure is a
missed memory rather than a wrong one, and the two-hit threshold is what keeps it from firing on noise.

**`EXPAND_N` and `EXPAND_CAP` are module constants, not settings.** `docs/MEMORY_DESIGN.md` proposed both
as `setting_value_read(...)` values on the `SALIENCE_K` precedent; the build made them plain constants, so
a resize is a code edit here rather than a `self/settings.toml` change. `EXPAND_CAP` is still ONE home —
`recall_index.py` imports it rather than restating it.

**`remember_labels_read()` puts `memory/` on `sys.path` on every call and never removes it.** The same hop
`circle.py` and `circle_delta.py` make, and idempotent in effect; it is a duplicate entry, not a leak.
