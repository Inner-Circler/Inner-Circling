#!/usr/bin/env python3
"""
identity.py — who "Self" is, for this installation.

RULED 2026-08-11: a literal personal name is forbidden PII. Nothing that
reaches a transcript or a part's prompt may carry one — see `SELF_ID` and
`DISPLAY` below. Personalisation survives in exactly one place: the local
console, which never becomes model input and never leaves the machine.

THREE NAMES, AND CONFLATING THEM IS THE BUG THIS MODULE PREVENTS.

    SELF_ID     "self"      the CANONICAL INTERNAL ID. Never
                            displayed, never written to a
                            transcript, never configurable.
                            Every `speaker ==` comparison uses
                            it.

    DISPLAY     "Self"      the TRANSCRIPT/PROMPT display name.
                            Fixed. Written into the transcript as
                            `[Self]:` and into every prompt block
                            that names Self at all. Never reads
                            configuration — that is the point.

    user_name_read() the HOME    the CONSOLE-ONLY display name. Shown at
                role's       the `Self> ` prompt and in `/help` and
                preferred_   `--identity`. Never written to a
                name, else   transcript, never sent to a model.
                $IFS_USER_   (The preferred name joined the order
                NAME, else   2026-08-23, R325; the home role is the
                "Self"       group's own since R468 — see
                             self_home_name_read() below.)

Before DISPLAY existed, `user_name_read()` was BOTH the comparison key and the
rendered tag, so personalising the tag would have silently changed every
comparison — and, after the 2026-08-07 personalisation ruling, would have
put a real name in front of a model on every circle. The reader below still
accepts any tag it does not recognise as a part:

    A TAG THAT IS NOT A PART IS SELF.

That rule is what makes every past transcript still readable: the 42
circles already on disk carry the names this installation wrote before
today, a fresh install writes `[Self]:`, and both parse. See
`HISTORICAL_NAMES` for the parsing side of this — it is unaffected by
today's ruling, which is about what gets WRITTEN, not what can be READ.

`user_name_read()` READS `IFS_USER_NAME` FROM THE `.env` FILE ONLY, never from
the process environment. `ANTHROPIC_API_KEY` already demonstrated the
failure mode a process-environment check invites (NEXT.md A16): a stale
value set hours ago silently outlives the file that was supposed to
control it. Reading the file directly means editing `.env` always takes
effect on the next call, with nothing else to check or clear. Absent from
the file, the default is the literal string `"Self"` — never the OS login,
which is a name nobody chose for this purpose and would otherwise leak
into the console prompt with no configuration at all.
"""

from __future__ import annotations

import os
import pathlib
import record_paths as _RP                                         # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

SELF_ID = "self"
DEFAULT_NAME = "Self"
DISPLAY = DEFAULT_NAME

ENV_PROJECT = "IFS_USER_NAME"


def _load_env() -> None:
    """Best-effort .env load into the process environment. Used only by
    `self_retired_tags_read()`, which reads a different variable and is unaffected by
    today's ruling — it exists to recognise old transcripts, never to
    decide what gets written.

    gitrepo._load_env() is the same eight lines. Kept separate on purpose: gitrepo.py is
    the git surface and identity.py is read by the prompt layer, so sharing this would
    put an import edge between them for a best-effort dotenv call that both must survive
    the absence of. .env is also this project's documented source of two-verdict bugs
    (R223/R234), which argues for each reader owning its own load rather than a hidden
    shared one."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(ROOT / ".env")


def _env_file() -> dict[str, str]:
    """The .env FILE's own contents, never the process environment — see
    the module docstring. `{}` when python-dotenv is absent or there is no
    .env file; both are normal."""
    try:
        from dotenv import dotenv_values
    except ModuleNotFoundError:
        return {}
    return dict(dotenv_values(ROOT / ".env")) if (ROOT / ".env").is_file() else {}


# THE SOUL'S ANSWER TO "WHAT DO YOU PREFER TO BE CALLED" — R325,
# 2026-08-23: *"6 - b; if none given use IFS_USER_NAME, if no IFS user name
# use 'Self'."* The initialization dialog (docs/Initialization.md) records it
# in parts/soul/part.toml [context.answers].preferred_name, and it names the
# CONSOLE — the same console-only standing $IFS_USER_NAME has under R132:
# never a transcript, never a model (R329). Read directly
# with tomllib, the way self_installed_tags_read() reads self/identity.toml, because
# this module must stay dependency-light (roster imports it); and read on
# every call, so a change in the file is the next prompt's name.
#
# THE HOME ROLE — R468, B120 (2026-09-07): the role that holds the user's own particulars is
# named by the group's own group.toml (`[identity] role`, `key`), never by shipped code. HOME_DIR
# is that role's directory for the group this process is bound to ("soul" for the IFS group,
# "" for a group that names none — the console name then falls through to $IFS_USER_NAME and
# "Self"); it follows record_paths.group_set(). SOUL_DIR was the literal until R468.
PREFERRED_NAME_KEY = "preferred_name"
HOME_DIR = ""
HOME_KEY = PREFERRED_NAME_KEY


def _home_rebind() -> None:
    global HOME_DIR, HOME_KEY
    ident = _RP.group_descriptor_read(_RP.group_read()).get("identity") or {}
    HOME_DIR = str(ident.get("role", "") or "").strip()
    HOME_KEY = str(ident.get("key", "") or "").strip() or PREFERRED_NAME_KEY


_RP.group_follow(_home_rebind)
_home_rebind()


def self_consumed_keys_read() -> tuple:
    """The context answers THE MECHANISM READS — 2026-08-28, and the answer to
    a question the audience rule left open.

    A part's context answer normally reaches a model and nothing else: it is
    rendered into BLOCK 3 through its own `render` string, and a model reads
    around a typo, so freedom of expression is the asset and a gate would only
    get in the way. A few answers are different — something in the program
    ACTS on them — and those must be discrete and always valid.

    A THIRD CATEGORY EXISTS AND HAD NO NAME. Ten of the Soul's questions
    declare no `render` at all: the two names (PII, R329) and, since
    2026-08-27, the gender and religion answers the operator ruled recorded
    but never spoken. Those reach NEITHER a model NOR the mechanism. Nothing
    acts on them, so there is nothing to keep valid, and they need no gate —
    only the shape rules every answer has.

    WHICH LEAVES THIS LIST, and it is declared HERE rather than inferred,
    because "the mechanism reads this" is not visible from the declaration
    and part_roster.part_verify() would otherwise have to guess. Adding a reader of an
    answer means adding its key here, and the check then demands that answer
    declare how it is kept valid.

    NO FLAG ON THE QUESTION ITSELF. R329 made the ABSENCE of `render` the
    gate — "not a flag the code has to remember to check" — and a second
    marker saying the same thing from the other side would be one fact in two
    places, which is the defect system_unique_home_verify.py exists for."""
    return (PREFERRED_NAME_KEY,)


def self_home_name_read() -> str:
    """parts/<HOME_DIR>/part.toml [context.answers].<HOME_KEY>, stripped; ""
    when the group names no home role, or the file, the table or the key is absent, empty, or
    unreadable — every failure degrades to "not given", never raises. (soul_preferred_name()
    until R468.)"""
    if not HOME_DIR:
        return ""
    p = _RP.record_dir(ROOT, "parts") / HOME_DIR / "part.toml"
    if not p.is_file():
        return ""
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        try:
            import tomli as tomllib                             # type: ignore
        except ModuleNotFoundError:
            return ""
    try:
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
        v = doc.get("context", {}).get("answers", {}).get(HOME_KEY, "")
    except Exception:                                           # noqa: BLE001
        return ""
    return v.strip() if isinstance(v, str) else ""


def user_name_read(explicit: str | None = None) -> str:
    """The CONSOLE-ONLY display name. Never used as a comparison key, never
    written to a transcript, never sent to a model — see DISPLAY for that.

    RESOLUTION, most explicit first (R325): an explicit
    argument; the home role's recorded preferred_name (the group's own, R468); $IFS_USER_NAME
    from the .env FILE; the literal "Self"."""
    if explicit and explicit.strip():
        return explicit.strip()
    return user_name_source()[0]


def user_name_source() -> tuple[str, str]:
    """(value, where it came from) — for `--identity` and the console
    banner, so a run says which name it is about to show."""
    v = self_home_name_read()
    if v:
        return v, _RP.record_rel(f"parts/{HOME_DIR}/part.toml") + f" {HOME_KEY}"
    v = _env_file().get(ENV_PROJECT, "").strip()
    if v:
        return v, f"${ENV_PROJECT}"
    return DEFAULT_NAME, "default"


# EVERY NAME SELF HAS EVER BEEN WRITTEN AS. An EXPLICIT SET, and the first
# version of this was not — it said "any tag that is not a part is Self",
# which is one line shorter and wrong.
#
# The corpus caught it. Four agent-teams transcripts carry `[Self, sings]`
# and `[Child — Self-report]`; under the permissive rule both parsed as
# ordinary Self statements instead of being refused, and test_resume's
# round-trip went from 0 failures to 4. parse_transcript's own docstring
# says it is "deliberately strict… a parser that guesses at a malformed one
# would launder damage into a live circle." Guessing is exactly what the
# short version did.
#
# A PERSONAL NAME USED TO BE IN THIS TUPLE, and Self ruled it out on
# 2026-08-07: a personal name "is PII, there is no place for it in a
# proper export." Right, and the literal was never doing work a
# configuration could not: `self_tags()` already unions the CURRENT name
# in, and the current name IS the one those transcripts carry. Removing it
# changes nothing for him and removes a stranger's name from a recipient's
# parser.
#
# `IFS_SELF_TAGS` exists for the case the literal was covering: a name this
# install USED TO write and no longer does. Nothing needs it today. If the
# configured name ever changes, put the retired one there and the older
# transcripts keep parsing.
#
# 2026-08-11 widened the same ruling from "not in an export" to "not
# written at all" — see the module docstring's DISPLAY. This function's job
# is now RECOGNITION ONLY: `self_tags()`'s dynamic union still resolves
# `user_name_read()` so a transcript carrying whatever name this install used to
# write (including from before today) still parses. Nothing here decides
# what gets written any more.
HISTORICAL_NAMES = ("Self",)
ENV_RETIRED = "IFS_SELF_TAGS"


def self_retired_tags_read() -> frozenset[str]:
    """Names this installation used to write. Comma-separated, from the
    environment or .env. Empty is the normal case."""
    _load_env()
    raw = os.environ.get(ENV_RETIRED, "")
    return frozenset(t.strip() for t in raw.split(",") if t.strip())


def self_installed_tags_read() -> frozenset[str]:
    """Names this installation used to write, from the TRACKED file
    `self/identity.toml`. Empty when it is absent, which is the normal case
    for a fresh install and for the shipped bundle — the file never ships.

    RULED 2026-08-18 (R234): a historic Self tag must resolve in EVERY
    environment. `self_retired_tags_read()` and `user_name_read()` both read `.env`, which
    is gitignored — present in the main checkout, absent from every
    worktree — so `memory/issue_gate.py` resolved the same transcript line
    to Self in one place and to the part that spoke before it in another,
    and returned two different verdicts on one graph. A tracked file is
    checked out everywhere; that is the whole mechanism.

    Read directly rather than through `REGISTER_CLASS`: this module is
    imported by `roster`, `transcript_store` and `issue_gate`, and must
    stay dependency-light."""
    p = _RP.record_dir(ROOT, "self") / "identity.toml"
    if not p.is_file():
        return frozenset()
    try:
        import tomllib
    except ModuleNotFoundError:                                 # py < 3.11
        try:
            import tomli as tomllib                             # type: ignore
        except ModuleNotFoundError:
            return frozenset()
    try:
        doc = tomllib.loads(p.read_text(encoding="utf-8"))
    except Exception:
        # A malformed file must not take down every caller that only wanted
        # to know whether a tag is a part. Absent and unreadable degrade the
        # same way, and `--identity` below is where it is meant to show.
        return frozenset()
    return frozenset(str(t).strip() for t in doc.get("tags", ())
                     if str(t).strip())


def self_tags(current: str | None = None) -> frozenset[str]:
    """The tags that mean Self: the universal one, this installation's own
    recorded ones, any retired ones, and whatever it writes now.

    `self_installed_tags_read()` is the only member that does not depend on the
    process environment or on `.env` — see R234, and `self/identity.toml`
    for why it is a tracked file."""
    return (frozenset(HISTORICAL_NAMES) | self_installed_tags_read() | self_retired_tags_read()
            | {current or user_name_read()})


def self_is_tag(tag: str, current: str | None = None) -> bool:
    """True only for a KNOWN Self tag. An unrecognised tag is neither a part
    nor Self, and the caller must refuse it rather than absorb it."""
    return tag in self_tags(current)


if __name__ == "__main__":
    v, src = user_name_source()
    print(f"  canonical id       {SELF_ID!r}   (never configurable)")
    print(f"  transcript tag     [{DISPLAY}]:   (fixed, never {ENV_PROJECT})")
    print(f"  console prompt     {v}>   <- {src}")
    print(f"  parses as Self     {', '.join(sorted(self_tags(v)))}")
    print("\n  git author identity: python coordinator/gitrepo.py --identity")
