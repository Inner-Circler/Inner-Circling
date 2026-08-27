#!/usr/bin/env python3
"""
ifs_model.py — structural model of the IFS memory files, and the invariant gate.

WHAT THIS IS
    Phase 6 of NIGHTLY_DESIGN.md, built first and on purpose. It parses
    long_term.md / relationships.md / the self/ files into a structured model and
    compares a CANDIDATE tree against a BASELINE tree, reporting every structural
    change and failing on the ones that are not allowed.

    It writes nothing, anywhere, ever. Read-only by construction.

WHY THIS FIRST
    A transaction guarantees a CONSISTENT set of files, not a CORRECT one. A
    nightly run that drops three sections from long_term.md and commits cleanly
    passes every atomicity check ever written. These invariants are the part that
    notices.

    Invariants are derived from the baseline rather than hardcoded. The files are
    not uniform — a part's relationships.md can carry sections another part's
    doesn't, self.md accumulates one "## Dream synthesis <date>" heading
    per night, settled headers come in two shapes ("was review 15", "was
    review") — so any hardcoded schema would be wrong on contact. Comparing
    against what is actually there is both stricter and more honest.

USE
    from ifs_model import compare_trees
    findings = compare_trees(baseline_dir, candidate_dir)
"""

from __future__ import annotations

import datetime
import hashlib
import pathlib
import re
import sys
import unicodedata

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import roster as R                                            # noqa: E402
import proposals as PR                                        # noqa: E402
import check_best_practices as BPX                            # noqa: E402

PARTS = R.ALPHA_DIR_NAMES   # B29: was a hand-typed alphabetical copy

# self/ files the nightly writes. append_only ones must keep the prior content as
# a byte PREFIX -- the single cheapest guard against a rewrite-instead-of-append.
#
# "circle_briefing.md": "rewritten" REMOVED 2026-08-11: the file itself is
# retired. circle.py's build_briefing() constructs circle_objectives directly
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
# selfcheck_tree() FAILED "MISSING" on every fresh install, for a file
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


def is_reconstructed(text: str | None) -> bool:
    """Was this short_term written again afterwards, rather than at close?

    Substring, not a line match: the mark opens a header line that also names
    the tool and the reason, and those may be reworded without this changing
    its answer."""
    return bool(text) and RECONSTRUCTED_MARK in text

# Fields the nightly's deterministic bookkeeping is ALLOWED to change on an
# existing dream entry. Anything else changing is a model having edited history.
MUTABLE_FIELDS = {"last mentioned", "review flagged", "settled"}

# THE IDENTITY/HISTORY BOUNDARY IN long_term.md. Everything ABOVE it is the
# part's identity -- editable, and the only part of the file a prompt ever sees
# (prompt_build.strip_to_identity cuts here). Everything BELOW is append-only
# history, which compare_long_term() verifies was not rewritten.
#
# IT USED TO BE `## Dream entries`, and Self ruled that out 2026-08-22:
# *"do not restore the obsolete ## Dream entries heading as a delimiter; add a
# valid delim like '## required end' and change to code accordingly."* The
# heading had stopped describing what follows it -- the dream corpus moved to
# parts/<p>/dreams.toml on 2026-08-12, leaving all seven files with a heading
# over a one-line tombstone and ZERO entries beneath it. A delimiter whose name
# is a lie is one a writer deletes in good faith, which is exactly what happened
# when the Soul's long_term.md was rewritten: the heading went, and with it the
# boundary compare_long_term() needs, which then failed closed.
IDENTITY_END = "## required end"

# CONTENT, NOT BOUNDARY, since the rename above. Parsed if present so a legacy
# file still yields its entries; no part has any today.
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
_SYNTH_RE = re.compile(r"^## Dream synthesis (\d{4}-\d{2}-\d{2})\s*$")


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
def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_bytes(p: pathlib.Path) -> bytes | None:
    try:
        return p.read_bytes()
    except OSError:
        return None


def decode(data: bytes) -> tuple[str | None, str | None]:
    """(text, error). Deliberately strict -- errors='replace' is how corruption
    becomes invisible."""
    nul = data.find(b"\x00")
    if nul >= 0:
        return None, f"NUL byte at offset {nul}"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as e:
        return None, f"not valid UTF-8 ({e})"


def line_endings(data: bytes) -> str:
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


def suspicious_chars(text: str) -> list[str]:
    """Stray characters from a model's output that are valid UTF-8 and therefore
    invisible to every encoding check. Real example, this session: a Chinese
    character mid-sentence in an English short_term ('felt like<CJK>ly seeing
    her'). check_integrity.py would have passed it."""
    bad = []
    for ch in set(text):
        if ord(ch) < 0x80 or ch in "—–‘’“”… ":
            continue
        name = unicodedata.name(ch, "")
        if name.startswith(("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "ARABIC",
                            "HEBREW", "CYRILLIC", "DEVANAGARI", "THAI")):
            bad.append(f"U+{ord(ch):04X} {name}")
    return sorted(bad)


def headings(text: str, level: int = 2) -> list[str]:
    out = []
    for line in text.splitlines():
        m = _HEADING_RE.match(line)
        if m and len(m.group("hashes")) == level:
            out.append(m.group("text"))
    return out


def split_sections(text: str, level: int = 2) -> dict[str, str]:
    """heading text -> section body (heading line excluded). Later duplicates
    win; duplicates are themselves reported separately."""
    lines = text.splitlines(keepends=True)
    idx = [i for i, l in enumerate(lines)
           if (m := _HEADING_RE.match(l)) and len(m.group("hashes")) == level]
    out: dict[str, str] = {}
    for a, b in zip(idx, idx[1:] + [len(lines)]):
        out[_HEADING_RE.match(lines[a]).group("text")] = "".join(lines[a + 1:b])
    return out


def preamble(text: str, marker: str) -> str | None:
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


def parse_entries(section_body: str, section: str) -> list[Entry]:
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
        self.headings = headings(text, 2)
        secs = split_sections(text, 2)
        self.preamble = preamble(text, IDENTITY_END)
        self.dreams = parse_entries(secs.get("Dream entries", ""), "dream")
        self.settled = parse_entries(secs.get("Settled", ""), "settled")
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
def check_file(path: str, data: bytes | None) -> tuple[str | None, list[Finding]]:
    """§4.1 -- every file. Returns (text_or_None, findings)."""
    out: list[Finding] = []
    if data is None:
        return None, [_f("FAIL", "MISSING", path, "file absent or unreadable")]
    if not data.strip():
        return None, [_f("FAIL", "EMPTY", path, "file is empty")]
    text, err = decode(data)
    if text is None:
        return None, [_f("FAIL", "ENCODING", path, err)]
    if not text.endswith("\n"):
        out.append(_f("FAIL", "NO-EOL", path, "does not end with a newline"))
    elif text.endswith("\n\n"):
        out.append(_f("WARN", "TRAILING-BLANK", path, "ends with blank line(s)"))
    for c in suspicious_chars(text):
        out.append(_f("FAIL", "STRAY-CHAR", path,
                      f"unexpected script character {c} in English prose"))
    return text, out


def check_short_term(path: str, data: bytes | None, part: str,
                     open_time: str) -> list[Finding]:
    """A short_term is well-formed: readable, four sections in order, each with
    something under it, and headed for the right part and circle.

    Empty sections matter. A backfill that emits the headings and nothing beneath
    them passes a naive 'are the sections present' test and tells the nightly
    nothing — which is indistinguishable, downstream, from the loss it was meant
    to repair."""
    text, out = check_file(path, data)
    if text is None:
        return out
    idx = []
    for h in SHORT_TERM_SECTIONS:
        i = text.find(h)
        if i < 0:
            out.append(_f("FAIL", "MISSING-SECTION", path, f"no '{h}'"))
        idx.append(i)
    if any(i < 0 for i in idx):
        return out
    if idx != sorted(idx):
        out.append(_f("FAIL", "SECTION-ORDER", path,
                      "the four sections are not in the canonical order"))
    bounds = sorted(idx) + [len(text)]
    for h, a, b in zip(SHORT_TERM_SECTIONS, bounds, bounds[1:]):
        body = text[a + len(h):b].strip()
        if len(body.split()) < 8:
            out.append(_f("FAIL", "EMPTY-SECTION", path,
                          f"'{h}' has {len(body.split())} word(s) under it"))
    head = text.splitlines()[0] if text.splitlines() else ""
    if not head.startswith("# Short-term"):
        out.append(_f("FAIL", "BAD-HEADER", path, f"first line is {head[:50]!r}"))
    elif PARTS and part in PARTS:
        tag = part.replace("_", " ").title().replace("Soul", "Soul")
        if tag.lower() not in head.lower():
            out.append(_f("WARN", "HEADER-PART", path,
                          f"header names neither {part} nor {tag}: {head[:60]!r}"))
    if open_time and open_time[:10] not in text[:200]:
        out.append(_f("WARN", "HEADER-DATE", path,
                      f"header does not carry the circle date {open_time[:10]}"))
    return out


def check_size(path, base: bytes, cand: bytes, allow_shrink: bool) -> list[Finding]:
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
def compare_long_term(path: str, base_text: str, cand_text: str) -> list[Finding]:
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

    # -- everything above '## Dream entries' is frozen
    if b.preamble != c.preamble:
        out.append(_f("FAIL", "PREAMBLE-CHANGED", path,
                      "content above '## Dream entries' was modified; the "
                      "foundational identity sections are not the nightly's to touch"))

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
                out.append(_f("OK", "SETTLED", path, f"'{eid}' moved to ## Settled"))
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
                          f"new entry '{eid}' was written straight into ## Settled"))
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
                          f"new entry '{nid}' is not at the top of ## Dream entries"))
    return out


# ---------------------------------------------------------------- others
def compare_headed(path: str, base_text: str, cand_text: str,
                   allow_new: re.Pattern | None = None) -> list[Finding]:
    """self.md (and relationships.md until its 2026-08-15 TOML conversion):
    the '## ' heading set is the contract, and unchanged sections must be
    byte-identical."""
    out: list[Finding] = []
    bh, ch = headings(base_text), headings(cand_text)
    for h in bh:
        if h not in ch:
            out.append(_f("FAIL", "SECTION-LOST", path, f"section '## {h}' removed"))
    for h in ch:
        if h in bh:
            continue
        ok = allow_new and allow_new.match(f"## {h}")
        out.append(_f("OK" if ok else "FAIL", "SECTION-ADDED", path,
                      f"new section '## {h}'"))
    bs, cs = split_sections(base_text), split_sections(cand_text)
    for h in bh:
        if h in cs and bs[h] != cs[h]:
            out.append(_f("OK", "SECTION-REWRITTEN", path,
                          f"'## {h}' rewritten ({len(bs[h])} -> {len(cs[h])} chars)"))
    return out


def compare_append_only(path: str, base_text: str, cand_text: str) -> list[Finding]:
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


# ---------------------------------------------------------------- tree compare
def _tree_files(root: pathlib.Path) -> list[pathlib.Path]:
    # relationships.md REMOVED 2026-08-15: converted to per-part
    # part_relationships.toml (coordinator/part_relationships.py, renamed
    # from relationships.py/.toml 2026-08-17, R220) and retired.
    # The gate does not cover the TOML successor — that is B37's already
    # open "no gate exists for any TOML register today", now one file
    # wider, not a new gap invented here.
    out = [root / "parts" / p / "long_term.md" for p in PARTS]
    out += [root / "self" / f for f in SELF_FILES]
    return out


def compare_trees(baseline: pathlib.Path, candidate: pathlib.Path,
                  today: str | None = None,
                  first_synthesis: bool = False) -> list[Finding]:
    """Every invariant in NIGHTLY_DESIGN §4, baseline vs candidate.

    `first_synthesis` — R348, the operator's
    "(a)" (2026-08-25): when NOTHING has ever been processed in this tree
    (inter_circle.first_synthesis_here() is the one caller and the one
    test), self.md's shrink tolerance is waived — what the first synthesis
    replaces is the shipped seed, not a record this gate is protecting.
    Seen in the fresh install Inner-Circling-2026-08-25_1309, circle
    _1414: a valid same-headings replacement, 1,742 -> 1,115 bytes,
    refused the whole staged batch. The waiver is REPORTED (an OK
    FIRST-SYNTHESIS finding), never silent, and every later run keeps the
    full tolerance. Default False, so every other caller is unchanged."""
    today = today or datetime.date.today().isoformat()
    synth_ok = re.compile(rf"^## Dream synthesis {re.escape(today)}$")
    out: list[Finding] = []

    for bp in _tree_files(baseline):
        rel = bp.relative_to(baseline).as_posix()
        cp = candidate / rel
        bdata, cdata = read_bytes(bp), read_bytes(cp)
        if bdata is None:
            out.append(_f("WARN", "NO-BASELINE", rel, "not in the baseline; skipped"))
            continue
        if cdata is None:
            out.append(_f("FAIL", "MISSING", rel, "in baseline, absent from candidate"))
            continue
        ctext, cf = check_file(rel, cdata)
        out += cf
        btext, _ = check_file(rel, bdata)
        if ctext is None or btext is None:
            continue
        be, ce = line_endings(bdata), line_endings(cdata)
        if be != ce:
            out.append(_f("FAIL", "LINE-ENDINGS", rel,
                          f"line endings changed {be} -> {ce}. Nothing in this "
                          f"pipeline rewrites line endings on purpose; the usual "
                          f"cause is git core.autocrlf converting on checkout, "
                          f"which breaks every sha256 and byte-identical check. "
                          f"See .gitattributes."))
        elif ce == "mixed":
            out.append(_f("WARN", "LINE-ENDINGS", rel, "mixed CRLF and LF"))
        if bdata == cdata:
            out.append(_f("OK", "UNCHANGED", rel, "byte-identical"))
            continue

        name = bp.name
        if name == "long_term.md":
            settling = any(f.code == "SETTLED" for f in
                           compare_long_term(rel, btext, ctext))
            out += check_size(rel, bdata, cdata, allow_shrink=settling)
            out += compare_long_term(rel, btext, ctext)
        else:
            # SELF_FILES holds ONE member today: self.md, "structured".
            # "rewritten" went with circle_briefing.md (2026-08-11) and
            # "append_only" with narrative_arc.md (2026-08-24, the phantom
            # -- see SELF_FILES above). The append_only arm is KEPT rather
            # than deleted: it is the byte-prefix rule itself, the cheapest
            # guard this file has against a rewrite-instead-of-append, and
            # the next self/ document to need it should find it here rather
            # than re-derive it. It is UNREACHED while SELF_FILES has one
            # member, and no probe exercises compare_append_only() today --
            # so a future member must not assume this arm still works
            # without checking it.
            kind = SELF_FILES[name]
            out += check_size(rel, bdata, cdata, allow_shrink=first_synthesis)
            if (first_synthesis and len(bdata)
                    and (len(cdata) - len(bdata)) / len(bdata)
                    < -SHRINK_TOLERANCE):
                out.append(_f("OK", "FIRST-SYNTHESIS", rel,
                              "shrink past tolerance ACCEPTED — nothing has "
                              "ever been processed in this tree, so what this "
                              "replaces is the shipped seed, not a record "
                              "(R348)"))
            if kind == "append_only":
                out += compare_append_only(rel, btext, ctext)
            else:
                out += compare_headed(rel, btext, ctext, allow_new=synth_ok)

    # TOML registers — the PAIRED half of the register gate
    # (docs/REGISTER_GATE_DESIGN.md, R188). Iterated over BOTH trees so a
    # register staged into existence (circle_history's first run) is judged
    # with an empty baseline rather than skipped; a register absent from the
    # candidate was not part of the run and is skipped by compare_register.
    seen: set[str] = set()
    for tree in (baseline, candidate):
        for p, spec in _register_paths(tree):
            rel = p.relative_to(tree).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            out += compare_register(rel, read_bytes(baseline / rel),
                                    read_bytes(candidate / rel), spec)

    # narrative_<date>.md must be new, never an overwrite. Judge that on what the
    # run actually WRITES, not on what happens to exist: a run that stages no
    # narrative is unaffected by one already being there, and flagging it turns a
    # second look at an already-dreamed day into a phantom failure.
    nd = f"narrative_{today}.md"
    bn, cn = baseline / "self" / nd, candidate / "self" / nd
    bdata, cdata = read_bytes(bn), read_bytes(cn)
    if cdata is None:
        pass                                   # this run writes no narrative
    elif bdata is None:
        t, cf = check_file(f"self/{nd}", cdata)
        out += cf or [_f("OK", "NARRATIVE-NEW", f"self/{nd}", "written")]
    elif bdata != cdata:
        out.append(_f("FAIL", "NARRATIVE-OVERWRITE", f"self/{nd}",
                      f"already exists ({len(bdata):,} B) and this run would "
                      f"replace it ({len(cdata):,} B). One narrative per day; a "
                      f"second nightly for the same date must not clobber the "
                      f"first."))
    return out


def selfcheck_tree(root: pathlib.Path) -> list[Finding]:
    """No baseline: prove the parser understands the real files, and that they
    satisfy the invariants that do not need a comparison. Run this first."""
    out: list[Finding] = []
    # TOML registers — the single-tree half of the register gate
    # (docs/REGISTER_GATE_DESIGN.md, R188).
    for p, spec in _register_paths(root):
        out += check_register_file(p.relative_to(root).as_posix(),
                                   read_bytes(p), spec)
    for p in _tree_files(root):
        rel = p.relative_to(root).as_posix()
        data = read_bytes(p)
        text, cf = check_file(rel, data)
        out += cf
        if text is None:
            continue
        if (le := line_endings(data)) == "mixed":
            out.append(_f("WARN", "LINE-ENDINGS", rel,
                          "mixed CRLF and LF in one file"))
        elif le == "crlf":
            out.append(_f("WARN", "LINE-ENDINGS", rel,
                          "CRLF; the rest of the tree is LF"))
        if p.name == "long_term.md":
            lt = LongTerm(text)
            if lt.preamble is None:
                out.append(_f("FAIL", "NO-DREAM-SECTION", rel,
                              f"no '{IDENTITY_END}' delimiter"))
                continue
            for line in lt.unparsed:
                out.append(_f("FAIL", "UNPARSED-ENTRY", rel,
                              f"'### ' line does not match the entry template and "
                              f"is invisible to every count and comparison: "
                              f"{line[:90]!r}"))
            dupes = [e.id for e in lt.dreams + lt.settled
                     if [x.id for x in lt.dreams + lt.settled].count(e.id) > 1]
            if dupes:
                out.append(_f("FAIL", "DUPLICATE-ENTRY", rel,
                              f"entry id(s) appear twice: {sorted(set(dupes))}"))
            for e in lt.dreams:
                if e.is_tombstone:
                    out.append(_f("WARN", "TOMBSTONE", rel,
                                  f"'{e.id}' has a header but no body -- the entry "
                                  f"itself was lost; only the marker remains"))
                    continue
                anchor, src = e.recency
                if src == "entry-date":
                    out.append(_f("OK", "RECENCY-DERIVED", rel,
                                  f"'{e.id}' has no *Last mentioned:*; recency "
                                  f"anchored to its own dream date {anchor}"))
                if e.is_review and "review flagged" not in e.fields:
                    out.append(_f("WARN", "NO-FIELD", rel,
                                  f"'{e.id}' is [review] but has no *Review flagged:*"))
            for e in lt.settled:
                if "settled" not in e.fields:
                    out.append(_f("WARN", "NO-FIELD", rel,
                                  f"settled '{e.id}' has no *Settled:* field"))
            out.append(_f("OK", "PARSED", rel,
                          f"{len(lt.headings)} sections, {len(lt.dreams)} dream + "
                          f"{len(lt.settled)} settled entries, "
                          f"{len([e for e in lt.dreams if e.is_review])} [review]"))
        else:
            out.append(_f("OK", "PARSED", rel, f"{len(headings(text))} sections"))
    return out


# ---------------------------------------------------------- register gate
# docs/REGISTER_GATE_DESIGN.md, approved R188. The TOML arm of the ONE gate:
# compare_trees() gains register rows, selfcheck_tree() gains their
# single-tree half. "Append-only, mutable-fields-only" for a TOML register
# is defined HERE, as data, not as a regex:
#
#   PAIRED (baseline vs candidate — the phase-2 transaction gate)
#     ZERO mutations, every register: candidate records[:len(baseline)]
#     must equal baseline's records exactly (value equality), the [doc]
#     preamble and every non-table scalar except a declared monotonic
#     counter must be untouched, and both sides must be dumps()
#     FIXED-POINTS — a baseline that does not re-render byte-identically
#     was hand-edited without a re-save, and that is a FINDING, never a
#     silent fallback to value comparison. The tail is then judged:
#     count, cap, id sequence, date order, chain target, state vocabulary.
#   SINGLE-TREE (selfcheck — no baseline, no intent)
#     parse, id uniqueness and prefix, ids below next_id, date order,
#     state vocabulary, caps. FIELD-CONDITIONAL: a check activates only
#     where the field exists (today's remember.toml has no id/chain;
#     circle_history may not exist yet). Fixed-point failures are WARN
#     here (a hand-edit indicator) and FAIL in paired mode (the
#     precondition). FROZEN is paired-only — no reference bytes exist
#     single-tree, and git already watches the file.
#
# The driver side (intent validation, writer-scope matrix) lives with the
# phase-2 driver; this arm never trusts intents — it judges the trees.
def _ch_cap() -> int:
    """circle_history.CAP, imported rather than duplicated. Late import: this
    module is imported by circle_history's own dependency chain, so a
    top-level import would be circular. Falls back to the ruled value only if
    the module cannot be loaded at all, and says so rather than guessing
    silently."""
    try:
        import circle_history as _CH
        return _CH.CAP
    except Exception:
        return 8000        # R191's ruled value; see circle_history.CAP


def _mem_cap() -> int:
    """remember.GATE_CHAR_CEILING, imported rather than duplicated — the rule
    _ch_cap() below already writes down, applied to the register that needed
    it and did not have it.

    THIS ROW SAID 600 AND WAS WRONG FROM R255 (2026-08-19). 600 is
    RECORD_CAP, the COORDINATOR's ceiling; a PART's own authored memory may
    run to 1000 WORDS, and this gate measures characters. It refused the
    first live close that produced one — 2026-08-20, all seven parts, after
    dreaming had already written the live tree — which is exactly the
    failure the circle_history row was rewritten to prevent.

    Late import for the same reason _ch_cap() is late."""
    try:
        import remember as _RM
        return _RM.GATE_CHAR_CEILING
    except Exception:
        return 12000       # see remember.GATE_CHAR_CEILING for the reasoning


def _so_order() -> tuple[str, ...]:
    """self_observation_log.ORDER, imported rather than duplicated. Late for
    the same reason _ch_cap() is late — that module imports self_schema,
    which this module's own dependency chain already pulls in."""
    try:
        import self_observation_log as _SO
        return _SO.ORDER
    except Exception:
        return ("id", "date", "circle", "text", "note")


REGISTERS: dict[str, dict] = {
    "parts/*/remember.toml": {
        "table": "remember",
        # "salience" ADDED 2026-08-22 (DESIGN_V2 DREAMING extension) — MUST
        # equal remember.ORDER exactly: _fixed_point() re-renders a
        # candidate with THIS tuple, and a mismatch here would fail every
        # staged DREAMING record as NOT-FIXED-POINT the moment one carried
        # a salience field the gate did not know to render back.
        "order": ("id", "date", "circle", "text", "chain", "class",
                  "salience"),
        # CAP IS IMPORTED, NOT COPIED — see _mem_cap() and the
        # circle_history row below, which learned this first.
        "id_prefix": "MEM-", "cap": _mem_cap(), "per_run_max": 1,
        "preamble": False, "chain": True,
    },
    # "parts/*/part_relationships.toml" RETIRED 2026-08-22 — the register,
    # its module (coordinator/part_relationships.py) and the seven files are
    # deleted (RULINGS.md, after R308). It was the only register with
    # cap_exempt_first=True; that flag stays generic (see
    # check_register_file()'s `start = 1 if spec.get("cap_exempt_first")`)
    # for any future register to opt into, even with no current user.
    "self/topics.toml": {
        "table": "topic",
        "order": ("id", "circle", "date", "text", "state"),
        "id_prefix": "TP-", "cap": 800, "per_run_max": None,
        "preamble": True,
        "state_values": ("open",), "state_prefixes": ("closed by Self ",),
        "new_state": "open",
    },
    "self/proposals.toml": {
        "table": "proposal",
        # ORDER IS IMPORTED, NOT COPIED — see the circle_history entry
        # below for why a literal here would be a second source of truth.
        "order": PR.ORDER,
        # No file exists yet — no [propose ...] has ever converged to a
        # real row (R202, 2026-08-16). preamble=False: proposals.py's
        # _doc() writes {register, next_id, proposal}, no [doc] block —
        # unlike best_practices.toml, this register never had one.
        "id_prefix": "P-", "cap": None, "per_run_max": None,
        "preamble": False, "new_state": "proposed",
        # Same state shape as best_practices.toml (propose_class.py is
        # the shared base for both): state_values/state_prefixes omitted
        # for the same reason that entry omits them — accepted/denied
        # carry free-form ISO timestamps, not a fixed vocabulary.
    },
    # self/ since 2026-08-16 — Self's memory/ ruling returned the
    # register to the user-owned record (it was coordinator/ from
    # 2026-08-11).
    "self/best_practices.toml": {
        "table": "practice",
        # ORDER IS IMPORTED, NOT COPIED — the same rule this dict already
        # wrote down for circle_history's cap, applied to itself
        # (2026-08-16, the phase-2 review's finding #2): a literal here
        # was a second source of truth for a tuple check_best_practices
        # owns, and the proposals entry below had already shown the
        # correct form.
        "order": BPX.ORDER,
        # A phase-2 write may STAGE a proposal, never rule on one — every
        # new row arrives state="proposed". No cap: a practice row's title
        # is Self's or a part's own words, ruled unlimited (R023).
        "id_prefix": "BP-", "cap": None, "per_run_max": None,
        "preamble": True, "new_state": "proposed",
        # _sync_tally keeps an "**Entries: N**" count inside this file's
        # own preamble — the one register whose [doc] legitimately moves
        # when a row lands. Everything else about it stays immutable;
        # the tally is that module's own truth-keeping, not an edit.
        "preamble_tally": True,
        # single-tree state sanity intentionally omitted: accepted/denied
        # states carry free-form timestamps and R-prose; parse + ids only.
    },
    "self/circle_history.toml": {
        "table": "history",
        "order": ("id", "date", "circle", "text", "chain"),
        # CAP IS IMPORTED, NOT COPIED. This row said 600 until 2026-08-15 and
        # went on saying it after R191 raised circle_history.CAP to 8000 —
        # two places asserting the same number, one of them stale, which the
        # gate then enforced against real records that were correct. A
        # literal here is a second source of truth for a value that already
        # has an owner.
        "id_prefix": "CH-", "cap": _ch_cap(), "per_run_max": 1,
        "preamble": True, "chain": True,
    },
    "self/self_observation_log.toml": {
        "table": "observation",
        # ORDER IS IMPORTED, NOT COPIED — the rule this dict already wrote
        # down for circle_history's cap and best_practices' order.
        "order": _so_order(),
        # NO CAP: nothing upstream bounds an OBSERVATION section, so a cap
        # here would fail on legitimate output rather than enforce a
        # contract. See self_observation_log.py's own note.
        "id_prefix": "SO-", "cap": None, "per_run_max": 1,
        "preamble": True,
    },
    "parts/*/dreams.toml": {
        # READ-ONLY since R178 — nothing writes it. Any paired delta is a
        # defect. Excluded from single-tree checks: its schema predates
        # this gate and recency.py/mid_term.py are its readers of record.
        "frozen": True,
    },
}


def _register_paths(root: pathlib.Path) -> list[tuple[pathlib.Path, dict]]:
    """(path, spec) for every register file matching REGISTERS under root —
    existing files only; an absent register (circle_history before its
    first run) is simply not iterated."""
    out = []
    for pat, spec in REGISTERS.items():
        for p in sorted(root.glob(pat)):
            if p.is_file():
                out.append((p, spec))
    return out


def _load_register(data: bytes) -> tuple[dict | None, str | None]:
    try:
        import tomllib
    except ModuleNotFoundError:                                # 3.10
        import tomli as tomllib                                # type: ignore
    try:
        return tomllib.loads(data.decode("utf-8")), None
    except Exception as e:                                     # parse = gate
        return None, f"{type(e).__name__}: {e}"


def _fixed_point(data: bytes, spec: dict) -> bool:
    """dumps(load(bytes)) == bytes — true only for files self_schema wrote."""
    import self_schema as SS
    doc, err = _load_register(data)
    if doc is None:
        return False
    try:
        return SS.dumps(doc, spec["table"], spec["order"]).encode("utf-8") \
            == data
    except Exception:
        return False


def _idnum(rec: dict, prefix: str) -> int | None:
    v = rec.get("id", "")
    if isinstance(v, str) and v.startswith(prefix) and v[len(prefix):].isdigit():
        return int(v[len(prefix):])
    return None


def check_register_file(rel: str, data: bytes | None,
                        spec: dict) -> list[Finding]:
    """The SINGLE-TREE half. Field-conditional; must be 0 FAIL on the tree
    as it stands at merge (the design's own acceptance test)."""
    if spec.get("frozen"):
        return []
    if data is None:
        return [_f("WARN", "NO-FILE", rel, "register absent")]
    out: list[Finding] = []
    doc, err = _load_register(data)
    if doc is None:
        return [_f("FAIL", "UNPARSEABLE", rel, f"does not load: {err}")]
    # A hand edit can leave `doc` a scalar (`doc = 1` still parses as
    # TOML); .get on it crashed the whole gate with a traceback instead
    # of a finding (2026-08-18 review, tier 3 #30). Same for a non-int
    # next_id and a table of non-dict rows below — this gate exists to
    # catch hand-edit damage, so hand-edit damage must never crash it.
    dtab = doc.get("doc")
    if dtab is not None and not isinstance(dtab, dict):
        out.append(_f("FAIL", "BAD-DOC", rel,
                      f"[doc] is {type(dtab).__name__}, not a table"))
        dtab = {}
    if spec.get("preamble") and not (dtab or {}).get("preamble"):
        out.append(_f("WARN", "NO-PREAMBLE", rel, "no [doc] preamble"))
    recs = doc.get(spec["table"], [])
    if not isinstance(recs, list):
        return out + [_f("FAIL", "BAD-TABLE", rel,
                         f"{spec['table']!r} is not an array of tables")]
    if any(not isinstance(r, dict) for r in recs):
        return out + [_f("FAIL", "BAD-TABLE", rel,
                         f"{spec['table']!r} holds non-table entries")]
    pre = spec.get("id_prefix")
    if pre:
        ids = [r.get("id") for r in recs if "id" in r]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            out.append(_f("FAIL", "DUPLICATE-ID", rel, f"reused: {dupes}"))
        bad = [i for i in ids if not (isinstance(i, str) and i.startswith(pre)
                                      and i[len(pre):].isdigit())]
        if bad:
            out.append(_f("FAIL", "BAD-ID", rel,
                          f"not {pre}NNNN-shaped: {bad[:4]}"))
        if "next_id" in doc and not isinstance(doc["next_id"], int):
            out.append(_f("FAIL", "BAD-NEXT-ID", rel,
                          f"next_id is {type(doc['next_id']).__name__} "
                          f"({doc['next_id']!r}), not an int"))
        elif "next_id" in doc and ids and not bad:
            top = max(int(i[len(pre):]) for i in ids)
            if top >= doc["next_id"]:
                out.append(_f("FAIL", "NEXT-ID-BEHIND", rel,
                              f"max id {top} >= next_id {doc['next_id']} — "
                              f"the high-water counter has fallen behind"))
    dates = [r.get("date", "") for r in recs if r.get("date")]
    if any(a > b for a, b in zip(dates, dates[1:])):
        out.append(_f("WARN", "DATE-ORDER", rel,
                      "record dates are not nondecreasing in file order"))
    cap = spec.get("cap")
    if cap:
        start = 1 if spec.get("cap_exempt_first") else 0
        over = [i for i, r in enumerate(recs[start:], start)
                if len(r.get("text", "")) > cap]
        if over:
            out.append(_f("FAIL", "OVER-CAP", rel,
                          f"record(s) {over} exceed the {cap:,}-char cap"))
    sv = spec.get("state_values")
    if sv:
        okpre = spec.get("state_prefixes", ())
        bad = [r.get("id", "?") for r in recs
               if not (r.get("state") in sv
                       or any(str(r.get("state", "")).startswith(x)
                              for x in okpre))]
        if bad:
            out.append(_f("FAIL", "BAD-STATE", rel,
                          f"state outside vocabulary: {bad}"))
    if not _fixed_point(data, spec):
        out.append(_f("WARN", "NOT-FIXED-POINT", rel,
                      "does not re-render byte-identically — hand-edited "
                      "without a re-save? Paired mode will refuse this "
                      "baseline"))
    if not out:
        out.append(_f("OK", "PARSED", rel, f"{len(recs)} record(s)"))
    return out


def compare_register(rel: str, base: bytes | None, cand: bytes | None,
                     spec: dict) -> list[Finding]:
    """The PAIRED half — the phase-2 transaction gate for one register."""
    out: list[Finding] = []
    if cand is None:
        return []                       # not part of this run; nothing staged
    if spec.get("frozen"):
        if base != cand:
            return [_f("FAIL", "FROZEN", rel,
                       "read-only register changed — nothing may write it "
                       "(R178)")]
        return [_f("OK", "UNCHANGED", rel, "frozen and byte-identical")]
    if base is not None and not _fixed_point(base, spec):
        return [_f("FAIL", "NOT-FIXED-POINT", rel,
                   "baseline does not re-render byte-identically — "
                   "hand-edited without a re-save; normalize before phase 2 "
                   "(the design's named precondition)")]
    bdoc = ({spec["table"]: []} if base is None
            else _load_register(base)[0])
    cdoc, err = _load_register(cand)
    if bdoc is None or cdoc is None:
        return [_f("FAIL", "UNPARSEABLE", rel, f"does not load: {err}")]
    if not _fixed_point(cand, spec):
        return [_f("FAIL", "NOT-FIXED-POINT", rel,
                   "candidate is not a dumps() render — phase 2 stages "
                   "module-rendered bytes and nothing else")]
    if base is not None:
        # A register CREATED this run (base None) introduces its preamble
        # and scalars legitimately; an existing one may touch neither —
        # except best_practices' own "**Entries: N**" tally
        # (preamble_tally), which its module keeps true on every append.
        if bdoc.get("doc") != cdoc.get("doc"):
            # scalar-[doc] guard, same class as check_register_file's
            # BAD-DOC (tier 3 #30): a hand-edited candidate must FAIL
            # here as PREAMBLE-CHANGED, never crash the paired gate.
            bd = bdoc.get("doc") if isinstance(bdoc.get("doc"), dict) else {}
            cd = cdoc.get("doc") if isinstance(cdoc.get("doc"), dict) else {}
            bpre = str(bd.get("preamble", ""))
            cpre = str(cd.get("preamble", ""))
            _tly = re.compile(r"\*\*Entries: \d+\*\*")
            tally_only = (spec.get("preamble_tally")
                          and dict(bd, preamble="") == dict(cd, preamble="")
                          and _tly.sub("#", bpre) == _tly.sub("#", cpre))
            if not tally_only:
                out.append(_f("FAIL", "PREAMBLE-CHANGED", rel,
                              "[doc] differs — the preamble is immutable"))
        for k in set(bdoc) | set(cdoc):
            if k in (spec["table"], "doc", "next_id"):
                continue
            if bdoc.get(k) != cdoc.get(k):
                out.append(_f("FAIL", "SCALAR-CHANGED", rel,
                              f"top-level {k!r} changed"))
    brecs = bdoc.get(spec["table"], [])
    crecs = cdoc.get(spec["table"], [])
    if crecs[:len(brecs)] != brecs:
        n = next((i for i, (a, b) in enumerate(zip(crecs, brecs)) if a != b),
                 min(len(crecs), len(brecs)))
        out.append(_f("FAIL", "NOT-APPEND-ONLY", rel,
                      f"prior records are not a prefix of the candidate; "
                      f"first divergence at record {n}"))
        return out
    tail = crecs[len(brecs):]
    mx = spec.get("per_run_max")
    if mx is not None and len(tail) > mx:
        out.append(_f("FAIL", "TOO-MANY", rel,
                      f"{len(tail)} new record(s); this register takes at "
                      f"most {mx} per run"))
    pre = spec.get("id_prefix")
    if pre:
        base_n = bdoc.get("next_id", 1)
        want = cdoc.get("next_id")
        # The counter may be ABSENT on both sides of an id-less register
        # (today's remember.toml, before its first dreamt write) — that is
        # the one shape where no expectation exists. Everywhere else —
        # a tail, or a counter on either side — the arithmetic is exact.
        if tail or "next_id" in bdoc or want is not None:
            if want != base_n + len(tail):
                out.append(_f("FAIL", "NEXT-ID", rel,
                              f"next_id {want!r}; expected "
                              f"{base_n + len(tail)} "
                              f"(baseline {base_n} + {len(tail)} new)"))
        for i, r in enumerate(tail):
            if _idnum(r, pre) != base_n + i:
                out.append(_f("FAIL", "ID-SEQUENCE", rel,
                              f"new record {i} has id {r.get('id')!r}; "
                              f"expected {pre}{base_n + i:04d}"))
    cap = spec.get("cap")
    newest_base = max((r.get("date", "") for r in brecs), default="")
    base_ids = {r.get("id") for r in brecs if "id" in r}
    for i, r in enumerate(tail):
        if cap and len(r.get("text", "")) > cap:
            out.append(_f("FAIL", "OVER-CAP", rel,
                          f"new record {i}: {len(r.get('text', '')):,} chars "
                          f"over the {cap:,} cap — refuse upstream, never "
                          f"truncate here"))
        if r.get("date", "") < newest_base:
            out.append(_f("FAIL", "DATE-REGRESSION", rel,
                          f"new record {i} predates the baseline's newest"))
        ns = spec.get("new_state")
        if ns and r.get("state") != ns:
            out.append(_f("FAIL", "BAD-NEW-STATE", rel,
                          f"new record {i} arrives state={r.get('state')!r}; "
                          f"a phase-2 write may only stage {ns!r}"))
        if spec.get("chain") and r.get("chain") is not None \
                and r["chain"] not in base_ids:
            out.append(_f("FAIL", "CHAIN-TARGET", rel,
                          f"new record {i} chains to {r['chain']!r}, which is "
                          f"not an id in THIS register — a chain never leaves "
                          f"its own file"))
    if not out:
        what = f"+{len(tail)} record(s)" if tail else "unchanged"
        out.append(_f("OK", "REGISTER", rel, what))
    return out


def summarise(findings: list[Finding]) -> tuple[int, int, int]:
    f = sum(1 for x in findings if x.level == "FAIL")
    w = sum(1 for x in findings if x.level == "WARN")
    return f, w, len(findings) - f - w
