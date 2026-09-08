#!/usr/bin/env python3
"""
short_term_manager.py — THE ONE READER AND WRITER of a SHORT_TERM. B96 / R434, 2026-09-04.

    import short_term_manager as STM
    p   = STM.short_term_locate(parts_root / part, ot)        # the file, either suffix, or None
    rec = STM.short_term_read(p)                              # ONE dict shape for .toml and legacy .md
    rec = STM.short_term_record_build(part, tag, ot, reply)   # from a /close (or backfill) reply
    STM.short_term_write(path, rec)                           # by the path's own suffix; LF; atomic
    STM.short_term_dreamt_append(path, text)                  # [[dreamt]] to a .toml, ## Dreamt to a .md
    STM.short_term_prose_render(rec)                          # the .md shape, for a prompt or a chunker
    STM.short_term_verify(rel, data, part, ot)                # the well-formed line, both formats

WHAT CHANGED AND WHAT DID NOT. R434 (2026-09-02): `parts/<part>/short_term_<OT>.md` becomes
`short_term_<OT>.toml`, FORWARD-ONLY. Every circle from 2026-09-04 writes the .toml; the 309
files already on disk stay .md, untouched — each is sha256-pinned by its own
`work/logs/close_<OT>.json`, the same grandfather logic the eight CRLF-pinned files of
2026-07-26_1910 already had. So this module reads BOTH and writes whichever suffix the path
carries, and every reader in the tree comes through it: a caller that knows only a part
directory and an open time asks `short_term_locate()` and never spells a suffix.

THE FORMAT. Four named keys, one per section of the /close reply (SHORT_TERM_PROMPT in
circle_close.py), each the lowercase snake_case of its heading:

    part = "<dir>"                    the parts/ directory
    tag = "<Tag>"                     the display tag (roster)
    circle = "2026-09-04_1200"        the OT
    reconstructed = false             R248's mark, as a value rather than a header sentence
    what_i_said = \"\"\"...\"\"\"
    what_i_observed_in_others = \"\"\"...\"\"\"
    shifts_toward_other_parts = \"\"\"...\"\"\"
    current_emotional_state = \"\"\"...\"\"\"
    other = \"\"\"...\"\"\"                 ONLY when the reply carried text outside the four —
                                      a preamble, a heading of the part's own. Never dropped
                                      silently; the .md kept it and so does this.
    [[dreamt]]                        one table per dreaming pass, appended — the `## Dreamt`
    date = "..."                      section's successor. A legacy .md's `## Dreamt` reads as
    text = \"\"\"...\"\"\"                  the same table with an empty date.

PROSE IS STORED VERBATIM, NOT RE-WRAPPED. issues/*.toml hold hard-wrapped prose and unwrap it
on read ("a single newline is soft") — that rule cannot apply here: 73 of the 309 legacy
short_terms carry list lines (`- ` / `1. `), which a soft-newline read would fold into one
paragraph, and nothing may change what a part wrote. REGISTER_CLASS._lit is the literal rule
("NEVER re-wraps and never normalises whitespace"); the `\"\"\"` container is R434's requirement,
the width was never part of it. Lines run to 660 characters in the corpus; they stay so.

WHAT A PART SEES DOES NOT CHANGE. part_dreaming.part_dream() puts the whole short_term into
the dreaming prompt. For a .toml it puts `short_term_prose_render()` there — the same
`# Short-term — Tag — date time` header, the same note line, the same four `## ` headings —
so the record's format is invisible to the model. Putting raw TOML in a prompt would be a
change to what a part sees, which is the operator's call and was not made.

THE ONE WRITER TODAY WRITES NO `## Dreamt`. The `[[dreamt]]` half of this module has readers
(part_mid_term_manager.part_mid_term_dreamt_read, recall_index) and one probe writer
(work/tools/memory_probe.py's fixture). Nothing in the live close appends a dream to a
short_term: DREAMING's output goes to remember.toml (inter_circle.py, remember_dreamt_render)
and the `## Dreamt` sections on disk were written by the RETIRED nightly skill. The appender
exists so the read side is whole and the fixture has one door; wiring it into a live close
would be a new write path, which is not this build's.

BOTH FORMATS, ONE DICT:

    {"format": "toml" | "md", "name": <filename>, "part": ..., "tag": ..., "circle": <OT>,
     "reconstructed": bool, "sections": {heading: body}, "other": str,
     "dreamt": [{"date": str, "text": str}, ...]}

`sections` is keyed by the HEADING (`## What I said`), the one spelling record_model owns, so a
caller that already holds SHORT_TERM_SECTIONS indexes it directly.
"""
from __future__ import annotations

import pathlib
import re

try:
    import tomllib
except ModuleNotFoundError:                                  # pragma: no cover
    import tomli as tomllib                                  # type: ignore

import record_model as M
import REGISTER_CLASS as SS
from atomic_write import record_atomic_write

SECTIONS = M.SHORT_TERM_SECTIONS
FORMAT_NEW = "toml"                     # what a NEW circle writes (R434)
FORMAT_LEGACY = "md"                    # what the 309 pinned files are
SUFFIXES = (".toml", ".md")             # locate order: the live format first
HEAD_PREFIX = "# Short-term"
WRITTEN_NOTE = "*(Written by the local coordinator.)*"
RECONSTRUCTED_NOTE = (f"{M.RECONSTRUCTED_MARK} — not what this part wrote in the "
                      f"moment. The close-write was lost or malformed; this was "
                      f"written again from the transcript.)*")
DREAMT_HEADING = "## Dreamt"
OT_RE = re.compile(r"short_term_(\d{4}-\d{2}-\d{2}_\d{4})")
HEAD_RE = re.compile(r"^# Short-term\s+[—-]+\s+(.+?)\s+[—-]+\s+(\d{4}-\d{2}-\d{2})\s+(\d{4})\s*$")


def short_term_key(heading: str) -> str:
    """`## What I said` -> `what_i_said`: the TOML key of a section heading."""
    return re.sub(r"[^a-z0-9]+", "_", heading.removeprefix("## ").strip().lower()).strip("_")


KEYS = tuple(short_term_key(h) for h in SECTIONS)
HEADING_OF = dict(zip(KEYS, SECTIONS))
# THE RECORD'S KEYS, in file order — docs/BNF.md's <short_term> production, which
# work/tools/bnf_conformance.py reads off this literal. Spelled out rather than
# built from KEYS so the tool can read it; the assertion below is what keeps
# the spelling and record_model's headings from drifting apart.
ORDER = ("part", "tag", "circle", "reconstructed",
         "what_i_said", "what_i_observed_in_others", "shifts_toward_other_parts",
         "current_emotional_state", "other")
assert ORDER[4:-1] == KEYS, f"ORDER's section keys {ORDER[4:-1]} != the headings' {KEYS}"
# A [[dreamt]] table carries `date` and `text` — spelled where it is written
# (short_term_dreamt_append) and read (short_term_dreamt_read); a DREAMT_ORDER
# constant sat here from B96 (776bf20) until 2026-09-04 with no reader
# (audit-register #41).


# ------------------------------------------------------------------ where
def short_term_name(ot: str, fmt: str = FORMAT_NEW) -> str:
    return f"short_term_{ot}.{fmt}"


def short_term_ot_read(path: pathlib.Path | str) -> str:
    """The OT a short_term file is filed under, from its name."""
    m = OT_RE.search(pathlib.Path(path).name)
    return m.group(1) if m else ""


def short_term_locate(part_dir: pathlib.Path, ot: str) -> pathlib.Path | None:
    """This part's record of this circle, whichever suffix it carries — the .toml
    first, then the legacy .md. None when the part has none."""
    for suffix in SUFFIXES:
        p = part_dir / f"short_term_{ot}{suffix}"
        if p.is_file():
            return p
    return None


def short_term_paths_read(part_dir: pathlib.Path) -> list[pathlib.Path]:
    """Every short_term this part has, both suffixes, oldest first — sorted by
    STEM, which for an OT-named file is by circle and for the handful of
    oddly-named 2026-06 files (`_gift`, `_circle-open`, `0900a`) is the same
    name order the old `glob("short_term_*.md")` gave them. Nothing is skipped:
    the legacy corpus is read whole, exactly as before."""
    # The two globs are LITERAL CALL ARGUMENTS, not built from SUFFIXES and not
    # a tuple a loop feeds to glob(): work/graph/coordinator_draw.py reads a
    # module's .toml path sites off the AST and sees a literal only as a `/`
    # operand or a call argument — the tuple form (B96's first spelling) left
    # this module invisible as the record's owner and the full picture refused
    # to draw (2026-09-04).
    out = [p for p in part_dir.glob("short_term_*.toml") if p.is_file()]
    out += [p for p in part_dir.glob("short_term_*.md") if p.is_file()]
    return sorted(out, key=lambda p: (p.stem, p.suffix))


def short_term_glob(parts_root: pathlib.Path, ot: str) -> list[pathlib.Path]:
    """Every part's record of ONE circle, across parts/ — the `*/short_term_<OT>.*`
    glob every resume and interrupted-close check used to spell with `.md`."""
    out = []
    for d in sorted(p for p in parts_root.iterdir() if p.is_dir()) if parts_root.is_dir() else []:
        p = short_term_locate(d, ot)
        if p is not None:
            out.append(p)
    return out


def short_term_format_read(parts_root: pathlib.Path, ot: str) -> str:
    """The format ONE circle's records are in — decided by what already exists for
    that OT across parts/, so a repair matches the circle it lands in. A circle
    with no record yet is a NEW circle: the live format."""
    found = {p.suffix.lstrip(".") for p in short_term_glob(parts_root, ot)}
    if FORMAT_NEW in found:
        return FORMAT_NEW
    if FORMAT_LEGACY in found:
        return FORMAT_LEGACY
    return FORMAT_NEW


def short_term_path_new(parts_root: pathlib.Path, part: str, ot: str) -> pathlib.Path:
    """Where this part's record of this circle IS, or where it goes: the existing
    file if there is one (a repair lands in place, whatever its suffix), else the
    circle's own format, else the live format."""
    existing = short_term_locate(parts_root / part, ot)
    if existing is not None:
        return existing
    return parts_root / part / short_term_name(ot, short_term_format_read(parts_root, ot))


# ------------------------------------------------------------------ parse
def _blocks(text: str) -> tuple[list[str], list[tuple[str, str]]]:
    """(preamble lines, [(heading line, body)]) — a markdown document split on its
    `## ` headings. The body is stripped; the heading keeps its `## `."""
    pre: list[str] = []
    blocks: list[tuple[str, list[str]]] = []
    for ln in text.splitlines():
        if ln.startswith("## "):
            blocks.append((ln.strip(), []))
        elif blocks:
            blocks[-1][1].append(ln)
        else:
            pre.append(ln)
    return pre, [(h, "\n".join(b).strip()) for h, b in blocks]


def _dreamt_md(text: str) -> list[dict]:
    """EVERY `## Dreamt` in a legacy .md — the exact loop part_mid_term_manager ran
    from 2026-08-07 until this module took it, kept verbatim so the bytes it hands
    the derivation (and so the source hash) do not move for any existing part."""
    out = []
    rest = text
    while "\n## Dreamt" in rest:
        body = rest.split("\n## Dreamt", 1)[1]
        nxt = body.find("\n## ")
        out.append({"date": "", "text": (body[:nxt] if nxt >= 0 else body).strip()})
        rest = body[nxt:] if nxt >= 0 else ""
    return out


def _md_parse(text: str) -> dict:
    pre, blocks = _blocks(text)
    head = pre[0].strip() if pre else ""
    m = HEAD_RE.match(head)
    tag = m.group(1).strip() if m else ""
    circle = f"{m.group(2)}_{m.group(3)}" if m else ""
    # A file's first line is its `# Short-term` header; a REPLY has none, and
    # its first line is the part's own text — kept, like everything else the
    # part wrote outside the four sections.
    body_pre = pre[1:] if head.startswith(HEAD_PREFIX) else pre
    other_pre = [ln for ln in body_pre
                 if ln.strip() and ln.strip() != WRITTEN_NOTE
                 and M.RECONSTRUCTED_MARK not in ln]
    sections: dict[str, str] = {}
    other_blocks: list[str] = []
    for h, body in blocks:
        if h in SECTIONS and h not in sections:
            sections[h] = body
        elif h == DREAMT_HEADING or h.startswith(DREAMT_HEADING + " "):
            continue
        else:
            other_blocks.append(f"{h}\n\n{body}" if body else h)
    other = "\n\n".join(["\n".join(other_pre)] * bool(other_pre) + other_blocks).strip()
    return {"format": FORMAT_LEGACY, "tag": tag, "circle": circle,
            "reconstructed": M.record_is_reconstructed(text),
            "sections": sections, "other": other, "dreamt": _dreamt_md(text)}


def _toml_parse(text: str) -> dict:
    doc = tomllib.loads(text)
    sections = {HEADING_OF[k]: str(doc[k]) for k in KEYS if k in doc}
    dreamt = [{"date": str(d.get("date", "")), "text": str(d.get("text", ""))}
              for d in doc.get("dreamt", []) if isinstance(d, dict)]
    return {"format": FORMAT_NEW, "tag": str(doc.get("tag", "")),
            "circle": str(doc.get("circle", "")),
            "reconstructed": bool(doc.get("reconstructed", False)),
            "part": str(doc.get("part", "")),
            "sections": sections, "other": str(doc.get("other", "")), "dreamt": dreamt}


def short_term_parse(name: str, text: str, part: str = "") -> dict:
    """ONE dict for either format, decided by the NAME's suffix (a .toml parses as
    TOML and raises tomllib.TOMLDecodeError if it is not one; anything else is the
    legacy markdown). `part` is the directory the caller knows; a .toml carries its
    own and the two are both kept, the file's winning when it says one."""
    fmt = FORMAT_NEW if str(name).endswith(".toml") else FORMAT_LEGACY
    rec = _toml_parse(text) if fmt == FORMAT_NEW else _md_parse(text)
    rec["name"] = pathlib.Path(name).name
    rec["part"] = rec.get("part") or part
    rec["circle"] = rec.get("circle") or short_term_ot_read(name)
    return rec


def short_term_read(path: pathlib.Path, part: str = "") -> dict:
    """The record on disk, through short_term_parse(). Raises on an unreadable file
    or a .toml that does not parse — a caller that wants a verdict rather than an
    exception asks short_term_verify()."""
    text = path.read_text(encoding="utf-8")
    return short_term_parse(path.name, text, part or path.parent.name)


def short_term_record_build(part: str, tag: str, ot: str, reply: str,
                            reconstructed: bool = False) -> dict:
    """A record from what a part REPLIED — the four sections and whatever else it
    wrote, in the .md shape the prompt asked for. The remember bracket is the
    caller's to take out first (R255); this keeps everything it is given."""
    rec = _md_parse(reply.strip() + "\n")
    rec.update({"format": FORMAT_NEW, "name": short_term_name(ot), "part": part,
                "tag": tag, "circle": ot, "reconstructed": reconstructed})
    rec["dreamt"] = []
    return rec


def short_term_sections_missing(rec: dict) -> list[str]:
    """The canonical headings this record lacks OR has nothing under. The
    close-time format check: a heading with an empty body is the shape B54 exists
    for — present on disk, read downstream as no engagement."""
    secs = rec.get("sections") or {}
    return [h for h in SECTIONS if not (secs.get(h) or "").strip()]


# ------------------------------------------------------------------ render
def short_term_header_render(tag: str, ot: str, reconstructed: bool = False) -> str:
    """The .md header: title line, then the coordinator's note or R248's mark."""
    note = RECONSTRUCTED_NOTE if reconstructed else WRITTEN_NOTE
    return f"{HEAD_PREFIX} — {tag} — {ot[:10]} {ot[11:]}\n\n{note}\n\n"


def short_term_prose_render(rec: dict, dreamt: bool = True) -> str:
    """The record in the .md shape — what a part wrote, under the headings it wrote
    under. What part_dreaming puts in a prompt for a .toml, what recall_index
    chunks, and what short_term_write() writes when the path says .md."""
    out = [short_term_header_render(rec.get("tag", ""), rec.get("circle", ""),
                                    bool(rec.get("reconstructed"))).rstrip("\n")]
    secs = rec.get("sections") or {}
    for h in SECTIONS:
        if h not in secs:
            continue                    # absent stays absent; the verifier says MISSING-SECTION
        body = (secs.get(h) or "").strip()
        out.append(f"{h}\n\n{body}" if body else h)
    if (rec.get("other") or "").strip():
        out.append(rec["other"].strip())
    if dreamt:
        for d in rec.get("dreamt") or []:
            out.append(f"{DREAMT_HEADING}\n\n{(d.get('text') or '').strip()}")
    return "\n\n".join(out) + "\n"


def short_term_toml_render(rec: dict) -> str:
    """The record as TOML: the scalars, the four sections in canonical order, `other`
    only when it carries something, then one [[dreamt]] table per entry. Prose
    verbatim through REGISTER_CLASS._lit — see the module docstring for why it is
    NOT wrapped."""
    secs = rec.get("sections") or {}
    out = [f'part = {SS._lit(str(rec.get("part", "")))}',
           f'tag = {SS._lit(str(rec.get("tag", "")))}',
           f'circle = {SS._lit(str(rec.get("circle", "")))}',
           f'reconstructed = {str(bool(rec.get("reconstructed"))).lower()}']
    for k in KEYS:
        if HEADING_OF[k] not in secs:
            continue                    # absent stays absent; the verifier says MISSING-SECTION
        out.append(f"{k} = {SS._lit((secs.get(HEADING_OF[k]) or '').strip())}")
    if (rec.get("other") or "").strip():
        out.append(f"other = {SS._lit(rec['other'].strip())}")
    for d in rec.get("dreamt") or []:
        out.append(_dreamt_table_render(d))
    return "\n".join(out) + "\n"


def _dreamt_table_render(d: dict) -> str:
    return (f"\n[[dreamt]]\ndate = {SS._lit(str(d.get('date', '')))}\n"
            f"text = {SS._lit((d.get('text') or '').strip())}")


def short_term_render(rec: dict, fmt: str) -> str:
    return short_term_toml_render(rec) if fmt == FORMAT_NEW else short_term_prose_render(rec)


def _same(a: dict, b: dict) -> bool:
    """Round-trip equality on what the record carries — the parts a write must not
    change. `name`/`format` are the path's; `other` and each dreamt text compare
    stripped, since the renderers strip and the parsers strip."""
    strip = lambda s: (s or "").strip()                                    # noqa: E731
    return (a.get("part") == b.get("part") and a.get("tag") == b.get("tag")
            and a.get("circle") == b.get("circle")
            and bool(a.get("reconstructed")) == bool(b.get("reconstructed"))
            and {h: strip(v) for h, v in (a.get("sections") or {}).items() if strip(v)}
            == {h: strip(v) for h, v in (b.get("sections") or {}).items() if strip(v)}
            and strip(a.get("other")) == strip(b.get("other"))
            and [strip(d.get("text")) for d in a.get("dreamt") or []]
            == [strip(d.get("text")) for d in b.get("dreamt") or []])


# ------------------------------------------------------------------ write
def short_term_write(path: pathlib.Path, rec: dict) -> None:
    """Write the record in the format the PATH names. Validate, THEN commit
    atomically (REGISTER_CLASS.register_write's own order): the text is parsed back
    through short_term_parse() and refused if it does not carry what it was
    given, so a record that cannot be read never reaches disk. LF, always."""
    fmt = FORMAT_NEW if path.suffix == ".toml" else FORMAT_LEGACY
    text = short_term_render(rec, fmt)
    back = short_term_parse(path.name, text, str(rec.get("part", "")))
    if not _same(rec, back):
        raise ValueError(f"{path.name}: does not round-trip — refusing to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    record_atomic_write(path, text)


def short_term_dreamt_append(path: pathlib.Path, text: str, date: str = "") -> None:
    """Append ONE dreaming pass to an existing record: a `[[dreamt]]` table to a
    .toml, a `## Dreamt` section to a .md. Append-only in both — the four sections'
    bytes are never rewritten. The result is parsed before it lands."""
    current = path.read_text(encoding="utf-8")
    if path.suffix == ".toml":
        new = current.rstrip("\n") + "\n" + _dreamt_table_render(
            {"date": date, "text": text}) + "\n"
    else:
        new = current.rstrip("\n") + f"\n\n{DREAMT_HEADING}\n\n{text.strip()}\n"
    back = short_term_parse(path.name, new)
    if not back["dreamt"] or back["dreamt"][-1]["text"] != text.strip():
        raise ValueError(f"{path.name}: the appended dream does not read back")
    record_atomic_write(path, new)


# ------------------------------------------------------------------ verify
# MOVED FROM backfill.py, 2026-09-04 (B96) — and from record_model.py before that
# (2026-09-03, cohesion re-homing stage 4). The rule is unchanged: readable, four
# sections in order, each with something under it, headed for the right part and
# circle. What is new is the .toml branch, which reads the same line through the
# same parser the close writes with.
def short_term_verify(path: str, data: bytes | None, part: str,
                      open_time: str) -> list[M.Finding]:
    """A short_term is well-formed: readable, four sections in order, each with
    something under it, and headed for the right part and circle.

    Empty sections matter. A backfill that emits the headings and nothing beneath
    them passes a naive 'are the sections present' test and tells the nightly
    nothing — which is indistinguishable, downstream, from the loss it was meant
    to repair."""
    text, out = M.record_file_verify(path, data)
    if text is None:
        return out
    if str(path).endswith(".toml"):
        return out + _verify_toml(path, text, part, open_time)
    return out + _verify_md(path, text, part, open_time)


def _verify_sections(path: str, secs: dict[str, str]) -> list[M.Finding]:
    out: list[M.Finding] = []
    for h in SECTIONS:
        if h not in secs:
            out.append(M._f("FAIL", "MISSING-SECTION", path, f"no '{h}'"))
    if out:
        return out
    for h in SECTIONS:
        n = len((secs.get(h) or "").split())
        if n < 8:
            out.append(M._f("FAIL", "EMPTY-SECTION", path, f"'{h}' has {n} word(s) under it"))
    return out


def _verify_toml(path: str, text: str, part: str, open_time: str) -> list[M.Finding]:
    try:
        rec = _toml_parse(text)
    except (tomllib.TOMLDecodeError, ValueError) as e:
        return [M._f("FAIL", "PARSE", path, f"not a TOML short_term: {e}")]
    out = _verify_sections(path, rec["sections"])
    if part and rec["part"] and rec["part"] != part:
        out.append(M._f("WARN", "HEADER-PART", path,
                        f"record says part {rec['part']!r}, filed under {part!r}"))
    if open_time and rec["circle"] and rec["circle"] != open_time:
        out.append(M._f("WARN", "HEADER-DATE", path,
                        f"record says circle {rec['circle']!r}, filed under {open_time!r}"))
    return out


def _verify_md(path: str, text: str, part: str, open_time: str) -> list[M.Finding]:
    # VERBATIM from backfill.short_term_verify (2026-09-03) — substring order and
    # all, so a legacy file's verdict is the one it always had.
    out: list[M.Finding] = []
    idx = []
    for h in SECTIONS:
        i = text.find(h)
        if i < 0:
            out.append(M._f("FAIL", "MISSING-SECTION", path, f"no '{h}'"))
        idx.append(i)
    if any(i < 0 for i in idx):
        return out
    if idx != sorted(idx):
        out.append(M._f("FAIL", "SECTION-ORDER", path,
                        "the four sections are not in the canonical order"))
    bounds = sorted(idx) + [len(text)]
    for h, a, b in zip(SECTIONS, bounds, bounds[1:]):
        body = text[a + len(h):b].strip()
        if len(body.split()) < 8:
            out.append(M._f("FAIL", "EMPTY-SECTION", path,
                            f"'{h}' has {len(body.split())} word(s) under it"))
    head = text.splitlines()[0] if text.splitlines() else ""
    if not head.startswith(HEAD_PREFIX):
        out.append(M._f("FAIL", "BAD-HEADER", path, f"first line is {head[:50]!r}"))
    elif M.PARTS and part in M.PARTS:
        tag = part.replace("_", " ").title()
        if tag.lower() not in head.lower():
            out.append(M._f("WARN", "HEADER-PART", path,
                            f"header names neither {part} nor {tag}: {head[:60]!r}"))
    if open_time and open_time[:10] not in text[:200]:
        out.append(M._f("WARN", "HEADER-DATE", path,
                        f"header does not carry the circle date {open_time[:10]}"))
    return out
