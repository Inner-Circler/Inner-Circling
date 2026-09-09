#!/usr/bin/env python3
"""
prompt_capture.py — save what each part was sent, verbatim, per circle: the
four system blocks once, and every request after that.

    python coordinator/prompt_capture.py --verify          check every capture
    python coordinator/prompt_capture.py --verify <OT>     check one circle
    python coordinator/prompt_capture.py --stats [<OT>]    per-item char counts

WHY THIS EXISTS

    The system prompt is GENERATED CODE. `prompt_build.system_blocks()`
    assembles it per part per circle out of `process_core.md`, the live
    issue graph, that part's own distillate and registers. It is the program
    a part runs, and until 2026-08-01 nothing in the project had ever looked
    at the emitted artifact — only at the files that generate it.

    Both defects found that day were codegen bugs, invisible from the sources:

        the filter leak   three orphaned fragments of other parts' best
                          practices were emitted into six parts' prompts.
                          Sources correct, emission wrong. LOG E09.
        the truncation    a best practice was cut mid-sentence and shipped.
                          Every check validated the source; none read the output.

    Both were found by rendering a part's actual prompt and reading it. Neither
    could have been found by reading the generator. **Check the emitted program,
    not only the inputs to the generator.**

    Self's ruling, 2026-08-01: *"The prompts are discrete, absolutely save them
    locally, verbatim, for each part. Dreaming and synthesis will be watching for
    patterns to be selected in the coming years."*

THE LAYOUT — R277, 2026-08-21. One directory per circle, and inside it:

    Block1_circle_identity.md        BLOCK 1, shared — written ONCE
    Block2_circle_objectives.md      BLOCK 2, shared — written ONCE
    Block3_<part>_identity.md        BLOCK 3, one per part
    Block4_<part>_objectives.md      BLOCK 4, one per part
    Per_turn_<part>_<time>_<seq>.json
                                     ONE PER REQUEST — every request that
                                     carried the part's system prompt:
                                     the pre-warm, each statement and its
                                     truncation retry, the /close
                                     short_term and its retry. Not the API
                                     ping (no part, no system prompt) and
                                     not a token count.
                                     AND, since R412/R413 (2026-08-30/31),
                                     every call the coordinator makes for
                                     itself at a live /close that WRITES
                                     THE RECORD: dreaming (per part), the
                                     synthesis, the mid_term refresh (per
                                     part), the coalesce pass — one string
                                     system prompt inline, one user message,
                                     the same reply record. The two
                                     circle-wide kinds have no part, and
                                     the KIND fills the slot:
                                     Per_turn_synthesis_<time>_<seq>.json.
                                     Not the failure diagnostic, which
                                     writes nothing.
    manifest.json                    sha256, size and item counts per
                                     block file; one record per turn file.

    EACH BLOCK FILE IS THE BLOCK'S BYTES AND NOTHING ELSE — no header, no
    delimiter, so the file IS the verbatim text and slices nothing. The four
    blocks are static for the whole circle (built once at open, never
    rebuilt), which is what makes a file per block the right shape; the old
    one-file-per-part capture interleaved delimiters and sliced them back out
    by manifest offsets. That layout was replaced outright, no backward
    compatibility (Self, 2026-08-21: *"do not consider backward
    compatibility"*), and the six captures written in it were deleted the
    same day; git holds them at their old paths.

THE PER-TURN RECORD is the Messages-API request body as sent, plus the reply:

    {
      "seq": 12, "part": "<dir>", "kind": "statement",
      "time": "2026-08-21_143022", "dry_run": false,
      "request": {
        "model": ..., "max_tokens": ...,
        "system": [
          {"type": "text", "block": "circle_identity",
           "file": "Block1_circle_identity.md", "sha256": "...",
           "cache_control": {...}},                    ; blocks 1-3 BY REFERENCE
          ...                                          ; to the Block files —
          {"type": "text", "block": "part_objectives",  ; same bytes, by sha
           "text": "<verbatim>"}                       ; BLOCK 4 INLINE, marked
        ],
        "messages": [...],                              ; VERBATIM — see TAIL
        "messages_omitted": {"turns": n, "sha256": "..."}   ; when trimmed
      },
      "response": {"id", "model", "stop_reason", "text", "usage",
                   "thinking"},                   ; when RECORD_THINKING is on
      "error": "..."                                    ; only when it raised
    }

    To rebuild the exact wire body: for each `system` entry carrying `file`,
    replace it with {"type", "text": <that file's bytes>, "cache_control"},
    and drop the `block` key. A block whose text did NOT match the Block file
    (no such case exists today — the blocks are static by construction) is
    written inline with `"differs_from_capture": true` so the record is exact
    whatever the generator does.

    TAIL. `messages` is recorded from the part's own last statement — its
    last assistant turn — through the closing line, Self 2026-08-21: *"only
    send the tail of the transcript.. from the last statement of the part
    through current."* What precedes that turn is the transcript as it stood,
    already on record in `circles/` and in this part's earlier turn files; it
    is not repeated here, and `messages_omitted` records how many turns were
    trimmed and the sha256 of their JSON so a reconstruction can be checked.
    A part that has not yet spoken has no anchor and its messages are
    recorded whole. THE REQUEST ITSELF IS NOT TRIMMED — what a part is sent
    is prompt_build.prompt_messages_render()'s business, and this module only
    records it.

    `response.text` is the RAW reply — before circle_rounds.part_statement_ask() strips a
    sign-off, a `[To: ...]` prefix or a bracket, and before "[pass]" becomes
    silence. The transcript holds the cleaned text; this is the only record
    of what the model SAID. `usage` is the SDK's usage object as a dict, so
    the cache hit/miss of every request is on file.

    THAT SENTENCE READ "the only record of what the model actually returned"
    until 2026-08-29, and it was overbroad in a way nothing here would have
    caught. `text` is the TEXT BLOCKS. A reply also carries the model's
    reasoning, on every statement, and this file recorded the SIZE of it —
    `usage.output_tokens_details.thinking_tokens`, on file since the captures
    began — while dropping the thing itself.

    `response.thinking` IS THAT REASONING, kept since the operator ruled it
    kept (llm_client.RECORD_THINKING, default on). Two things bound what it
    is worth. It is a SUMMARY the service returns, not the raw trace; and its
    PRESENCE is the record of the setting — an empty string means recording
    was on and the model thought nothing, an ABSENT key means recording was
    off or the capture predates this. `thinking_redacted_blocks` appears only
    when the reply carried reasoning this project cannot read, so that a
    partial record never passes for a whole one.

VERBATIM, AND CHECKED

    On write, every Block file is re-read and compared byte-for-byte against
    the text that was sent; a file that does not reproduce its block is a
    failure at write time, not a discovery years later. --verify re-hashes
    every file against the manifest, checks no SHARED block carries a
    part-addressed marker (E09), and checks every turn file's block
    references resolve to the Block files by sha — which is the static-blocks
    claim, proven per request rather than assumed.

SIZE

    The Block files are ~80 KB per circle for seven parts (process_core.md
    once, the briefing once, not seven times as before). The turn files are
    the new cost: roughly one per part per round, each carrying BLOCK 4, the
    tail of the conversation and the reply. A content-addressed store is
    still deliberately NOT built: indirection costs a future reader a step.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
import re
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "memory"))   # the issue-graph code (R203)
import part_roster as R                                            # noqa: E402
# One home for the roots (2026-08-19, review tier 5 #41) — see
# remember_manager.py's note beside its own import: this was the third private
# ROOT/SANDBOX derivation, each a place the next relocation could miss.
from record_paths import ROOT, SANDBOX                               # noqa: E402
from atomic_write import record_atomic_write                         # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PROMPTS = ROOT / "work" / "prompts"        # moved from coordinator/, R176, 2026-08-15
# B13. --verify walked only `prompts/` and reported "3 circles" while a
# FOURTH sat in the sandbox — and the sandbox captures are the ones the
# part-context design work actually rests on, so they were the only
# captures never re-hashed. Both roots now.
SANDBOX_PROMPTS = SANDBOX / "prompts"


def _roots() -> list[pathlib.Path]:
    return [d for d in (PROMPTS, SANDBOX_PROMPTS) if d.is_dir()]


# The four blocks of system_blocks(), in order. Names are recorded in the
# manifest so a reader knows what each file IS without reading prompt_build.
#
# DERIVED, NOT COPIED (2026-08-28). These four strings were written out here
# AND in prompt_build.ORDER — one fact in two modules, and prompt_build's own
# block_order() already said "`prompt_capture` labels by this", which was the
# intent but not the mechanism.
#
# LAZILY, which is this file's established way of reaching a coordinator
# module (see the `import remember_manager as RM` inside record_projection). It
# matters here: prompt_build pulls the transport and the provider behind it,
# and this module is a VERIFIER the pre-commit hook runs — the same reason
# _source_constant greps a constant out of source text rather than importing
# the module that holds it.
#
# NOT taken from turn_contract.toml, though it names the same four. That file
# is the contract's INDEPENDENT expectation — the thing a capture is checked
# against — and a contract that derived its expectation from the code would
# check nothing.
def block_names() -> tuple:
    import prompt_build as _PB
    return tuple(_PB.ORDER)
SHARED_BLOCKS = ("circle_identity", "circle_objectives")
IDENTITY_BLOCKS = ("part_identity", "part_objectives")   # the per-part pair
MANIFEST = "manifest.json"
PROJECTION_PREFIX = 96      # chars of the newest record recorded as the probe

# B29: derived from part_roster.py — was a hand-typed copy.
PART_TAGS = tuple(R.TAGS)


def _tags_rebind() -> None:
    """The CURRENT group's Tags — B117 stage 5 (2026-09-07)."""
    global PART_TAGS
    PART_TAGS = tuple(R.TAGS)


import record_paths as _RPf                                            # noqa: E402
_RPf.group_follow(_tags_rebind)
# PART_TAGS_BY_DIR (= R.TAG_BY_DIR) DELETED 2026-09-01 -- audit-register.md
# #30 found it a zero-reference symbol; two docs cited it as this module's
# own surface, but nothing anywhere imports or reads it. Use
# part_roster.TAG_BY_DIR directly.


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _remember_expectation(part: str) -> dict:
    """What this part's OWN register says must be inside its identity blocks
    — recorded at capture time so --verify can check it forever after.

    THE INVARIANT R355 LEANS ON, ASSERTED. The distillation drops a fresh
    single-source record BY INSTRUCTION (mid_term SYSTEM v9; ruled to stand
    2026-08-26), and that drop is harmless for exactly one reason: the
    register projection carries every fresh record verbatim into BLOCK 3/4
    until reinforcement consolidates it. That was a load-bearing claim with
    nothing asserting it — --verify re-hashed every block and never once
    asked whether a remembered thing had reached the part it belongs to.
    Built R362, 2026-08-27.

    RECORDED HERE BECAUSE IT CANNOT BE RECOVERED LATER. A capture is checked
    months after its circle, against a register that has moved on; a
    verifier reading today's register would be answering a different
    question. So the bytes to look for travel WITH the capture.

    TWO INDEPENDENT PATHS, which is the whole point: prompt_build assembles
    Block 3/4 through remember_prompt_projection.remember_settled_render()/block_tail(), and this reads
    remember_manager.remember_read() directly. A check that reads the same object twice
    checks nothing.

    THE WINDOW IS RESPECTED, NOT ASSUMED AWAY. The projection shows records
    newest-first to a character BUDGET, in a salience-bounded order that can
    promote an older record — so an individual record is only GUARANTEED to
    appear when the whole register fits. When it does not, `windowed` is
    recorded and the verifier skips rather than inventing an expectation the
    projection never made.

    IT NEVER COSTS A CAPTURE. Any failure is recorded as `error` and skipped
    at verify time, the same degrade block_items() takes."""
    try:
        import remember_manager as RM
        es = sorted(RM.remember_read(part), key=lambda r: r.get("date", ""),
                    reverse=True)
        if not es:
            return {"records": 0}
        rendered = sum(len("\n- " + str(r.get("text", "")) + "\n") for r in es)
        if rendered > RM.BUDGET:
            return {"records": len(es), "windowed": True,
                    "rendered_chars": rendered, "budget": RM.BUDGET}
        newest = str(es[0].get("text", ""))
        return {"records": len(es), "chars": len(newest),
                "sha256": _sha(newest.encode("utf-8")),
                "prefix": newest[:PROJECTION_PREFIX]}
    except Exception as e:                                   # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


def block_filename(index: int, name: str, part: str) -> str:
    """`Block1_circle_identity.md` / `Block3_child_identity.md` — the names
    Self specified 2026-08-21 (R277). A shared block's file carries the
    block name; a per-part block's file substitutes the part for the
    `part_` prefix of its block name."""
    if name in SHARED_BLOCKS:
        return f"Block{index + 1}_{name}.md"
    stem = name.replace("part_", f"{part}_", 1) if name.startswith("part_") \
        else f"{part}_{name}"
    return f"Block{index + 1}_{stem}.md"


# ------------------------------------------------------------------ the blocks
def prompt_capture_write(ot: str, sysblocks: dict[str, list[dict]], notes: dict[str, str],
          live: bool,
          names: "tuple[str, ...] | None" = None) -> pathlib.Path | None:
    """Write <root>/<OT>/: the Block files and manifest.json. Returns the
    directory, or None if nowhere to write.

    Raises if a Block file cannot be re-read byte-for-byte, or if a SHARED
    block differs between parts — one file cannot record two texts, and two
    texts would mean the cache prefix the 2026-08-06 restructure bought is
    broken. Either way the circle goes on; the caller reports and fails the
    run (circle.py: *a capture failure must not cost a circle, but it must be
    loud*).

    A NON-LIVE run captures nothing: the `sandbox_dir` root that once
    caught --minimal's captures left with that mode (R360); dry-run's
    evidence is its transcript."""
    if live:
        d = PROMPTS / ot
    else:
        return None
    names = tuple(names or block_names())
    parts = list(sysblocks)

    def _name(i: int) -> str:
        return names[i] if i < len(names) else f"block{i}"

    # THE SHARED BLOCKS MUST BE ONE TEXT. Checked BEFORE anything is written,
    # so a refusal leaves no half-capture behind.
    for i in range(max((len(b) for b in sysblocks.values()), default=0)):
        nm = _name(i)
        if nm not in SHARED_BLOCKS:
            continue
        seen: dict[str, str] = {}
        for p in parts:
            if i < len(sysblocks[p]):
                seen.setdefault(sysblocks[p][i]["text"], p)
        if len(seen) > 1:
            raise RuntimeError(
                f"SHARED block {nm} differs between parts "
                f"({', '.join(sorted(seen.values()))}) — one file cannot "
                f"record two texts, and the cache prefix is broken; "
                f"REFUSING to capture")

    d.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict] = {}
    per_part: dict[str, dict] = {}

    def _emit(fname: str, b: dict, i: int, nm: str, part: "str | None") -> None:
        text = b["text"]
        f = d / fname
        record_atomic_write(f, text)
        raw = f.read_bytes()
        if raw != text.encode("utf-8"):
            raise RuntimeError(
                f"prompt capture {fname} does not re-read byte-for-byte — "
                f"REFUSING to record a capture that cannot reproduce what "
                f"was sent")
        try:
            items = block_items(nm, text)
        except Exception as e:                    # NEVER cost a capture —
            items = [{"label": f"(item extraction failed: "
                              f"{type(e).__name__}: {e})", "chars": None}]
        files[fname] = {
            "block": nm, "index": i, "shared": part is None, "part": part,
            "bytes": len(raw), "chars": len(text), "sha256": _sha(raw),
            "cached": "cache_control" in b, "items": items,
        }

    for p in parts:
        blocks = sysblocks[p]
        mine: list[str] = []
        for i, b in enumerate(blocks):
            nm = _name(i)
            if nm in SHARED_BLOCKS:
                fname = block_filename(i, nm, p)
                if fname not in files:
                    _emit(fname, b, i, nm, None)
            else:
                fname = block_filename(i, nm, p)
                _emit(fname, b, i, nm, p)
            mine.append(fname)
        per_part[p] = {"briefing_filter": notes.get(p, ""), "blocks": mine,
                       "remember_projection": _remember_expectation(p)}

    manifest = {
        "open_time": ot,
        "block_order": list(names),
        "files": files,
        "parts": per_part,
        "block_bytes": sum(r["bytes"] for r in files.values()),
        "turns": [],
        "turn_bytes": 0,
        "turns_format": (
            "one JSON file per request: the Messages-API body as sent, "
            "system blocks 1-3 by reference to the Block files (same bytes, "
            "by sha256), BLOCK 4 inline, messages from the part's own last "
            "statement through the closing line, plus the raw reply. R277."),
    }
    record_atomic_write(d / MANIFEST, json.dumps(manifest, indent=1,
                                          ensure_ascii=False) + "\n")
    return d


def prompt_manifest_read(d: pathlib.Path) -> dict:
    return json.loads((d / MANIFEST).read_text(encoding="utf-8"))


def block_shas(manifest: dict) -> dict[str, list[str]]:
    """{part: [sha256 of each of its blocks, in block order]} — what a
    resume compares to decide whether the emitted program moved between
    sittings (circle_close.py::_prompt_blocks_changed). Per part, not per file:
    the shared files count for every part that carries them."""
    out: dict[str, list[str]] = {}
    for p, rec in manifest.get("parts", {}).items():
        out[p] = [manifest["files"][f]["sha256"] for f in rec.get("blocks", [])
                  if f in manifest.get("files", {})]
    return out


# ------------------------------------------------------------------ the turns
# ONE CIRCLE PER PROCESS, so one open turn log. circle.py opens it right
# after prompt_capture_write() and before the pre-warm; everything llm_client sends on a
# part's behalf is then recorded here. A second open (a later circle in the
# same process — the UI suites do this) replaces the first.
_LOG: dict = {"dir": None, "ot": None, "manifest": None, "seq": 0,
              "lock": threading.Lock()}


def prompt_turn_log_open(d: "pathlib.Path | None", ot: "str | None" = None) -> None:
    """Point record_turn() at <d>. None closes it: record_turn() then writes
    nothing — the plain-sandbox case, where prompt_capture_write() returned None too."""
    with _LOG["lock"]:
        _LOG["dir"], _LOG["ot"], _LOG["manifest"], _LOG["seq"] = None, ot, None, 0
        if d is None:
            return
        man = prompt_manifest_read(d)
        man.setdefault("turns", [])
        _LOG["dir"], _LOG["manifest"] = d, man
        _LOG["seq"] = max((t.get("seq", 0) for t in man["turns"]), default=0)


def prompt_turn_log_locate() -> "pathlib.Path | None":
    return _LOG["dir"]


def _messages_tail(messages: list) -> tuple[list, "dict | None"]:
    """From the part's own last statement — its last assistant turn — to the
    end. Whole when it has none. Returns (tail, omitted-record-or-None)."""
    last = None
    for i, m in enumerate(messages):
        if isinstance(m, dict) and m.get("role") == "assistant":
            last = i
    if not last:                       # None, or 0 (nothing before it)
        return list(messages), None
    omitted = messages[:last]
    rec = {"turns": last,
           "sha256": _sha(json.dumps(omitted, ensure_ascii=False)
                          .encode("utf-8"))}
    return list(messages[last:]), rec


def _system_record(part: str, system: list, man: dict) -> list:
    """Blocks 1-3 by reference to the Block files when the bytes match;
    BLOCK 4 inline; anything that does not match its Block file inline and
    flagged, so the record is exact whatever the generator did."""
    order = man.get("block_order") or list(block_names())
    files = man.get("files", {})
    out = []
    for i, b in enumerate(system):
        if not isinstance(b, dict) or "text" not in b:
            out.append(b)
            continue
        nm = order[i] if i < len(order) else f"block{i}"
        fname = block_filename(i, nm, part)
        rec = files.get(fname)
        sha = _sha(b["text"].encode("utf-8"))
        entry: dict = {"type": b.get("type", "text"), "block": nm}
        if nm == "part_objectives" or rec is None or rec["sha256"] != sha:
            entry["text"] = b["text"]
            if rec is not None and rec["sha256"] != sha:
                entry["differs_from_capture"] = True
        else:
            entry["file"] = fname
            entry["sha256"] = sha
        for k, v in b.items():
            if k not in ("type", "text"):
                entry[k] = v
        out.append(entry)
    return out


def record_turn(part: "str | None", kind: str, request: dict,
                response: "dict | None" = None, dry_run: bool = False,
                error: "str | None" = None) -> "pathlib.Path | None":
    """Write one Per_turn file and its manifest record. Returns the path, or
    None when no log is open. `request` is the messages.create kwargs —
    model, max_tokens, system, messages — exactly as passed; `response` is
    already a plain dict (llm_client builds it from the SDK object).

    TWO SHAPES OF REQUEST PASS THROUGH HERE since R412/R413 (2026-08-31). A
    PART's turn carries `system` as the four blocks, and 1-3 are written by
    reference to their Block files. A PROCESSING turn — dreaming, synthesis,
    mid_term, coalesce — carries `system` as ONE STRING, recorded inline and
    untouched (a string has no Block file to point at), and `part` may be
    None: the synthesis and the coalesce pass speak for no one part. The file
    then takes the KIND in the part slot — Per_turn_synthesis_<time>_<seq>
    — and the body says `"part": null`. prompt_capture_contract_verify() makes the same
    substitution when it checks the name, so writer and checker agree.

    Thread-safe: the blind round asks seven parts in parallel, so the
    sequence number, the file write and the manifest rewrite all happen
    under one lock. The write is milliseconds; the lock costs nothing."""
    with _LOG["lock"]:
        d, man = _LOG["dir"], _LOG["manifest"]
        if d is None or man is None:
            return None
        _LOG["seq"] += 1
        seq = _LOG["seq"]
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        tail, omitted = _messages_tail(list(request.get("messages") or []))
        req: dict = {}
        for k, v in request.items():
            if k == "system":
                # a list is the four blocks, by reference where the bytes
                # match; a string is a processing prompt and rides as it is
                req["system"] = (_system_record(part or "", list(v or []), man)
                                 if isinstance(v, list) else v)
            elif k == "messages":
                req["messages"] = tail
                if omitted:
                    req["messages_omitted"] = omitted
            else:
                req[k] = v
        body: dict = {"seq": seq, "part": part, "kind": kind, "time": now,
                      "dry_run": bool(dry_run), "request": req,
                      "response": response}
        if error:
            body["error"] = error
        actor = part if part is not None else kind
        fname = f"Per_turn_{actor}_{now}_{seq:03d}.json"
        f = d / fname
        text = json.dumps(body, indent=1, ensure_ascii=False) + "\n"
        record_atomic_write(f, text)
        raw = f.read_bytes()
        man["turns"].append({"file": fname, "seq": seq, "part": part,
                             "kind": kind, "time": now, "bytes": len(raw),
                             "sha256": _sha(raw), "dry_run": bool(dry_run),
                             "error": bool(error)})
        man["turn_bytes"] = sum(t["bytes"] for t in man["turns"])
        record_atomic_write(d / MANIFEST, json.dumps(man, indent=1,
                                              ensure_ascii=False) + "\n")
        return f


def prompt_capture_discard(d: "pathlib.Path | None") -> int:
    """Remove a capture that belongs to a circle which left no trace — the
    pre-warm failed, nothing was ever said, the transcript was withdrawn.
    EXACTLY the files the manifest lists, by name, then the manifest, then
    the directory if that emptied it. Never a glob (E12). Returns how many
    files were removed; 0 when there is no manifest to trust."""
    if d is None or not (d / MANIFEST).is_file():
        return 0
    try:
        man = prompt_manifest_read(d)
    except Exception:                                      # noqa: BLE001
        return 0
    names = list(man.get("files", {})) + [t["file"] for t in man.get("turns", [])]
    n = 0
    for nm in names + [MANIFEST]:
        f = d / nm
        if f.is_file():
            f.unlink()
            n += 1
    try:
        d.rmdir()
    except OSError:
        pass
    with _LOG["lock"]:
        if _LOG["dir"] == d:
            _LOG["dir"], _LOG["manifest"] = None, None
    return n


# -------------------------------------------------------------- item stats
# Per-item character counts WITHIN a block — ruled 2026-08-16: "per single
# item add (topics, part-relationships, issues, etc.)". PARSES THE EMITTED
# TEXT, never a generator (circle_briefing_build, topic_manager.block(), etc.) — the same
# rule this whole module exists to enforce (see the docstring above, E09/
# E12): stats threaded out of a generator would describe its INTENT; stats
# parsed from the captured block describe what was actually sent, and drift
# between the two is exactly the bug class this project keeps finding.
#
# NAME-AWARE, NOT LEVEL-AWARE. mid_term's own distillate carries its own
# `## ` headings (e.g. "## Relationships — current stances", prose, not a
# relationship record) INSIDE circle_identity's "## Your identity" span —
# treating every `## `/`### ` line as an item boundary would count those.
# Only the LITERAL marker strings circle.py / issue_prompt_projection.py / topic_manager.py /
# practice_manager.py / remember_manager.py / part_relationships.py already
# hardcode start a new item; everything else is that item's body.
#
# NEVER COSTS A CAPTURE. prompt_capture_write() calls block_items() inside a try/except
# that degrades to a single "(item extraction failed)" entry — a parser bug
# here must not be able to trip prompt_capture_write()'s byte re-read refusal, which
# guards the verbatim capture itself (ruled 2026-08-01).

_ISSUE_ITEM = re.compile(r"(?m)^### (n\d{4} — .*)$")
_TOPIC_ITEM = re.compile(r"(?m)^- (TP-\d+) \(from circle")
_BULLET_ITEM = re.compile(r"(?m)^- (.+)$")
_HEADING_ITEM = re.compile(r"(?m)^## (.+)$")

_LABEL_CAP = 80


def _cap(label: str) -> str:
    label = label.strip()
    return label if len(label) <= _LABEL_CAP else label[:_LABEL_CAP - 1] + "…"


def _sections(text: str, markers: list[str]) -> dict[str, str]:
    """Split `text` into contiguous, non-overlapping spans at each literal
    marker string in `markers` — searched IN THE GIVEN ORDER, each starting
    where the previous one ended, so a marker that also appears earlier
    (unexpectedly) is never matched out of order. Content before the first
    found marker keys under "" — never silently dropped, so a caller can
    still account for every character even when no marker is present."""
    positions, pos = [], 0
    for mk in markers:
        i = text.find(mk, pos)
        if i == -1:
            continue
        positions.append((i, mk))
        pos = i + len(mk)
    out: dict[str, str] = {}
    if not positions:
        if text:
            out[""] = text
        return out
    if positions[0][0] > 0:
        out[""] = text[:positions[0][0]]
    for k, (start, mk) in enumerate(positions):
        end = positions[k + 1][0] if k + 1 < len(positions) else len(text)
        out[mk] = text[start:end]
    return out


def _sub_items(section: str, pattern: "re.Pattern", heading_label: str,
               item_prefix: str) -> list[dict]:
    """Item breakdown for a KNOWN section, given WHOLE — including its own
    marker line, which becomes one synthetic '(heading)' item so it can
    never be mistaken for the section's first real item. `pattern` is
    matched only against the body after that line. Every character of
    `section` is accounted for by exactly one returned item."""
    nl = section.find("\n")
    head = (nl + 1) if nl != -1 else len(section)
    out = [{"label": heading_label, "chars": head}]
    body = section[head:]
    ms = list(pattern.finditer(body))
    if not ms:
        if body:
            out.append({"label": f"{heading_label} (no items found)",
                        "chars": len(body)})
        return out
    if ms[0].start() > 0:
        out.append({"label": f"{heading_label} (preamble)",
                    "chars": ms[0].start()})
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(body)
        out.append({"label": f"{item_prefix}{_cap(m.group(1))}",
                    "chars": end - m.start()})
    return out


_BLOCK1_MARKERS = ["## Best practices", "### Better options (for Self)"]
# The "*Below: the hand-written account," marker is GONE, 2026-08-25. It
# split off <issues_narrative>, whose emitter prompt_build.py lost at B46
# (2026-08-17) — so no block 2 has carried it since, and no capture under
# work/prompts/ ever contained it (the R277 layout postdates B46). A marker
# nothing emits cannot split anything; it only made the branch below look
# reachable.
_BLOCK2_MARKERS = ["## Issues", "## Relations between issues",
                   "## Topics for this circle's review"]
# "## Your relationships" IS KEPT, DELIBERATELY, AND IT IS NOT THE SAME CASE AS THE DEAD
# _BLOCK2_MARKERS ENTRY ABOVE — audit-register.md #19, checked and reversed 2026-09-08.
#
# The finding was right about the writer: no BLOCK 3 has carried that heading since
# 2026-08-22, the register was renamed at R220 and retired that day, and docs/BNF.md records
# `<relationships_distillate> ::= ε ; GENUINELY UNREAD NOW`. Removing the marker and its
# branch was the obvious next step, and it is wrong.
#
# THESE MARKERS PARSE THE ARCHIVE, NOT THE PRESENT. block_items() runs over every capture
# under work/prompts/, and work/prompts/2026-08-21_1139/Block3_*_identity.md — five of the
# seven parts — still contain "## Your relationships", because they were captured while the
# heading was live. Those files are permanent by ruling (2026-08-01: "absolutely save them
# locally, verbatim, for each part. Dreaming and synthesis will be watching for patterns to
# be selected in the coming years"). Drop the marker and the tool silently mis-splits a
# capture it is the only reader of.
#
# WHICH IS THE DIFFERENCE FROM THE B46 CASE ABOVE: that marker's emitter went before the
# R277 capture layout existed, so NO capture ever contained it — nothing to read. This one
# has readers on disk. The test suite's two relationship checks assert exactly that.
_BLOCK3_MARKERS = ["## Your relationships", "## Your best practices",
                   "## REMEMBER"]
_BLOCK4_MARKERS = ["## What you have chosen to remember"]


def block_items(name: str, text: str) -> list[dict]:
    """Per-item char counts within ONE system-prompt block. Falls back to a
    single '(unparsed)' item covering the whole text when none of that
    block's known markers are found — a shape this parser does not know
    must degrade rather than claim a breakdown it does not have (the
    retired --minimal blocks were the founding case, R360)."""
    if name == "circle_identity":
        secs = _sections(text, _BLOCK1_MARKERS)
        items = []
        if "" in secs:
            items.append({"label": "process_core.md", "chars": len(secs[""])})
        if "## Best practices" in secs:
            items += _sub_items(secs["## Best practices"], _BULLET_ITEM,
                                "## Best practices (heading)", "practice: ")
        if "### Better options (for Self)" in secs:
            items += _sub_items(secs["### Better options (for Self)"],
                                _BULLET_ITEM, "### Better options (heading)",
                                "option: ")
        return items or [{"label": "(unparsed)", "chars": len(text)}]

    if name == "circle_objectives":
        secs = _sections(text, _BLOCK2_MARKERS)
        items = []
        if "" in secs:
            items.append({"label": "issue_model.md prologue",
                          "chars": len(secs[""])})
        if "## Issues" in secs:
            items += _sub_items(secs["## Issues"], _ISSUE_ITEM,
                                "## Issues (heading)", "issue: ")
        if "## Relations between issues" in secs:
            items.append({"label": "relations brief",
                          "chars": len(secs["## Relations between issues"])})
        if "## Topics for this circle's review" in secs:
            items += _sub_items(secs["## Topics for this circle's review"],
                                _TOPIC_ITEM, "## Topics (heading)", "topic: ")
        return items or [{"label": "(unparsed)", "chars": len(text)}]

    if name == "part_identity":
        secs = _sections(text, _BLOCK3_MARKERS)
        items = []
        if "" in secs:
            items.append({"label": "identity (long_term + distillate)",
                          "chars": len(secs[""])})
        # UNREACHABLE FOR A NEW CAPTURE, LIVE FOR AN OLD ONE — see _BLOCK3_MARKERS' own note.
        # No BLOCK 3 has emitted this heading since 2026-08-22, so nothing captured from that
        # day on takes this branch; work/prompts/2026-08-21_1139's five Block3 files do, and
        # they are kept permanently. The label below still says "relationship: ", the
        # pre-R220 word, and that is CORRECT here: it describes bytes written before the
        # rename, and renaming it would misdescribe the file being read.
        if "## Your relationships" in secs:
            items += _sub_items(secs["## Your relationships"], _HEADING_ITEM,
                                "## Your relationships (heading)",
                                "relationship: ")
        if "## Your best practices" in secs:
            items += _sub_items(secs["## Your best practices"], _BULLET_ITEM,
                                "## Your best practices (heading)",
                                "practice: ")
        if "## REMEMBER" in secs:
            items.append({"label": "remember guidance",
                          "chars": len(secs["## REMEMBER"])})
        return items or [{"label": "(unparsed)", "chars": len(text)}]

    if name == "part_objectives":
        secs = _sections(text, _BLOCK4_MARKERS)
        if "## What you have chosen to remember" in secs:
            items = []
            if secs.get(""):
                items.append({"label": "(preamble)", "chars": len(secs[""])})
            items += _sub_items(secs["## What you have chosen to remember"],
                                _BULLET_ITEM, "## What you remember (heading)",
                                "memory: ")
            return items
        return [{"label": "(no memories)", "chars": len(text)}]

    return []


# ------------------------------------------------------------------ verify
def _leak_check(fname: str, text: str) -> list[str]:
    """No SHARED block may carry a part-addressed `**Part** —` marker.

    **INVERTED 2026-08-06, with the block restructure.** It used to assert
    that a per-part FILTER had removed the other six parts' entries from a
    34,000-character briefing. There is no filter now — practices route by
    self/best_practices.toml's own `addressee` field (R134), and
    circle_objectives is built directly by group_attention's `circle_briefing_build()`
    (2026-08-11, self/circle_briefing.md retired) — so the shared blocks
    should contain no addressed entry at all, not this part's either.

    E09 stays permanently detectable either way. The leak existed from
    2026-07-27 and was found by chance, because no record of what a part was
    sent survived the circle."""
    hits = [t for t in PART_TAGS
            if f"\n**{t}** —" in text or text.startswith(f"**{t}** —")]
    return [f"{fname} (SHARED) carries {t}'s addressed marker — it belongs "
            f"in part_objectives (E09)" for t in hits]


# ------------------------------------------------------------ the wire contract

CONTRACT = pathlib.Path(__file__).resolve().parent / "turn_contract.toml"

_TYPES = {"int": int, "str": str, "bool": bool, "list": list, "dict": dict,
          # a processing turn's `part` (R412): a part's name, or null for the
          # synthesis and the coalesce pass, which speak for no one part
          "str|null": (str, type(None))}


def prompt_shape_read(kind: "str | None", contract: dict) -> tuple["str | None", dict]:
    """(name, spec) of the [shape.*] table that declares `kind`; (None, {})
    when none does. R412/R413, 2026-08-31: a PART's turn and a PROCESSING
    turn are two wire shapes under one file format, and the shape is what
    the kind names."""
    for name, spec in (contract.get("shape") or {}).items():
        if kind in (spec.get("kinds") or []):
            return name, spec
    return None, {}


def prompt_capture_kinds_read(contract: dict) -> list[str]:
    """Every kind any shape declares — the ONE list, derived, never copied.
    Falls back to a pre-shape contract's `[turn] kinds` so an old TOML still
    checks something rather than nothing."""
    out: list[str] = []
    for spec in (contract.get("shape") or {}).values():
        out.extend(spec.get("kinds") or [])
    return out or list((contract.get("turn") or {}).get("kinds") or [])


def prompt_capture_contract_read() -> dict:
    """turn_contract.toml, or {} when it is absent or unreadable. A MISSING
    CONTRACT IS A NOTE, NOT A PASS — _verify_dir says so out loud, because a
    check that quietly stops checking is the defect this whole file exists
    to catch.

    One of three identical bodies, deliberately — see
    circle_close_verify.circle_close_contract_read() for the reasoning."""
    try:
        import tomllib as _toml
    except ModuleNotFoundError:                              # pragma: no cover
        import tomli as _toml                                # type: ignore
    try:
        with CONTRACT.open("rb") as fh:
            return _toml.load(fh)
    except (OSError, ValueError):
        return {}


def _source_constant(spec: str) -> "str | None":
    """`coordinator/llm_client.py::MODEL`, GREPPED FROM THE SOURCE TEXT and
    never imported — importing llm_client pulls `anthropic` and its API-key
    check into a verifier the pre-commit hook runs. Same discipline, and the
    same reason, as bnf_conformance.py's own site resolver."""
    path, _, name = spec.partition("::")
    if not name:
        return None
    try:
        src = (ROOT / path).read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'^' + re.escape(name) + r'\s*=\s*["\']([^"\']+)["\']',
                  src, re.M)
    if m:
        return m.group(1)
    # THE CONSTANT MAY NOW BE OVERRIDABLE, 2026-08-28 (R379).
    # llm_client.MODEL became `SET.setting_value_read("model", "claude-sonnet-5")`, and the
    # literal-only pattern above stopped matching it — which did not fail the
    # check, it SKIPPED it (`if want_model and ...` below), turning the one
    # assertion that a request carries the code's own model into a gate that
    # checked nothing. That silent-pass shape is the defect this project
    # treats as worse than a loud failure, so the form is understood here
    # rather than left to miss.
    #
    # The EFFECTIVE model is what the request actually carried, so the
    # override is applied on top of the source default. settings is imported
    # for it — not llm_client, which would pull `anthropic` and an API-key
    # check into a verifier the pre-commit hook runs. That is the same reason
    # this function greps rather than imports in the first place.
    m = re.search(r'^' + re.escape(name)
                  + r'\s*=\s*(?:\w+\.)?setting_value_read\(\s*["\'](\w+)["\']\s*,\s*'
                    r'["\']([^"\']+)["\']\s*\)', src, re.M)
    if not m:
        return None
    key, default = m.group(1), m.group(2)
    try:
        import setting_manager as SET
        return SET.setting_value_read(key, default)
    except Exception:                                          # noqa: BLE001
        return default


def _typed(where: str, obj: dict, types: dict, out: list) -> None:
    for key, want in types.items():
        if key not in obj:
            continue
        cls = _TYPES.get(want)
        if cls is None:
            continue
        # bool is an int subclass, so an int field must not accept True
        if cls is int and isinstance(obj[key], bool):
            out.append(where + ": " + key + " is a bool, contract says int")
        elif not isinstance(obj[key], cls):
            out.append(where + ": " + key + " is "
                       + type(obj[key]).__name__ + ", contract says " + want)


def _keys(where: str, obj: dict, spec: dict, out: list) -> None:
    for key in spec.get("required", []):
        if key not in obj:
            out.append(where + ": missing required key " + repr(key))
    if spec.get("closed"):
        allowed = set(spec.get("required", [])) | set(spec.get("optional", []))
        for key in sorted(set(obj) - allowed):
            out.append(where + ": unexpected key " + repr(key)
                       + " — the contract is closed")
    _typed(where, obj, spec.get("types", {}), out)


def prompt_capture_contract_verify(fname: str, body: dict, contract: dict) -> list[str]:
    """Every rule in turn_contract.toml against ONE captured turn. Returns
    the failures; empty when the turn honours the contract."""
    out: list[str] = []
    if not contract:
        return out

    t = contract.get("turn", {})
    _keys(fname, body, t, out)
    kind = body.get("kind")
    kinds = prompt_capture_kinds_read(contract)
    if kinds and kind not in kinds:
        out.append(fname + ": kind " + repr(kind)
                   + " is not one of " + repr(kinds))
    # THE SHAPE TYPES `part` — a str for a part's turn, str-or-null for a
    # processing one, where null means the synthesis or the coalesce pass.
    _shape_name, shape = prompt_shape_read(kind, contract)
    if "part" in shape:
        _typed(fname, body, {"part": shape["part"]}, out)
    if t.get("time_re") and isinstance(body.get("time"), str) \
            and not re.match(t["time_re"], body["time"]):
        out.append(fname + ": time " + repr(body["time"])
                   + " is not the recorded shape")
    if t.get("filename") and isinstance(body.get("seq"), int) \
            and all(k in body for k in ("part", "time")):
        # THE ACTOR fills the part slot: the part, or the kind when there is
        # none — the same substitution record_turn() makes when it names the
        # file, so writer and checker cannot disagree about a synthesis turn.
        actor = body["part"] if body["part"] is not None else kind
        want = t["filename"].format(part=actor, time=body["time"],
                                    seq=body["seq"])
        if want != fname:
            out.append(fname + ": the body says it should be named " + want)
    if t.get("null_response_needs_error") and body.get("response") is None \
            and not body.get("error"):
        out.append(fname + ": response is null and no error is recorded")

    req = body.get("request")
    if not isinstance(req, dict):
        out.append(fname + ": request is not an object")
        return out
    rspec = contract.get("request", {})
    _keys(fname + " request", req, rspec, out)
    # `system` IS TYPED BY THE SHAPE: four blocks for a part's turn, one
    # string for a processing turn. A list under a processing kind or a string
    # under a part kind is refused here, by name.
    if "system" in shape:
        _typed(fname + " request", req, {"system": shape["system"]}, out)

    want_model = _source_constant(rspec.get("model_from", ""))
    if want_model and req.get("model") != want_model:
        out.append(fname + ": model " + repr(req.get("model"))
                   + " is not the code's own constant " + repr(want_model))
    cap = (rspec.get("max_tokens_when") or {}).get(body.get("kind"))
    if cap is not None and req.get("max_tokens") != cap:
        out.append(fname + ": a " + str(body.get("kind")) + " turn must send "
                   "max_tokens " + str(cap) + ", not "
                   + repr(req.get("max_tokens")))

    sspec = contract.get("system", {})
    order = sspec.get("order") or []
    system = req.get("system")
    # THE BLOCK WALK IS THE PART SHAPE'S. A processing turn declares
    # `system = "str"` and has no blocks to order or to cache; a shape that
    # declares nothing (an unknown kind) is walked as before, so the checker
    # never checks LESS than it did.
    if order and isinstance(system, list) and shape.get("system", "list") == "list":
        got = [b.get("block") if isinstance(b, dict) else None for b in system]
        if got != order:
            out.append(fname + ": system blocks are " + repr(got)
                       + ", contract says " + repr(order))
        for b in system:
            if not isinstance(b, dict):
                out.append(fname + ": a system entry is not an object")
                continue
            name = str(b.get("block"))
            for key in sspec.get("entry_required", []):
                if key not in b:
                    out.append(fname + ": system " + name + " has no "
                               + repr(key))
            groups = sspec.get("entry_one_of") or []
            if groups and not any(all(k in b for k in g) for g in groups):
                out.append(fname + ": system " + name
                           + " is neither by reference nor inline")
            cached = bool(b.get("cache_control"))
            if name in sspec.get("cached", []) and not cached:
                out.append(fname + ": system " + name + " lost its "
                           "cache_control — the cached-prefix claim broke")
            if name in sspec.get("uncached", []) and cached:
                out.append(fname + ": system " + name + " carries "
                           "cache_control, and the uncached tail never may")

    mspec = contract.get("messages", {})
    msgs = req.get("messages")
    if mspec and isinstance(msgs, list):
        if len(msgs) < mspec.get("min", 0):
            out.append(fname + ": " + str(len(msgs)) + " message(s), contract "
                       "wants at least " + str(mspec["min"]))
        # a processing turn is one user message — the material, assembled by
        # the caller — and never a conversation
        exactly = shape.get("messages_exactly")
        if exactly is not None and len(msgs) != exactly:
            out.append(fname + ": " + str(len(msgs)) + " message(s), a "
                       + str(kind) + " turn carries exactly " + str(exactly))
        roles = []
        for m in msgs:
            if not isinstance(m, dict):
                out.append(fname + ": a message is not an object")
                continue
            for key in mspec.get("entry_required", []):
                if key not in m:
                    out.append(fname + ": a message has no " + repr(key))
            roles.append(m.get("role"))
        allowed = mspec.get("roles") or []
        for r in roles:
            if allowed and r not in allowed:
                out.append(fname + ": message role " + repr(r)
                           + " is not one of " + repr(allowed))
        if roles and mspec.get("ends_with") \
                and roles[-1] != mspec["ends_with"]:
            out.append(fname + ": the recorded tail ends on "
                       + repr(roles[-1]) + ", contract says "
                       + repr(mspec["ends_with"]))
        if mspec.get("alternates"):
            for a, b in zip(roles, roles[1:]):
                if a == b:
                    out.append(fname + ": two " + repr(a)
                               + " messages in a row")
                    break

    resp = body.get("response")
    # A dry run records what WOULD have been sent and gets no service
    # reply, so it answers to its own shape (R368).
    pspec = contract.get("response_dry_run" if body.get("dry_run")
                         else "response", {})
    if isinstance(resp, dict) and pspec:
        _keys(fname + " response", resp, pspec, out)
        reasons = pspec.get("stop_reasons") or []
        if reasons and resp.get("stop_reason") not in reasons:
            out.append(fname + ": stop_reason "
                       + repr(resp.get("stop_reason"))
                       + " is not one of " + repr(reasons))
        uspec = pspec.get("usage", {})
        usage = resp.get("usage")
        if uspec and isinstance(usage, dict):
            _keys(fname + " response.usage", usage, uspec, out)
    return out


def _verify_dir(d: pathlib.Path, fails: list[str],
                notes: "list[str] | None" = None) -> tuple[int, int]:
    """Returns (block files checked, turn files checked)."""
    try:
        man = prompt_manifest_read(d)
    except Exception as e:                                   # noqa: BLE001
        fails.append(f"{d.name}/{MANIFEST}: unreadable — {e}")
        return 0, 0
    if "files" not in man:
        # A pre-R277 manifest (one <part>.md per part, blocks sliced by
        # offset). That layout was replaced outright and master's captures
        # in it deleted 2026-08-21 — but a LAB tree keeps its own (its
        # live circles closed before the ruling, tagged circle/lab/<OT>),
        # and nothing travels lab -> main (R249), so they stay. A NOTE,
        # not a failure: this verifier cannot vouch for them, and it has no
        # evidence they were altered either. Failing here would have made
        # the hook's `*prompts/*` trigger refuse every later close commit
        # in that tree on the strength of a directory it cannot read.
        (notes if notes is not None else fails).append(
            f"{d.name}/{MANIFEST}: pre-R277 layout — not verified (the "
            f"old per-part captures were retired 2026-08-21)")
        return 0, 0
    files = man.get("files", {})
    contract = prompt_capture_contract_read()
    if not contract:
        # R368: a checker that quietly stops checking is worse than none.
        (notes if notes is not None else fails).append(
            f"{CONTRACT.name} is missing or unreadable — the wire contract "
            f"was NOT checked for {d.name}")
    nb = nt = 0
    for fname, rec in files.items():
        f = d / fname
        if not f.is_file():
            fails.append(f"{d.name}/{fname} is missing")
            continue
        raw = f.read_bytes()
        nb += 1
        if len(raw) != rec["bytes"]:
            fails.append(f"{d.name}/{fname}: {len(raw)} bytes, manifest says "
                         f"{rec['bytes']}")
        if _sha(raw) != rec["sha256"]:
            fails.append(f"{d.name}/{fname}: sha256 mismatch — the capture "
                         f"has been altered")
        if rec.get("shared"):
            fails += [f"{d.name}/{x}"
                      for x in _leak_check(fname, raw.decode("utf-8", "replace"))]
    # Every part's block list must name files the manifest records, and its
    # shared entries must be THE shared files — one text per shared block is
    # the property the 2026-08-06 restructure bought (the cache prefix).
    for p, rec in man.get("parts", {}).items():
        for i, fname in enumerate(rec.get("blocks", [])):
            if fname not in files:
                fails.append(f"{d.name}: {p} lists {fname}, not in manifest")
            elif files[fname].get("shared") and files[fname]["part"] is not None:
                fails.append(f"{d.name}/{fname}: shared but bound to a part")
    # THE PROJECTION ASSERTION (R362) — the safety net R355 leans on, made
    # self-checking. `_remember_expectation()` carries the why; here it is
    # only ever a skip or a failure, never a repair.
    for p, rec in man.get("parts", {}).items():
        exp = rec.get("remember_projection")
        if not isinstance(exp, dict):
            continue                       # a pre-R362 capture: no claim made
        if exp.get("error") or exp.get("windowed") or not exp.get("records"):
            continue                       # nothing on file, or not promised
        prefix = exp.get("prefix") or ""
        if not prefix:
            continue
        idents = [(d / f).read_text(encoding="utf-8", errors="replace")
                  for f in rec.get("blocks", [])
                  if files.get(f, {}).get("block") in IDENTITY_BLOCKS
                  and (d / f).is_file()]
        if not idents:
            continue
        if not any(prefix in text for text in idents):
            fails.append(
                f"{d.name}: {p}'s newest remembered record reached neither "
                f"BLOCK 3 nor BLOCK 4 — the register projection did not "
                f"carry it into the prompt (the safety net R355 rests on)")

    seen_seq: set[int] = set()
    for t in man.get("turns", []):
        f = d / t["file"]
        if not f.is_file():
            fails.append(f"{d.name}/{t['file']} is missing")
            continue
        raw = f.read_bytes()
        nt += 1
        if len(raw) != t["bytes"] or _sha(raw) != t["sha256"]:
            fails.append(f"{d.name}/{t['file']}: sha256/size mismatch — the "
                         f"turn record has been altered")
            continue
        if t["seq"] in seen_seq:
            fails.append(f"{d.name}/{t['file']}: duplicate seq {t['seq']}")
        seen_seq.add(t["seq"])
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception as e:                               # noqa: BLE001
            fails.append(f"{d.name}/{t['file']}: not JSON — {e}")
            continue
        # THE WIRE CONTRACT, per request (R368). The sha checks above
        # prove the file has not been altered since it was written;
        # this proves what was written was the shape the code is
        # supposed to send.
        for bad in prompt_capture_contract_verify(t["file"], body, contract):
            fails.append(f"{d.name}/{bad}")
        part = body.get("part")
        for b in (body.get("request") or {}).get("system") or []:
            if not isinstance(b, dict):
                continue
            if "file" in b:
                rec = files.get(b["file"])
                if rec is None:
                    fails.append(f"{d.name}/{t['file']}: refers to "
                                 f"{b['file']}, not in manifest")
                elif rec["sha256"] != b.get("sha256"):
                    fails.append(f"{d.name}/{t['file']}: {b['file']} sha "
                                 f"does not match the Block file — a block "
                                 f"moved mid-circle?")
            elif b.get("block") == "part_objectives" and "text" in b \
                    and not b.get("differs_from_capture"):
                idx = (man.get("block_order") or list(block_names()))
                i = idx.index("part_objectives") if "part_objectives" in idx else 3
                fname = block_filename(i, "part_objectives", part or "")
                rec = files.get(fname)
                if rec is not None and rec["sha256"] != _sha(
                        b["text"].encode("utf-8")):
                    fails.append(f"{d.name}/{t['file']}: BLOCK 4 text is not "
                                 f"{fname}'s — the static-blocks claim broke")
    return nb, nt


def _dirs(ot: "str | None") -> list[pathlib.Path]:
    if ot is None:
        dirs = sorted(d for r in _roots() for d in r.glob("*") if d.is_dir())
    else:
        dirs = [r / ot for r in _roots() if (r / ot).is_dir()]
    return [d for d in dirs if (d / MANIFEST).is_file()]


def prompt_capture_verify(ot: "str | None" = None) -> int:
    """Re-hash every Block file and every turn file against the manifest,
    assert no SHARED block carries an addressed marker, and assert every
    turn file's block references resolve to the Block files by sha."""
    dirs = _dirs(ot)
    if not dirs:
        print("  no captures found under "
              + " or ".join(str(r.relative_to(ROOT)) + "/"
                            for r in (PROMPTS, SANDBOX_PROMPTS)))
        return 0
    fails: list[str] = []
    notes: list[str] = []
    nb = nt = 0
    for d in dirs:
        b, t = _verify_dir(d, fails, notes)
        nb += b
        nt += t
    print(f"  {len(dirs)} circle(s), {nb} block file(s) and {nt} turn file(s) "
          f"re-hashed, each request against turn_contract.toml")
    for n in notes:
        print(f"  note  {n}")
    if fails:
        print(f"\n  {len(fails)} FAILURE(S):")
        for f in fails:
            print(f"    - {f}")
        return 1
    print("  PASS — every file reproduces its sha256, no shared block\n"
          "         carries an addressed marker, and every turn's block\n"
          "         references resolve to the Block files, and every\n"
          "         request honours turn_contract.toml")
    return 0


def prompt_stats_read(ot: "str | None" = None) -> int:
    """Per-block, per-item character breakdown of the captured part-context
    prompt (Blocks 1-4) for one circle, or every circle if `ot` is None,
    read from manifest.json's own "items" — what was captured at open."""
    dirs = _dirs(ot)
    if not dirs:
        print("  no captures found under "
              + " or ".join(str(r.relative_to(ROOT)) + "/"
                            for r in (PROMPTS, SANDBOX_PROMPTS)))
        return 1
    for d in dirs:
        man = prompt_manifest_read(d)
        files = man.get("files", {})
        print(f"\n{d.relative_to(ROOT).as_posix()}:")
        for part, rec in man.get("parts", {}).items():
            total = sum(files[f]["chars"] for f in rec["blocks"] if f in files)
            print(f"\n  {part}  ({total:,} chars total)")
            for fname in rec["blocks"]:
                b = files.get(fname)
                if b is None:
                    print(f"    {fname}: MISSING from manifest")
                    continue
                items = b.get("items") or []
                print(f"    {b['block']}  {b['chars']:,} chars  ({fname})")
                w = max((len(x["label"]) for x in items), default=0)
                accounted = 0
                for x in items:
                    if x.get("chars") is None:
                        print(f"        {x['label']}")
                        continue
                    accounted += x["chars"]
                    print(f"        {x['label']:<{w}}  {x['chars']:,}")
                if accounted != b["chars"]:
                    print(f"        [reconciliation: {accounted:,} of "
                          f"{b['chars']:,} chars accounted for]")
        turns = man.get("turns", [])
        if turns:
            print(f"\n  {len(turns)} turn file(s), {man.get('turn_bytes', 0):,} bytes")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--stats" in argv:
        i = argv.index("--stats")
        sys.exit(prompt_stats_read(argv[i + 1] if i + 1 < len(argv) else None))
    args = [a for a in argv if a != "--verify"]
    sys.exit(prompt_capture_verify(args[0] if args else None))
