#!/usr/bin/env python3
"""
stream_redaction.py — the redact pipeline: what the CONSOLE_IO stream shows when the redacted view is
on. A STREAM class method (the plan's Q-2/Q-7: STREAM ::= CONSOLE_IO | LLM_IO; redaction is CONSOLE_IO
only — LLM_IO carries the real text, by ruling). Presentation-only: nothing in the transcript moves.

IN redaction.py UNTIL 2026-09-03 (B99 stage 18d). The pipeline — the structured-identifier patterns,
the alias lookup cached against the register's mtime, the write-through token minting, stream_redact() —
moved verbatim, read through `RD.`: the two registers and their paths stay in redaction_manager.py,
and the suites rebind RD.ALIAS_PATH / RD.MAP_PATH there, so this file reads them by attribute, never
by copy. REDACT_VIEW_DEFAULT came with it — the view's default is the stream's, not the register's.

THE TICKER'S SESSION REDACTION FOLDS IN HERE TOO (bridge.py's _redact_one/_token until the same day):
stream_session_redact() is the flavor's presentation-only transform — the alias registry's short and
long names to their registry ids, chat-log speakers to their saved ids, then the user's own name,
email, url and phone to stable per-session tokens held in dicts the bridge owns. Two pipelines, one
home, both CONSOLE_IO, one alias lookup and one speaker lookup.

THE SPEAKER PASS (2026-09-29, the operator: "saved"). A line shaped `[time]  Name (user.name): text` names
its speaker by position, not by curation; the original design's own speaker detection. Each new
speaker is minted `U<n>` into the reverse map on first sight (redaction_manager.redaction_speaker_add),
and its whole slot, display name, given name and handle then redact everywhere, case-sensitively.
Nothing in the transcript or the journal moves; the map is the one write, as for a structured token.
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import identity as ID                                            # noqa: E402
import redaction_manager as RD                                   # noqa: E402
import setting_manager as SET                                           # noqa: E402

# Off by default: "a privacy mechanism for depersonalizing statements, for example if you were
# to share some circle dialog with a third party" (ruled R564, 2026-09-12).
REDACT_VIEW_DEFAULT = SET.setting_value_read("redact_view", False)


# --------------------------------------------------------- the redact pipeline
_STRUCTURED_RE = {
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "url": re.compile(r"https?://\S+"),
    "phone": re.compile(r"(?<![\w.])\+?\d[\d ().-]{7,}\d(?![\w.])"),
    # run AFTER email — an email's own "@" is already a token by then.
    "handle": re.compile(r"@[A-Za-z0-9_]{2,32}"),
}
_STRUCTURED_ORDER = RD.STRUCTURED_KINDS      # ONE HOME: the manager's tuple, imported, not copied (the
                                             # one line of the move that is not the cut's bytes)

_alias_cache: dict = {"mtime": "unread", "re": None, "form_to_row": {}}


def _alias_lookup() -> tuple[re.Pattern | None, dict]:
    """(compiled longest-first alternation, {form.lower(): row}) over
    every alias's own forms, protected terms already excluded — both
    cached together against self/redaction.toml's mtime, so a re-render
    on every displayed line neither recompiles a growing pattern nor
    re-reads the register from disk each time."""
    mtime = RD.ALIAS_PATH.stat().st_mtime if RD.ALIAS_PATH.is_file() else None
    if _alias_cache["mtime"] == mtime:
        return _alias_cache["re"], _alias_cache["form_to_row"]
    form_to_row: dict = {}
    for row in (RD.alias_read() if RD.ALIAS_PATH.is_file() else []):
        for form in RD.alias_forms_expand(row):
            if RD._protected_hit(form) is None:
                form_to_row.setdefault(form.lower(), row)
    pattern = None
    if form_to_row:
        words = sorted(form_to_row, key=len, reverse=True)
        alt = "|".join(re.escape(w) for w in words)
        # Lookarounds, not \b: a form may start or end in a non-word character — the whole
        # `Robin (sherwood.archer)` ends in `)`, where \b would demand a word character follow.
        pattern = re.compile(rf"(?<!\w)(?:{alt})(?!\w)", re.IGNORECASE)
    _alias_cache.update(mtime=mtime, re=pattern, form_to_row=form_to_row)
    return pattern, form_to_row


def _alias_sub(text: str, kinds: tuple[str, ...]) -> str:
    """Every alias form in `text` -> its alias's stable id (P1, L1, O1, G1), outside the structured
    spans (_outside_spans_sub)."""
    alias_re, form_to_row = _alias_lookup()
    if alias_re is None:
        return text
    return _outside_spans_sub(text, kinds, alias_re,
                              lambda m: form_to_row[m.group(0).lower()]["id"])


# --------------------------------------------------------- the speaker pass
# A chat-log line: a bracketed time, optionally dated (`[05:14]`, `[2023/06/01 05:14]`), then the
# speaker slot up to the first colon. The anchor is what keeps prose untouched — a sentence never
# starts that way — the same precision-first stance as the structured patterns. The slot may not
# hold a colon, and a colon that opens `//` is a url's, not a speaker's.
_SPEAKER_RE = re.compile(
    r"(?m)^[ \t]*\[(?:\d{4}[/-]\d{1,2}[/-]\d{1,2}[ T]+)?\d{1,2}:\d{2}(?::\d{2})?\][ \t]+"
    r"([^:\n]+):(?!//)")

_speaker_cache: dict = {"mtime": "unread", "re": None, "form_to_row": {}, "keys": set()}


def _speaker_lookup() -> tuple[re.Pattern | None, dict, set]:
    """(compiled pattern, {form: row}, {identity key}) over every discovered speaker in the map,
    protected terms excluded, cached against the MAP's mtime — a speaker is minted there, so a
    cache keyed on the alias registry would not see it. CASE-SENSITIVE, the original design's own
    bound on false positives: a given name `Rose` is a speaker, `rose` stays a flower."""
    mtime = RD.MAP_PATH.stat().st_mtime if RD.MAP_PATH.is_file() else None
    if _speaker_cache["mtime"] == mtime:
        return _speaker_cache["re"], _speaker_cache["form_to_row"], _speaker_cache["keys"]
    form_to_row: dict = {}
    # a removed speaker's key counts as known, so discovery never mints it again
    keys: set = set(RD.redaction_speaker_suppressed_read()) if RD.MAP_PATH.is_file() else set()
    for row in (RD.redaction_speaker_read() if RD.MAP_PATH.is_file() else []):
        exp = RD.redaction_speaker_expand(row.get("literal", ""))
        if exp is None:
            continue
        keys.add(exp[0])
        for form in exp[1]:
            if RD._protected_hit(form) is None:
                form_to_row.setdefault(form, row)
    pattern = None
    if form_to_row:
        alt = "|".join(re.escape(w) for w in sorted(form_to_row, key=len, reverse=True))
        pattern = re.compile(rf"(?<!\w)(?:{alt})(?!\w)")
    _speaker_cache.update(mtime=mtime, re=pattern, form_to_row=form_to_row, keys=keys)
    return pattern, form_to_row, keys


def _speakers_discover(text: str) -> None:
    """Mint a map row for every speaker slot in `text` not yet on file. Skipped: a speaker whose
    slot, display name or handle a CURATED alias already covers (the operator's id wins), and one
    whose slot or display name is a part or Self name."""
    slots = [m.group(1).strip() for m in _SPEAKER_RE.finditer(text)]
    if not slots:
        return
    _, _, keys = _speaker_lookup()
    _, curated = _alias_lookup()
    minted = False
    for slot in slots:
        exp = RD.redaction_speaker_expand(slot)
        if exp is None or exp[0] in keys:
            continue
        display, handle = RD.redaction_speaker_split(slot)
        if RD._protected_hit(slot) is not None or RD._protected_hit(display) is not None:
            continue
        if any(x.lower() in curated for x in (slot, display, handle) if x):
            continue
        RD.redaction_speaker_add(slot)
        keys.add(exp[0])
        minted = True
    if minted:
        _speaker_cache["mtime"] = "unread"


def _speaker_sub(text: str, kinds: tuple[str, ...]) -> str:
    """Every discovered speaker's forms in `text` -> its stable id (U1, U2, ...), outside the
    structured spans (_outside_spans_sub)."""
    speaker_re, form_to_row, _ = _speaker_lookup()
    if speaker_re is None:
        return text
    return _outside_spans_sub(text, kinds, speaker_re, lambda m: form_to_row[m.group(0)]["id"])


def _outside_spans_sub(text: str, kinds: tuple[str, ...], pattern: re.Pattern, repl) -> str:
    """`pattern.sub(repl, ...)` over `text`, OUTSIDE any span one of the structured `kinds` matches.
    A short name is often the local part of an email or a path segment of a url; redacted there
    first, an email whose local part is a name would reach the structured pass with the id in its
    place, and the reverse map would record that as the literal. The structured pass that runs
    after owns those spans whole."""
    merged: list[list[int]] = []
    for s, e in sorted(m.span() for k in kinds for m in _STRUCTURED_RE[k].finditer(text)):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out, at = [], 0
    for s, e in merged + [[len(text), len(text)]]:
        out.append(pattern.sub(repl, text[at:s]))
        out.append(text[s:e])
        at = e
    return "".join(out)


def _token_for(kind: str, literal: str) -> str:
    """The stable opaque id for one structured-identifier literal —
    minted and WRITTEN THROUGH on first sight, so the same email always
    redacts to the same token even across restarts."""
    key = literal.lower()
    doc = RD._map_doc()
    for row in doc.get(RD.MAP_TABLE, []):
        if row.get("kind") == kind and row.get("literal", "").lower() == key:
            return row["id"]
    n = doc.get(f"next_{kind}", 1)
    rec = {"id": f"{RD.STRUCTURED_PREFIX[kind]}{n}", "kind": kind,
          "literal": literal, "created": RD.SS.register_now()}
    doc.setdefault(RD.MAP_TABLE, []).append(rec)
    doc[f"next_{kind}"] = n + 1
    RD._map_save(doc)
    return rec["id"]


def stream_redact(text: str) -> str:
    """The presentation-only transform ui/circling.py's Pane calls when
    its redact_view is on. Never writes the transcript, never touches
    anything but the string handed in — except for minting a new
    structured-identifier token or speaker id the first time one is seen
    (see _token_for, _speakers_discover). Part names are NEVER matched
    here, by construction: both lookups' patterns already exclude them."""
    _speakers_discover(text)
    text = _alias_sub(text, _STRUCTURED_ORDER)
    text = _speaker_sub(text, _STRUCTURED_ORDER)
    for kind in _STRUCTURED_ORDER:
        text = _STRUCTURED_RE[kind].sub(
            lambda m, k=kind: _token_for(k, m.group(0)), text)
    return text



# ------------------------------------------------- the Ticker's session redaction
def stream_session_redact(text: str, redact_map: dict, redact_counts: dict) -> str:
    """bridge.py's _redact_one until 2026-09-03: the alias registry first — every short and long
    name alias_forms_expand() gives, to the alias's own registry id — then every chat-log speaker,
    to its saved U id (a new speaker is minted into the map on first sight, the one write here),
    then the user's own name and the structured identifiers, which take stable typed tokens per
    SESSION, held in the bridge's two dicts and never written."""
    kinds = ("email", "url", "phone")   # the three this session pass tokenises
    _speakers_discover(text)
    text = _alias_sub(text, kinds)
    text = _speaker_sub(text, kinds)
    name = ID.user_name_read()
    if name:
        text = re.sub(re.escape(name),
                      lambda m: _session_token(redact_map, redact_counts, "person", m.group(0)),
                      text, flags=re.IGNORECASE)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+",
                  lambda m: _session_token(redact_map, redact_counts, "email", m.group(0)), text)
    text = re.sub(r"https?://\S+",
                  lambda m: _session_token(redact_map, redact_counts, "url", m.group(0)), text)
    text = re.sub(r"(?<![\w.])\+?\d[\d ().-]{7,}\d(?![\w.])",
                  lambda m: _session_token(redact_map, redact_counts, "phone", m.group(0)), text)
    return text


def _session_token(redact_map: dict, redact_counts: dict, kind: str, matched: str) -> str:
    key = f"{kind}:{matched.lower()}"
    if key not in redact_map:
        redact_counts[kind] = redact_counts.get(kind, 0) + 1
        redact_map[key] = f"{kind}-{redact_counts[kind]:02d}"
    return redact_map[key]
