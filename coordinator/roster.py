#!/usr/bin/env python3
"""
roster.py — ONE roster, READ FROM `parts/`. B29 2026-08-07, R123 2026-08-08.

WHAT THIS REPLACES. A14 counted thirteen hardcoded copies of the part list
across eight files; coordinator/circle_close.py makes it nine files, ten copies.
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
are now the same list, and keeping the name means `ifs_model` and
`check_best_practices` do not move for a rename that changes nothing.

`verify()` IS THE CHECK, AND IT IS CALLED. It used to compare a list against
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
PARTS_DIR = ROOT / "parts"

# The marker. A directory under parts/ that has one IS a part; a directory
# that has none is reported, never silently skipped.
MARKER = "part.toml"

# Not parts, and not reported as missing one either.
SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv"})

# `[Tag]:` is the transcript grammar (circle.py, circle_audit.py,
# circle_close.py all parse on it), so a Tag carrying either bracket or a
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
# writer. write_context() replaces exactly the bytes between the two markers
# above — never re-serialises the file, whose comment prose is history (a
# tomli_w round-trip would flatten it) — and re-reads the result before it
# returns.

CONTEXT_OPEN = "# >>> context.answers"
CONTEXT_CLOSE = "# <<< context.answers"
DATA_TYPES = ("STRING", "NUMERIC_STRING")
# `unique_in`, OPTIONAL per question — the operator, 2026-08-23: *"Duplicates
# of any UNIQUE KEY member (e.g. part name "Soul", issue id "n0001") must be
# detected and rejected, echo error and loop at the prompt."* A question may
# say which unique space its answer must not collide with; the validator in
# initialization.py checks it. The Soul's preferred_name declares "part_tags":
# it becomes the console's reserved name (identity.user_name()), which
# roster.verify() refuses any part to wear.
UNIQUE_SPACES = ("part_tags", "issue_ids", "issue_labels")


def context_problems(dir_name: str, doc: dict) -> list[str]:
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
        dm = q.get("data_max")
        if not isinstance(dm, int) or isinstance(dm, bool) or dm <= 0:
            out.append(f"{where} {k}: `data_max` must be a positive integer, "
                       f"got {dm!r}")
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


def read_context(dir_name: str, base: pathlib.Path | None = None
                 ) -> dict | None:
    """The part's [context] as declared RIGHT NOW — purpose, questions (each
    with key/ask/data_type/data_max and render when declared), answers (a
    key->string dict over every declared key, "" where unanswered). None
    when the part declares no context, or its file cannot be read or has a
    problem context_problems() would report — so a caller never sees a
    half-shaped table. Reads the file every call, deliberately
    (R332: a hand-tuned data_max is active at once)."""
    f = (base or PARTS_DIR) / dir_name / MARKER
    try:
        doc = tomllib.loads(f.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return None
    ctx = doc.get("context")
    if ctx is None or context_problems(dir_name, doc):
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


def write_context(dir_name: str, answers: dict[str, str],
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
    from atomic_write import atomic_write
    ctx = read_context(dir_name, base)
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
    probs = context_problems(dir_name, doc)
    if probs:
        raise ValueError(f"parts/{dir_name}/{MARKER}: the rewrite would not "
                         f"verify ({probs[0]}); nothing written")
    atomic_write(f, new)
    if read_context(dir_name, base) is None:              # belt and braces
        raise RuntimeError(f"parts/{dir_name}/{MARKER}: written, but does "
                           f"not read back — restore it from git")


def scan(base: pathlib.Path | None = None
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
    and loud beats included and malformed, but only because `verify()` is
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
        # above). verify() refuses the open on any problem, so it is loud.
        problems += context_problems(d.name, doc)

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


ROSTER, ALT_TAGS, IDENTITY_TAILS, PROBLEMS = scan()

DIR_NAMES: list[str] = [d for d, _t in ROSTER]               # alphabetical
ALPHA_DIR_NAMES: list[str] = DIR_NAMES                       # alias, see above
TAGS: list[str] = [t for _d, t in ROSTER]                    # same order
TAG_BY_DIR: dict[str, str] = dict(ROSTER)                    # dir -> Tag
DIR_BY_TAG: dict[str, str] = {t: d for d, t in ROSTER}       # Tag -> dir, current only
DIR_BY_TAG_ALL: dict[str, str] = {**DIR_BY_TAG, **ALT_TAGS}  # + historical


def statement_re(tags):
    """THE transcript statement-line grammar, compiled for a tag set —
    exactly what the writer produces (transcript_store.statement_line):
    "[Tag]: text" or "[Tag] [To: X]: text", one space, [To: ...] the only
    legal second bracket. One builder since 2026-08-19 (review, tier 3
    #35): circle_close.py and circle_audit.py (then nightly.py) each
    hand-rolled their own and the two had drifted — close accepted ANY
    second bracket, the audit accepted arbitrary spacing — so the close's
    who-owes-a-short_term set and the audit's backfill set could disagree
    on the same line, the exact gap both scanners exist to close.
    Measured before converging: across all 47 transcripts on 2026-08-19,
    neither divergence matched a single real line, so the writer's
    grammar is the corpus's whole truth. The TAG SET stays the caller's
    parameter — circle_close walks historical transcripts and passes
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
# roster.py now owns only per-part facts, which is what this comment always
# said the test was.


def verify(base: pathlib.Path | None = None) -> list[str]:
    """Everything scan() refused, plus the checks that need the wider tree.

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
    _roster, _alt, _tails, problems = scan(base)

    # Self is not a part but shares the transcript's `[Tag]:` grammar, so a
    # part tagged with Self's display name would make every statement
    # ambiguous about who spoke. Imported here rather than at module load:
    # identity.py reads .env, and nine modules import this file.
    try:
        import identity as ID
        reserved = {ID.user_name(), ID.DEFAULT_NAME, ID.SELF_ID}
    except Exception:                    # no dotenv, no .env — not this file's
        reserved = {"Self", "self"}
    for d, t in _roster:
        if t in reserved or t.lower() in {r.lower() for r in reserved}:
            problems.append(f"parts/{d}/{MARKER}: tag {t!r} is Self's name — "
                            f"a part cannot share the operator's tag")
    return problems


if __name__ == "__main__":
    probs = verify()
    print(f"  {len(DIR_NAMES)} part(s): {', '.join(DIR_NAMES) or '(none)'}")
    if probs:
        for p in probs:
            print(f"    FAIL  {p}")
        raise SystemExit(1)
    print(f"  PASS — every directory under parts/ has a {MARKER}")
