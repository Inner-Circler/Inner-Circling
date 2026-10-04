#!/usr/bin/env python3
"""
redaction_manager.py — the two REDACTION registers, self/redaction.toml (the aliases) and
self/redaction_map.toml (the structured-identifier tokens): their one reader/writer.
(redaction.py until 2026-09-03 — B99 stage 18d under R435; the redact PIPELINE and the view's
default are stream_redaction.py's now, a STREAM class method.) The file's own account follows:

redaction.py — the CIRCLE pane's redacted view: a user-curated alias
registry plus always-on structured-identifier detection, both reversible
through stable opaque ids.

    python coordinator/redaction_manager.py            listing
    python coordinator/redaction_manager.py --init      write both empty registers

RULED 2026-08-31, the operator, on `ui/circling.py`'s redacted view:
*"Let's distinguish redaction from search. A raw/redacted switch can be on
the settings page, support CRUD of target strings, offer stable reversable
opaque ids, according to the original design. ... applied: only in the top
pane, never in any lower tab."* "The original design" is a design document
from a separate, unrelated personal project (a diary app) this project's
own `ui/ticker/` flavor adapted a UI from, but whose fuller redaction
model (a curated alias registry with stable reversible ids) was dropped
when that flavor shipped (`docs/TICKER_RESEARCH_DESIGN.md (archived)`).
Both flavors read this registry: `ui/circling.py`'s CIRCLE pane through
`stream_redaction.stream_redact()`, and `ui/ticker/bridge.py`'s
`do_redact()` through `stream_redaction.stream_session_redact()`, whose
structured identifiers stay per-session tokens. Each alias matches every
short and long name `alias_forms_expand()` derives from it.

TWO REGISTERS, DELIBERATELY SEPARATE — `REGISTER_CLASS.register_dumps()` renders
exactly one `[[table]]` array per file, and these are two different
concerns at two different sensitivity levels:

    self/redaction.toml       the CURATED alias registry — canonical name,
                             kind (person/place/org/other, matching the
                             original design's own four — "handle" there
                             is a STRUCTURED type, never a registry kind),
                             extra surface forms, a stable opaque id
                             (P1, L1, O1, G1). Ships empty via the
                             ordinary self/ scaffold exception: it holds
                             only the labels the operator chose to hide,
                             never the PII itself.
    self/redaction_map.toml   the REVERSE MAP for auto-detected structured
                             identifiers (email/url/phone/handle) —
                             literal -> stable opaque id (E1, W1, T1, H1),
                             minted the first time each is seen so the
                             same email always redacts to the same token
                             even across restarts — and every chat-log
                             SPEAKER detected by its line's shape (U1,
                             U2), the same way. `literal` here IS raw
                             PII — this file never ships
                             (packaging/runtime_only.txt).

TOKEN SPELLING IS UNHYPHENATED — `P1`, `E1`, not this project's usual
`BP-0004`/`P-12` house style. Deliberate: every other id in this codebase
is registry bookkeeping and never appears inside circle dialog; these are
PROSE-FACING — they replace a name inline in the rendered pane. Matches
the original design's own literal examples verbatim.

THE HARD EXEMPTION — the operator's own words, unconditional, in both
circles and consults: *"part names are never redacted."* Every current
part tag, every historical alt-spelling (`part_roster.ALT_TAGS`), and every
name Self has ever gone by (`identity.self_tags()`) is refused at
`alias_add()`/`alias_update()` time AND filtered out of the compiled
registry pattern every time it is built — the second check is defense in
depth against a hand-edited `redaction.toml` bypassing the first.
Structured-identifier passes need no equivalent guard: a part tag does
not shape-match an email, URL, phone, or handle.

NON-DESTRUCTIVE, PRESENTATION-ONLY. `redact()` never touches the
transcript file, the record, or anything but the string it is handed —
`ui/circling.py`'s `Pane` calls it only when rendering the CIRCLE pane
(never the COMMAND pane), on a copy of what's already been said. The one
write this module ever does is minting a new structured-identifier token
into `self/redaction_map.toml` the first time that identifier is seen —
a display-time function committing a small write, so the token stays
stable across restarts; everything else here is a pure transform.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import REGISTER_CLASS as SS                                       # noqa: E402
import part_roster as R                                               # noqa: E402
import identity as ID                                            # noqa: E402
import record_paths as P                                                 # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# REDACT_VIEW_DEFAULT moved to stream_redaction.py 2026-09-03 — the view's default is the stream's.

# --------------------------------------------------------------- the alias registry
ALIAS_PATH = P.REDACTION
ALIAS_TABLE = "alias"
ALIAS_ORDER = ("id", "kind", "canonical", "forms", "created")
ALIAS_KINDS = ("person", "place", "org", "other")
KIND_PREFIX = {"person": "P", "place": "L", "org": "O", "other": "G"}

_ALIAS_PREAMBLE = (
    "The operator's own curated redaction targets -- names, places, orgs "
    "to hide in ui/circling.py's redacted CIRCLE-pane view: added, "
    "updated and removed one at a time, each under a stable, reversible "
    "opaque id. Part names are never eligible "
    "-- redaction_manager.py refuses one at "
    "add/update time and filters it out of the compiled pattern besides.")

# ---------------------------------------------------------- the reverse map
MAP_PATH = P.REDACTION_MAP


@P.group_follow
def _paths_rebind() -> None:
    """The CURRENT group's registers — B117 stage 4 (2026-09-07)."""
    global ALIAS_PATH, MAP_PATH
    ALIAS_PATH = P.REDACTION
    MAP_PATH = P.REDACTION_MAP
MAP_TABLE = "token"
MAP_ORDER = ("id", "kind", "literal", "created")
STRUCTURED_KINDS = ("email", "url", "phone", "handle")
STRUCTURED_PREFIX = {"email": "E", "url": "W", "phone": "T", "handle": "H"}
# A chat-log SPEAKER, detected by the shape of its line rather than curated — stream_redaction.py's
# speaker pass. Its row lives HERE, in the map, not in the alias registry: the literal is a third
# party's name the operator never typed, so it takes the map's sensitivity (never ships, not
# tracked), and the registry keeps only what the operator curated. `U` is the original design's own
# prefix for a discovered speaker; `P` is the registry's person counter and would collide.
SPEAKER_KIND = "speaker"
SPEAKER_PREFIX = "U"
# A speaker the operator REMOVED: its id and identity key stay on file under this kind, so the
# same slot is never detected again and the id is never reused.
SUPPRESSED_KIND = "suppressed"

_MAP_PREAMBLE = (
    "The reverse map for auto-detected structured identifiers -- literal "
    "-> stable opaque id, so the same email/url/phone/handle always "
    "redacts to the same token across restarts. NEVER SHIPS -- `literal` "
    "IS the PII this exists to hide (packaging/runtime_only.txt).")


def _alias_doc() -> dict:
    if ALIAS_PATH.is_file():
        return SS.register_read(ALIAS_PATH)
    doc: dict = {"register": "redaction", "doc": {"preamble": _ALIAS_PREAMBLE},
                ALIAS_TABLE: []}
    for k in ALIAS_KINDS:
        doc[f"next_{k}"] = 1
    return doc


def _alias_save(doc: dict) -> None:
    ALIAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(ALIAS_PATH, doc, ALIAS_TABLE, ALIAS_ORDER)


def _map_doc() -> dict:
    if MAP_PATH.is_file():
        return SS.register_read(MAP_PATH)
    doc: dict = {"register": "redaction_map", "doc": {"preamble": _MAP_PREAMBLE},
                MAP_TABLE: []}
    for k in STRUCTURED_KINDS:
        doc[f"next_{k}"] = 1
    return doc


def _map_save(doc: dict) -> None:
    MAP_PATH.parent.mkdir(parents=True, exist_ok=True)
    SS.register_write(MAP_PATH, doc, MAP_TABLE, MAP_ORDER)


# ------------------------------------------------------- the hard exemption
def alias_protected_read() -> frozenset[str]:
    """Every word that may NEVER be redacted, casefolded: the seven live
    part tags, every historical alt-spelling, and every name Self has
    ever gone by. The operator's own words: "part names are never
    redacted in consults or circles." Rebuilt on every call — part_roster.py
    and identity.py cache their own reads, so this costs nothing worth
    caching a second time over."""
    return frozenset(t.casefold() for t in
                     set(R.TAGS) | set(R.ALT_TAGS) | ID.self_tags())


def _protected_hit(s: str) -> str | None:
    """The protected term `s` collides with, casefolded, or None."""
    folded = s.casefold()
    return folded if folded in alias_protected_read() else None


# ------------------------------------------------------------ alias CRUD
def alias_read() -> list[dict]:
    """Every curated alias, unordered."""
    return _alias_doc().get(ALIAS_TABLE, [])


def alias_add(canonical: str, kind: str = "other",
             forms: list[str] | None = None) -> tuple[bool, str]:
    """Curate one alias. Refuses a part tag, an alt tag, or any of Self's
    own names outright — canonical AND every form are checked, not just
    the canonical — so the operator learns of the collision at curation
    time rather than by a redaction silently not happening."""
    canonical = canonical.strip()
    if not canonical:
        return False, "a canonical name is required"
    kind = (kind or "other").strip().lower()
    if kind not in ALIAS_KINDS:
        return False, f"{kind!r} is not one of: {', '.join(ALIAS_KINDS)}"
    forms = [f.strip() for f in (forms or []) if f.strip()]
    for candidate in [canonical] + forms:
        hit = _protected_hit(candidate)
        if hit is not None:
            return False, (f"{candidate!r} is a part/Self name ({hit!r}) — "
                           f"part names are never redacted, in circles or "
                           f"consults")
    doc = _alias_doc()
    n = doc.get(f"next_{kind}", 1)
    rec = {"id": f"{KIND_PREFIX[kind]}{n}", "kind": kind,
          "canonical": canonical, "forms": [canonical] + forms,
          "created": SS.register_now()}
    doc.setdefault(ALIAS_TABLE, []).append(rec)
    doc[f"next_{kind}"] = n + 1
    _alias_save(doc)
    return True, f"added [{rec['id']}] {kind} {canonical!r}"


def alias_update(n: int, canonical: str,
                 forms: list[str] | None = None) -> tuple[bool, str]:
    """Replace one alias's canonical/forms in place — same id, same kind,
    same position in /redact-alias-list.

    KIND IS NOT EDITABLE HERE, on purpose. An id's prefix names its kind
    at creation (P/L/O/G) and never changes — the same "an id is never
    reused or renumbered" rule this project holds everywhere else. Letting
    update change kind would either leave a stale prefix (a `G1` now
    called "org") or require minting a second id for one row, which is a
    delete-and-recreate wearing a different name. Delete and re-add if
    the kind itself was wrong; the original design this replicates had no
    update verb at all for the same reason — add/list/delete only."""
    # Rides REGISTER_CLASS.register_row_update() since stage 2 of B116 (R465, 2026-09-07):
    # locate by the listing's number, id and kind immutable, the part-name precheck first,
    # only canonical/forms touched. The save stays here.
    canonical = canonical.strip()
    if not canonical:
        return False, "a canonical name is required"
    forms = [f.strip() for f in (forms or []) if f.strip()]

    def _precheck(fields: dict, _row: dict) -> str:
        for candidate in fields["forms"]:
            hit = _protected_hit(candidate)
            if hit is not None:
                return (f"{candidate!r} is a part/Self name ({hit!r}) — part names are "
                        f"never redacted, in circles or consults")
        return ""

    doc = _alias_doc()
    ok, msg, row = SS.register_row_update(
        doc, ALIAS_TABLE, locate=n, immutable=("id", "kind"), precheck=_precheck,
        fields={"canonical": canonical, "forms": [canonical] + forms})
    if not ok:
        return False, msg + (" — /redact-alias-list" if "1.." in msg else "")
    _alias_save(doc)
    return True, f"updated [{row['id']}] {row['kind']} {canonical!r}"


def alias_delete(n: int) -> tuple[bool, str]:
    """Remove the n-th alias AS /redact-alias-list numbers them — the id
    is never reused (this project's universal rule); the counter is
    untouched."""
    doc = _alias_doc()
    rows = doc.get(ALIAS_TABLE, [])
    if not 1 <= n <= len(rows):
        return False, f"{n} is not in 1..{len(rows)} — /redact-alias-list"
    gone = rows.pop(n - 1)
    _alias_save(doc)
    return True, f"removed [{gone['id']}] {gone['kind']} {gone['canonical']!r}"


def alias_forms_expand(row: dict) -> list[str]:
    """Every surface form one alias redacts, longest first: its curated `forms`, plus the short
    and long names derived from its canonical — `anon::expand_forms` from the original design's
    own anonymization engine, itself a chat anonymizer's token expansion. `"Robin (sherwood.archer)"` -> the whole label, `Robin`, `sherwood.archer`, `sherwood`,
    `archer`; a PERSON's canonical also splits on whitespace (`"Alice Smith"` -> `Alice`,
    `Smith`). Other kinds keep the whole label — splitting an org into its common words invites
    false positives. A derived word shorter than two characters is dropped. Nothing is written:
    the register keeps what the operator curated, and the expansion is recomputed at read."""
    found = {f.strip() for f in row.get("forms", []) if f.strip()}
    canonical = (row.get("canonical") or "").strip()
    if canonical:
        found.add(canonical)
        words: list[str] = []
        open_at = canonical.find("(")
        if open_at != -1 and canonical.endswith(")"):
            display = canonical[:open_at].strip()
            user = canonical[open_at + 1:-1].strip()
            if display:
                found.add(display)
                words += display.split()
            if user:
                found.add(user)
                words += user.replace(".", " ").split()
        elif row.get("kind") == "person":
            words += canonical.split()
        found.update(w for w in words if len(w) >= 2)
    return sorted(found, key=lambda f: (-len(f), f))


# ------------------------------------------------------------ discovered speakers
def redaction_speaker_split(segment: str) -> tuple[str, str]:
    """`"Jackie Davies (jackie.collingwood)"` -> (`"Jackie Davies"`, `"jackie.collingwood"`);
    `"Jackie Davies"` -> (`"Jackie Davies"`, `""`)."""
    seg = segment.strip()
    open_at = seg.find("(")
    if open_at != -1 and seg.endswith(")"):
        return seg[:open_at].strip(), seg[open_at + 1:-1].strip()
    return seg, ""


def redaction_speaker_expand(segment: str) -> tuple[str, list[str]] | None:
    """(identity key, forms longest first) for one speaker slot, or None if it is empty — the
    original design's `anon::expand_speaker`. Forms are the whole slot, the display name, its
    GIVEN name (two characters or more) and the handle: never the surname or the handle's
    dotted pieces, which read as ordinary words in prose far more often. The key is the handle,
    lowercased, when there is one, else the display name — so a slot with a handle and a later
    bare handle are one speaker."""
    seg = segment.strip()
    if not seg:
        return None
    display, handle = redaction_speaker_split(seg)
    forms = {seg}
    if display:
        forms.add(display)
        given = display.split()[0]
        if len(given) >= 2:
            forms.add(given)
    if handle:
        forms.add(handle)
    key = (handle or display).lower()
    if not key:
        return None
    return key, sorted(forms, key=lambda f: (-len(f), f))


def redaction_speaker_read() -> list[dict]:
    """Every discovered speaker's row in the map."""
    return [r for r in _map_doc().get(MAP_TABLE, []) if r.get("kind") == SPEAKER_KIND]


def redaction_speaker_add(segment: str) -> dict:
    """The map row for this speaker, minting `U<n>` and writing it through on first sight — so
    the same speaker redacts to the same id across restarts. A speaker already on file by key
    returns its own row and writes nothing."""
    exp = redaction_speaker_expand(segment)
    if exp is None:
        raise ValueError("an empty speaker slot")
    doc = _map_doc()
    for row in doc.get(MAP_TABLE, []):
        if row.get("kind") == SPEAKER_KIND:
            have = redaction_speaker_expand(row.get("literal", ""))
            if have is not None and have[0] == exp[0]:
                return row
    n = doc.get(f"next_{SPEAKER_KIND}", 1)
    rec = {"id": f"{SPEAKER_PREFIX}{n}", "kind": SPEAKER_KIND,
           "literal": segment.strip(), "created": SS.register_now()}
    doc.setdefault(MAP_TABLE, []).append(rec)
    doc[f"next_{SPEAKER_KIND}"] = n + 1
    _map_save(doc)
    return rec


def redaction_speaker_suppressed_read() -> frozenset[str]:
    """The identity key of every speaker the operator removed — never detected again."""
    return frozenset(r.get("literal", "") for r in _map_doc().get(MAP_TABLE, [])
                     if r.get("kind") == SUPPRESSED_KIND)


def redaction_speaker_delete(n: int) -> tuple[bool, str]:
    """Remove the n-th speaker AS /redact-speaker-list numbers them, and suppress it: the row
    becomes a `suppressed` row holding the same id and the speaker's identity key, so the
    detector skips that slot from now on. Its names show again at once. To hide them again,
    curate the name with /redact-alias-add — a curated alias is matched whatever is suppressed."""
    doc = _map_doc()
    rows = [r for r in doc.get(MAP_TABLE, []) if r.get("kind") == SPEAKER_KIND]
    if not 1 <= n <= len(rows):
        return False, f"{n} is not in 1..{len(rows)} — /redact-speaker-list"
    gone = rows[n - 1]
    exp = redaction_speaker_expand(gone.get("literal", ""))
    at = next(i for i, r in enumerate(doc[MAP_TABLE]) if r is gone)
    doc[MAP_TABLE][at] = {"id": gone["id"], "kind": SUPPRESSED_KIND,
                          "literal": exp[0] if exp else "", "created": SS.register_now()}
    _map_save(doc)
    return True, (f"removed [{gone['id']}] {gone.get('literal', '')!r} — shown again, and never "
                  f"detected again")


def redaction_speaker_list() -> str:
    rows = redaction_speaker_read()
    if not rows:
        return "  no detected speakers"
    out = []
    for i, e in enumerate(rows, 1):
        exp = redaction_speaker_expand(e.get("literal", ""))
        forms = ", ".join(exp[1]) if exp else ""
        out.append(f"  {i:>2}. [{e['id']}] {e.get('literal', '')}  ({forms})")
    out.append("\n" + SS.register_list_footer(len(rows), "/redact-speaker-list"))
    return "\n".join(out)


def redaction_speaker_record_show(n: int) -> str:
    """`/redact-speaker-list <n>`: that speaker WHOLE, through
    REGISTER_CLASS.register_record_show() (B133)."""
    return SS.register_record_show(redaction_speaker_read(), n, MAP_ORDER,
                                   verb="/redact-speaker-list")


def alias_list() -> str:
    rows = alias_read()
    if not rows:
        return "  no redaction aliases"
    out = []
    for i, e in enumerate(rows, 1):
        forms = ", ".join(e.get("forms", []))
        out.append(f"  {i:>2}. [{e['id']}] {e['kind']:<7} {e['canonical']}"
                  f"  ({forms})")
    out.append("\n" + SS.register_list_footer(len(rows), "/redact-alias-list"))
    return "\n".join(out)


def alias_record_show(n: int) -> str:
    """`/redact-alias-list <n>`: that alias WHOLE — every field, through
    REGISTER_CLASS.register_record_show() (B133)."""
    return SS.register_record_show(alias_read(), n, ALIAS_ORDER, verb="/redact-alias-list")


def main() -> int:
    a = sys.argv[1:]
    if "--init" in a:
        wrote = []
        if not ALIAS_PATH.is_file():
            _alias_save(_alias_doc())
            wrote.append(ALIAS_PATH.relative_to(ROOT))
        if not MAP_PATH.is_file():
            _map_save(_map_doc())
            wrote.append(MAP_PATH.relative_to(ROOT))
        print(f"  wrote {', '.join(str(w) for w in wrote)}" if wrote
             else "  both registers already exist — untouched")
        return 0
    print(alias_list())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
