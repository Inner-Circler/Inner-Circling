# PROMPT_CAPTURE.PY(1)

## NAME
prompt_capture.py — saves what each part was sent, verbatim, per circle: the four system blocks once, as one file per block, and then every request the transport sends on a part's behalf, one JSON file per request — and, since R412/R413, every request the coordinator sends for itself at a live /close that writes the record (dreaming, synthesis, the mid_term refresh, the coalesce pass); verifies that every saved file still reproduces its recorded bytes.

## SYNOPSIS
```
python coordinator/prompt_capture.py --verify           # check every capture
python coordinator/prompt_capture.py --verify <OT>       # check one circle's capture
python coordinator/prompt_capture.py --stats [<OT>]      # per-block, per-item character counts
```
(As a library: `write(ot, sysblocks, notes, live, names=None)` from `circle.py` at circle open; `open_turn_log(dir, ot)` right after it — and from `inter_circle.process_circle()` for a hand re-run, which opens the circle's own capture and closes it after; `record_turn(part, kind, request, response, dry_run, error)` from `llm_client.py` on every request, `part` None for a call made for no one part; `discard(dir)` from `circle.py` when an unspoken circle is withdrawn; `read_manifest(dir)` and `block_shas(manifest)` for the resume compare.)

## DESCRIPTION
The system prompt sent to a part is GENERATED CODE — `prompt_build.system_blocks()`
assembles it per part per circle from `process_core.md`, the live issue graph, the
part's distillate and its registers — and until 2026-08-01 nothing in the project
looked at the emitted artifact, only at its sources. Two defects found that day were
invisible from the sources (a filter leak, LOG E09, and a truncated practice shipped
mid-sentence); both were found only by rendering a part's actual prompt and reading
it. The module's principle: **check the emitted program, not only the inputs to the
generator.** Self's ruling, 2026-08-01: save the prompts, verbatim, per part, per
circle — *"Dreaming and synthesis will be watching for patterns to be selected in the
coming years."*

**THE LAYOUT IS R277's (2026-08-21), and it replaced the old one outright** — no
backward compatibility, the six old captures deleted the same day (git has them).
One directory per circle, `work/prompts/<OT>/` live or `work/sandbox/prompts/<OT>/`
under the retired `--minimal` mode (R360), holding:

- `Block1_circle_identity.md`, `Block2_circle_objectives.md` — the two SHARED blocks,
  written ONCE per circle;
- `Block3_<part>_identity.md`, `Block4_<part>_objectives.md` — per part;
- `Per_turn_<part>_<time>_<seq>.json` — ONE PER REQUEST that carried the part's
  system prompt: the pre-warm, each statement and its truncation retry, the `/close`
  short_term and its retry (not the API ping, not a token count); AND, since R412
  (2026-08-30) and R413 (2026-08-31), one per PROCESSING request — every call the
  coordinator makes for itself at a live `/close` that writes the record: dreaming
  (per part), the synthesis, the mid_term refresh (per part), the coalesce pass.
  Those carry the contract's SECOND SHAPE — one plain-string system prompt inline,
  exactly one user message, the same reply record — and the two circle-wide kinds
  have no part, so the KIND fills the slot: `Per_turn_synthesis_<time>_<seq>.json`,
  `"part": null` in the body. Not the failure diagnostic, which writes nothing;
- `manifest.json` — sha256, size, chars, cached flag and per-item counts per Block
  file; the per-part file lists; one record per turn file.

A Block file IS the block's bytes — no header, no delimiter, nothing to slice; the
old one-file-per-part capture interleaved delimiters and sliced blocks back out by
manifest offsets. All four blocks are static for the whole circle (built once at
open, never rebuilt), which is what makes one file per block the right shape.

A per-turn record is the Messages-API request body as sent — `model`, `max_tokens`,
`system`, `messages` — plus the reply. Blocks 1-3 in `system` are written BY
REFERENCE to their Block files (`file` + `sha256`, same bytes) because the ruling's
own PER_TURN_CONTENT excludes them; BLOCK 4 is inline and marked `"block":
"part_objectives"`. A block whose text does not match its Block file (no such case
exists today) is written inline with `"differs_from_capture": true`, so the record is
exact whatever the generator does. `messages` is recorded from the part's own last
statement — its last assistant turn — through the closing line (Self: *"only send
the tail of the transcript.. from the last statement of the part through
current"*); what precedes it is the transcript as it stood, and `messages_omitted`
records how many turns were trimmed and the sha256 of their JSON. A part that has
not spoken has no anchor and its messages are recorded whole. THE REQUEST ITSELF IS
NOT TRIMMED — what a part is sent is `prompt_build.render_messages()`'s business;
this module only records it (D57 asked whether the sending should narrow too; R278 ruled
no — the whole transcript is sent).
`response.text` is the RAW reply, before `rounds.ask_statement()` strips a sign-off,
a `[To: ...]` or a bracket and before "[pass]" becomes silence, with the stop reason
and the usage object as a dict. It is the text BLOCKS — this line called it "what the
model actually returned" until 2026-08-29, which was overbroad: a reply also carries
the model's reasoning, on every statement.

`response.thinking` is that reasoning, kept since the operator ruled it kept —
`llm_client.RECORD_THINKING`, a yes/no setting, default on. The provider extracts it,
because where reasoning sits in a reply is one vendor's business. Two bounds on what
it is worth: it is a SUMMARY the service returns rather than the raw trace, and the
KEY'S PRESENCE is the record of the setting — empty means "recording was on, the model
thought nothing", absent means "recording was off, or the capture predates this".
`thinking_redacted_blocks` appears only when a reply carried reasoning this project
cannot read, so a partial record never passes for a whole one. The transcript is
unaffected either way: thinking never enters the room.

Verbatim-ness is enforced at write (every Block file is re-read and compared
byte-for-byte against what was sent; a SHARED block that differs between parts is
refused before anything is written) and re-checked by `--verify`, which re-hashes
every file, asserts no SHARED block carries a part-addressed marker (E09), and
asserts every turn file's block references resolve to the Block files by sha — the
static-blocks claim, proven per request.

`--verify` also holds every request to **the wire contract**, `coordinator/
turn_contract.toml` (R368). The sha checks prove a capture has not been altered
since it was written; the contract proves what was written was the shape the code
is supposed to send: the four blocks in order, `cache_control` on 1-3 and never on
4, a messages tail that alternates and ends on the cue, `model` equal to
`llm_client.MODEL` (grepped from the source, never imported, so this stays cheap
enough for the pre-commit hook), a pre-warm asking for no output, and a response
in either the live shape or the narrower dry-run one. A missing contract file is
reported as a NOTE, never passed over in silence. `check_contract()` is the one
reader; `coordinator/tests/test_turn_contract.py` breaks one thing at a time and
asserts each rule still refuses, so the walker cannot quietly stop walking.

Size: ~80 KB of Block files per circle for
seven parts (the shared blocks once, not seven times), plus one turn file of a few KB
per request; a content-addressed store is still deliberately not built.

## MAIN
There is no `main()`; `__main__` dispatches directly:
```
if ("--stats" is in argv) then {
    call stats(the argument after it, if any, else None) and exit with its code.
} else {
    strip "--verify" from argv;
    if (an argument remains) then { call verify(that argument) }
    else { call verify(None) — every capture under both roots };
    exit with verify()'s code.
}
```

## COMMAND-LINE ARGUMENTS
- `--verify [OT]` — re-hash every Block and turn file against the manifest and run
  the leak and reference checks. Without an open time, every capture under both
  roots; with one, that circle's capture in whichever root has it. Default when no
  flag is given.
- `--stats [OT]` — print the per-block, per-item character breakdown recorded in
  the manifest at circle open, and the turn-file count and bytes.

## DEPENDENCIES
Standard library: `datetime`, `hashlib`, `json`, `pathlib`, `re`, `sys`,
`threading`. Sibling modules: `roster` (as `R`, for `R.TAGS`/`R.TAG_BY_DIR` →
`PART_TAGS`/`PART_TAGS_BY_DIR`), `paths` (`ROOT`, `SANDBOX`), `atomic_write`. No
third-party packages, no external programs, no network access.

## EXTERNAL FILES
Read: `work/prompts/<OT>/manifest.json` and `work/sandbox/prompts/<OT>/manifest.json`
(by `verify()`, `stats()`, `open_turn_log()`, `discard()`, `read_manifest()`); every
Block and turn file a manifest names (by `verify()`); the just-written Block and turn
files (re-read by `write()` and `record_turn()` to prove the bytes).

Written (all through `atomic_write`, LF only): under the capture directory —
`Block1_circle_identity.md`, `Block2_circle_objectives.md`,
`Block3_<part>_identity.md`, `Block4_<part>_objectives.md`, `manifest.json` (by
`write()`); `Per_turn_<part>_<YYYY-MM-DD_HHMMSS>_<NNN>.json` and a rewritten
`manifest.json` (by `record_turn()`). Removed: exactly the files the manifest lists,
the manifest, and the directory if emptied (by `discard()`). A non-live circle with
no `sandbox_dir` writes nothing (`write()` returns `None`, and `open_turn_log(None)`
makes `record_turn()` a no-op).

## NETWORK ACCESS
None.

## HUMAN I/O
No stdin. `verify()` prints how many circles, Block files and turn files were
re-hashed, a `note` line for every pre-R277 capture directory it cannot read (a lab
tree keeps its own; not a failure), then a PASS line or a numbered list of every
failure (missing file, size or sha256 mismatch, a shared block bound to a part, a
leak, a duplicate seq, a turn file that is not JSON, a block reference that does not
resolve or whose sha differs, a BLOCK 4 text that is not the Block file's). Exit 0
if no captures exist or all pass, 1 otherwise. `stats()` prints per part the four files
with their items and a reconciliation line when the items do not sum; exit 1 when no
captures exist. `write()`, `record_turn()`, `discard()` print nothing; `write()`
raises `RuntimeError` on a byte mismatch or a shared-block mismatch.

## OPERATION

### block_filename(index, name, part)
```
if (name is a SHARED block) then { return "Block<index+1>_<name>.md" }
else {
    the stem is `name` with its leading "part_" replaced by "<part>_" (or
    "<part>_<name>" if it has no such prefix); return "Block<index+1>_<stem>.md".
}
```

### write(ot, sysblocks, notes, live, names=None)
```
if (live) then { the directory is work/prompts/<ot> }
else { return None — nothing is written. The sandbox_dir root left with
       --minimal, R360; a dry run's evidence is its transcript. }
{
    names default to BLOCK_NAMES; a block past the names is "block<i>".
    FOR EACH SHARED block position: collect the distinct texts across every
    part; if (more than one) then { raise RuntimeError naming the parts —
    REFUSED before anything is written }.
    make the directory.
    FOR EACH part, FOR EACH of its blocks, in order:
        if (the block is SHARED) then {
            if (its file is not yet written) then { emit it once, bound to no part }
        } else { emit it under the per-part name, bound to this part }
        and append the file name to the part's block list.
    EMIT = atomic_write the text; re-read the bytes;
        if (they differ from the text's UTF-8) then { raise RuntimeError — REFUSING
        to record a capture that cannot reproduce what was sent };
        compute block_items() (a failure becomes one "(item extraction failed)"
        item, never a refusal); record block, index, shared, part, bytes, chars,
        sha256, cached (whether the block carried cache_control), items.
    FOR EACH part, ask its OWN remember register what must be in its identity
        blocks (_remember_expectation): no records -> {records: 0}; a register
        whose rendered records exceed remember.BUDGET -> {windowed: true},
        because the projection never promised to show any particular one; else
        the count, and the NEWEST record's chars, sha256 and first 96
        characters. Any exception becomes {error: ...}. It never costs a
        capture, and verify() skips anything but the third case.
    write manifest.json: open_time, block_order, files, parts (briefing_filter
    note + block list + remember_projection each), block_bytes, turns = [],
    turn_bytes = 0, and a one-line turns_format.
    return the directory.
}
```
**Why the register is read here and not at verify time (R362, 2026-08-27).** A
capture is checked months after its circle, against a register that has moved
on; a verifier reading today's register would be answering a different
question. So the bytes to look for travel WITH the capture. The two paths stay
independent — `prompt_build` assembles Block 3/4 through
`remember.block_settled()`/`block_tail()`, this reads `remember.entries()` —
which is the point: a check that reads the same object twice checks nothing.

### read_manifest(d) / block_shas(manifest)
`read_manifest` loads `<d>/manifest.json`. `block_shas` returns, per part, the sha256
of each of its listed block files in order — the shared files counting for every
part that lists them — which is what `circle.py::_prompt_blocks_changed` compares
across a resume.

### open_turn_log(d, ot=None) / turn_log_dir()
```
under the module lock {
    reset the log (no dir, no manifest, seq 0, remember ot);
    if (d is None) then { return — record_turn() now writes nothing }
    else { load d's manifest, ensure a "turns" list, point the log at d, and set
           seq to the highest seq already recorded there. }
}
```
One circle per process, so one open log; a later open replaces the earlier (the UI
suites run several circles in one process).

### _messages_tail(messages)
```
find the index of the LAST message whose role is "assistant";
if (there is none, or it is the first message) then { return (messages whole, None) }
else { return (messages from that index on,
               {"turns": that index, "sha256": sha256 of the JSON of what precedes}) }
```

### _system_record(part, system, manifest)
```
FOR EACH system entry, by position:
    if (it is not a dict with "text") then { pass it through unchanged }
    else {
        name it from the manifest's block_order ("block<i>" past the end); derive
        its Block file name; hash its text;
        if (it is part_objectives, OR no such file is in the manifest, OR the file's
            sha differs) then {
            write "type", "block", the text INLINE; and if (a file existed and its
            sha differs) then { add "differs_from_capture": true }
        } else { write "type", "block", "file", "sha256" — by reference }
        copy every other key of the original entry (cache_control and kin) after.
    }
```

### record_turn(part, kind, request, response=None, dry_run=False, error=None)
```
under the module lock {
    if (no log is open) then { return None }
    seq += 1; time = now to the second;
    split request["messages"] into (tail, omitted) with _messages_tail;
    build the record's request: "system" via _system_record when it is a list of
        blocks, AS IT IS when it is a string (a processing prompt has no Block file
        to point at — R412/R413), "messages" = tail, "messages_omitted" when
        anything was trimmed, every other key verbatim;
    body = {seq, part, kind, time, dry_run, request, response} plus "error" when
        one was given — part is null for a call made for no one part;
    file = Per_turn_<actor>_<time>_<seq:03d>.json, actor = part, or the KIND when
        part is null (check_contract makes the same substitution); atomic_write the
        JSON; re-read;
    append {file, seq, part, kind, time, bytes, sha256, dry_run, error: bool} to
        the manifest's turns; recompute turn_bytes; atomic_write the manifest;
    return the file path.
}
```
The lock covers the sequence number, the file write and the manifest rewrite: the
blind round asks seven parts in parallel.

### discard(d)
```
if (d is None, or has no manifest) then { return 0 }
try to read the manifest; if (it cannot be read) then { return 0 }
FOR EACH file the manifest lists (Block files, then turn files), then the
    manifest itself: if (it exists) then { unlink it; count it }
try to remove the directory (ignored if not empty);
under the lock, if (this was the open log) then { close it };
return the count.
```
Exactly the listed files, by name — never a glob (E12).

### block_items(name, text) and its helpers (_sections, _sub_items, _cap)
Unchanged from before R277: per-item character counts within ONE block, split at
the literal marker strings each generator already hardcodes (issue headings, topic
bullets, `## Your relationships`, `## What you have chosen to remember`, …), every
character of the input accounted for by exactly one item, degrading to a single
"(unparsed)" / "(no memories)" item when no marker is found. Parses
the EMITTED text, never a generator.

### _leak_check(fname, text)
Returns a failure for every part tag whose addressed marker `\n**Tag** —` (or a
leading `**Tag** —`) appears in a SHARED block's text — E09 kept permanently
detectable. (Inverted 2026-08-06 from "did the per-part filter drop the right
entries" to "is anything addressed in a block every part shares".)

### _verify_dir(d, fails)
```
read the manifest; if (unreadable) then { record a failure; return (0, 0) }
if (it has no "files" key) then { record a NOTE "pre-R277 layout — not
                                   verified" (a failure only if no notes list
                                   was given); return (0, 0) }
FOR EACH Block file in files:
    if (missing) then { record } else { re-read; count it;
        if (size differs) then { record }; if (sha256 differs) then { record };
        if (shared) then { run _leak_check } }
FOR EACH part's block list: if (a name is not in files) then { record };
    if (a shared file is bound to a part) then { record }
FOR EACH part's remember_projection (R362 — absent on a pre-R362 capture,
        which makes no claim and is skipped):
    if (error, or windowed, or records == 0) then { skip — no claim was made }
    read the part's part_identity and part_objectives files;
    if (the recorded prefix is in NEITHER) then { record — the register
        projection did not carry the newest remembered record into the
        prompt, which is the safety net R355 rests on }
FOR EACH turn record:
    if (the file is missing) then { record; continue }
    re-read; count it; if (size or sha256 differs) then { record; continue }
    if (its seq was already seen) then { record }
    parse the JSON; if (it is not JSON) then { record; continue }
    FOR EACH system entry of its request:
        if (it carries "file") then {
            if (that file is not in the manifest) then { record }
            else if (the manifest's sha differs from the entry's) then { record —
                "a block moved mid-circle?" } }
        else if (it is part_objectives, inline, not flagged differs_from_capture)
            then { hash its text; if (the part's Block4 file is in the manifest and
                   its sha differs) then { record — the static-blocks claim broke } }
return (block files checked, turn files checked).
```

### verify(ot=None)
```
collect capture directories (one circle across both roots, or every directory
    with a manifest under both);
if (none) then { print "no captures found under …"; return 0 }
run _verify_dir over each, summing counts;
print the counts;
if (any failure) then { print them all; return 1 }
else { print the PASS line; return 0 }
```

### stats(ot=None)
```
collect directories as verify() does; if (none) then { print; return 1 }
FOR EACH directory: FOR EACH part: print its total chars, then each of its four
    files with the block name, chars, file name, every item and its chars, and a
    reconciliation line if the items do not sum to the block; then the turn-file
    count and bytes if any.
return 0.
```

## BUGS
None found.
