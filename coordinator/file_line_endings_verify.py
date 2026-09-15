#!/usr/bin/env python3
"""
file_line_endings_verify.py — no CR in a file the tree hashes.
(check_line_endings.py until 2026-09-03 — B99 stage 18a, R435's verifier suffix)

    python coordinator/file_line_endings_verify.py
    python coordinator/file_line_endings_verify.py <path> [<path> ...]
    python coordinator/file_line_endings_verify.py --staged
    python coordinator/file_line_endings_verify.py --fix <path> [...]

`.gitattributes` sets `* -text` so that git stores every byte verbatim —
which is what makes sha256 and byte-identical comparison mean anything
here. It also means NOTHING NORMALISES A CR AWAY. A file written with
CRLF stays CRLF, through the commit, into the bundle, and into the
recipient's checks.

WHY THIS EXISTS. On 2026-08-07 three files were converted wholesale to
CRLF by this project's own repair scripts: `pathlib.Path.write_text(...,
encoding="utf-8")` translates `\\n` to `\\r\\n` on Windows unless
`newline=""` is passed. The damage was invisible — every probe passed,
the content was correct — and it buried a ONE-LINE regex fix under 1,193
lines of carriage-return noise. A reviewer reading that diff cannot see
the change.

    the writers in this project pass newline="";
    THE ONES THAT FORGET ARE WHAT THIS CATCHES

--------------------------------------------------------------------------
THE EXEMPTIONS ARE NOT A CONVENIENCE. READ THEM BEFORE ADDING ONE.

Some CRs are LOAD-BEARING. A close report hashes the short_terms of its
circle, and if those bytes are CRLF then the recorded sha256 is the hash
of the CRLF bytes. Converting such a file does not clean it — it BREAKS
A RECORD, which stops verifying against itself.

`line_endings_grandfathered.toml` beside this file is that register, and
it is a data file rather than a list in here for a reason: the paths
belong to one corpus and this checker ships. **An entry must be
MEASURED** — read the sha256 the record claims and confirm it matches the
bytes as they are, not as they would be converted. Exempt BY PATH, never
by a directory or a date: a blanket rule would let the next CRLF
transcript through silently, which is the failure this catches.

--------------------------------------------------------------------------
AND NO NUL BYTE, ADDED 2026-08-25 ON THE OPERATOR'S WORD — after one turned
up in `ui/README.md`, put there by an edit that let Python read `\\x00` as an
escape instead of as the literal text it was meant to be. Git began diffing
that README as BINARY, which is how it was noticed at all; nothing in the
tree had refused it.

    record_verify.py sweeps for NULs, but only across
    parts/, self/, issues/, circles/ and
    work/manifests/ — the DATA. Nothing swept the
    code, the docs or the READMEs.

**AND THE SILENT SKIP WAS THE WORSE HALF.** This scanner treated a NUL in
the first 8,000 bytes as "binary that slipped the suffix list" and skipped
the file — so a NUL did not merely go unreported, it TURNED OFF the CR check
for that file too. A defect that disables its own detector is exactly the
shape this project treats as worse than a loud failure.

There is no `--fix` for a NUL and there should not be: a CR has one correct
repair, and a NUL has none that can be guessed. `\\x00` was meant to be four
characters here and a terminator somewhere else, and only the writer knows
which. A genuinely binary file that lands in scope is answered by adding its
suffix to BINARY_SUFFIX, not by exempting the byte.

EXIT
    0  clean
    1  a CR, or a NUL, in a file that must not have one
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# WHAT MUST BE LF. Scoped deliberately: these are the files this project
# writes, hashes, parses or ships. "prompts/" dropped 2026-08-08: it moved
# to coordinator/prompts/, already covered by "coordinator/", then moved
# again to work/prompts/, R176, 2026-08-15 — now covered by "work/logs/"'s
# sibling addition below instead. "export/" dropped 2026-08-08 — retired
# along with build_export.py; packaging/ is not in scope here (packaging
# assets are not hashed/parsed by this project's own code the way these
# directories are).
# The code half DERIVES from system_lint_verify.CODE_DIRS (stdlib-only sibling,
# same directory — importable even under the hook's bare python): until
# 2026-08-19 this tuple was a fourth hand-copy of the code-directory
# policy and had rotted — memory/ and ui/, where ALL the running code
# now lives, were absent, so a wholesale CRLF rewrite of ui/circling.py
# committed clean (review, tier 3 #26). scripts/ DROPPED 2026-08-19 with
# the directory itself: its last two files, the nightly SKILL prompts,
# were retired out of the tree, so the leg matched nothing.
# "rulings/" ADDED 2026-09-04 (B95): RULINGS.md at the root was in scope by
# suffix; its successor is a directory of .toml files, and the final leg
# below rejects anything with a "/" in it — so a hand-written
# rulings/RNEW-<slug>.toml with CRs would parse as valid TOML, pass the
# RULING shape check, and land with CRs that `* -text` never removes.
import record_paths as _RP                                         # noqa: E402
SCOPE_DIRS = tuple(f"{d}/" for d in _RP.CODE_DIRS) + (
    "docs/", _RP.record_rel("issues") + "/", _RP.record_rel("parts") + "/", "rulings/",
    _RP.record_rel("circles") + "/", "work/logs/", "work/prompts/")
SCOPE_ROOT_SUFFIX = (".md", ".toml", ".py", ".json")
# self/ holds hand-authored .txt beside generated .md and .toml. Only the
# generated kinds are ours to insist on.
SCOPE_SELF_SUFFIX = (".md", ".toml", ".json")

# AND docs/ HOLDS THEM TOO — 2026-08-28, the operator's ruling. The same decision
# self/ already made, applied where the same kind of file turned up: prose
# the operator typed, that nothing hashes and nobody reads as a diff.
#
# THE DISTINCTION THIS ENCODES, because the blanket hid it. Byte-exactness
# is load-bearing for USER DATA and nothing else — measured 2026-08-28:
# close_<OT>.json hashes parts/<p>/short_term_<OT>.toml (.md before R434), mid_term's
# source_hash covers long_term.md, dreams.toml, `[[dreamt]]` / `## Dreamt` and
# remember.toml, prompt_capture covers work/prompts/, and record_model covers
# parts/ and self/. NOTHING hashes a .py, a docs/*.md or a skill file.
# What keeps this check over CODE is a different concern with a different
# value: 2026-08-07, when repair scripts rewrote three files wholesale to
# CRLF and buried a one-line fix under 1,193 lines of diff. Reviewability,
# not provenance.
#
# A hand-authored note is neither. It carries no hash and is never read as
# a diff, so a CR in it costs nothing — and firing on it is how a check
# gets switched off, which the paragraph above already says once.
#
# .md IS NOT HERE, DELIBERATELY. docs/ is mostly the design documents, four
# of which ship; those are the project's own prose and stay in scope.
NOTES_SUFFIX = (".txt",)

# NOT OURS TO CONVERT. Third-party logs, a vendored config, Self's own
# .txt notes, and the art. A check that fires on someone's hand-authored
# notes is a check that gets switched off, and a switched-off check is
# worse than no check.
# "archive/" DROPPED 2026-08-19 with the archiving mechanism (the
# operator's ruling): it was always redundant here — archive/ is not in SCOPE_DIRS,
# so system_line_endings_is_in_scope()'s final leg rejects it for having a "/" in the path, and
# the entry only restated that. Verified by running this check with the
# entry gone; the file count is unchanged.
OUT_OF_SCOPE = ("our_art/", ".fileintel/", ".venv/", ".git/",
                "work/nightly/", "work/circle_audit/", "work/sandbox/",
                # the Ticker flavor's toolchain output (branch
                # Ticker_Research, 2026-08-29): gitignored binary trees
                # that npm install / cargo build create under ui/, which
                # is a SCOPE dir. Mirrors .gitignore's own four entries —
                # a bare sweep in a built tree found 1,042 NUL "offenders"
                # here, all of them someone else's compiled artifacts.
                "ui/ticker/node_modules/", "ui/ticker/dist/",
                "ui/ticker/src-tauri/target/", "ui/ticker/src-tauri/gen/")

REGISTER = pathlib.Path(__file__).resolve().parent \
    / "line_endings_grandfathered.toml"


def _grandfathered() -> dict[str, str]:
    """LOAD-BEARING CRLF — see the docstring. Measured, not assumed.

    An ABSENT or EMPTY register is the normal state, not a fault: a system
    that has never written a CRLF file has nothing to grandfather."""
    if not REGISTER.is_file():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:                      # pragma: no cover
        import tomli as tomllib                      # type: ignore
    doc = tomllib.loads(REGISTER.read_text(encoding="utf-8"))
    return {e["path"]: e for e in doc.get("file", [])}


GRANDFATHERED = _grandfathered()

_GF_CHECKED: tuple[set, list] | None = None


def system_line_endings_grandfather_verify() -> tuple[set, list]:
    """(paths whose exemption VERIFIES, failure lines). Cached per run.

    The register's own rule is that every entry "must have been MEASURED
    — not assumed", but until 2026-08-19 the exemption was path-keyed and
    never re-measured (review, tier 3 #33): a file deleted and recreated
    with fresh CRLF stayed silently exempt, and the Soul directory's
    2026-08-08 rename had already orphaned an entry once. The register now CARRIES
    each measurement (its `sha256` field — added because the close report
    hashes only the seven short_terms, so the transcript entry never had
    a recorded measurement anywhere), and an entry exempts its path only
    while the file's current bytes still hash to it. Every failure mode
    is loud and names its repair: a missing file means fix the path (a
    rename) or delete the entry; a missing or mismatched sha256 means
    the exemption no longer describes the file — it drops back into
    scope (a fresh CR in it FAILs below) until re-measured."""
    global _GF_CHECKED
    if _GF_CHECKED is not None:
        return _GF_CHECKED
    import hashlib
    valid: set = set()
    fails: list = []
    for rel, entry in GRANDFATHERED.items():
        p = ROOT / rel
        if not p.is_file():
            fails.append(f"grandfather entry {rel!r} names no file on disk — "
                         f"a rename orphaned it (fix the path) or the file "
                         f"is gone (delete the entry)")
            continue
        want = entry.get("sha256", "")
        if not want:
            fails.append(f"grandfather entry {rel!r} carries no sha256 — "
                         f"the register's rule is measured, not assumed; "
                         f"add the field (the register header shows how)")
            continue
        got = hashlib.sha256(p.read_bytes()).hexdigest()
        if got != want:
            fails.append(f"grandfather entry {rel!r}: bytes no longer match "
                         f"the recorded measurement ({got[:12]}… != "
                         f"{want[:12]}…) — the file changed since it was "
                         f"grandfathered; delete or re-measure the entry")
            continue
        valid.add(rel)
    _GF_CHECKED = (valid, fails)
    return _GF_CHECKED

BINARY_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".ico",
                 ".xlsx", ".docx", ".pyc", ".db", ".sqlite", ".woff",
                 ".woff2", ".exe", ".dll"}


def system_line_endings_is_in_scope(rel: str) -> bool:
    if rel in GRANDFATHERED and rel in system_line_endings_grandfather_verify()[0]:
        return False        # exempt only while the measurement still holds
    if any(rel.startswith(d) for d in OUT_OF_SCOPE):
        return False
    if rel.startswith(_RP.record_rel("self") + "/"):
        return rel.endswith(SCOPE_SELF_SUFFIX)
    if rel.startswith("docs/") and rel.endswith(NOTES_SUFFIX):
        return False
    if any(rel.startswith(d) for d in SCOPE_DIRS):
        return pathlib.PurePath(rel).suffix not in BINARY_SUFFIX
    return "/" not in rel and rel.endswith(SCOPE_ROOT_SUFFIX)


def system_line_endings_scan(paths=None) -> tuple[list[tuple[str, int, int]], list[tuple[str, int]]]:
    """ONE pass, TWO answers: (CR offenders, NUL offenders).

    CR offenders are `(rel, CRLF count, LF count)`; NUL offenders are
    `(rel, NUL count)`.

    A FILE WITH A NUL IS NOT ALSO REPORTED FOR ITS CRs, and that is not a
    kindness — line counts through a NUL describe nothing anyone can act
    on, and the NUL is the repair that comes first. Before 2026-08-25 such
    a file was skipped ENTIRELY and silently, as presumed binary, which is
    how a NUL in a README also switched off that README's CR check."""
    if paths is None:
        it = (p for p in ROOT.rglob("*") if p.is_file())
    else:
        it = (pathlib.Path(p).resolve() for p in paths)
    crs: list[tuple[str, int, int]] = []
    nuls: list[tuple[str, int]] = []
    for p in it:
        try:
            rel = p.relative_to(ROOT).as_posix()
        except ValueError:
            continue
        if not p.is_file() or not system_line_endings_is_in_scope(rel):
            continue
        b = p.read_bytes()
        if b"\x00" in b:
            nuls.append((rel, b.count(b"\x00")))
            continue
        if b"\r" in b:
            crs.append((rel, b.count(b"\r\n"), b.count(b"\n")))
    return sorted(crs), sorted(nuls)


def system_line_endings_fix(rel_paths) -> int:
    """Byte surgery. NOT a text-mode rewrite — a text-mode write is what
    caused this, and repairing it the same way would reintroduce it."""
    n = 0
    for r in rel_paths:
        p = ROOT / r if not pathlib.Path(r).is_absolute() else pathlib.Path(r)
        b = p.read_bytes()
        fixed = b.replace(b"\r\n", b"\n")
        if fixed != b:
            p.write_bytes(fixed)
            print(f"  fixed  {r}  ({len(b) - len(fixed)} CR removed)")
            n += 1
    return n


def system_line_endings_staged_read() -> list[str]:
    """The paths this commit actually touches, deletions excluded.

    Read here rather than passed by the hook: `-z` avoids every quoting
    question a shell would otherwise have to get right."""
    import subprocess
    p = subprocess.run(["git", "diff", "--cached", "--name-only",
                        "--diff-filter=d", "-z"], cwd=str(ROOT),
                       capture_output=True, timeout=30)
    return [str(ROOT / r) for r in
            p.stdout.decode("utf-8", "replace").split("\0") if r]


def main(argv: list[str]) -> int:
    do_fix = "--fix" in argv
    args = [a for a in argv if not a.startswith("--")]
    if "--staged" in argv:
        args = system_line_endings_staged_read()
        if not args:
            print("  OK    nothing staged")
            return 0
    _, gf_fails = system_line_endings_grandfather_verify()
    for line in gf_fails:
        print(f"  FAIL  {line}")
    bad, nul = system_line_endings_scan(args or None)

    if do_fix:
        if not bad:
            print("  nothing to fix" if not nul else
                  "  nothing to fix — a NUL is not repairable by rule; see "
                  "below")
            return 1 if nul else 0
        system_line_endings_fix([r for r, _, _ in bad])
        bad, nul = system_line_endings_scan(args or None)

    if nul:
        print(f"  FAIL  {len(nul)} file(s) carry a NUL byte, which a text "
              f"file must not:\n")
        for rel, n in nul:
            print(f"    {rel}  ({n} NUL)")
        print("\n  There is no --fix for this, by design: a NUL has no single\n"
              "  correct repair. Find what wrote it — an escape read as an\n"
              "  escape where the literal text was meant is the usual cause —\n"
              "  and repair by byte surgery, never a text-mode rewrite. If the\n"
              "  file is GENUINELY binary, add its suffix to BINARY_SUFFIX in\n"
              "  this file rather than exempting the byte.")

    if bad:
        print(f"  FAIL  {len(bad)} file(s) carry a CR, and `* -text` means "
              f"nothing will\n        remove it for you:\n")
        for rel, crlf, lf in bad:
            how = "wholly CRLF" if crlf == lf else f"{crlf} of {lf} lines"
            print(f"    {rel}  ({how})")
        print("\n  Repair with byte surgery, never a text-mode rewrite:\n"
              "      python coordinator/file_line_endings_verify.py --fix <path>\n"
              "  And find the writer: a `write_text(..., encoding=\"utf-8\")`\n"
              "  with no `newline=\"\"` translates on Windows.")
        return 1

    if nul:
        return 1

    if gf_fails:
        return 1            # a broken exemption fails even a CR-free scan

    scanned = "the tree" if not args else f"{len(args)} path(s)"
    print(f"  OK    no CR and no NUL in {scanned} "
          f"({len(GRANDFATHERED)} file(s) grandfathered, every "
          f"measurement re-verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
