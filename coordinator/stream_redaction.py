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
stream_session_redact() is the flavor's presentation-only transform — the user's own name, then email, url
and phone, to stable per-session tokens held in dicts the bridge owns; nothing on disk moves and
nothing is minted. Two pipelines, one home, both CONSOLE_IO.
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
        for form in row.get("forms", []):
            if RD._protected_hit(form) is None:
                form_to_row[form.lower()] = row
    pattern = None
    if form_to_row:
        words = sorted(form_to_row, key=len, reverse=True)
        alt = "|".join(re.escape(w) for w in words)
        pattern = re.compile(rf"\b(?:{alt})\b", re.IGNORECASE)
    _alias_cache.update(mtime=mtime, re=pattern, form_to_row=form_to_row)
    return pattern, form_to_row


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
    structured-identifier token the first time one is seen (see
    _token_for). Part names are NEVER matched here, by construction:
    _alias_lookup()'s pattern already excludes them."""
    alias_re, form_to_row = _alias_lookup()
    if alias_re is not None:
        text = alias_re.sub(lambda m: form_to_row[m.group(0).lower()]["id"],
                            text)
    for kind in _STRUCTURED_ORDER:
        text = _STRUCTURED_RE[kind].sub(
            lambda m, k=kind: _token_for(k, m.group(0)), text)
    return text



# ------------------------------------------------- the Ticker's session redaction
def stream_session_redact(text: str, redact_map: dict, redact_counts: dict) -> str:
    """bridge.py's _redact_one until 2026-09-03, verbatim in effect: identity-derived first (the
    user's own name), then structured identifiers. Stable typed tokens per SESSION — the two dicts
    are the bridge's own — Ticker's contract kept: presentation-only, nothing on disk moves."""
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
