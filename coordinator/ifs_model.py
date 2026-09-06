#!/usr/bin/env python3
"""
ifs_model.py — structural model of the IFS memory files (the invariant gate that
judges with it is register_gate.py's, since 2026-09-03).

WHAT THIS IS
    Phase 6 of NIGHTLY_DESIGN.md, built first and on purpose. It parses
    long_term.md / the self/ files (and relationships.md, until R185's 2026-08-15
    TOML conversion; the register itself retired 2026-08-22) into a structured model and
    supplies the per-file comparisons register_gate.record_tree_compare() runs over
    a CANDIDATE tree against a BASELINE tree, reporting every structural change
    and failing on the ones that are not allowed.

    It writes nothing, anywhere, ever. Read-only by construction.

WHY THIS FIRST
    A transaction guarantees a CONSISTENT set of files, not a CORRECT one. A
    nightly run that drops three sections from long_term.md and commits cleanly
    passes every atomicity check ever written. These invariants are the part that
    notices.

    Invariants are derived from the baseline rather than hardcoded. The files are
    not uniform — one part's file can carry sections another part's doesn't
    (relationships.md, retired 2026-08-22, was the original example here),
    self.md accumulates one "## Dream synthesis <date>" heading
    per SYNTHESIS run, settled headers come in two shapes ("was review 15", "was
    review") — so any hardcoded schema would be wrong on contact. Comparing
    against what is actually there is both stricter and more honest.

USE
    import ifs_model as M
    text, findings = M.check_file(rel, data)

THE GATE MOVED OUT, 2026-09-03 (cohesion re-homing stage 9): record_tree_compare,
record_tree_verify, REGISTERS and the register checks are register_gate.py's, and
read this module as M. What stays here is the model — Finding, the primitives,
the entries, and the three comparisons the gate composes.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import roster as R                                            # noqa: E402

PARTS = R.ALPHA_DIR_NAMES   # B29: was a hand-typed alphabetical copy

# self/ files SYNTHESIS writes. append_only ones must keep the prior content as
# a byte PREFIX -- the single cheapest guard against a rewrite-instead-of-append.
#
# "circle_briefing.md": "rewritten" REMOVED 2026-08-11: the file itself is
# retired. group_attention.py's circle_briefing_build() constructs circle_objectives directly
# from issue_model.md and the live issues/*.toml graph (and, until B46
# 2026-08-17, issues_narrative.md)
# at prompt-assembly time -- there is no self/ file left for the nightly to
# rewrite, and check_briefing() (which asserted this file's `## Issues`
# section existed) went with it.
# "self_observation_log.md": "append_only" REMOVED 2026-08-19
# (R256, B14's DESIGNED half): the file is
# self/self_observation_log.toml now and is judged by the REGISTERS arm
# below, not by the byte-prefix rule. self.md stays here — SYNTHESIS reads
# it back and replaces it whole, which is what "structured" is for.
#
# "narrative_arc.md": "append_only" REMOVED 2026-08-24. A PHANTOM
# DEPENDENCY, and it had been one for nine days: R165 (2026-08-15) moved
# its one job — the cross-circle phase bullet — into
# self/circle_history.toml, and R256 (2026-08-19) recorded the
# consequence outright, *"no writer since R165 ... absent from both
# packaging/scaffold/ and additions.toml — it does not ship at all"*.
# Nothing writes it, nothing reads it, and it reaches no prompt block
# (docs/INTER_CIRCLE_DESIGN.md §1202 says so; prompt_build.py never opens
# it). This entry was the only thing left asserting it must exist — so
# record_tree_verify() FAILED "MISSING" on every fresh install, for a file
# the project had already ruled it does not ship. A gate outliving its
# subject reports a defect that is its own.
#
# The operator's own self/narrative_arc.md is untouched and stays where it
# is: it is real history, frozen 2026-07-27. Dropping the entry drops a
# byte-prefix check that nothing could ever violate, because nothing
# writes the file.
SELF_FILES = {
    "self.md": "structured",
}

SHRINK_TOLERANCE = 0.02          # 2%, per NIGHTLY_DESIGN §4.1

# The four sections every short_term must carry, in this order. Previously these
# lived inline in nightly.py's phase 2 behind a hasattr() fallback — which is what
# a constant looks like just before it becomes two constants that disagree.
SHORT_TERM_SECTIONS = ("## What I said", "## What I observed in others",
                       "## Shifts toward other parts", "## Current emotional state")

# THE RECONSTRUCTION MARK — R248, 2026-08-19: "Do mark reconstructions."
#
# A part that spoke but lost its short_term has it written again afterwards,
# from the transcript (circle_audit.py phase 3, and now the live close guard
# too). That is a DIFFERENT ACT from writing one in the moment, and the reader
# that most needs to know is dreaming, which would otherwise take the
# reconstruction for the part's own contemporaneous record.
#
# A CONTRACT, NOT A DECORATION. The header already carried an italic sentence
# saying so before the ruling; what it did not have was anything that PARSES
# it, so every downstream reader was blind to the distinction the sentence
# described. The literal lives here, in the module that owns a short_term's
# shape, so the writer and the reader cannot drift apart.
#
# PROSE, NOT METADATA, and now RULED so rather than merely deferred. This
# said "whether that becomes TOML is B15, unruled — inventing frontmatter for
# one bit of provenance would decide that question by accident". Self closed
# B15 on 2026-08-19 (R252): a short_term stays a prose
# .md. So the mark stays prose because that is the format, not because the
# format is undecided. There is no frontmatter for it to become.
RECONSTRUCTED_MARK = "*(RECONSTRUCTED from the transcript after the fact"


def record_is_reconstructed(text: str | None) -> bool:
    """Was this short_term written again afterwards, rather than at close?

    Substring, not a line match: the mark opens a header line that also names
    the tool and the reason, and those may be reworded without this changing
    its answer."""
    return bool(text) and RECONSTRUCTED_MARK in text

# Fields SYNTHESIS's deterministic bookkeeping is ALLOWED to change on an
# existing dream entry. Anything else changing is a model having edited history.
MUTABLE_FIELDS = {"last mentioned", "review flagged", "settled"}

# THE IDENTITY/HISTORY BOUNDARY IN long_term.md. Everything ABOVE it is the
# part's identity -- editable, and the only part of the file a prompt ever sees
# (prompt_build.part_identity_strip cuts here). Everything BELOW is append-only
# history, which record_long_term_compare() verifies was not rewritten.
#
# IT USED TO BE `## Dream entries`, and Self ruled that out 2026-08-22:
# *"do not restore the obsolete ## Dream entries heading as a delimiter; add a
# valid delim like '## required end' and change to code accordingly."* The
# heading had stopped describing what follows it -- the dream corpus moved to
# parts/<p>/dreams.toml on 2026-08-12, leaving all seven files with a heading
# over a one-line tombstone and ZERO entries beneath it. A delimiter whose name
# is a lie is one a writer deletes in good faith, which is exactly what happened
# when the Soul's long_term.md was rewritten: the heading went, and with it the
# boundary record_long_term_compare() needs, which then failed closed.
IDENTITY_END = "## required end"

# CONTENT, NOT BOUNDARY, since the rename above. Parsed if present so a legacy
# file still yields its entries; no part has any today. Also the ONE HOME for
# these two heading strings — record_long_term_compare()'s own FAIL/OK/WARN messages
# below quote them by reference, not as separately hand-typed literals
# (audit-register.md #30 found four that had drifted into duplicates).
DREAM_SECTION = "## Dream entries"
SETTLED_SECTION = "## Settled"

# "### Dream 2026-07-11 — title"
# "### [review] Dream 2026-07-04 — title"
# "### [50] Dream 2026-06-18 — title"
# "### [settled 2026-07-05, was review 15] Dream 2026-06-24 — title"
# Markers are a SEQUENCE, not one field. An entry can be flagged for review while
# still carrying its frozen historic weight:
#     ### [review] [15] Dream 2026-06-24 — The hollow that holds
# An earlier version of this regex allowed only one bracket group, so entries like
# that parsed as nothing at all and vanished from every count in silence. Found
# 2026-07-26 by the UNPARSED-ENTRY check, which exists precisely because a
# parser's blind spot is invisible until something forces it to account for every
# line it skipped.
_ENTRY_RE = re.compile(
    r"^###\s+(?P<markers>(?:\[[^\]]*\]\s+)*)Dream\s+(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"[—–-]\s+(?P<title>.+?)\s*$"
)
_MARKER_RE = re.compile(r"\[([^\]]*)\]")
# The files use TWO field spellings, both canonical, and a parser that accepts only
# one silently reports the other as a missing field:
#     *Last mentioned: circle_2026-07-11_1644*     value inside the emphasis
#     *Review flagged:* 2026-07-12_0112            label emphasised, value outside
# The second is the form the dreaming SKILL specifies verbatim ("add
# `*Review flagged:* OPEN_TIME` as the second field line"), so it is not a typo to
# be normalised away. Accept either; the trailing/leading `*` is optional on both
# sides and at least one of them is always present.
_FIELD_RE = re.compile(
    r"^\*(?P<name>[^:*]+):(?P<lead>\*?)\s*(?P<value>.*?)\s*(?P<trail>\*?)\s*$")
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.+?)\s*$")
# _SYNTH_RE (a generic, date-wildcard variant of this pattern) DELETED
# 2026-09-01 -- audit-register.md #30 found it a zero-reference symbol; the
# one call site (below) builds its own date-pinned pattern inline instead.


# ---------------------------------------------------------------- findings
class Finding:
    __slots__ = ("level", "code", "path", "message")

    def __init__(self, level: str, code: str, path: str, message: str):
        self.level, self.code, self.path, self.message = level, code, path, message

    def __str__(self) -> str:
        return f"  {self.level:<4} {self.path:<44} {self.code}: {self.message}"


def _f(level, code, path, message):
    return Finding(level, code, str(path), message)


# ---------------------------------------------------------------- primitives
def record_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def record_bytes_read(p: pathlib.Path) -> bytes | None:
    try:
        return p.read_bytes()
    except OSError:
        return None


def record_decode(data: bytes) -> tuple[str | None, str | None]:
    """(text, error). Deliberately strict -- errors='replace' is how corruption
    becomes invisible."""
    nul = data.find(b"\x00")
    if nul >= 0:
        return None, f"NUL byte at offset {nul}"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as e:
        return None, f"not valid UTF-8 ({e})"


def record_line_endings_read(data: bytes) -> str:
    """'lf' | 'crlf' | 'mixed' | 'none'. Line endings are load-bearing here: the
    close-report sha256s, the byte-identical checks below, and git-as-rollback all
    assume the bytes of an untouched file do not move. A file that changes ending
    style has been rewritten by something, and that is worth knowing even when the
    visible text is unchanged."""
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    if crlf and lf:
        return "mixed"
    if crlf:
        return "crlf"
    return "lf" if lf else "none"


def record_suspicious_chars_read(text: str) -> list[str]:
    """Stray characters from a model's output that are valid UTF-8 and therefore
    invisible to every encoding check. Real example, this session: a Chinese
    character mid-sentence in an English short_term ('felt like<CJK>ly seeing
    her'). record_verify.py would have passed it."""
    bad = []
    for ch in set(text):
        if ord(ch) < 0x80 or ch in "—–‘’“”… ":
            continue
        name = unicodedata.name(ch, "")
        if name.startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "ARABIC",
                            "HEBREW", "CYRILLIC", "DEVANAGARI", "THAI")):
            bad.append(f"U+{ord(ch):04X} {name}")
    return sorted(bad)


def record_headings_read(text: str, level: int = 2) -> list[str]:
    out = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m and len(m.group("hashes")) == level:
            out.append(m.group("text"))
    return out


def record_sections_split(text: str, level: int = 2) -> dict[str, str]:
    """heading text -> section body (heading line excluded). Later duplicates
    win; duplicates are themselves reported separately."""
    lines = text.splitlines(keepends=True)
    idx = [i for i, l in enumerate(lines)
           if (m := _HEADING_RE.match(l)) and len(m.group("hashes")) == level]
    out: dict[str, str] = {}
    for a, b in zip(idx, idx[1:] + [len(lines)]):
        out[_HEADING_RE.match(lines[a]).group("text")] = "".join(lines[a + 1:b])
    return out


def record_preamble_read(text: str, marker: str) -> str | None:
    """Everything above `marker`. None if the marker is absent."""
    i = text.find(marker)
    return None if i < 0 else text[:i]


# ---------------------------------------------------------------- entries
class Entry:
    __slots__ = ("marker", "date", "title", "fields", "body", "raw", "section")

    def __init__(self, marker, date, title, fields, body, raw, section):
        # the raw bracket run, e.g. "[review] [15] " or "" — parsed by .markers
        self.marker = marker
        self.date = date
        self.title = title
        self.fields = fields          # lowercased name -> value
        self.body = body              # everything after the field block
        self.raw = raw
        self.section = section        # "dream" | "settled"

    @property
    def id(self) -> str:
        return f"{self.date}|{self.title}"

    @property
    def markers(self) -> list[str]:
        return [m.strip() for m in _MARKER_RE.findall(self.marker or "")]

    @property
    def is_review(self) -> bool:
        return any(m.lower() == "review" for m in self.markers)

    @property
    def is_tombstone(self) -> bool:
        """A header with no body: an entry that was lost, leaving only its marker.
        parts/<part> '### [8] Dream 2026-06-18 — [entry incomplete — body not
        recovered]' is the known instance."""
        return not self.body.strip()

    @property
    def recency(self) -> tuple[str, str]:
        """(YYYY-MM-DD, source) for the recency clock.

        RULE (NIGHTLY_DESIGN §10, settled 2026-07-26): an entry with no
        *Last mentioned:* field anchors to ITS OWN dream date. Self-report entries
        written outside any circle carry no circle reference -- reasonably, since
        no circle occurred -- and without a rule they sit outside the recency model
        forever: circles-since is uncomputable, so they can never be flagged
        [review] and never settle. Anchoring to the entry date brings them in on
        the same footing as everything else. Derived at read time; phase 4
        materialises the field the first time it touches the entry."""
        raw = self.fields.get("last mentioned", "")
        m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
        if m:
            return m.group(1), "field"
        return self.date, "entry-date"

    @property
    def weight(self) -> str | None:
        """The frozen historic weight, if this entry carries one. CLAUDE.md:
        'historic weight numbers frozen'."""
        return next((m for m in self.markers if m.isdigit()), None)


def record_entries_parse(section_body: str, section: str) -> list[Entry]:
    lines = section_body.splitlines(keepends=True)
    starts = [i for i, l in enumerate(lines) if _ENTRY_RE.match(l)]
    out = []
    for a, b in zip(starts, starts[1:] + [len(lines)]):
        m = _ENTRY_RE.match(lines[a])
        fields, j = {}, a + 1
        while j < b:
            s = lines[j].strip()
            if not s:
                j += 1
                continue
            fm = _FIELD_RE.match(s)
            if not fm:
                break
            fields[fm.group("name").strip().lower()] = fm.group("value").strip()
            j += 1
        out.append(Entry(
            marker=m.group("markers"), date=m.group("date"), title=m.group("title"),
            fields=fields, body="".join(lines[j:b]).strip(),
            raw="".join(lines[a:b]), section=section,
        ))
    return out


class LongTerm:
    def __init__(self, text: str):
        self.text = text
        self.headings = record_headings_read(text, 2)
        secs = record_sections_split(text, 2)
        self.preamble = record_preamble_read(text, IDENTITY_END)
        self.dreams = record_entries_parse(secs.get("Dream entries", ""), "dream")
        self.settled = record_entries_parse(secs.get("Settled", ""), "settled")
        # Every '### ' line in these two sections MUST parse as an entry. If one
        # does not, it has been silently dropped from every count, every
        # comparison and every recency decision -- the entry is still visible to a
        # human reading the file and invisible to the machinery. That is the worst
        # possible failure mode, so it is a hard error.
        #
        # Real instance, 2026-07-26: a markdown editor auto-escaped
        # '### [review] Dream ...' to '### \[review] Dream ...' across
        # parts/<part>/long_term.md. 14 of 22 entries stopped parsing and the
        # self-check still reported 0 FAIL, because it only ever looked at what it
        # had successfully parsed.
        self.unparsed: list[str] = []
        for name in ("Dream entries", "Settled"):
            for line in secs.get(name, "").splitlines():
                if line.startswith("### ") and not _ENTRY_RE.match(line):
                    self.unparsed.append(line.strip())

    @property
    def by_id(self) -> dict[str, Entry]:
        return {e.id: e for e in self.dreams + self.settled}

    @property
    def total(self) -> int:
        return len(self.dreams) + len(self.settled)


# ---------------------------------------------------------------- file checks
def record_file_verify(path: str, data: bytes | None) -> tuple[str | None, list[Finding]]:
    """§4.1 -- every file. Returns (text_or_None, findings)."""
    out: list[Finding] = []
    if data is None:
        return None, [_f("FAIL", "MISSING", path, "file absent or unreadable")]
    if not data.strip():
        return None, [_f("FAIL", "EMPTY", path, "file is empty")]
    text, err = record_decode(data)
    if text is None:
        return None, [_f("FAIL", "ENCODING", path, err)]
    if not text.endswith("\n"):
        out.append(_f("FAIL", "NO-EOL", path, "does not end with a newline"))
    elif text.endswith("\n\n"):
        out.append(_f("WARN", "TRAILING-BLANK", path, "ends with blank line(s)"))
    for c in record_suspicious_chars_read(text):
        out.append(_f("FAIL", "STRAY-CHAR", path,
                      f"unexpected script character {c} in English prose"))
    return text, out


def record_size_verify(path, base: bytes, cand: bytes, allow_shrink: bool) -> list[Finding]:
    if len(base) == 0:
        return []
    delta = (len(cand) - len(base)) / len(base)
    if delta < -SHRINK_TOLERANCE and not allow_shrink:
        return [_f("FAIL", "SHRANK", path,
                   f"{len(base):,} -> {len(cand):,} bytes ({delta:+.1%}); "
                   f"tolerance is -{SHRINK_TOLERANCE:.0%}")]
    if abs(delta) > 0.0001:
        return [_f("OK", "SIZE", path, f"{len(base):,} -> {len(cand):,} ({delta:+.1%})")]
    return []


# ---------------------------------------------------------------- long_term
def record_long_term_compare(path: str, base_text: str, cand_text: str) -> list[Finding]:
    """§4.2. The strict one: history is append-only and immutable except in the
    named fields."""
    out: list[Finding] = []
    b, c = LongTerm(base_text), LongTerm(cand_text)

    if b.preamble is None:
        return [_f("FAIL", "NO-DREAM-SECTION", path,
                   f"baseline has no '{IDENTITY_END}' delimiter -- cannot verify")]
    if c.preamble is None:
        return [_f("FAIL", "NO-DREAM-SECTION", path,
                   f"'{IDENTITY_END}' delimiter is gone")]
    for line in c.unparsed:
        out.append(_f("FAIL", "UNPARSED-ENTRY", path,
                      f"'### ' line no longer matches the entry template: "
                      f"{line[:90]!r}"))

    # -- heading set: nothing may vanish; only '## Settled' may appear
    lost = [h for h in b.headings if h not in c.headings]
    gained = [h for h in c.headings if h not in b.headings]
    if lost:
        out.append(_f("FAIL", "SECTION-LOST", path,
                      f"identity section(s) removed: {', '.join(lost)}"))
    for g in gained:
        lvl = "OK" if g == "Settled" else "FAIL"
        out.append(_f(lvl, "SECTION-ADDED", path, f"new '## {g}' section"))

    # -- everything above DREAM_SECTION is frozen
    if b.preamble != c.preamble:
        out.append(_f("FAIL", "PREAMBLE-CHANGED", path,
                      f"content above {DREAM_SECTION!r} was modified; the "
                      "foundational identity sections are not SYNTHESIS's to touch"))

    # -- append-only
    if c.total < b.total:
        out.append(_f("FAIL", "ENTRIES-LOST", path,
                      f"{b.total} entries -> {c.total}; dream history is append-only"))

    bi, ci = b.by_id, c.by_id
    for eid, be in bi.items():
        ce = ci.get(eid)
        if ce is None:
            out.append(_f("FAIL", "ENTRY-VANISHED", path,
                          f"entry '{eid}' is present in the baseline and gone now"))
            continue
        if be.body != ce.body:
            out.append(_f("FAIL", "ENTRY-BODY-EDITED", path,
                          f"body of '{eid}' changed; existing dream bodies are "
                          f"immutable ({len(be.body)} -> {len(ce.body)} chars)"))
        if be.weight and ce.weight != be.weight:
            out.append(_f("FAIL", "WEIGHT-CHANGED", path,
                          f"'{eid}' historic weight {be.weight} -> {ce.weight}; "
                          f"historic weights are frozen"))
        for name in set(be.fields) | set(ce.fields):
            bv, cv = be.fields.get(name), ce.fields.get(name)
            if bv == cv:
                continue
            lvl = "OK" if name in MUTABLE_FIELDS else "FAIL"
            out.append(_f(lvl, "FIELD-CHANGED", path,
                          f"'{eid}' *{name}*: {bv!r} -> {cv!r}"))
        if be.section != ce.section:
            if (be.section, ce.section) == ("dream", "settled"):
                out.append(_f("OK", "SETTLED", path, f"'{eid}' moved to {SETTLED_SECTION}"))
            else:
                out.append(_f("FAIL", "UNSETTLED", path,
                              f"'{eid}' moved {be.section} -> {ce.section}"))
        if be.is_review and not ce.is_review and ce.section == "dream":
            has_ev = ce.fields.get("last mentioned") != be.fields.get("last mentioned")
            out.append(_f("OK" if has_ev else "FAIL", "REVIEW-CLEARED", path,
                          f"'{eid}' [review] cleared"
                          + ("" if has_ev else " without updating *Last mentioned*"
                             " -- a flag may only clear on engagement or by settling")))

    # -- new entries must match the template
    for eid, ce in ci.items():
        if eid in bi:
            continue
        out.append(_f("OK", "ENTRY-NEW", path, f"new entry '{eid}'"))
        if ce.section != "dream":
            out.append(_f("FAIL", "NEW-IN-SETTLED", path,
                          f"new entry '{eid}' was written straight into {SETTLED_SECTION}"))
        if ce.weight:
            out.append(_f("FAIL", "NEW-HAS-WEIGHT", path,
                          f"new entry '{eid}' carries weight [{ce.weight}]; "
                          f"new entries do not carry weight numbers"))
        if "last mentioned" not in ce.fields:
            out.append(_f("FAIL", "NEW-NO-FIELD", path,
                          f"new entry '{eid}' has no *Last mentioned:* field"))
        wc = len(ce.body.split())
        if not 60 <= wc <= 320:
            out.append(_f("WARN", "NEW-LENGTH", path,
                          f"new entry '{eid}' body is {wc} words (template says 100-200)"))
    if c.dreams and ci and (nid := next((e.id for e in c.dreams if e.id not in bi), None)):
        if c.dreams[0].id != nid:
            out.append(_f("WARN", "NEW-NOT-FIRST", path,
                          f"new entry '{nid}' is not at the top of {DREAM_SECTION}"))
    return out


# ---------------------------------------------------------------- others
def record_headed_compare(path: str, base_text: str, cand_text: str,
                   allow_new: re.Pattern | None = None) -> list[Finding]:
    """self.md (and relationships.md until its 2026-08-15 TOML conversion):
    the '## ' heading set is the contract, and unchanged sections must be
    byte-identical."""
    out: list[Finding] = []
    bh, ch = record_headings_read(base_text), record_headings_read(cand_text)
    for h in bh:
        if h not in ch:
            out.append(_f("FAIL", "SECTION-LOST", path, f"section '## {h}' removed"))
    for h in ch:
        if h in bh:
            continue
        ok = allow_new and allow_new.match(f"## {h}")
        out.append(_f("OK" if ok else "FAIL", "SECTION-ADDED", path,
                      f"new section '## {h}'"))
    bs, cs = record_sections_split(base_text), record_sections_split(cand_text)
    for h in bh:
        if h in cs and bs[h] != cs[h]:
            out.append(_f("OK", "SECTION-REWRITTEN", path,
                          f"'## {h}' rewritten ({len(bs[h])} -> {len(cs[h])} chars)"))
    return out


def record_append_only_compare(path: str, base_text: str, cand_text: str) -> list[Finding]:
    """§4.4. The prior content must be a byte prefix of the new content."""
    if cand_text.startswith(base_text):
        added = len(cand_text) - len(base_text)
        return [_f("OK", "APPENDED", path, f"+{added:,} chars appended")] if added else []
    n = 0
    for n, (x, y) in enumerate(zip(base_text, cand_text)):
        if x != y:
            break
    return [_f("FAIL", "NOT-APPEND-ONLY", path,
               f"prior content is not a prefix of the new file; they diverge at "
               f"char {n:,} of {len(base_text):,} -- this file is append-only")]


# ---------------------------------------------------------------- the gate
# record_tree_compare / record_tree_verify / _tree_files, REGISTERS with its cap readers,
# register_verify / register_compare and summarise MOVED to register_gate.py,
# 2026-09-03 (cohesion re-homing stage 9). This file is the model they judge with.
