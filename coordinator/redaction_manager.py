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
`ui/ticker/bridge.py`'s own `do_redact()`/`_redact_one()` stays the
simpler, fixed version it always was; this module is the fuller model,
for `ui/circling.py` alone.

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
                             even across restarts. `literal` here IS raw
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
    "to hide in ui/circling.py's redacted CIRCLE-pane view. Ruled "
    "2026-08-31: CRUD, stable reversible opaque ids, adapted from a "
    "design used in a separate personal project (see this module's own "
    "docstring). Part names are never eligible, "
    "in either circles or consults -- redaction_manager.py refuses one at "
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
