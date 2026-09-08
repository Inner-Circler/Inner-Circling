#!/usr/bin/env python3
"""
record_verify.py — the operational-file corruption gate.
(check_integrity.py until 2026-09-03 — B99 stage 18a, R435's verifier suffix)

WHAT THIS IS
    One sweep over every file this system keeps state in, for the damage classes
    that are invisible to a reader and fatal to a run:

        NUL bytes        the file is binary or truncated; it will not load cleanly
        invalid UTF-8    the same defect, one layer up
        invalid JSON     a manifest that no longer parses
        invalid TOML     a register, a part.toml or an issue node that no longer parses

    plus a truncation guard on the rulebooks — the operations rulebook, the universal
    layer, and EVERY GROUP'S OWN LAYER, discovered from the group descriptors rather
    than named here: each must still carry its own section anchors, because a rulebook
    cut short still looks like a rulebook.

WHY THIS IS A GATE AND NOT A REPORT
    NUL-byte damage is what once silenced a part. The file still had a name, a
    plausible size and a plausible first line; the part simply went dark, and
    nothing downstream could tell corruption from content. That is the whole
    problem: every reader below this point takes the bytes as the truth. The only
    place it can be caught is before a circle is built on them.

    What a corrupted file costs, by where it sits:

      parts/<name>/long_term.md      BLOCK 3 of that part's prompt. mid_term.md is
      parts/<name>/mid_term.md       DERIVED from the record, so damage propagates
                                     into the distillate and into the prompt: the
                                     part runs with a mangled identity, or the API
                                     call fails on the malformed body.
      parts/<name>/part.toml         THE ROSTER. Its presence is what makes a
                                     directory a part (R123). Corrupt it and the
                                     part does not exist for this circle — the
                                     failure is a part silently missing, not an error.
      issues/issue_model.md          circle_briefing_build()'s ONE hard file dependency.
      issues/*.toml                  The graph behind it. Both feed BLOCK 2, which is
      self/best_practices.toml       byte-identical for all seven parts and CACHED —
                                     so one corrupt file poisons every prompt at once
                                     and the cached prefix holds it for the whole
                                     circle rather than for one turn.
      work/manifests/*.json          NOT product runtime data — this repo's own
                                     .claude/skills/workflow dev-tooling writes its
                                     own task manifests here (verified 2026-08-31:
                                     no coordinator/*.py reads or writes this
                                     schema). Real engineering work-logs, still
                                     swept: corruption under work/ should never hide.
      circles/*.md                   The single canonical record. parts_that_spoke()
                                     parses it, and the close report, --reconcile and
                                     the transcript safety net all read it. A part
                                     that spoke can be read as silent, which
                                     dreaming then reads as no-engagement.

    And corruption here does not decay — it SETS. `.gitattributes` is `* -text`, so
    git normalises nothing on the way through, and every sha256 in
    work/logs/close_<OT>.json is computed over whatever bytes were present. Once a
    corrupt file has been hashed into a close report, --reconcile confirms it
    matches its record and reports no drift: the damage has become the record.

WHERE IT RUNS
    coordinator/circle.py    at open, before the API check and before anything is
                             typed or written. A failure returns 2 and the circle is
                             never opened — no transcript, no working-set entry.
    coordinator/circle_audit.py   phase 0.
    bare                     python coordinator/record_verify.py

    There is deliberately NO override flag. "Open anyway" on a corruption finding is
    the act this gate exists to prevent, and the remedy is a git checkout away.

HISTORY
    Extracted 2026-08-18 from scripts/preflight_check.py, the agent-teams-era
    circle-open guard, which had exactly one caller (nightly.py, itself unscheduled)
    and so never ran before a circle. Its agent-definition, team-dir and
    statement_temp checks all died with that runtime and are not carried over; this
    sweep and the rulebook anchors are the part that was never about agent-teams.

    COVERAGE WIDENED in the same move. preflight swept parts/*/*.md, self/*.md,
    work/manifests/*.json and circles/*.md — no .toml at all, and nothing under
    issues/. That left the roster, the whole issue graph and every self/ register
    outside the only sweep of its kind, including issues/issue_model.md, the one
    file circle_briefing_build() cannot proceed without.
"""

from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import NamedTuple

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and arrows this
# project prints. Degrade instead of crashing: a probe that dies formatting its own
# PASS message reports a failure that is not there.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
import record_paths as _RP                                         # noqa: E402
# PROCESS/PROCESS_CORE module constants DELETED 2026-09-01 --
# audit-register.md #30 found them zero-reference: the actual guard
# (below, record_process_verify()) rebuilds both paths inline against a
# parameterized `root`, never these two.

# Rulebook anchors — a TRUNCATION GUARD, not a style rule. Each is a section whose
# absence means the file was cut short. Kept verbatim from preflight_check.py,
# including its 2026-08-07 correction: process_core.md v2026-08-06 renamed "## On
# circle start" to "## What is with you", and the stale anchor made the guard FAIL
# on a correct file and tell the reader not to open a circle. A truncation guard
# that fires on a rename is worse than none, because the one thing it must mean is
# "this file was cut short".
# "## Nightly" is RETIRED content (process.md itself says so) but the
# HEADING stays an anchor on purpose — process.md carries its own matching
# note at that heading (audit-register.md #12) so a future retirement of
# the section does not silently break this guard.
PROCESS_ANCHORS = ["## Orchestration", "## Coordinator constraints",
                   "## Close", "## Nightly"]
CORE_ANCHORS = ["## What is with you", "## Speaking rules", "## After each circle"]
# The IFS layer (R464, B115, 2026-09-07): process_core.md is the universal layer since then, and
# "## The Soul" lives in coordinator/process_ifs.md — the same truncation guard, on that file.
IFS_LAYER_ANCHORS = ["## What you are", "## The Soul", "## Goals"]

# EVERY GROUP'S LAYER, NOT A HARDCODED LIST. The pairs below named process.md, process_core.md and
# process_ifs.md by hand, so coordinator/process_band.md — the band's BLOCK 1 layer since B115
# stage 4 — was guarded by nothing: it is in neither the pairs nor STATE_GLOBS, and truncating it
# passed. A hardcoded tuple would have repeated that for the next group, so the layer set is read
# from each groups/<name>/group.toml's own `layer` field instead.
#
# LAYER_ANCHORS are the sections every layer carries whatever its craft — a cut-short layer loses
# Goals and the honesty mandate first, because they sit at the end. LAYER_ANCHORS_EXTRA adds what
# one layer alone must keep.
LAYER_ANCHORS = ["## What you are", "## Goals", "## The honesty mandate"]
LAYER_ANCHORS_EXTRA = {"coordinator/process_ifs.md": ["## The Soul"]}


def record_group_layers_read(root: Path = ROOT) -> list[tuple[Path, list[str]]]:
    """(layer file, anchors) for every group that declares one. A group whose descriptor is
    unreadable is skipped here rather than reported: _check_one() already judges every
    group.toml as an operational state file, and one defect should be said once."""
    out: list[tuple[Path, list[str]]] = []
    groups = root / "groups"
    if not groups.is_dir():
        return out
    for desc in sorted(groups.glob("*/group.toml")):
        try:
            layer = tomllib.loads(desc.read_text(encoding="utf-8")).get("layer")
        except (OSError, ValueError):
            continue
        if not isinstance(layer, str) or not layer:
            continue
        out.append((root / layer, LAYER_ANCHORS + LAYER_ANCHORS_EXTRA.get(layer, [])))
    # A FLOOR, not a default. A flat tree (a snapshot, a probe's temp tree) has no groups/,
    # and discovering nothing would silently drop the layer check that was unconditional
    # before. Checking the IFS layer when it exists and no descriptor named one keeps the
    # coverage this function replaced.
    if not out:
        ifs = root / "coordinator" / "process_ifs.md"
        if ifs.is_file():
            out.append((ifs, IFS_LAYER_ANCHORS))
    return out

# Every operational state file, by (subdirectory, glob). A directory that is absent
# is skipped rather than reported, so this still runs against a partial or archived
# tree. The rulebooks are covered by record_process_verify() instead, which reads them
# deeper.
STATE_GLOBS = [
    ("parts", "*/*.md"),
    ("parts", "*/*.toml"),
    ("self", "*.md"),
    ("self", "*.toml"),
    ("issues", "*.md"),
    ("issues", "*.toml"),
    ("work/manifests", "*.json"),
    ("circles", "*.md"),
    # circles/ HOLDS THE CIRCLE'S OWN METADATA TOO — R-NEW (2026-09-07): the four registers whose
    # rows are one-per-circle and frozen once written live beside the transcripts they are about.
    # This glob is taught BEFORE any of them moves: a .toml arriving in a directory swept only for
    # *.md leaves the corruption gate silently not reading it, which is the failure this gate exists
    # to make loud.
    ("circles", "*.toml"),
]


class Finding(NamedTuple):
    """One BLOCK-level defect. `path` is repo-relative posix where there is a file."""
    path: str
    defect: str
    remedy: str


def _restore(rel: str) -> str:
    return f"restore it:  git checkout -- {rel}"


def _check_bytes(rel: str, raw: bytes) -> tuple[str | None, Finding | None]:
    """Returns (decoded text, None) if clean, else (None, Finding)."""
    if b"\x00" in raw:
        n = raw.count(0)
        return None, Finding(
            rel, f"{n} NUL byte(s) — the file is corrupted or binary and will not "
                 f"load cleanly", _restore(rel))
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as e:
        return None, Finding(
            rel, f"not valid UTF-8 ({e})",
            _restore(rel) + "  — and check the editor that last wrote it")


def _check_one(p: Path, root: Path) -> Finding | None:
    """NUL / UTF-8 / parse check on a single state file."""
    rel = p.relative_to(root).as_posix()
    try:
        raw = p.read_bytes()
    except OSError as e:
        return Finding(rel, f"cannot be read ({e})",
                       "check file permissions and whether another process holds it open")
    text, bad = _check_bytes(rel, raw)
    if bad is not None:
        return bad
    assert text is not None
    if p.suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            return Finding(rel, f"is not valid JSON ({e})",
                           f"fix the syntax at that position, or {_restore(rel)}")
    elif p.suffix == ".toml":
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as e:
            return Finding(rel, f"is not valid TOML ({e})",
                           f"fix the syntax at that position, or {_restore(rel)}")
    return None


def record_process_verify(root: Path = ROOT) -> list[Finding]:
    """The rulebooks — the operations rulebook, the universal layer, and EVERY GROUP'S OWN
    LAYER: readable, clean, and not cut short. The layers are discovered from the group
    descriptors, so a new group is guarded the day it declares one."""
    out: list[Finding] = []
    pairs = [(root / "coordinator" / "process.md", PROCESS_ANCHORS),
             (root / "coordinator" / "process_core.md", CORE_ANCHORS)]
    pairs += record_group_layers_read(root)
    for path, anchors in pairs:
        rel = path.relative_to(root).as_posix()
        if not path.exists():
            out.append(Finding(rel, "is missing", _restore(rel)))
            continue
        f = _check_one(path, root)
        if f is not None:
            out.append(f)
            continue
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                out.append(Finding(
                    rel, f"has lost its '{anchor}' section — the file was cut short",
                    _restore(rel)))
    return out


def record_lab_tags_read(tags: list[str], is_ancestor) -> list[str]:
    """Which lab-stamped tags have become reachable from master. Pure, so the
    decision can be probed with fabricated inputs.

    `is_ancestor(ref)` answers "is this ref an ancestor of master".
    """
    return [t for t in tags if is_ancestor(t)]


def record_lab_merge_verify(root: Path = ROOT) -> list[Finding]:
    """R249, 2026-08-19: *"Nothing in a lab will be merged back. Travel is only
    main --> lab, never the reverse."* This is the tripwire.

    WHAT IT ACTUALLY TESTS, and why not the obvious thing. The obvious check —
    is `lab` in `git branch --merged master` — IS WRONG HERE AND WOULD FIRE
    TODAY. The lab branch sits at a commit that came from an already-merged
    worktree branch, so it is an ancestor of master while having contributed
    nothing; a checker that cries wolf gets switched off, which is worse than
    no checker.

    Worse, the violation is INVISIBLE in the graph after the fact: once lab
    work lands on master those commits are simply master's, and nothing in the
    shape of the history says where they were authored. The check needs a
    marker for "made in the lab", and B56(5)/R245 built the only one there is —
    a lab tree stamps its refs `<kind>/lab/<OT>`. So: no lab-stamped tag may
    ever be reachable from master.

    ITS LIMIT, stated rather than papered over. This catches lab work that
    carried a TAG — a closed circle, which is the RECORD, and the record is
    what R249 protects. An untagged lab code commit merged to master is
    invisible to it; the prohibition written into .claude/CLAUDE.md is the
    guard for that case, and a rule a person has to remember is exactly what
    this cannot replace.

    The stamping it depends on is pinned by test_inter_circle's own checks —
    not re-tested here, so the two do not drift into disagreeing.

    FAILS OPEN on a git error, matching this file's other checks: it is the
    corruption gate that runs before a circle opens, and a missing git must
    not be the thing that stops one."""
    try:
        import gitrepo as G
        rc, out = G.system_git_run("tag", "-l", "*/lab/*", read_only=True)
        if rc != 0:
            return []
        tags = [t for t in out.split() if t]
        if not tags:
            return []

        def _anc(ref: str) -> bool:
            return G.system_git_run("merge-base", "--is-ancestor", ref, "master",
                         read_only=True)[0] == 0
        hits = record_lab_tags_read(tags, _anc)
    except Exception:
        return []
    return [Finding(
        f"git tag {t}",
        "a LAB-stamped tag is reachable from master — lab work has been "
        "merged back, which R249 forbids in both directions of the record",
        "master must not carry it. Reset master to before the merge, or if "
        "the merge is genuinely wanted, get a ruling that reverses R249 "
        "first — travel is main -> lab only.") for t in hits]


def record_sweep(root: Path = ROOT) -> tuple[list[Finding], int]:
    """Returns (findings, files scanned). Empty findings means the tree is clean."""
    out: list[Finding] = []
    seen = 0
    # A GROUP DESCRIBES ITSELF — R468, B120 (2026-09-07): under the real ROOT, every
    # groups/<name>/group.toml is swept like any register (a parse failure refuses), and a folder
    # under groups/ holding a record but no descriptor is REPORTED — never silently a group.
    if Path(root).resolve() == _RP._REAL_ROOT:
        for g in _RP.group_present_read():
            seen += 1
            f = _check_one(_RP.group_descriptor_locate(g), ROOT)
            if f is not None:
                out.append(f)
        for stray in _RP.group_stray_read():
            out.append(Finding(
                f"groups/{stray}",
                "holds a record but no group.toml — a folder is a group only when its "
                "descriptor is present (R468)",
                "write one (/group-add) or move the folder out of groups/"))
    for subdir, pattern in STATE_GLOBS:
        # a record kind resolves through the group's tree under the real ROOT (B117), flat
        # elsewhere. Under the real ROOT EVERY group's tree is swept (stage 6): a damaged file in
        # groups/band/ is as much a refusal as one in groups/ifs/.
        if subdir in _RP.RECORD_KINDS:
            if Path(root).resolve() == _RP._REAL_ROOT:
                bases = [_RP.group_tree(g) / subdir for g in _RP.group_present_read()]
            else:
                bases = [_RP.record_dir(root, subdir)]
        else:
            bases = [root / subdir]
        for base in bases:
            if not base.is_dir():
                continue
            for p in sorted(base.glob(pattern)):
                if not p.is_file():
                    continue
                seen += 1
                f = _check_one(p, root)
                if f is not None:
                    out.append(f)
    out += record_process_verify(root)
    out += record_lab_merge_verify(root)
    return out, seen


def record_report_lines_render(findings: list[Finding]) -> list[str]:
    """The actionable block a caller prints. One stanza per corrupted file."""
    lines: list[str] = []
    for f in findings:
        lines.append(f"  {f.path}")
        lines.append(f"      {f.defect}")
        lines.append(f"      {f.remedy}")
    return lines


def main() -> int:
    findings, seen = record_sweep()
    rulebooks = 2 + len(record_group_layers_read(ROOT))
    print(f"Integrity: {seen} operational state file(s) + {rulebooks} rulebook(s)")
    if findings:
        print()
        for f in findings:
            print(f"  FAIL  {f.path}")
            print(f"          {f.defect}")
            print(f"          {f.remedy}")
        print(f"\nINTEGRITY FAIL — {len(findings)} corrupted file(s). "
              f"Do NOT open a circle until resolved.")
        return 1
    print("  OK    no NUL bytes, valid UTF-8, every JSON and TOML parses")
    print("\nINTEGRITY PASS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
