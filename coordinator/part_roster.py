#!/usr/bin/env python3
"""
part_roster.py — ONE roster, READ FROM `parts/`. B29 2026-08-07, R123 2026-08-08.

WHAT THIS REPLACES. A14 counted thirteen hardcoded copies of the part list
across eight files; coordinator/circle_close_verify.py makes it nine files, ten copies.
Each copy was a place a part could be silently absent — adding a part meant
finding and editing all ten, and a miss does not error, it just leaves that
reader blind to the new part. B29 collapsed those ten into one list here.

WHAT R123 CHANGED, AND WHY IT MATTERED MORE. The one list was still typed by
hand, in a module that SHIPS — so the bundle carried seven names that are one
person's parts, exported as though they were mechanism. It was already broken
by it: `export/parts/` holds two delegates, so a recipient's roster named five
directories that do not exist and `circle.py --live` would have opened on them.

    *"TWO parts, Soul and Child, are shipped as
     delegates ... other parts will be created
     per-user; NOT 7 parts."*
    *"Parts have their roots in parts/ — the
     directory contains home directories for each
     part, thus the directory names are the part
     names."*

THE DIRECTORY NAME GIVES THE ID; IT CANNOT GIVE THE TAG. So `parts/<dir>/
part.toml` names the display Tag, and **its presence is what makes a
directory a part** — a decision a bare scan cannot make, and the reason
this is a marker file rather than a glob for `long_term.md`.

WHAT ELSE THE MARKER MAY CARRY. Three keys now, each the same shape of
fact: something true of THIS part that no directory name can give, and
that shipped code must therefore not hardcode. `tag` (required), the
historical spellings `alt_tags` (R123-era, 2026-08-08), and — R246,
2026-08-22 — `identity_tail`, this part's own BLOCK 3 tail (it was
`minimal_tail`, a BLOCK 4 suffix under `--minimal` only, R246).
Each arrived the same way: as a per-part literal in a module that SHIPS,
keyed by a part NAME. `identity_tail` is the last of that class B29 and
R123 began removing. The marker is still narrow, and the test is whether a
key is a fact about one part or a policy about all of them. `REMEMBER_GUIDANCE`
was the only policy that had been living here and it LEFT, R-NEW 2026-08-22,
for process_core.md and BLOCK 1 — so this module now carries per-part facts
and nothing else, which is what the test always implied.

A FOURTH, 2026-08-23 (R331): the `[context]` table — what this
part wants to know about its human, and the answers once given. Same test,
same side of it. It is the one key this module also WRITES (write_context);
see the `[context]` section below.

ORDER IS ALPHABETICAL BY DIRECTORY NAME, AND THAT IS THE WHOLE OF IT.
Previously two orders coexisted: a canonical circle order typed here, and
alphabetical for three readers. A canonical order cannot survive a scan —
there is nothing in a directory to derive it from, and an `order = N` key
would be per-installation config a recipient must set correctly to be safe.

    who SPEAKS when   already random, per
                      round — circle.py
                      shuffles the poll order
                      on every pass, and has.
    who is LISTED     alphabetical, stable.

Deterministic listing is load-bearing rather than incidental: prompt blocks 1
and 2 are byte-identical across every part, which is what makes the cached
prefix 42,464 characters rather than 6,976, and `prompt_capture --verify`
asserts it. A shuffled enumeration would rewrite those bytes every run.

`ALPHA_DIR_NAMES` is kept as an ALIAS of `DIR_NAMES`, not deleted — the two
are now the same list, and keeping the name means `record_model` and
`practice_manager` do not move for a rename that changes nothing.

`part_verify()` IS THE CHECK, AND IT IS CALLED. It used to compare a list against
the tree; the list is now the tree, so that comparison can never fail and
keeping it under the same name would be a check that quietly stopped
checking. What it refuses instead is below, and `circle.py` runs it before
opening — a part dropped for a malformed `part.toml` is a part absent from
the circle, and absence reads downstream as no engagement.
"""

from __future__ import annotations

import pathlib

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
import sys                                                   # noqa: E402
sys.path.insert(0, str(HERE))
import record_paths as _RP                                   # noqa: E402
PARTS_DIR = _RP.PARTS_DIR       # the default group's parts/ — record_paths.group_tree (B117)

# The marker. A directory under parts/ that has one IS a part; a directory
# that has none is reported, never silently skipped.
MARKER = "part.toml"

# Not parts, and not reported as missing one either.
SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv"})

# `[Tag]:` is the transcript grammar (circle.py, circle_audit.py,
# circle_close_verify.py all parse on it), so a Tag carrying either bracket or a
# newline would write a transcript its own readers cannot parse.
BAD_IN_TAG = ("[", "]", "\n", "\r")


# ------------------------------------------------------------------ [context]
# THE FOURTH THING THE MARKER MAY CARRY — R331, 2026-08-23 (the
# design is docs/Initialization.md; the first declarers are the shipped Soul
# and Child). A part may declare what it wants to know about its human:
#
#     [context]
#     purpose = "Tell me a bit about where you come from"
#     [[context.questions]]
#     key = "birth_year"  ask = "What year were you born"
#     data_type = "NUMERIC_STRING"  data_max = 2100
#     render = "I came into the world in {answer}."      # OPTIONAL — see below
#     ...
#     # >>> context.answers
#     [context.answers]
#     birth_year = ""
#     # <<< context.answers
#
# Same test as every other key here: a fact about ONE part, not a policy about
# all of them — what the Soul wants to know is the Soul's. `data_type` and
# `data_max` ride with each question because the operator hand-tunes them and
# "changed numbers should be active" (R332): nothing here is
# cached, every reader reads the file.
#
# `render` IS THE ONLY PATH FROM AN ANSWER INTO A PROMPT. prompt_build's
# identity_tail() renders an answer through its question's render string and
# through nothing else, so a question that declares none is recorded-only —
# R329, 2026-08-23: the Soul's given and preferred names
# are PII, held in the file and never rendered (R132). The gate is the absence
# of a string, not a flag the code has to remember to check.
#
# THIS MODULE STAYS THE ONE READER OF part.toml's FORMAT, and gains the one
# writer. part_context_write() replaces exactly the bytes between the two markers
# above — never re-serialises the file, whose comment prose is history (a
# tomli_w round-trip would flatten it) — and re-reads the result before it
# returns.

CONTEXT_OPEN = "# >>> context.answers"
CONTEXT_CLOSE = "# <<< context.answers"
DATA_TYPES = ("STRING", "NUMERIC_STRING")

# HOW A FIELD IS MADE VALID — ruled 2026-08-28, "declare the gate kind". The
# vocabulary and the checking live in initialization.py beside validate(),
# which is what actually enforces them; this file gates the DECLARATION, so a
# question cannot be added that says it is constrained and is not.
#
# `data_type` is the SHAPE (a string, a number). `gate` is the CONSTRAINT.
# ONE_OF is a gate over a STRING rather than a type of its own, which is why
# a question declares both — the two answer different questions and collapsing
# them would make "a number from a fixed list" inexpressible.
GATES = ("ONE_OF", "BOUNDED", "UNIQUE_IN", "CHECK_AT_USE")


# A BOUND MAY BE A RULE RATHER THAN A NUMBER, and for a birth year it must
# be: `current year - 15` is 2011 today and 2012 on the first of January. A
# literal in a register would be quietly wrong within months — the shape of
# every stale number this project has had to find twice.
#
# A CLOSED TABLE, NOT AN EXPRESSION LANGUAGE. Nothing is parsed and nothing is
# evaluated: a bound is an integer or one of these names. `"year - 15"` read
# out of a register and evaluated would be a small language inside a file a
# person edits by hand, and there would be no way to gate it.
#
# IT LIVES HERE, IN THE LEAF, and initialization.py imports it — this was
# briefly a mirrored copy with a note that a probe would keep the two equal,
# which is the two-copies-of-one-fact defect this project records more than
# any other. `initialization` imports `roster`, so the one direction that
# closes no cycle is this one.
BOUND_RULES = {"year_minus_15": lambda today: today.year - 15}


def part_bound_resolve(spec, today=None):
    """A declared bound as a number, or None when there is none."""
    if isinstance(spec, bool):
        return None
    if isinstance(spec, int):
        return spec
    rule = BOUND_RULES.get(spec) if isinstance(spec, str) else None
    if rule is None:
        return None
    import datetime
    return rule(today or datetime.date.today())


def part_context_value_verify(q: dict, answer: str) -> "str | None":
    """THE ONE VALUE CHECK, shared by every editor — None when `answer` is
    acceptable for the declaration `q`, else the line to print before asking
    again.

    IT LIVES IN THE LEAF SO THERE IS ONLY ONE. Before 2026-08-28 there were
    three: initialization.initialization_validate() for a part's context questions,
    setting_manager.setting_coerce() for the settings register, and — added the same week and
    the reason this consolidation happened at all — an inline `not in
    knob.choices` in setting_manager.setting_tuning_write() for provider tuning, which
    bypassed both. Three vocabularies for one idea is how they drift.

    PURE, DELIBERATELY. Everything here is decidable from the declaration and
    the answer alone. The checks that need live data — uniqueness against the
    roster or the issue graph — stay in initialization.initialization_validate(), which calls
    this first and then adds its own.

    Empty is always valid: unset, take the default. That is R332's rule and it
    holds for every gate."""
    if answer == "":
        return None
    dt = q.get("data_type")

    values = q.get("values")
    if q.get("gate") == "ONE_OF" or values:
        vals = [str(v) for v in (values or ())]
        if answer.strip().lower() not in {v.lower() for v in vals}:
            return f"  one of: {', '.join(vals)}"
        return None

    dm = q.get("data_max")
    if dt == "NUMERIC_STRING":
        lo = part_bound_resolve(q.get("minimum", 0))
        lo = 0 if lo is None else lo
        hi = part_bound_resolve(q.get("maximum"))
        if hi is None:
            hi = dm if isinstance(dm, int) and not isinstance(dm, bool) else None
        if not part_context_is_whole_number(answer.strip()):
            shape = "whole" if lo < 0 else "whole, positive"
            return f"  a number is needed here — {shape}, numerals only"
        n = int(answer.strip())
        if n < lo:
            return f"  too small — at least {lo}"
        if hi is not None and n > hi:
            return f"  too large — at most {hi}"
        return None

    if isinstance(dm, int) and not isinstance(dm, bool) and len(answer) > dm:
        return f"  too long — {len(answer)} characters; at most {dm}"
    if "[" in answer or "]" in answer:
        return "  no square brackets — they mean something to the circle"
    return None


def part_context_is_whole_number(t: str) -> bool:
    """Whole, optionally negative. NEGATIVES ARE NEW, 2026-08-28 (minimum
    defaults to 0 but may go below it) — the old test was `answer.isdigit()`,
    which refuses a leading minus outright, and the line it printed said
    "positive"."""
    body = t[1:] if t.startswith("-") else t
    return bool(body) and body.isdigit() and body.isascii()


def part_canonical_read(q: dict, answer: str) -> str:
    """What to STORE for an accepted answer. A ONE_OF match is
    case-insensitive, so the declared spelling is what lands in the file and
    the register stays canonical however it was typed."""
    vals = q.get("values")
    if vals:
        for v in vals:
            if str(v).lower() == answer.strip().lower():
                return str(v)
    return answer


def _mechanism_keys() -> tuple:
    """Context answers the MECHANISM reads, from the module that reads them.
    Late import: identity is a leaf this one is imported BY."""
    try:
        import identity as _ID
        return tuple(_ID.self_consumed_keys_read())
    except Exception:                                          # noqa: BLE001
        return ()


def _gate_faults(where: str, k: str, q: dict) -> list:
    """What is wrong with one question's gate declaration, or [].

    A GATE IS REQUIRED WHERE THE MECHANISM READS THE ANSWER, and nowhere else
    — 2026-08-28. An answer that only reaches a model may be loose, because a
    model reads around a typo and the looseness is the asset. An answer that
    reaches NEITHER (the ten questions declaring no `render`: the two names,
    and the gender and religion answers ruled recorded-but-never-spoken) has
    nothing acting on it, so there is nothing to keep valid.

    Which is why the requirement is keyed on identity.self_consumed_keys_read() rather
    than on anything in the declaration: whether the mechanism reads an answer
    is a fact about the READER, and only the reader can state it."""
    out = []
    if k in _mechanism_keys() and not q.get("gate"):
        out.append(f"{where} {k}: the mechanism reads this answer "
                   f"(identity.self_consumed_keys_read), so it must declare a `gate` — "
                   f"one of {', '.join(GATES)}")
    gate = q.get("gate")
    if gate is not None and gate not in GATES:
        out.append(f"{where} {k}: `gate` must be one of "
                   f"{', '.join(GATES)}, got {gate!r}")
        return out
    if gate == "ONE_OF" or "values" in q:
        vals = q.get("values")
        if not isinstance(vals, list) or not vals:
            out.append(f"{where} {k}: ONE_OF needs a non-empty `values` list")
            return out
        if not all(isinstance(v, str) and v.strip() for v in vals):
            out.append(f"{where} {k}: every `values` entry must be a "
                       f"non-empty string")
        folded = [str(v).strip().lower() for v in vals]
        if len(set(folded)) != len(folded):
            # Case-folded, because matching is: two choices differing only in
            # case would make one of them unreachable.
            out.append(f"{where} {k}: `values` has duplicates, case-insensitively")
        if "data_max" in q:
            # A closed list IS the constraint; a length cap on top could only
            # ever refuse a value already in the list, which reads as a bug.
            out.append(f"{where} {k}: ONE_OF must not also declare `data_max`")
        return out
    # Everything else still needs its size bound — this is the rule that has
    # always been here, now conditional so ONE_OF is expressible at all.
    # WITHOUT THAT CONDITION THIS CRASHED: validate() read int(data_max)
    # unconditionally, so a ONE_OF question declared without one took down the
    # first-run dialog rather than failing a check.
    dm = q.get("data_max")
    if not isinstance(dm, int) or isinstance(dm, bool) or dm <= 0:
        out.append(f"{where} {k}: `data_max` must be a positive integer, "
                   f"got {dm!r}")
    for bound in ("minimum", "maximum", "advisory_maximum"):
        if bound not in q:
            continue
        v = q[bound]
        ok = (isinstance(v, int) and not isinstance(v, bool)) or (
            isinstance(v, str) and v in BOUND_RULES)
        if not ok:
            out.append(f"{where} {k}: `{bound}` must be a whole number or one "
                       f"of {', '.join(sorted(BOUND_RULES))}, got {v!r}")
    if "advisory_maximum" in q and not str(q.get("advisory_note", "")).strip():
        out.append(f"{where} {k}: `advisory_maximum` needs an "
                   f"`advisory_note` — a threshold that says nothing is just "
                   f"a bound nobody enforces")
    return out


# `unique_in`, OPTIONAL per question — the operator, 2026-08-23: *"Duplicates
# of any UNIQUE KEY member (e.g. part name "Soul", issue id "n0001") must be
# detected and rejected, echo error and loop at the prompt."* A question may
# say which unique space its answer must not collide with; the validator in
# initialization.py checks it. The Soul's preferred_name declares "part_tags":
# it becomes the console's reserved name (identity.user_name_read()), which
# part_roster.part_verify() refuses any part to wear.
UNIQUE_SPACES = ("part_tags", "issue_ids", "issue_labels")


def part_context_problems_read(dir_name: str, doc: dict) -> list[str]:
    """Everything wrong with a loaded part.toml's [context] table, as
    human-readable lines; [] for a clean table and for no table at all
    (absent is the normal case — five of seven parts here declare none)."""
    ctx = doc.get("context")
    if ctx is None:
        return []
    where = f"parts/{dir_name}/{MARKER} [context]"
    if not isinstance(ctx, dict):
        return [f"{where} must be a table, got {type(ctx).__name__}"]
    out: list[str] = []
    if not isinstance(ctx.get("purpose", ""), str):
        out.append(f"{where}: `purpose` must be a string")
    qs = ctx.get("questions", [])
    if not isinstance(qs, list) or any(not isinstance(q, dict) for q in qs):
        return out + [f"{where}: `questions` must be an array of tables"]
    keys: list[str] = []
    for i, q in enumerate(qs, 1):
        k = q.get("key")
        if not isinstance(k, str) or not k.strip():
            out.append(f"{where} question {i}: `key` must be a non-empty string")
            continue
        if k in keys:
            out.append(f"{where} question {i}: key {k!r} is declared twice")
        keys.append(k)
        if not isinstance(q.get("ask"), str) or not q["ask"].strip():
            out.append(f"{where} {k}: `ask` must be a non-empty string")
        if q.get("data_type") not in DATA_TYPES:
            out.append(f"{where} {k}: `data_type` must be one of "
                       f"{', '.join(DATA_TYPES)}, got {q.get('data_type')!r}")
        out.extend(_gate_faults(where, k, q))
        if "render" in q and not isinstance(q["render"], str):
            out.append(f"{where} {k}: `render` must be a string when present")
        if "unique_in" in q and q["unique_in"] not in UNIQUE_SPACES:
            out.append(f"{where} {k}: `unique_in` must be one of "
                       f"{', '.join(UNIQUE_SPACES)}, got {q.get('unique_in')!r}")
    ans = ctx.get("answers", {})
    if not isinstance(ans, dict):
        return out + [f"{where}: `answers` must be a table"]
    for k, v in ans.items():
        if not isinstance(v, str):
            out.append(f"{where}.answers: {k} must be a string, got {v!r}")
        if k not in keys:
            out.append(f"{where}.answers: {k!r} answers no declared question")
    return out


def part_context_read(dir_name: str, base: pathlib.Path | None = None
                 ) -> dict | None:
    """The part's [context] as declared RIGHT NOW — purpose, questions (each
    with key/ask/data_type/data_max and render when declared), answers (a
    key->string dict over every declared key, "" where unanswered). None
    when the part declares no context, or its file cannot be read or has a
    problem part_context_problems_read() would report — so a caller never sees a
    half-shaped table. Reads the file every call, deliberately
    (R332: a hand-tuned data_max is active at once)."""
    f = (base or PARTS_DIR) / dir_name / MARKER
    try:
        doc = tomllib.loads(f.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None
    ctx = doc.get("context")
    if ctx is None or part_context_problems_read(dir_name, doc):
        return None
    qs = []
    for q in ctx.get("questions", []):
        row = {"key": q["key"], "ask": q["ask"],
               "data_type": q["data_type"], "data_max": q["data_max"]}
        if isinstance(q.get("render"), str) and q["render"].strip():
            row["render"] = q["render"]
        if q.get("unique_in"):
            row["unique_in"] = q["unique_in"]
        qs.append(row)
    recorded = ctx.get("answers", {})
    answers = {q["key"]: recorded.get(q["key"], "") for q in qs}
    return {"purpose": ctx.get("purpose", ""), "questions": qs,
            "answers": answers}


def _toml_str(s: str) -> str:
    """A TOML basic string literal for `s` — the four escapes tomllib
    requires, nothing clever."""
    return '"' + (s.replace("\\", "\\\\").replace('"', '\\"')
                  .replace("\n", "\\n").replace("\t", "\\t")) + '"'


def part_context_write(dir_name: str, answers: dict[str, str],
                  base: pathlib.Path | None = None) -> None:
    """Record answers: replace the bytes between CONTEXT_OPEN and
    CONTEXT_CLOSE in parts/<dir>/part.toml with a fresh [context.answers]
    table (appending the block if the file has none yet), atomically, then
    re-read the file and refuse — raising, with the file untouched — if the
    result would not load or would not verify. Every declared question gets
    a key, in question order, "" where unanswered; a key that answers no
    declared question is refused before anything is written.

    The rest of the file is NOT re-serialised: its comment prose is the
    part's history and tomli_w would flatten it. Bytes outside the markers
    are preserved exactly."""
    from atomic_write import record_atomic_write
    ctx = part_context_read(dir_name, base)
    if ctx is None:
        raise ValueError(f"parts/{dir_name}/{MARKER} declares no usable "
                         f"[context]; nothing to record answers against")
    keys = [q["key"] for q in ctx["questions"]]
    stray = [k for k in answers if k not in keys]
    if stray:
        raise ValueError(f"parts/{dir_name}/{MARKER}: {', '.join(stray)} "
                         f"answer(s) no declared question")
    for k, v in answers.items():
        if not isinstance(v, str):
            raise ValueError(f"parts/{dir_name}/{MARKER}: {k} must be a "
                             f"string, got {v!r}")
    merged = dict(ctx["answers"])
    merged.update(answers)
    body = "\n".join([CONTEXT_OPEN, "[context.answers]"]
                     + [f"{k} = {_toml_str(merged.get(k, ''))}" for k in keys]
                     + [CONTEXT_CLOSE])
    f = (base or PARTS_DIR) / dir_name / MARKER
    text = f.read_text(encoding="utf-8")
    i, j = text.find(CONTEXT_OPEN), text.find(CONTEXT_CLOSE)
    if i >= 0 and j > i:
        new = text[:i] + body + text[j + len(CONTEXT_CLOSE):]
    elif i < 0 and j < 0:
        new = text.rstrip("\n") + "\n\n" + body + "\n"
    else:
        raise ValueError(f"parts/{dir_name}/{MARKER}: the context.answers "
                         f"markers are unpaired — repair the file by hand")
    # VALIDATE, THEN COMMIT — the register writers' ordering: the new text
    # must load and verify BEFORE it replaces the file.
    try:
        doc = tomllib.loads(new)
    except Exception as e:                                      # noqa: BLE001
        raise ValueError(f"parts/{dir_name}/{MARKER}: the rewrite would not "
                         f"load ({e}); nothing written") from e
    probs = part_context_problems_read(dir_name, doc)
    if probs:
        raise ValueError(f"parts/{dir_name}/{MARKER}: the rewrite would not "
                         f"verify ({probs[0]}); nothing written")
    record_atomic_write(f, new)
    if part_context_read(dir_name, base) is None:              # belt and braces
        raise RuntimeError(f"parts/{dir_name}/{MARKER}: written, but does "
                           f"not read back — restore it from git")


def part_scan(base: pathlib.Path | None = None
         ) -> tuple[list[tuple[str, str]], dict[str, str],
                    dict[str, str], list[str]]:
    """Read parts/ and return (roster, alt_tags, identity_tails, problems).

    roster         [(dir_name, Tag)], alphabetical by dir_name
    alt_tags       {historical Tag: dir_name}
    identity_tails {dir_name: text} — only parts that declare one
    problems       human-readable; empty is clean

    NEVER RAISES. Nine modules import this at load; a malformed part.toml
    must not take down a probe run or a `--status`. A part with any problem
    of its own is EXCLUDED from the roster and NAMED in problems — excluded
    and loud beats included and malformed, but only because `part_verify()` is
    wired into the one path where the difference is destructive.

    `identity_tails` ARRIVED WITH R246, 2026-08-19 as `minimal_tails` ("put it in a part.toml
    field") — the fourth return value, so every reader of part.toml's
    format stays this one function. It is keyed by DIRECTORY, which is the
    whole point of the ruling: the text used to sit in prompt_build under a
    part NAME typed into shared mechanism, and a rename in that lineage
    (`injured_soul` -> `soul`) had already orphaned one such key silently.
    """
    base = base or PARTS_DIR
    roster: list[tuple[str, str]] = []
    alt: dict[str, str] = {}
    tails: dict[str, str] = {}
    problems: list[str] = []

    if not base.is_dir():
        return roster, alt, tails, [f"{base} does not exist — no parts to read"]

    seen: dict[str, str] = {}     # Tag (or alt Tag) -> dir that claimed it
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if d.name in SKIP_DIRS or d.name.startswith("."):
            continue
        f = d / MARKER
        if not f.is_file():
            problems.append(f"parts/{d.name}/ has no {MARKER} — not a part. "
                            f"Add one naming its Tag, or move the directory "
                            f"out of parts/.")
            continue
        try:
            doc = tomllib.loads(f.read_text(encoding="utf-8"))
        except Exception as e:                    # tomllib raises its own type
            problems.append(f"parts/{d.name}/{MARKER} does not load: {e}")
            continue

        tag = doc.get("tag")
        if not isinstance(tag, str) or not tag.strip():
            problems.append(f"parts/{d.name}/{MARKER}: `tag` must be a "
                            f"non-empty string, got {tag!r}")
            continue
        tag = tag.strip()
        bad = [c for c in BAD_IN_TAG if c in tag]
        if bad:
            shown = ", ".join(repr(c) for c in bad)
            problems.append(f"parts/{d.name}/{MARKER}: tag {tag!r} contains "
                            f"{shown} — `[Tag]:` is the transcript grammar")
            continue
        if tag in seen:
            problems.append(f"parts/{d.name}/{MARKER}: tag {tag!r} is already "
                            f"used by parts/{seen[tag]}/ — a duplicate tag "
                            f"collapses the Tag->dir mapping silently")
            continue
        seen[tag] = d.name
        roster.append((d.name, tag))

        # READ BEFORE alt_tags, deliberately: that block's own `continue`
        # skips the rest of this part's processing on a malformed value,
        # and a part's identity tail must not go missing because its
        # historical-spelling list is wrong. Absent is the normal case —
        # six of seven parts here declare none, and a bundle's Child
        # declares none either.
        mt = doc.get("identity_tail", "")
        if not isinstance(mt, str):
            problems.append(f"parts/{d.name}/{MARKER}: `identity_tail` must "
                            f"be a string, got {mt!r}")
        elif mt.strip():
            tails[d.name] = mt

        # THE [context] TABLE — R331, 2026-08-23. Reported, never
        # excluding: a malformed context is one dialog that cannot be asked,
        # and dropping the part for it would be the absence-reads-as-silence
        # failure this scan exists to prevent (the identity_tail precedent
        # above). part_verify() refuses the open on any problem, so it is loud.
        problems += part_context_problems_read(d.name, doc)

        alts = doc.get("alt_tags", [])
        if not isinstance(alts, list) or any(not isinstance(a, str)
                                             for a in alts):
            problems.append(f"parts/{d.name}/{MARKER}: `alt_tags` must be a "
                            f"list of strings, got {alts!r}")
            continue
        for a in alts:
            a = a.strip()
            if not a:
                continue
            if a in seen:
                problems.append(f"parts/{d.name}/{MARKER}: alt tag {a!r} is "
                                f"already used by parts/{seen[a]}/")
                continue
            seen[a] = d.name
            alt[a] = d.name

    if not roster:
        problems.append(f"no {MARKER} found under {base} — the roster is "
                        f"EMPTY and a circle would open with no parts")
    return roster, alt, tails, problems


ROSTER, ALT_TAGS, IDENTITY_TAILS, PROBLEMS = part_scan()

DIR_NAMES: list[str] = [d for d, _t in ROSTER]               # alphabetical
ALPHA_DIR_NAMES: list[str] = DIR_NAMES                       # alias, see above
TAGS: list[str] = [t for _d, t in ROSTER]                    # same order
TAG_BY_DIR: dict[str, str] = dict(ROSTER)                    # dir -> Tag
DIR_BY_TAG: dict[str, str] = {t: d for d, t in ROSTER}       # Tag -> dir, current only
DIR_BY_TAG_ALL: dict[str, str] = {**DIR_BY_TAG, **ALT_TAGS}  # + historical


@_RP.group_follow
def part_roster_rebind() -> None:
    """Re-scan the CURRENT group's parts/ into the tables above, IN PLACE — B117 stage 3
    (2026-09-07). Every reader holds these same list and dict objects (`R.DIR_NAMES`,
    `from record_paths import PART_TAGS`), so mutating them is what makes a process opened on
    another group see that group's roster without re-importing anything. Runs after every
    record_paths.group_set()."""
    global PARTS_DIR
    PARTS_DIR = _RP.PARTS_DIR
    roster, alt, tails, probs = part_scan(PARTS_DIR)
    ROSTER[:] = roster
    ALT_TAGS.clear(); ALT_TAGS.update(alt)
    IDENTITY_TAILS.clear(); IDENTITY_TAILS.update(tails)
    PROBLEMS[:] = probs
    DIR_NAMES[:] = [d for d, _t in roster]
    TAGS[:] = [t for _d, t in roster]
    TAG_BY_DIR.clear(); TAG_BY_DIR.update(dict(roster))
    DIR_BY_TAG.clear(); DIR_BY_TAG.update({t: d for d, t in roster})
    DIR_BY_TAG_ALL.clear(); DIR_BY_TAG_ALL.update({**DIR_BY_TAG, **alt})


def statement_re(tags):
    """THE transcript statement-line grammar, compiled for a tag set —
    exactly what the writer produces (transcript_store.statement_line):
    "[Tag]: text" or "[Tag] [To: X]: text", one space, [To: ...] the only
    legal second bracket. One builder since 2026-08-19 (review, tier 3
    #35): circle_close_verify.py and circle_audit.py (then nightly.py) each
    hand-rolled their own and the two had drifted — close accepted ANY
    second bracket, the audit accepted arbitrary spacing — so the close's
    who-owes-a-short_term set and the audit's backfill set could disagree
    on the same line, the exact gap both scanners exist to close.
    Measured before converging: across all 47 transcripts on 2026-08-19,
    neither divergence matched a single real line, so the writer's
    grammar is the corpus's whole truth. The TAG SET stays the caller's
    parameter — circle_close_verify walks historical transcripts and passes
    DIR_BY_TAG_ALL; the audit processes only its own recent circles and
    passes TAGS — that difference is documented intent, not drift.

    Lives HERE because this module owns the tags a statement line can
    carry; the full-statement PARSER (transcript_store._STMT_RE) stays
    its own — it fullmatches whole records and captures text, a
    different job from line-scanning."""
    import re
    return re.compile(
        r"^\[(" + "|".join(re.escape(t) for t in tags)
        + r")\](?: \[To:[^\]]*\])?:")

# REMEMBER GUIDANCE — a part capability, not a circle one, so it is owned
# here rather than in circle.py: the same reasoning that makes this module
# (not circle.py) the source of TAG_BY_DIR. ruled 2026-08-12: "Part memory
# is a part feature, block 3, not a circle feature." ONE constant, not a
# field on seven part.toml files — the text is deliberately identical for
# every part and names no part, so it is POLICY, not a fact about any one
# of them. That distinction is the whole test, and it survives R246 adding
# `identity_tail` to the marker: a per-part tail differs per part by
# definition, this does not.
#
# REMEMBER_GUIDANCE WAS THAT POLICY AND IS GONE FROM HERE — R-NEW,
# 2026-08-22. Its own argument finished the journey: text that is policy
# about all of them belongs with the other policy, in process_core.md and
# BLOCK 1, beside the `[remember: ...]` annotation it governs. Keeping it
# here put 1,518 identical bytes into BLOCK 3, the one block that exists to
# differ per part. What a part CHOOSES to remember is still per-part and
# still reaches block 3, under `## What you have chosen to remember`.
# part_roster.py now owns only per-part facts, which is what this comment always
# said the test was.


def part_verify(base: pathlib.Path | None = None) -> list[str]:
    """Everything part_scan() refused, plus the checks that need the wider tree.

    Returns problems; empty is clean. Re-scans rather than reading PROBLEMS
    so a caller can point it at a fixture, and so a tree edited since import
    is read as it is now.

        no part.toml in a parts/ subdirectory
        part.toml that does not load
        tag missing, empty, or not a string
        tag carrying [ ] or a newline
        duplicate tag across two parts
        alt_tags not a list of strings
        identity_tail not a string
        zero parts
        tag colliding with Self's display name
    """
    _roster, _alt, _tails, problems = part_scan(base)

    # Self is not a part but shares the transcript's `[Tag]:` grammar, so a
    # part tagged with Self's display name would make every statement
    # ambiguous about who spoke. Imported here rather than at module load:
    # identity.py reads .env, and nine modules import this file.
    try:
        import identity as ID
        reserved = {ID.user_name_read(), ID.DEFAULT_NAME, ID.SELF_ID}
    except Exception:                    # no dotenv, no .env — not this file's
        reserved = {"Self", "self"}
    for d, t in _roster:
        if t in reserved or t.lower() in {r.lower() for r in reserved}:
            problems.append(f"parts/{d}/{MARKER}: tag {t!r} is Self's name — "
                            f"a part cannot share the operator's tag")
    return problems


if __name__ == "__main__":
    probs = part_verify()
    print(f"  {len(DIR_NAMES)} part(s): {', '.join(DIR_NAMES) or '(none)'}")
    if probs:
        for p in probs:
            print(f"    FAIL  {p}")
        raise SystemExit(1)
    print(f"  PASS — every directory under parts/ has a {MARKER}")
