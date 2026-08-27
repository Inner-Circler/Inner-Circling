#!/usr/bin/env python3
"""
gitrepo.py — the project's git surface. Shared by circle.py and circle_audit.py.

WHAT IS AUTOMATED, AND WHY THE REST IS NOT

    Everything routine is here and runs from the scripts: init, config,
    .gitignore / .gitattributes upkeep, un-tracking paths that should never have
    been tracked, and committing a run's own output.

    Four things are deliberately NOT automated. Each is a case where a script
    acting on its own could destroy something a human wanted:

    1. REMOTES. Never added by a script, and never one that could take this
       material OFF THIS MACHINE (docs/NIGHTLY_DESIGN.md §6). A committing
       operation refuses if any configured remote fails that test.

       AMENDED 2026-08-10 (R130). The rule was written as "no remote, ever"
       and enforced literally; Self then added a `backup` remote pointing at
       a bare repository on a second physical disk, against disk failure —
       which is what the rule exists to permit, not to stop. The literal
       version silently blocked every circle close for a day. classify_remote()
       now decides by shape and by DRIVE TYPE, and fails closed.

    2. HISTORY REWRITING — filter-repo, rebase, reset --hard, commit --amend.
       Irreversible. If you ever want our_art/ out of the history, that is a
       deliberate, manual, backed-up operation.

    3. ROLLBACK — checkout, revert, restore. Reverting is a judgement about
       whether last night's dreaming was *wrong*, which no invariant can decide.
       The scripts print the exact command and stop.

    4. `git add -A` DURING AN AUTOMATED RUN. A machine commit stages ONLY the
       paths that run produced. Otherwise a nightly at 01:11 would sweep up
       whatever you happened to be editing at midnight and commit it under a
       message about dreaming. commit_paths() takes an explicit list.
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = pathlib.Path(__file__).resolve().parent.parent

# Git identity is CONFIGURATION, never a constant in source. Ruled
# 2026-08-07 after the classification pass found a real name and a real
# email address sitting as argparse defaults in nightly.py — the working
# tree's only PII in executable code, and it would have shipped in any
# export. See docs/configuration.md.
ENV_GIT_NAME = "IFS_GIT_NAME"
ENV_GIT_EMAIL = "IFS_GIT_EMAIL"

# Paths that must never enter history. Anything here is appended to .gitignore by
# ensure_ignore() and un-tracked by untrack_ignored() if already indexed.
REQUIRED_IGNORES = [
    ("# Secrets — never commit", [".env", ".env.*"]),
    ("# Python virtual environment", [".venv/"]),
    ("# Python caches", ["__pycache__/", "*.pyc"]),
    # `work/sandbox/` (coordinator/sandbox/ until R176, 2026-08-15) IS NOT
    # HERE, and removing it was a ruling.
    #
    # .gitignore carries the ruled form instead — `work/sandbox/*`
    # with `!prompts/` and `!circles/` re-included (2026-08-03, path moved
    # 2026-08-15). The directory form defeats those negations outright: git
    # will not re-include anything beneath a directory it has already
    # excluded, so appending `work/sandbox/` silently untracks the two
    # things the earlier ruling kept. `have` never matched it, because the
    # file says `sandbox/*` — so every --git-setup proposed it again.
    #
    # It reached a staged deletion of 21 files on 2026-08-07. Ruled the
    # same day: ALL FILES ARE TRACKED IN THE LOCAL. Nothing under
    # work/sandbox/ ships — the classification omits it — so
    # tracking it costs the bundle nothing.
    # work/nightly/ stays ignored after the 2026-08-19 rename: it is still
    # transaction.py's staging/journal root (shared with inter_circle.py);
    # work/circle_audit/ is the renamed audit's own lock/snapshot home.
    ("# Temp workspaces — staging, caches, locks, snapshots", [
        "work/nightly/", "work/circle_audit/", "work/issue_trial/"]),
    ("# Tool working databases — rewritten constantly, ~11MB each time", [
        ".fileintel/"]),
    # Derived output. Left untracked these show as dirty forever, which is noise in
    # exactly the check meant to catch real uncommitted work. Automated runs never
    # commit them anyway, and git history already records what each run did.
    ("# Run logs — derived, one per run", ["work/logs/nightly*.log",
                                           "work/logs/circle_audit*.log"]),
]

ATTRIBUTES_RULE = "* -text"


class GitError(RuntimeError):
    pass


# READ-ONLY CALLS MUST NOT TAKE THE INDEX LOCK. Ruled 2026-08-10.
#
# `git status` is not read-only on disk: it refreshes the index stat cache and
# WRITES IT BACK, which means creating and renaming `.git/index.lock` on every
# call. Measured — after touching a tracked file, `git status --porcelain`
# moved `.git/index`'s mtime; `git --no-optional-locks status --porcelain`
# did not.
#
# That write is the "optional lock" git names the flag after, and it is a
# create/unlink pair that can fail or be interrupted. A specimen caught during
# the 2026-08-09 analysis: `.git/index.lock`, ZERO BYTES, no git process alive
# — a lock created by a call that died before writing a byte of the new index.
# Nothing in this project needs that refresh; every caller here wants an
# answer, not a faster `git status` next time.
#
# THE FLAG IS A TOP-LEVEL OPTION and must precede the subcommand.
# `git status --no-optional-locks` exits 129: `status` has no such option.
def run(*args: str, check: bool = False, read_only: bool = False) -> tuple[int, str]:
    cmd = ["git"] + (["--no-optional-locks"] if read_only else []) + list(args)
    try:
        # errors="replace": `commit` runs the pre-commit and post-commit hooks
        # as children of git, and their stdout/stderr pass through into git's
        # own — inheriting whatever encoding surprise a hook script's own
        # unreconfigured stdout produces (same cp1252-on-Windows problem as
        # the sys.stdout.reconfigure() above, one process further out). A
        # strict decode there doesn't just mangle `out`, it crashes the
        # reader thread, which silently turns p.stdout/p.stderr into None
        # (Lib/subprocess.py: `stdout = stdout[0] if stdout else None`) —
        # AFTER git has already committed. Degrade instead of crashing.
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=120)
    except OSError as e:
        raise GitError(f"git not available: {e}") from e
    except subprocess.TimeoutExpired as e:
        # TimeoutExpired is not an OSError, so until 2026-08-19 it escaped
        # raw through every caller that treats gitrepo as non-fatal — and
        # the v47+ hook runs enough suites that a `git commit` can honestly
        # exceed 120s on a slow or AV-burdened machine, crashing the whole
        # close instead of reporting. subprocess has already killed git by
        # the time this raises; a stale .git/index.lock may remain, which
        # the message names because the next command will hit it.
        raise GitError(f"git {' '.join(args)} exceeded 120s and was killed "
                       f"— a stale .git/index.lock may be left behind; "
                       f"remove it if the next git command refuses") from e
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    if check and p.returncode != 0:
        raise GitError(f"git {' '.join(args)} -> {p.returncode}: {out}")
    return p.returncode, out


def available() -> bool:
    try:
        return run("--version", read_only=True)[0] == 0
    except GitError:
        return False


def is_repo() -> bool:
    return run("rev-parse", "--git-dir", read_only=True)[0] == 0


def in_main_checkout() -> bool:
    """Is the tree this code is running in the MAIN checkout, or a worktree?

    `.git` is a DIRECTORY in the main checkout and a FILE — the `gitdir: ...`
    pointer — in every worktree. No subprocess, and unlike
    `rev-parse --show-toplevel` it cannot disagree with ROOT depending on the
    cwd a caller happens to have. The run skill's isolation-check has used
    this same test since it was written.

    B56, 2026-08-19. One home for a question three callers were about to
    answer for themselves."""
    return (ROOT / ".git").is_dir()


# The stamp R245 ruled, 2026-08-19: a lab tree's tags are STAMPED as practice,
# never skipped. A lab exists to prove the real thing works, and a lab that
# skips tagging cannot rehearse the close/process path at all — which is the
# path already_processed() lives on and the one most worth rehearsing.
LAB_SEGMENT = "lab"


def tag_name(*parts: str) -> str:
    """The tag this TREE should write. `tag_name("dream", ot)` ->
    `dream/<ot>` in the main checkout, `dream/lab/<ot>` anywhere else.

    THE INVARIANT, and the only thing the spelling has to satisfy: NO TAG
    WRITTEN FROM A LAB TREE MAY EVER BE BYTE-EQUAL TO ONE THE MAIN TREE WOULD
    WRITE. The tag namespace is the one thing a worktree does not isolate —
    files are contained by construction (paths.ROOT derives from __file__),
    refs are not, because `.git` is shared and every worktree reads one
    namespace. already_processed() is the double-dream guard and it reads
    these refs by EXACT name, so an unstamped lab tag would make the MAIN
    tree refuse to process a real circle — a refusal that would not look like
    a lab problem when it happened.

    THE SEGMENT GOES AFTER THE KIND, following `circle/sandbox/<OT>`, which
    this repository already writes for the same reason (so a sandbox commit
    cannot collide with a live `circle/<OT>`). A lab sandbox circle therefore
    reads `circle/lab/sandbox/<OT>`: both stamps, each still legible.

    SELECTING THEM: `git tag -l '*/lab/*'`. Measured 2026-08-19 rather than
    assumed — `git tag -l` globs with fnmatch and NO FNM_PATHNAME, so `*`
    matches `/` too, which is why `circle/*` alone does NOT exclude a lab tag
    and why the guard's exact-name reads are what actually carry the
    isolation.

    THE READER MUST USE THIS TOO, not just the writer. A lab tree that wrote
    `dream/lab/<OT>` but still LOOKED for `dream/<OT>` would never find its
    own marker and would re-dream every run — the guard dead in exactly the
    venue meant to rehearse it."""
    if in_main_checkout():
        return "/".join(parts)
    return "/".join((parts[0], LAB_SEGMENT) + parts[1:])


def toplevel() -> pathlib.Path | None:
    rc, out = run("rev-parse", "--show-toplevel", read_only=True)
    if rc != 0 or not out.strip():
        return None
    return pathlib.Path(out.strip()).resolve()


def assert_isolated(log) -> bool:
    """True if the repository root IS this project folder.

    git commands walk UP the directory tree looking for .git, so if a repository
    were ever created at a parent (D:\\Projects\\.git, or a home-directory
    dotfiles repo), every command here would silently start operating on that
    larger repository instead — mixing this project's history with other
    projects', and putting private material in a repo that might well have a
    remote. Checked before anything that commits."""
    top = toplevel()
    if top is None:
        log("fail", "not inside a git repository")
        return False
    if top != ROOT:
        log("fail", f"the enclosing git repository is {top}, not {ROOT}. This "
                    f"project must be its own repository — a parent repo would "
                    f"mix its history with other projects'. Create one here: "
                    f"git init (in {ROOT})")
        return False
    return True


def remotes() -> list[str]:
    rc, out = run("remote", read_only=True)
    return out.split() if rc == 0 and out.strip() else []


def dirty() -> list[str]:
    rc, out = run("status", "--porcelain", read_only=True)
    return [l for l in out.splitlines() if l.strip()] if rc == 0 else []


def head() -> str:
    rc, out = run("rev-parse", "--short", "HEAD", read_only=True)
    return out if rc == 0 else "(no commits)"


# ---------------------------------------------------------------- setup
def ensure_repo(log) -> bool:
    if is_repo():
        if not assert_isolated(log):
            return False
        log("ok", f"git repository is this folder only (HEAD {head()})")
        return True
    run("init", check=True)
    log("did", f"git init in {ROOT}")
    return assert_isolated(log)


def _load_env() -> None:
    """Best-effort .env load, so IFS_GIT_* work the same way ANTHROPIC_API_KEY
    already does. Absent python-dotenv or an absent .env are both fine — a
    shell-exported variable still resolves."""
    try:
        from dotenv import load_dotenv
    except ModuleNotFoundError:
        return
    load_dotenv(ROOT / ".env")


def _configured(key: str) -> str | None:
    rc, out = run("config", key, read_only=True)
    return out.strip() or None if rc == 0 else None


def resolve_identity(name: str | None = None,
                     email: str | None = None) -> list[tuple[str | None, str]]:
    """Resolve (user.name, user.email) as [(value, source), ...].

    NO FALLBACK CONSTANT, DELIBERATELY. A default identity in source is how a
    real address came to sit in an argparse line for months, and a default
    that names the wrong person is worse than none: it would commit this
    project's history under someone else's name. Unset resolves to None, and
    ensure_config leaves git alone rather than inventing an author.

    Order, most explicit first:

        1  the --git-name / --git-email flag
        2  $IFS_GIT_NAME / $IFS_GIT_EMAIL, shell or .env
        3  git's own user.name / user.email — LOCAL THEN GLOBAL, which is
           git's normal resolution. This is the one that matters: git
           already stores an identity, and keeping a second copy in this
           repository is what created the leak.
        4  unset
    """
    _load_env()
    out: list[tuple[str | None, str]] = []
    for flag, env, key in ((name, ENV_GIT_NAME, "user.name"),
                           (email, ENV_GIT_EMAIL, "user.email")):
        if flag:
            out.append((flag.strip(), "--git-" + key.split(".")[1]))
            continue
        v = os.environ.get(env, "").strip()
        if v:
            out.append((v, "$" + env))
            continue
        v = _configured(key)
        if v:
            out.append((v, "git config " + key))
            continue
        out.append((None, "unset"))
    return out


def ensure_config(log, name: str | None, email: str | None) -> None:
    (name, name_src), (email, email_src) = resolve_identity(name, email)
    for key, src in (("user.name", name_src), ("user.email", email_src)):
        if src == "unset":
            log("warn", f"{key} is not set anywhere — git will refuse to "
                        f"commit. Set ${ENV_GIT_NAME}/${ENV_GIT_EMAIL} in "
                        f".env, or `git config --global {key} ...`. "
                        f"See docs/configuration.md.")

    # core.autocrlf false: line-ending conversion breaks every sha256 and
    # byte-identical check in this project. See .gitattributes.
    for key, want, src in (("core.autocrlf", "false", "required"),
                           ("user.name", name, name_src),
                           ("user.email", email, email_src)):
        if want is None:
            continue
        rc, have = run("config", key, read_only=True)
        if rc == 0 and have.strip() == want:
            continue
        if key.startswith("user.") and rc == 0 and have.strip():
            # AN EXISTING IDENTITY IS NEVER OVERWRITTEN. Rewriting who authors
            # this history is item 2 of the not-automated list at the top of
            # this file. But an explicit request that does nothing must SAY so
            # — silently ignoring a flag is how a person concludes the flag
            # worked.
            if src.startswith(("--git-", "$")):
                log("warn", f"{key} is already {have.strip()} — NOT changed "
                            f"to {want} from {src}. An existing identity is "
                            f"never overwritten; run "
                            f"`git config {key} \"{want}\"` yourself.")
            else:
                log("ok", f"{key} already set to {have.strip()} — left alone")
            continue
        run("config", key, want, check=True)
        log("did", f"git config {key} {want}  (from {src})")


def ensure_attributes(log) -> None:
    p = ROOT / ".gitattributes"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    if any(l.strip() == ATTRIBUTES_RULE for l in text.splitlines()):
        log("ok", f".gitattributes has '{ATTRIBUTES_RULE}'")
        return
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write(f"\n{ATTRIBUTES_RULE}\n")
    log("did", f"appended '{ATTRIBUTES_RULE}' to .gitattributes")


# v55: the archiving mechanism is gone (ruled 2026-08-19) —
# archive_doc.py, part_relationships.py's --migrate/--archive-md, and the
# five dead one-shots that rode along. Only the template's COMMENTS named
# archive/, so no invocation changed; the bump is what installs the
# corrected body, since ensure_hooks() reinstalls on HOOK_MARK alone.
#
# v58: the SHIPPED SURFACE runs packaging/sanitize.py, which refuses on a
# HIGH finding — the owner's name first among them. packaging/package.py
# already refuses at build time (R253), and that alone
# makes shipping the name impossible; this case is what stops it being
# WRITTEN. Without it the tree accumulates quietly and the refusal lands
# on whoever next tries to build — which is exactly how 55 sites reached
# 24 files between 2026-08-09 and 2026-08-19, unnoticed because the only
# tool still looking could not say no.
#
# v59: the two BACKUP HOOKS — see the changelog entry inside the template
# below. IT WAS v58 ON ITS OWN BRANCH: both it and v58 above were cut from
# v57 and both bumped to v58, which git refused to merge. Renumbered here,
# which is the whole cost — HOOK_MARK is a high-water mark, so a skipped
# number is free and only the collision itself had to be noticed.
#
# v60: the SHIPPED SURFACE case calls sanitize.py with --dry-run. That
# case's trigger is *coordinator/*|*memory/*|*packaging/*|*process_core.md*,
# so it fires on nearly every commit — and sanitize.py wrote its report
# unconditionally, which left packaging/sanitize_report.toml modified in the
# working tree after every one of them. The hook only ever wanted the EXIT
# CODE. A generated file was moving for reasons that had nothing to do with
# the commit: line numbers shifting, or __pycache__ appearing because
# somebody had run the code. Ruled 2026-08-19. Regenerating the
# report stays a deliberate act — run sanitize.py with no flag.
#
# v64: A MERGE RECONCILIATION, AND A COLLISION WORTH THE ENTRY. Two
# branches each bumped HOOK_MARK to "v63" for DIFFERENT bodies —
# master's annotation surface (R254/R255) and worktree-b14-obslog-toml's
# self_observation register (R256). git merged the constant clean,
# because both sides made the IDENTICAL edit; that is the silent half of
# the same defect R238/R239 rule for ids, arriving here in the one
# constant whose whole job is to say "the installed hook is out of
# date". The merged TEMPLATE carried both invocation blocks while the
# INSTALLED hook carried only master's, and ensure_hooks() would never
# have replaced it — the mark already matched. So the register's own
# suite would have been triggered and never invoked, which is exactly
# v45's lesson, reached by a new route. v64 is not new checks; it is the
# number that makes the reinstall happen.
#
# THE HOOK VERSION IS NOT AN ALLOCATED ID and takes no placeholder, so
# assign_ids.py cannot help here. The rule that does: after any merge
# that touches this file, compare the template's mark against
# .git/hooks/pre-commit's, and bump if the BODIES differ even when the
# marks agree.
#
# v61: TEN SUITES THAT EXISTED AND RAN GREEN WERE INVOKED BY NOTHING. This
# is the v13/v45/v49 shape the changelog keeps rediscovering one suite at a
# time, and coordinator/tests/test_hook_template.py now checks it as a property
# instead: every suite in the tree is invoked by some case or named in an
# ALLOW list with a reason. It also runs sh -n over this template — editing
# PRE_COMMIT previously ran no shell check at commit time at all — asserts
# every path the hook names exists, and asserts no suite defines main()
# without calling it (ui/tests/circle_test.py had 518 lines of assertions behind
# an uncalled main() for its whole existence). ui/tests/circle_test.py is the one
# ALLOW entry: it runs now, but 16 of its checks are stale against B51(3)
# and R202 and it is wired only once those are realigned.
#
# Also v61: the two `if [ -f <new-name> ]; else <old-name>` legs are gone.
# v52 scoped them to "the merge window ... a v53 may drop it"; the mark is
# nine bumps past that and both old paths have been absent from master for
# a day.
# v68, 2026-08-21 — the lab-findings series (R283 B61, R288 the surface) added two
# probes with their own __main__ and nothing invoked them: test_dispatch_partition.py
# (the Self> loop and dispatch_dev_cmd() can never both hold a verb — the assertion
# B61's own entry said was missing) and test_issue_add.py (/issue-add writes a lead
# through the gate or writes nothing). Both ride the commands.py/circle.py case,
# trigger AND invocation, the same v45 lesson: a probe in a case that never invokes
# it reports nothing.
#
# v69, 2026-08-22 — part_relationships RETIRED (RULINGS.md, after R308):
# coordinator/part_relationships.py is deleted, so its own case entry named a
# path that no longer exists — test_hook_template.py asserts every path the
# hook names exists, so leaving it would have failed that suite, not just gone
# stale quietly. test_register_gate.py stays in the case; it is edited, not
# gone.
#
# v75, 2026-08-23 — Initialization stage 1 (docs/Initialization.md): identity.py
# gained a resolution step (the Soul's preferred_name names the console,
# R325) and prompt_build.identity_tail() renders a part's recorded
# [context] (R331); coordinator/tests/test_identity.py covers both
# and had no trigger — the v45 lesson, a probe nobody invokes reports nothing.
# INSTALLED FROM THE MAIN CHECKOUT AFTER THE MERGE (--git-setup), never from the
# worktree that wrote it.
# v76, 2026-08-23 — Initialization stage 5 (docs/Initialization.md):
# coordinator/part_add.py is the part-lifecycle register (A14's creation
# path) and coordinator/tests/test_part_add.py its probe; the case below
# gives the probe a trigger AND an invocation, the v45 lesson. Installed
# from the main checkout after the merge (--git-setup), never from the
# worktree that wrote it.
HOOK_MARK = "# inner-circling pre-commit v83"
HOOK_FAMILY = "# inner-circling pre-commit v"
PRE_COMMIT = f'''#!/bin/sh
{HOOK_MARK}
# Verifies whatever the commit actually touches. Nothing here depends on a human
# remembering to run a verifier.
#
# v1 covered issues/ only, and CLAUDE.md asked Self to remember
# `nightly.py --selfcheck` for parts/ and self/. That is a memory-based control
# over a failure class INVISIBLE to a reader — a markdown-aware editor silently
# rewriting a file. It damaged parts/mourner/long_term.md on 2026-07-26: 14 of 22
# dream entries unparseable, still reading correctly to a human.
#
# v8 adds the line-ending check and reconciles a DRIFT: the hook on disk and
# this template both called themselves v7 and were different programs — the
# installed one had project_stats and RULINGS.md, this one had six checks it
# lacked. ensure_hooks only ever REPORTED when it found the mark, so editing
# the template changed nothing that ran. It now replaces an out-of-date hook
# of its own family, and still refuses to touch a hook it did not write.
#
# v9 replaces the inline ast.parse with coordinator/check_lint.py. TWO
# reasons, both measured on 2026-08-08. `ast.parse` accepts a misplaced
# `from __future__` import that a real `import` refuses, and three modules
# had been un-importable for weeks while this hook called them clean. And a
# parse says nothing about a name: `m.group(1)` in a scope with no `m`
# parsed fine, shipped green, and killed every circle open for a day.
#
#
# v10 adds test_roster.py on parts/ and on roster.py. R123 moved the part
# list out of shipped code and into parts/<dir>/part.toml, which trades a
# list that could drift from the tree for a tree that can drop a part
# QUIETLY — a marker file missing, unparseable, or carrying a duplicate tag
# shrinks the roster, and an absent part reads downstream as no engagement.
#
# v11 RECONCILES A DRIFT FOUND, NOT MADE, 2026-08-11 — the exact failure v8's
# note above describes, recurring. The INSTALLED hook already called itself
# v10 while its body had been hand-edited past this template: test_roster.py,
# test_check_issues.py, test_working_set.py and the live_probe.py call had
# all been dropped (those four were retired 2026-08-09 and calling them by
# their old path was failing every commit that touched parts/ or
# self/ — a check catching its own absence, not a real problem), but this
# template — the one ensure_hooks() actually installs — still had all four.
# Restoring an equivalent roster-shrink check against the live tree is still
# open; test_roster.py was retired rather than replaced, which is a real
# loss of coverage, not a neutral cleanup.
#
# This version ALSO removes check_better_options.py — self/better_options.toml
# merged into coordinator/best_practices.toml (R133-R137). check_best_practices.py
# now covers the merged content; running the retired script here would fail
# every commit touching self/ or parts/ the moment the file stopped existing —
# the identical failure shape the four scripts above just demonstrated.
#
# v12 adds test_check_best_practices.py and test_practice_annotations.py —
# the PRACTICE LIFECYCLE build (docs/BNF.md): the six in-circle
# proposal annotations, the state="proposed" staging rows they write into
# coordinator/best_practices.toml, and the approve/deny/skip vetting that
# resolves them. Both touch the same file the routing checks above do, so
# they run in the same case block.
#
# v13 FIXES A GAP IN v12's OWN TRIGGER, found the same day: the practice
# case block below fired only on *parts/*, *self/*, or
# *coordinator/best_practices.toml* — the DATA. A commit that edited
# v63, 2026-08-19 (R256): self/self_observation_log.md became
# self/self_observation_log.toml, a real register with its own module and
# its own suite. BOTH ends added, because v45 is the standing lesson here —
# a new module inside a trigger whose case never INVOKES its probe reports
# nothing and looks green. The *self/* glob already caught the data file;
# it never caught coordinator/self_observation_log.py.
#
# v63 AND NOT v62, deliberately. .git/hooks is shared with every worktree,
# and the installed hook already read v62 while master's template read v61
# — an uncommitted bump in the main checkout, on no branch this sweep could
# see. Two templates at v62 with different bodies is the silent case:
# ensure_hooks() reinstalls only when HOOK_MARK DIFFERS, so the tree that
# already says v62 would skip the reinstall and this file's new trigger
# would never install. Skipping a number costs nothing here — HOOK_MARK is
# a version, not a contiguous register — while sharing one costs a trigger
# that reports nothing. If the other v62 lands after this, the two
# templates CONFLICT on this line, which is the outcome to want.
#
# check_best_practices.py, circle.py or self_schema.py — the CODE the
# PRACTICE LIFECYCLE build actually lives in — touched none of those paths
# and the whole block, including its own new tests, silently did not run.
# check_lint.py still caught it (line 413's *coordinator/* case, unchanged)
# but that is compile-and-import only; it would not have caught the
# **Entries: N** tally bug this same build found, which only a real test
# run surfaces. Added to the trigger: check_best_practices.py, circle.py,
# self_schema.py (the practice register's one reader/writer, per its own
# module docstring), and the two new test files themselves — editing a
# test without touching what it tests must not silently stop running it.
#
# v15 (v14 was superseded same-session, before ever being committed) adds
# test_remember.py, test_strip_malformed_markers.py, and test_self_mark.py
# to the SAME case block v13 fixed — all three exercise
# circle.py's annotation system directly (apply_remember/
# apply_self_remember/extract_markers/route_markers/
# strip_malformed_markers/apply_self_mark/record_mark) and the first was
# missing from the trigger for the same reason v13 named: circle.py is
# already in this block's path list, so nothing new needed adding to the
# trigger itself, only the test invocations that should have been there
# already. strip_malformed_markers() is new here too — the bracket-
# annotation half of E06 (work/instrument/LOG.md): an unknown SLASH
# command was already refused and never sent to the room, but a malformed
# ANNOTATION had no equivalent until now, so a typo'd or not-yet-built
# kind (e.g. `[propose concern: ...]` before "concern" is a real propose
# sub-kind) stayed in the transcript as room content every part would
# read. Same day, /mark retired into a SELF-REFERENTIAL [mark ...]
# annotation (ruled: "lose the [n]") — add_mark() is gone.
#
# v16 adds coordinator/concerns.py and coordinator/tests/test_concerns.py to
# BOTH the trigger AND the invocation list — concerns.py was never in
# either, the same v13-shaped gap (code touched, data paths untouched,
# whole block silently skipped) applied to it too, just never caught
# because nothing exercised it. Same day's field convergence
# ("title"->"text", "status"->"state", "raised_by"->"author" — ruled:
# "use common property names insofar as possible... update to converge")
# also touched self/open_concerns.toml, which the *self/* pattern already
# covered — but a commit editing concerns.py ALONE would not have.
#
# v17 adds coordinator/requests.py and coordinator/tests/test_requests.py, same
# reason as v16 — a NEW module (the REQUEST register, PROPOSE-class,
# docs/BNF.md) added to both trigger and invocation from the
# start, rather than shipped once and caught missing later.
#
# v18 adds coordinator/tests/test_convergence_queue.py to the invocation list
# (not the trigger — circle.py, which it tests, is already there). Same
# pre-existing gap as test_remember.py's own v14 fix: this file existed,
# tested real behavior, and was simply never wired in. Caught now because
# this session's vet-loop generalization (request retired from
# unruled_proposals()/convergence_queue(), each gaining its own coalesce/stage
# path — see v17) rewrote a chunk of what it covers.
#
# v19 adds coordinator/mark_proposals.py and coordinator/test_mark_
# proposals.py to both trigger and invocation, same reason as v17 — a
# NEW module, added from the start rather than shipped once and caught
# missing later. [hold] retires into [propose mark] here (ruled: "skip
# references to other statements for now" — self-referential only,
# same constraint that retired /mark's own <n>). CIRCLE-SCOPED, unlike
# practice/request: staged and vetted in the SAME /close, no second
# checkpoint at the next circle's priming — see the module's own
# docstring for why. record_mark() (circle.py) gained an explicit
# `index` parameter in the same change, so an APPROVAL can mark an
# EXISTING statement rather than only ever the next one about to be
# appended.
#
# v20 adds coordinator/relation_proposals.py and coordinator/test_
# relation_proposals.py to both trigger and invocation, same reason as
# v17/v19 — a NEW module, added from the start. #32: a converged
# `[propose nNNNN <type> nMMMM]` gets a staged/vetted register
# alongside the existing show_unruled_proposals()/`/issue-relationship-add` path
# (ADDITIVE, not a replacement — not yet ruled which
# survives). The one propose-class kind whose approval writes the live
# graph — test_relation_proposals.py's own real-gate integration tests
# copy issues/ into a temp dir first and never touch the tracked one,
# so this trigger is about the CODE paths (relation_proposals.py,
# circle.py's graph_now()/_relation_approve()/_relation_deny()), not a
# new issues/-touching case block.
#
# v21 REMOVES coordinator/concerns.py and coordinator/tests/test_concerns.py
# from both trigger and invocation — the OC register (self/open_
# concerns.toml) is retired outright, 2026-08-13, vestigial. Mirror image
# of v16, which added them.
#
# v22 ADDS ui/*.py, found ungated 2026-08-14 while auditing what runs
# `ui/circling.py --selftest`: check_lint.py's own SCOPE was
# `coordinator/` and `scripts/` only, and neither self-test (circling.py
# --selftest, ui/tests/test_circle_engine.py) was invoked anywhere but by hand.
# Same shape as v13's gap, one directory later. ui/*.py joins the
# compile+pyflakes case below, and a new case runs both self-tests —
# test_circle_engine.py needs `anthropic` (it imports circle.py), so
# unlike every other invocation in this hook it is called through
# `.venv/Scripts/python.exe` explicitly rather than bare `python`, which
# check_lint.py's own docstring already measured as the system 3.10 on
# this machine, not the venv.
#
# v23 REMOVES coordinator/marks.py's test (test_marks.py),
# coordinator/mark_proposals.py and its test (test_mark_proposals.py),
# and coordinator/tests/test_self_mark.py from both trigger and invocation —
# MARK, and PROPOSE MARK with it, RETIRED WHOLESALE 2026-08-14
# (docs/BNF.md), code included. Mirror image of v17/v19, which added
# requests.py and mark_proposals.py the same way; same shape as v21's OC
# removal. Found by this same commit's own presweep: the pre-existing
# v22 hook body called all three deleted files directly and would have
# failed every future commit touching circle.py or self/ — a check
# catching its own absence, the identical v8/v11 failure shape, this
# time caught before the commit rather than after.
#
# v51 ROUTES EVERY PROJECT-CODE INVOCATION THROUGH THE VENV — the
# standing rule ("always the venv's python, never the system
# interpreter") this hook violated on some twenty lines while its own
# comments measured bare `python` as the system 3.10, and while four
# blocks had already been rerouted one incident at a time (block-overlap,
# BNF, integrity, ui). The 2026-08-18 review filed it as tier 5 #59;
# every remaining invocation converts in one bump rather than after four
# more incidents. TWO deliberate exceptions keep bare python: the
# unconditional check_line_endings (stdlib-only, and the one check that
# must run even where .venv does not exist yet) and check_lint (stdlib-
# only, and it resolves .venv itself, by its own docstring — that
# self-resolution is the reason bare python was survivable here at all).
# v51 also closes v49's recorded debt: test_help_system.py (claimed by
# v35's comment, invoked by nothing) joins the practice case's pattern
# and body, run green — 77 checks — before wiring.
#
# v50 RETARGETS the lint trigger onto check_lint.CODE_DIRS — memory/ in,
# scripts/ out — and wires coordinator/tests/test_check_lint.py beside the lint
# it guards. The trigger was a hand-copy of the code-directory policy and
# had rotted (the 2026-08-18 review's tier 3 #25): memory/ has held
# running code since R203 while the pattern still named scripts/, empty
# of code since 2026-08-18 — so a commit touching only memory/ ran no
# lint at all (the very NameError class check_lint was built for, in the
# one directory the trigger could not see), while the scripts/ leg
# triggered a linter that does not scan it. The policy now has ONE owner
# (check_lint.CODE_DIRS, stdlib-only and importable from every checker,
# bare-python included); check_line_endings and ruling_sweep derive from
# it, and test_check_lint asserts the agreement — this sh pattern
# included, matched against the template text, since sh can derive
# nothing. That probe existed since the SCOPE legs were written and was
# itself invoked by nothing; it rides its own subject now.
#
# v49 ADDS coordinator/tests/test_vetting.py to the practice/annotation case
# (vetting.py has ridden its trigger since v37 with no suite behind it —
# the v22/v27 gap shape) and RESTORES two invocations this changelog has
# claimed since v36: "test_issue_status_cmd.py and test_issue_commands.py
# ride this case" was written about the TRIGGER when commands.py joined
# it, and no invocation was ever added to the body — a changelog claiming
# coverage the hook does not deliver is the v13 shape wearing a comment.
# All three suites pin the 2026-08-18 review's tier-2 approval-contract
# fixes (review-findings.md #12/#13/#16): the circle-ref normalization
# that lets a relationship proposal actually apply, the status-approval
# bool that keeps a cancelled command from recording as executed, and the
# comment-less ruling round-trip. test_help_system.py is claimed by v35's
# comment the same way and is still not invoked — left for its own bump,
# with a suite run to justify it, rather than smuggled into this one.
#
# v48 ADDS a probe pair for the nightly's transaction/lock machinery and
# wires two suites that existed and were invoked by nothing — the v13
# shape, all four found by the 2026-08-18 whole-tree review
# (review-findings.md), whose tier-1 fixes landed one commit before this.
#
# (1) NEW coordinator/tests/test_transaction.py + coordinator/tests/test_nightly_lock.py,
# narrow-triggered on transaction.py/nightly.py and themselves (the v46
# shape: both build their own temp trees — and rebind nightly.LOCK — so
# they need no other path to have moved and can never race a real
# nightly). The machinery they pin shipped with NO probe at all, and the
# review found four defects in exactly the states nothing exercised:
# journal_rollback could not roll back a created file, verify() compared
# the disk against itself, release_lock() deleted another run's live
# lock, and phase0 pinned may_commit=False. The crash states are reached
# by a scripted os.replace failure — the only way they are reachable.
#
# (2) coordinator/transcript_store.py and coordinator/mid_term.py join the
# practice/annotation case's PATTERN and BODY with their suites.
# transcript_store left circle.py in phase 1 step 3 (2026-08-16) without
# taking a trigger entry along — the per-stage obligation v31 names — so
# a commit touching only it ran check_lint and nothing else; the resume
# leak fixed one commit ago is precisely what that gap left unwatched.
# mid_term.py and test_mid_term.py were never in any trigger either.
# Both suites are invoked through the venv interpreter, like every
# post-v40 addition: proven under it, and never hostage to what bare
# `python` resolves to.
#
# v47 CLOSES B49's TWO TRIGGER GAPS, found by /presweep 2026-08-17, asked
# for 2026-08-18. Both are the v13 failure shape, in its two
# distinct forms — and the second form is the one this changelog keeps
# rediscovering.
#
# (1) TRIGGER ONLY. coordinator/remember.py and coordinator/tests/test_remember.py
# were absent from the practice/annotation trigger PATTERN while the body
# already invoked test_remember.py (added 2026-08-12 beside the E06
# bracket-annotation fix). So the suite ran often, but only ever as a
# PASSENGER — when some other path in that long case matched. A commit
# touching remember.py alone fired check_lint.py and nothing else. That was
# masked on 2026-08-17's D23 commit because circle.py, vetting.py,
# ifs_model.py, parts/ and self/ all match the same case. Masking is not
# coverage, and a part's own private memory register is a poor place to
# learn the difference.
#
# (2) TRIGGER AND INVOCATION BOTH. work/tools/test_bnf_conformance.py was
# in no trigger at all and called from nowhere — the whole v45 defect
# rather than half of it, so both halves land here. It is invoked BEFORE
# bnf_conformance.py in the same case: the probe checks the harness, and a
# broken harness's verdict on docs/BNF.md is not evidence of anything.
# work/tools/ also sits outside check_lint.py's own SCOPE, so nothing
# compiled either file automatically until now.
#
# NOT DONE HERE, deliberately, and recorded so the next presweep does not
# re-report them as new: work/tools/bnf_register_intake.toml is still
# outside this case's pattern, and work/tools/ is still outside
# check_line_endings.py's SCOPE_DIRS. Both are B49's own awareness-only
# footnote; neither was asked for.
#
# v46 ADDS a case for coordinator/tests/test_check_integrity.py, 2026-08-18. The
# corruption gate (coordinator/check_integrity.py) and its probe shipped that
# day covered by NO invocation at all: check_lint.py compiles them under the
# *coordinator/* case, which proves they import, not that the gate still
# refuses anything. That is v45's own defect one file later — a suite present
# and invoked by nothing — and it is exactly the shape this gate exists to
# stop, since a corruption check that has quietly stopped checking reports a
# clean tree either way. Narrow trigger on the two files themselves: the probe
# builds its own temp trees and needs no other path to have moved.
#
# v45 ADDS ui/tests/test_circling.py to the ui/ case's invocation — ruled
# 2026-08-18: "yes, add ui/tests/test_circling.py". The trigger already covered
# it (v22 gated *ui/*, and it lives there), but the case ran only
# --selftest and test_circle_engine.py, so the ONE harness that exercises
# submit_command's whole dispatch contract was hand-run or not run. It was
# not run: R221 (2026-08-17) added command_in, waiting_for_channel and
# speaking_turn to CircleEngine.__init__, test_circling.py builds its
# engine with __new__ and sets every attribute by hand, and the three
# missing ones crashed it with AttributeError on its first cmd> line —
# for a day, silently, while the commit that caused it passed this hook.
# A suite outside the gate reports nothing; that is v13's shape from the
# other side, a file present and covered by no invocation.
#
# --fast (0-0.02s per line rather than 10-20s) because the delay exists to
# let a human watch real interleaving. It rewrites ui/tests/outputs.txt every
# run, which is safe because that record is deterministic — verified by
# running it twice against a clean tree — so an unchanged commit leaves it
# byte-identical, and a commit that genuinely moves dispatch behaviour
# leaves the regenerated file unstaged, which is a report rather than a
# failure.
#
# v44 ADDS coordinator/tests/test_markers.py to trigger and invocation —
# stage_propose_proposals() (and stage_practice_proposals(), retired
# 2026-08-20) had NO probe at
# all until this file: both write self/best_practices.toml and
# self/proposals.toml (staged rows) but only run from inside circle.py's
# own /close handling, which also runs coordinator/circle_close.py and, live,
# a git commit — no end-to-end circle session can safely probe them, so
# this calls both functions directly against a fabricated transcript,
# live=True, with BP/PROPOSALS monkeypatched to scratch files, same
# isolation technique ui/tests/circle_test.py's RegisterIsolation established
# the same day. The gap surfaced while designing that file, not found by
# a presweep — added from the start rather than shipped once and caught
# missing later, the v13 failure shape every other new-module note here
# already names.
#
# v43 FOLLOWS coordinator/relationships.py to
# coordinator/part_relationships.py — B16, 2026-08-17 (R220): "relationship"
# alone is ambiguous between this (part-to-part) and an issue-graph edge,
# same disambiguation family as v42's issue_projection.py neighbor and
# /help issue-relationship (R218/R219). The practice/annotation trigger's
# explicit pattern follows the rename or a commit touching only the
# renamed module silently stops running the suites that cover it — the
# v13 failure shape.
#
# v42 FOLLOWS check_issues.py to memory/issue_projection.py —
# RULED rename (the check_ prefix misdescribed 90% of the file:
# a projection library with a 40-line self-check main() on top).
# The practice case invokes it at its new name.
#
# v41 FOLLOWS the issue-graph code to memory/ (R203 follow-on,
# 2026-08-16): the issues-case now invokes memory/issue_gate.py.
# test_issue_gate.py stays in coordinator/ with every other test.
#
# v40 FIXES THE v38 CHANGELOG ITSELF, found by independent review while
# verifying a commit: v38's note spelled the two-character escape it
# was describing as the raw pair inside this f-string, Python rendered
# a REAL newline there, and the orphaned tail of that comment became an
# executable line opening a stray double-quoted string — swallowed
# prose until the next quote, then ran the accumulation as a bogus
# command (bash warning on stderr at run time, exit still 0, so sh -n
# never saw it; the isolated comment block also tested clean, because
# the defect exists only in the RENDERED hook, never in this source
# file's own text). The note now spells it "backslash-n", and
# _hook_syntax_check gained an EXECUTION layer: with nothing staged,
# the template is run for real and must exit 0 with an empty stderr
# before any install. Two lessons for the price of one escape: a hook
# changelog is inside a template, and a template's source is not its
# rendering.
#
# v39 ADDS coordinator/rounds.py to the practice/annotation trigger
# — phase 2 stage 7, the last extraction (2026-08-16): the turn
# engine out of circle.py. Same per-stage obligation as v31-v37.
#
# v38 IS v37 CORRECTED, never separately shipped with content of its
# own: v37's template edit landed a literal two-character backslash-n inside
# the practice case's pattern (a scripted replace's escaping slip), so
# the INSTALLED v37 hook had an unterminated case line — sh refused it
# at commit time, which is the gate working: the broken hook FAILED the
# commit rather than silently skipping its checks. And because
# ensure_hooks() only reinstalls when HOOK_MARK differs, fixing the
# template alone changed nothing (the v8/v11 drift shape, again) — the
# fix needed this bump to reach .git/hooks. sh -n now gates every
# install below, so a template whose shell cannot parse can never be
# written into .git/hooks again.
#
# v37 ADDS coordinator/vetting.py to the practice/annotation
# trigger — phase 2 stage 4, built sixth (2026-08-16): Self's
# ruling loop + graph_now out of circle.py. Same per-stage
# obligation as v31-v36.
#
# v36 ADDS coordinator/commands.py to the practice/annotation trigger —
# phase 2 stage 6, built fifth (2026-08-16): the ic.py-era dev commands,
# dispatch_dev_cmd and the statements trio out of circle.py;
# test_issue_status_cmd.py and test_issue_commands.py ride this case.
# Same per-stage obligation as v31-v35.
#
# v35 ADDS coordinator/help_system.py to the practice/annotation
# trigger — phase 2 stage 5, built fourth (2026-08-16): /help's whole
# surface out of circle.py; test_help_system.py already rides this
# case. Same per-stage obligation as v31-v34.
#
# v34 ADDS coordinator/markers.py to the practice/annotation trigger —
# phase 2 stage 3 (2026-08-16) moved the whole bracket-annotation
# system (ASK_RE and its grammar, REMEMBER's write path, the malformed
# strip, live routing, close-time coalescing, the staging writers) out
# of circle.py; the annotation suites are exactly what that trigger
# runs. Same per-stage obligation as v31-v33.
#
# v33 ADDS coordinator/prompt_build.py to the block-overlap trigger —
# phase 2 stage 2 (2026-08-16) moved the prompt's construction (the
# identity read-layer, minimal case, build_briefing, the four-block
# assembly, render_messages) out of circle.py, and prompt blocks'
# sources are exactly what that case's checker guards. Also joins the
# practice/annotation trigger: the assembly reads the practice blocks.
#
# v32 ADDS coordinator/llm_client.py to the same trigger — phase 2
# stage 1 (2026-08-16) moved the Messages-API transport (MODEL/rates,
# Meter/METER, call, the retry ladder, key diagnostics, preflight,
# prewarm) out of circle.py; same per-stage obligation as v31.
#
# v31 ADDS coordinator/command_surface.py to the practice/annotation
# trigger — phase 2 stage 0 (2026-08-16) moved COMMANDS/PANE_OF/
# DEV_MIN_CMDS/DEV_CMD_HEADS/ISSUE_NODE_RE/dev_mode out of circle.py
# into it, and code that leaves a trigger's named files must take its
# trigger entry along or a commit touching only the new module silently
# stops running the suites that cover it — the v13 failure shape,
# named in the phase-2 review as a per-stage obligation.
#
# v30 FOLLOWS best_practices.toml from coordinator/ to self/ — Self's
# 2026-08-16 memory/ ruling ("out of coordinator and into self/"),
# reversing the 2026-08-11 move. Three trigger sites: the explicit
# *coordinator/best_practices.toml* alternates in the practice and
# project_stats case blocks are REMOVED rather than repathed — at
# self/best_practices.toml the file is already covered by the *self/*
# alternate each of those blocks carries, and an explicit pattern for a
# path that no longer exists is exactly the stale-trigger drift
# v8/v11/v22 keep finding. The block-overlap case has no *self/*
# alternate, so its entry is REPATHED to *self/best_practices.toml*
# instead. The echo text names the new location.
#
# v29 REPLACES coordinator/requests.py + test_requests.py and
# coordinator/relation_proposals.py + test_relation_proposals.py (v17/v20)
# with coordinator/proposals.py + test_proposals.py, in both trigger and
# invocation — R202, 2026-08-16: "the PROPOSE CLASS, syntax, and code
# subsume every possible future, including 'request'." request and
# relation folded into one PROPOSE marker/register; found by this same
# commit's own presweep — the pre-existing v20/v17 hook body still called
# two now-deleted files directly and would have failed every future
# commit touching circle.py or self/, the identical v23/v8/v11 failure
# shape.
#
# v28 ADDS the phase-2 build (B3, 2026-08-15) to trigger and invocation:
# coordinator/inter_circle.py (the INTER_CIRCLE_PROCESSOR — dreaming/
# synthesis at /close, R167/R168), circle_history.py (the CH- register),
# relationships.py (present since R185 but never a trigger — the v22 gap
# shape, caught here), ifs_model.py (now carries the register gate,
# R188), and their suites test_inter_circle.py + test_register_gate.py.
# Both suites are network-free: canned model outputs, staging-only, live
# registers byte-verified untouched.
#
# v27 REMOVES coordinator/tests/test_check_budget.py from invocation — retired
# 2026-08-15 with check_budget's `relationships` target (ruled: "retire 1
# and 2, successor for 3"); the suite's whole subject was that target, and
# leaving the call would fail every parts/-touching commit on a file that
# no longer exists, the v23/v8/v11 shape again. The LIVE-CITED successor
# lands in the register gate (docs/REGISTER_GATE_DESIGN.md), whose own
# probe suite joins this hook when built. v27 also ADDS
# coordinator/topics.py and coordinator/tests/test_topics.py to trigger and
# invocation — the TOPIC register (R184/R186) shipped in the same session;
# self/topics.toml commits already fired this case via *self/* with no
# suite behind them, the exact gap v22 closed for ui/.
#
# v26 wires work/tools/bnf_conformance.py — built 2026-08-14 specifically to
# catch docs/BNF.md drift and then never triggered by anything, which is the
# defect it exists to prevent, one level up. Found by a pre-commit sweep on
# 2026-08-15, the same day BNF.md gained four productions. Also gates
# .gitignore, whose own history includes a staged deletion of 21 files
# (2026-08-07, recorded in REQUIRED_IGNORES' comment above) with nothing
# checking it.
#
# v25 adds coordinator/check_block_overlap.py and its own probe suite
# (B39/R158): content delivered in a LOWER-numbered, broader prompt block
# must not repeat in a HIGHER-numbered, more specific one. Triggered on
# the block SOURCES as well as the checker itself — process_core.md, the
# practices register, and parts/ all feed system_blocks(), so a repeat can
# be introduced by editing content that never touches the checker. Added
# from the start rather than shipped once and caught missing later.
#
# v24 adds coordinator/check_next_md.py and coordinator/tests/test_check_next_md.py
# to both trigger and invocation, same v17/v19 shape as every other NEW
# module in this hook's history — added from the start rather than shipped
# once and caught missing later. Checks NEXT.md's BUILD QUEUE itself: every
# B-entry leads with a blocker (WAITS ON <id> / UNBLOCKED / BLOCKED ON:),
# and none carries a closure marker (MOOT, / FULLY BUILT) that means it
# should have been cut to progress.md already (R131) — the THIRD time that
# exact drift recurred (B33 2026-08-12, B40/B38/B4 2026-08-14), each time
# only a memory-based caution, never a test, until now.
#
# v59 adds coordinator/tests/test_backup_hooks.py, and the TWO BACKUP HOOKS for it
# to cover. GIT NEVER RUNS post-commit FOR A MERGE — not for a fast-forward,
# which creates no commit, and not for a merge commit, which does. So the
# backup push that has run after every commit since 2026-08-09 never ran
# after a merge, and on 2026-08-19 the backup disk was measured a whole merge
# behind master (74cd966 here, 6343e1f there). CLAUDE.md described this as
# affecting fast-forwards only and called it "the one case the hook cannot
# cover for you", which is why nobody looked: a merge that produced a visible
# commit looked covered. Same shape as v13's gap one hook later — a trigger
# that matches nothing real, discovered only by checking the thing it was
# supposed to protect.
#
# post-commit JOINS THE TEMPLATES in the same change, at v2. It had been
# hand-installed since 2026-08-09 with nothing in this file behind it, and
# that is not incidental to the gap above — ensure_hooks() managed pre-commit
# alone, so the hook nobody could see in the source was the hook nobody
# checked. Both bodies now come from one generator, _backup_push_hook().
#
# THIS WAS v58 ON ITS BRANCH AND COLLIDED. worktree-owner-name-gate took v58
# on master first, for the owner-name sanitize case; both branches had read
# v57 and both bumped to v58, which git cannot merge and did not. Renumbered
# to v59 at the merge — the same failure R238/R239 wrote the RNEW- mechanism
# for, in the one id series that has no placeholder. HOOK_MARK is a
# high-water mark like NEXT.md's, so skipping is safe and only the collision
# has to be noticed.
#
# Local-only repository, so this hook never leaves the machine.
# Bypass deliberately with: git commit --no-verify
set -e
FILES=$(git diff --cached --name-only)

# THE INTERPRETER, RESOLVED — v78, 2026-08-26. `.venv/Scripts/python.exe` was
# written into ~70 lines of this hook, which is this machine's layout: a POSIX
# venv puts it at .venv/bin/python, and a clone that has not made one yet has
# neither. Resolved once, here.
PY=".venv/Scripts/python.exe"
[ -x "$PY" ] || PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

# AND A SCRIPT THIS TREE DOES NOT HAVE IS NOT A FAILURE. The published package
# ships 6 of the 72 scripts named below — the probes and the dev gates are not
# part of the product — so before v78 a recipient who ran `--git-setup` got a
# hook that refused every commit, naming a test file they were never sent. The
# gates they DO have still run, and still fail the commit when they fail.
run() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    "$PY" "$@" || exit 1
}}

# AND THE SAME, FOR A SCRIPT WHOSE OWN OUTPUT IS NOISE. `run X >/dev/null`
# at the call site redirected run() ITSELF, so the note it was about to print
# went with it — one announcement silently absent from the dev tree's own
# hook run, which is how this was caught.
quiet() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    "$PY" "$@" >/dev/null || exit 1
}}

# FIRST, and unconditional. `.gitattributes` sets `* -text`, so a CR that
# reaches a commit is a CR that reaches every sha256 downstream of it —
# nothing normalises it away. Three files were converted wholesale on
# 2026-08-07 and every other check passed.
run coordinator/check_line_endings.py --staged
case "$FILES" in *issues/*)
    NOTE="  pre-commit: issues/ touched"
    run memory/issue_gate.py
    run coordinator/tests/test_issue_gate.py
esac

case "$FILES" in *parts/*|*self/*\
|*coordinator/check_best_practices.py*|*coordinator/circle.py*\
|*coordinator/command_surface.py*|*coordinator/llm_client.py*\
|*coordinator/prompt_build.py*|*coordinator/markers.py*\
|*coordinator/help_system.py*|*coordinator/commands.py*\
|*coordinator/vetting.py*|*coordinator/rounds.py*\
|*coordinator/self_schema.py*|*coordinator/tests/test_check_best_practices.py*\
|*coordinator/tests/test_practice_annotations.py*|*coordinator/proposals.py*\
|*coordinator/tests/test_proposals.py*|*coordinator/topics.py*\
|*coordinator/tests/test_topics.py*|*coordinator/inter_circle.py*\
|*coordinator/tests/test_inter_circle.py*|*coordinator/circle_history.py*\
|*coordinator/self_observation_log.py*\
|*coordinator/tests/test_self_observation_log.py*\
|*coordinator/backfill.py*|*coordinator/tests/test_register_gate.py*\
|*coordinator/ifs_model.py*|*coordinator/tests/test_markers.py*\
|*coordinator/remember.py*|*coordinator/tests/test_remember.py*\
|*coordinator/quote_as_mark.py*|*coordinator/tests/test_quote_as_mark.py*\
|*coordinator/process_core.md*|*coordinator/roster.py*\
|*coordinator/tests/test_annotation_exemplars.py*\
|*coordinator/transcript_store.py*|*coordinator/tests/test_transcript_store.py*\
|*coordinator/mid_term.py*|*coordinator/tests/test_mid_term.py*\
|*coordinator/tests/test_vetting.py*|*coordinator/tests/test_issue_commands.py*\
|*coordinator/tests/test_rounds_display.py*|*coordinator/llm_client.py*\
|*coordinator/token_count.py*|*coordinator/tests/test_token_count.py*\
|*coordinator/tests/test_llm_client.py*\
|*coordinator/tests/test_issue_status_cmd.py*|*coordinator/tests/test_help_system.py*\
|*coordinator/tests/test_dispatch_partition.py*|*coordinator/tests/test_issue_add.py*)
    NOTE="  pre-commit: parts/, self/ (incl. self/best_practices.toml), or its
  implementation (check_best_practices.py/circle.py/self_schema.py/
  proposals.py)
  touched"
    # live_probe.py, test_check_issues.py, test_working_set.py DROPPED —
    # retired 2026-08-09, see the v11 note.
    # v51: EVERY invocation of project code goes through the venv — the
    # standing rule ("never the system interpreter") this hook violated
    # on ~20 lines while its own comments measured bare `python` as the
    # system 3.10. Four blocks had already been rerouted one incident at
    # a time; the rest carried the same exposure (anything importing
    # anthropic, pyflakes, or tomli on 3.10). The two stdlib-only checks
    # DESIGNED for bare python keep it: check_line_endings (must run
    # even where .venv does not exist yet) and check_lint (resolves
    # .venv itself, by its own docstring).
    # v52: nightly.py is renamed circle_audit.py (the 2026-08-19 ruling). The
    # fallback exists ONLY for the merge window, while a live tree may
    # still carry the old name; a v53 may drop it.
    run coordinator/circle_audit.py --selfcheck
    run coordinator/check_best_practices.py
    run coordinator/tests/test_check_best_practices.py
    run coordinator/tests/test_practice_annotations.py
    run coordinator/check_rulings.py
    run memory/issue_projection.py
    run coordinator/tests/test_issue_projection.py
    run coordinator/check_budget.py
    # test_check_budget.py RETIRED 2026-08-15 with the relationships
    # target (v27) — successor probes arrive with the register gate.
    run coordinator/tests/test_topics.py
    run coordinator/tests/test_register_gate.py
    # v62: the SELF_OBSERVATION register (R256). Its own suite,
    # because test_register_gate.py runs on bytes it builds itself and so
    # cannot notice that the 30 migrated records are still whole.
    run coordinator/tests/test_self_observation_log.py
    run coordinator/tests/test_inter_circle.py
    # v56, B54: the transcript safety net. Its detect+repair moved out of
    # circle_audit's phase structure so the LIVE close path could reach it at
    # all, so its probe rides the case its two callers already trigger.
    run coordinator/tests/test_backfill.py
    # test_remember.py/test_strip_malformed_markers.py were missing from
    # this list — both exercise circle.py's annotation system directly
    # (apply_remember/apply_self_remember/extract_markers/route_markers/
    # strip_malformed_markers) and belong exactly where circle.py already
    # triggers this case. Added 2026-08-12 alongside the E06 bracket-
    # annotation fix these two files cover.
    run coordinator/tests/test_remember.py
    # v57: QUOTE-AS-MARK (R155, routed 2026-08-19). NEW MODULE, added to
    # the trigger AND the invocation in the same change — v19's rule, and
    # v45's lesson about the other order (triggered, uninvoked, crashing
    # unnoticed for a day). It rides this case because its subjects are
    # already here: circle.py's Self> loop calls it, and it writes
    # through remember.py, whose cap it changed.
    run coordinator/tests/test_quote_as_mark.py
    # v63: the ANNOTATION SURFACE (R254/R255). process_core.md and
    # roster.py join THIS case because they are what the parts are
    # actually taught. Both were already triggered elsewhere — v45's
    # block-overlap case and the owner-name sweep for process_core.md, the
    # roster case for roster.py — but by nothing that reads the GRAMMAR,
    # so a change rewriting every part's annotation instructions ran no
    # probe that could tell whether the forms still parsed. The suite
    # parses process_core.md's OWN exemplars through the real grammar, so
    # the taught form and the parsed form cannot drift apart: that
    # divergence is E09's shape, and it very nearly recurred the hour
    # R254 was built. Added to trigger AND invocation together — v19's
    # rule, and v45's lesson about the other order.
    run coordinator/tests/test_annotation_exemplars.py
    run coordinator/tests/test_strip_malformed_markers.py
    run coordinator/tests/test_convergence_queue.py
    run coordinator/tests/test_proposals.py
    run coordinator/tests/test_markers.py
    # v66: the room/record split in rounds.py — see the v66 note above.
    run coordinator/tests/test_rounds_display.py
    # v66: Self's retry ladder over the transport — see the v66 note above.
    run coordinator/tests/test_llm_client.py
    # v67: the counter that replaced chars//4 — see the v67 note above.
    run coordinator/tests/test_token_count.py
    # v48: the resume parser's room/record split and the mid_term lock
    # toggle; v49: the vetting approval contracts and the two suites
    # v36's comment always claimed here.
    run coordinator/tests/test_transcript_store.py
    run coordinator/tests/test_mid_term.py
    run coordinator/tests/test_vetting.py
    run coordinator/tests/test_issue_commands.py
    run coordinator/tests/test_issue_status_cmd.py
    # v51 closes v49's recorded debt: test_help_system was claimed by
    # v35's comment and invoked by nothing — 77 checks, run green before
    # wiring, riding the case its subject (help_system.py) already
    # triggers.
    run coordinator/tests/test_help_system.py
    # v68: the two probes the 2026-08-21 series added (see HOOK_MARK's note).
    run coordinator/tests/test_dispatch_partition.py
    run coordinator/tests/test_issue_add.py
esac

# v67 ADDS coordinator/token_count.py + coordinator/tests/test_token_count.py to
# the practice/annotation case, trigger AND invocation together. R260,
# 2026-08-20: every token figure this project printed was `len(text) // 4`,
# which runs ~30% under what is billed for this corpus, and the module that
# replaced it differences CUMULATIVE PREFIXES to get per-block numbers. That
# subtraction is exact only because `system` is a list of separately-tokenized
# blocks — an edit that concatenated them first would still "work" and be
# quietly wrong, which is precisely the kind of thing a probe has to hold.
#
# v66 ADDS coordinator/tests/test_rounds_display.py AND coordinator/llm_client.py
# + coordinator/tests/test_llm_client.py to the practice/annotation
# case, TRIGGER AND INVOCATION TOGETHER — v19's rule, and v45's lesson about
# the other order (triggered, uninvoked, crashing unnoticed for a day).
# rounds.py has ridden this case since v39; what it had no probe for was the
# line where the ROOM and the RECORD part company. Two 2026-08-20 rulings now
# pull in opposite directions there -- the trailing `[pass]` sign-off is
# dropped from BOTH, the whitespace-only lines from the ROOM ONLY -- and
# getting them the wrong way round is silent: nothing re-reads a transcript
# during a circle, so a record that had quietly started losing blank lines
# would surface as a close report that will not reproduce, months later.
#
# THE TRANSPORT JOINS THE SAME CASE. llm_client.py had NO trigger beyond the
# repo-wide lint sweep and no probe at all, while being the one module every
# statement and every short_term passes through. Its new suite pins Self's
# retry ladder -- which, until 2026-08-20, covered the two calls made BEFORE a
# circle exists and none of the calls made once there is a record to lose.
# test_hook_template.py caught the stray suite within the hour, which is the
# whole reason that check exists.
#
# v65, RULED 2026-08-20: the project_stats case block is GONE. It ran
# `project_stats.py --check` on *issues/*|*self/*|*parts/*|*circles/*|
# *RULINGS.md* — which is precisely the set a circle's own /close commits,
# so the close created the count drift it was then refused for, and no live
# close has committed cleanly since the gate was added. The file it guarded
# (project_stats.md) is deleted; the tool stays and prints on demand.
# Removed rather than repathed: there is nothing left to point it at.

# v72, R-NEW 2026-08-23: `work/pending/` joins this trigger. A branch's ruling
# and progress note live THERE now, not at the two ledgers' tails, so a commit
# that adds one must reach the checker that validates it -- otherwise the
# first reading of a malformed pending entry is the merge, which is the one
# moment no hook fires and the reader is not its author. progress.md is here
# for the branch-write refusal, which is the other half of the same rule.
case "$FILES" in *RULINGS.md*|*progress.md*|*work/pending/*\
|*coordinator/check_rulings.py*|*coordinator/tests/test_check_rulings.py*)
    NOTE="  pre-commit: RULINGS.md, progress.md, or a pending entry touched"
    run coordinator/check_rulings.py
    run coordinator/tests/test_check_rulings.py
esac

# v53, B55: the assign step is the one place ids change, and it runs at a
# `git merge` -- which fires NO pre-commit hook. Nothing here can guard the
# assignment itself; what it CAN do is keep the script and its probe honest
# on the way in.
case "$FILES" in *coordinator/assign_ids.py*|*coordinator/tests/test_assign_ids.py*)
    NOTE="  pre-commit: the id assign step touched"
    run coordinator/tests/test_assign_ids.py
esac

case "$FILES" in *NEXT.md*|*coordinator/check_next_md.py*\
|*coordinator/tests/test_check_next_md.py*)
    NOTE="  pre-commit: NEXT.md or its checker touched"
    run coordinator/check_next_md.py
    run coordinator/tests/test_check_next_md.py
esac

case "$FILES" in *coordinator/check_block_overlap.py*|*coordinator/tests/test_check_block_overlap.py*|*coordinator/process_core.md*|*coordinator/prompt_build.py*|*self/best_practices.toml*|*parts/*)
    NOTE="  pre-commit: a prompt block source or its overlap checker touched"
    # Through the venv, not bare `python`: this checker imports circle.py,
    # which imports anthropic, and the hook's `python` is the system 3.10
    # (measured in check_lint.py's docstring). Same reason ui/ is called
    # this way below.
    run coordinator/check_block_overlap.py
    run coordinator/tests/test_check_block_overlap.py
esac

case "$FILES" in *docs/BNF.md*|*work/tools/bnf_conformance.py*|*work/tools/bnf_known_gaps.toml*|*work/tools/test_bnf_conformance.py*|*work/graph/prompt_grammar_draw.py*)
    NOTE="  pre-commit: docs/BNF.md or its conformance harness touched"
    # The harness's own probe runs FIRST (v47): a broken harness's verdict
    # on docs/BNF.md is not evidence, so checking it before trusting it is
    # the only order that means anything.
    run work/tools/test_bnf_conformance.py
    run work/tools/bnf_conformance.py
esac

case "$FILES" in *coordinator/dream_history.py*|*coordinator/tests/test_dream_history.py*)
    NOTE="  pre-commit: DREAM_HISTORY touched"
    # R359/B45 — the one writer of Self's history records; its suite proves
    # the bootstrap-once/fold-per-dream contract and that refusals write
    # nothing.
    run coordinator/tests/test_dream_history.py
esac

case "$FILES" in *coordinator/coalesce.py*|*coordinator/tests/test_coalesce.py*)
    NOTE="  pre-commit: the proposal coalesce touched"
    # test_coalesce runs the module selftest itself, then the write path,
    # hash guard and ruled-group survival; test_vetting covers the loop the
    # coalesce presents into. R356/B69, and E22 for why the model call
    # lives at circle.py's checkpoints rather than in the loop these
    # suites drive.
    run coordinator/tests/test_coalesce.py
    run coordinator/tests/test_vetting.py
esac

case "$FILES" in *work/tools/memory_probe.py*|*work/tools/test_memory_probe.py*)
    NOTE="  pre-commit: the B68 probe harness touched"
    # The suite is the tool's LAB GUARD (every mutating verb refuses off the
    # lab branch); a probe tool whose guard quietly stopped guarding could
    # seed a record or open a live circle in the main tree. R351/R354.
    run work/tools/test_memory_probe.py
esac

case "$FILES" in *.gitignore*)
    echo "  pre-commit: .gitignore touched — sandbox re-negations are load-bearing"
    if git check-ignore -q work/sandbox/circles; then
        echo "  FAIL: work/sandbox/circles/ is ignored — the ruled negations"
        echo "        (!work/sandbox/circles/, !work/sandbox/prompts/) are broken."
        echo "        A directory-form ignore defeats them; see gitrepo.py."
        exit 1
    fi
    echo "    ok: work/sandbox/circles/ still tracked"
esac

case "$FILES" in *prompts/*)
    NOTE="  pre-commit: prompts/ touched"
    run coordinator/prompt_capture.py --verify
esac

case "$FILES" in *coordinator/*|*memory/*|*ui/*|*packaging/*|*.claude/skills/*|*work/graph/*)
    NOTE="  pre-commit: code touched — compiling and linting every module"
    # v54, B57(3): .claude/skills/ joins the TRIGGER because it joined
    # check_lint's SCOPE — the run skill's driver.py is 850 lines that open
    # a real circle and was linted only by a human remembering to. It is a
    # SCOPE leg, not a CODE_DIR: CODE_DIRS also drives
    # check_line_endings.SCOPE_DIRS, and .claude/ is CRLF by convention.
    # test_check_lint asserts this pattern against CODE_DIRS + EXTRA_LEGS.
    # v50: the pattern IS check_lint.CODE_DIRS — memory/ joined (it held
    # running code since R203 with no lint trigger at all, so an
    # undefined name there committed clean) and scripts/ left (no code
    # since 2026-08-18; check_lint's own SCOPE dropped it then, and a
    # trigger for a directory the linter does not scan is a dead leg).
    # test_check_lint asserts this pattern and CODE_DIRS stay one thing.
    run coordinator/check_lint.py
    run coordinator/tests/test_check_lint.py
esac

case "$FILES" in *coordinator/check_line_endings.py*\
|*coordinator/tests/test_check_line_endings.py*)
    # v77, 2026-08-25. The CR/NUL gate runs on every commit (the
    # unconditional line at the top), but nothing ran the probe that proves
    # it still REFUSES — and the NUL half was added the day a NUL sat in a
    # committed README with every gate green. A checker whose own probe is
    # never invoked is the v45 shape: triggered and uninvoked reports
    # nothing.
    NOTE="  pre-commit: the CR/NUL gate touched — asserting it still refuses"
    run coordinator/tests/test_check_line_endings.py
esac

case "$FILES" in *coordinator/gitrepo.py*|*coordinator/tests/test_backup_hooks.py*)
    NOTE="  pre-commit: the hook templates touched — asserting the backup hooks
  still install on the path that actually runs"
    run coordinator/tests/test_backup_hooks.py
esac

# v70, 2026-08-23, ruled (R312/R313). THREE THINGS NOTHING GATED.
#
# (a) THE TWO OPEN-TIME REPORTS. circle.py grew two detectors for failures
#     that used to be announced once and then never again: a close that died
#     before ANY short_term (settled by the start-of-close marker) and a
#     circle whose dreaming failed (settled by the dream/<OT> tag). Both are
#     read-only path logic with fixtures, so they cost a fraction of a second
#     and they ride circle.py itself — the file whose edit can break them.
#
# (b) work/graph/*.py WAS GATED BY NOTHING AT ALL. No case matched it and
#     check_lint's CODE_DIRS did not include it, so the script that REFUSES
#     to draw a wrong picture was the one file nothing checked. It is in the
#     lint trigger above now (as an EXTRA_LEG, not a CODE_DIR — see
#     check_lint's own note on why), and its probe runs here.
#
# (c) THE DIAGRAMS GO STALE SILENTLY, and redrawing them costs about fifteen
#     seconds — almost all of it crossing minimisation — which is why nobody
#     wanted it on every commit. --check parses and fingerprints instead, in
#     well under a second, so the expensive half runs ONLY when the module
#     graph actually moved. RULED to regenerate rather than refuse: "tell me
#     and regen", so this stages the six artifacts and lets the commit
#     proceed. It is the one case here that writes, and it writes only paths
#     it generated — never `git add -A`.
case "$FILES" in *coordinator/circle.py*|*coordinator/tests/test_close_marker.py*)
    NOTE="  pre-commit: circle.py's open-time failure reports touched"
    run coordinator/tests/test_close_marker.py
esac

case "$FILES" in *work/graph/coordinator_draw.py*|*work/graph/test_coordinator_draw.py*)
    NOTE="  pre-commit: the module diagram's derivations touched"
    run work/graph/test_coordinator_draw.py
esac

case "$FILES" in *coordinator/*.py*|*memory/*.py*)
    NOTE=""
    if [ ! -f work/graph/coordinator_draw.py ]; then
        :                    # not shipped in this tree
    elif "$PY" work/graph/coordinator_draw.py --check 2>/dev/null; then
        :
    else
        echo "  pre-commit: the module graph CHANGED — redrawing the diagrams"
        quiet work/graph/coordinator_draw.py --dump
        quiet work/graph/coordinator_draw.py --live --dump
        git add work/graph/coordinator_graph.svg work/graph/coordinator_graph.html                 work/graph/coordinator_graph.toml work/graph/coordinator_graph_live.svg                 work/graph/coordinator_graph_live.html work/graph/coordinator_graph_live.toml || exit 1
        echo "  pre-commit: six diagram artifacts regenerated and staged"
    fi
esac

case "$FILES" in *coordinator/check_integrity.py*|*coordinator/tests/test_check_integrity.py*)
    NOTE="  pre-commit: the corruption gate touched — asserting it still refuses"
    run coordinator/tests/test_check_integrity.py
esac

case "$FILES" in *coordinator/*|*memory/*|*packaging/*|*process_core.md*)
    NOTE="  pre-commit: shipped surface touched — the owner's name may not enter it"
    quiet packaging/sanitize.py --dry-run
esac

case "$FILES" in *packaging/package.py*|*packaging/test_package.py*|*packaging/sanitize.py*)
    NOTE="  pre-commit: the build's owner-name refusal touched — asserting it still refuses"
    run packaging/test_package.py
esac

case "$FILES" in *coordinator/transaction.py*|*coordinator/circle_audit.py*\
|*coordinator/tests/test_transaction.py*|*coordinator/tests/test_circle_audit_lock.py*)
    NOTE="  pre-commit: the audit's transaction/lock machinery touched"
    # v48. Both probes build their own temp trees (transaction's crash
    # states via a scripted os.replace failure, the lock cases against a
    # rebound circle_audit.LOCK) — nothing here reads or writes work/nightly
    # or the live registers, so this can never race a real run.
    # v52 merge-window fallback, same shape as the --selfcheck one above.
    run coordinator/tests/test_transaction.py
    run coordinator/tests/test_circle_audit_lock.py
esac

case "$FILES" in *ui/*)
    NOTE="  pre-commit: ui/ touched — running its self-tests"
    # circling.py's own --selftest needs no real import beyond circle.py
    # itself, but test_circle_engine.py runs a REAL dry-run CircleEngine
    # session (it imports circle.py, which imports anthropic) — bare
    # `python` here is the system 3.10, not the venv (measured in
    # check_lint.py's own docstring), so all three are called through the
    # venv explicitly rather than relying on what `python` happens to
    # resolve to on this machine.
    #
    # test_circling.py takes --fast (0-0.02s per line instead of 10-20s):
    # the delay exists to make a human watch real interleaving, and tests
    # nothing a commit gate needs. It REWRITES ui/tests/outputs.txt every run,
    # which is safe here because the record is deterministic — same
    # inputs.txt and same dispatch behaviour, byte-identical file, verified
    # 2026-08-18 by running it twice against a clean tree. If a commit DOES
    # change dispatch behaviour, this leaves the regenerated outputs.txt
    # unstaged afterwards; that is the harness reporting what moved, not a
    # failure.
    run ui/circling.py --selftest
    run ui/tests/test_circle_engine.py
    run ui/tests/test_circling.py --fast
esac

case "$FILES" in *parts/*|*coordinator/roster.py*|*coordinator/tests/test_roster.py*)
    NOTE="  pre-commit: the roster is read from the tree, so the tree can lie"
    # v61. The lament that stood here since v11 — "UNCOVERED again until this
    # gets a replacement" — is answered. The replacement shipped 2026-08-17 as
    # B34 and passed from the day it landed; it was simply never wired. A
    # missing or malformed part.toml shrinks the roster, and a part outside
    # the roster is ABSENT from the circle rather than faulty — downstream,
    # indistinguishable from a part present and silent.
    #
    # circle_audit.py --selfcheck rides the parts/ case above and LOOKS like
    # this gate. It is ifs_model.selfcheck_tree: register schemas, line
    # endings, long_term.md dream entries. It never calls roster.verify().
    run coordinator/tests/test_roster.py
esac

case "$FILES" in *coordinator/identity.py*|*coordinator/tests/test_identity.py*|*coordinator/prompt_build.py*|*parts/*)
    NOTE="  pre-commit: who Self is, or what a part's recorded context renders to"
    # v75. identity.user_name() resolves the Soul's preferred_name first
    # (R325) and prompt_build.identity_tail() renders [context]
    # answers through their render strings and through nothing else
    # (R329). Both are one probe; a parts/ edit can
    # change what either reads.
    run coordinator/tests/test_identity.py
esac

case "$FILES" in *coordinator/part_add.py*|*coordinator/tests/test_part_add.py*)
    NOTE="  pre-commit: the part-lifecycle register touched"
    # v76. Create/list/view/delete of a parts/ directory — every case runs
    # against a temp tree; a regression here is a part silently absent from
    # the circle, which downstream reads as chosen silence.
    run coordinator/tests/test_part_add.py
esac

case "$FILES" in *coordinator/initialization.py*|*coordinator/initialization.toml*|*coordinator/tests/test_initialization.py*|*parts/*)
    NOTE="  pre-commit: the first-run dialogs, their validator, their verb"
    # v75 too (same uninstalled mark; both cases land together).
    # PART_CONTEXT_DIALOG and /part-context-update: the ruled validator
    # (data_type/data_max/unique_in, empty always valid, echo-and-loop on
    # invalid), the statements-once flag, prefill semantics (Enter keeps,
    # `-` clears), and the dispatcher wiring. A parts/ edit can change what
    # the dialog asks.
    run coordinator/tests/test_initialization.py
esac

case "$FILES" in *coordinator/gitrepo.py*|*coordinator/tests/test_gitrepo_unstage.py*|*coordinator/tests/test_remote_classify.py*|*coordinator/tests/test_hook_template.py*)
    NOTE="  pre-commit: the hook's own module touched"
    # v61. Until now editing PRE_COMMIT ran no shell check at commit time:
    # *coordinator/* fires check_lint, which compiles the PYTHON and cannot
    # see the rendered SHELL. _hook_syntax_check() existed and was called by
    # nothing but --git-setup. That is the v37/v38 incident's own shape.
    run coordinator/tests/test_hook_template.py
    run coordinator/tests/test_gitrepo_unstage.py
    run coordinator/tests/test_remote_classify.py
esac

case "$FILES" in *coordinator/write_guard.py*|*coordinator/tests/test_write_guard.py*|*coordinator/circle_state.py*|*coordinator/tests/test_circle_state.py*|*coordinator/circle_close.py*|*coordinator/tests/test_circle_close.py*|*coordinator/transcript_store.py*)
    NOTE="  pre-commit: a record-safety module touched"
    # v61. Three modules that decide whether the record survives, none of
    # which had a suite before 2026-08-19: the write guard (nothing imported
    # it at all), the open-circle guard (E12's subject), and the close
    # verifier (whose exit code decides whether a close reports clean).
    run coordinator/tests/test_write_guard.py
    run coordinator/tests/test_circle_state.py
    run coordinator/tests/test_circle_close.py
esac

case "$FILES" in *coordinator/self_schema.py*|*coordinator/tests/test_self_schema.py*)
    NOTE=""
    run coordinator/tests/test_self_schema.py
esac

case "$FILES" in *coordinator/command_surface.py*|*coordinator/tests/test_dev_mode.py*)
    NOTE=""
    run coordinator/tests/test_dev_mode.py
esac

case "$FILES" in *coordinator/live_probe.py*|*coordinator/tests/test_live_probe.py*)
    NOTE=""
    run coordinator/tests/test_live_probe.py
esac

case "$FILES" in *coordinator/prompt_capture.py*|*coordinator/tests/test_prompt_capture.py*)
    NOTE=""
    run coordinator/tests/test_prompt_capture.py
esac
'''


# THE TWO BACKUP-PUSH HOOKS — post-commit and post-merge.
#
# ONE GENERATOR, TWO HOOKS, ON PURPOSE. They do the identical thing and differ
# only in when git calls them and what they call themselves in a warning. Two
# hand-maintained copies of the same shell is the shape this file has been
# bitten by four times at the pre-commit template alone (v8, v11, v22, v38 all
# reconcile the same drift), and here it would be worse: the two hooks are the
# disk-failure safeguard, so a divergence between them is silent by
# construction — nothing reads a backup until something has already been lost.
#
# WHY post-merge EXISTS AT ALL. `post-commit` pushed to `backup` after every
# commit from 2026-08-09, and everyone read that as "the backup keeps up by
# itself". It does not: **git never runs `post-commit` for a merge.** It runs
# `post-merge`, and there was no `post-merge` hook, so the backup disk learned
# nothing from any merge.
#
# MEASURED, not reasoned. On 2026-08-19 master was at 74cd966 while
# `git ls-remote backup master` returned 6343e1f — one merge behind, missing a
# whole branch's work. Found by checking the backup after a merge rather than
# by reading a file that claimed it was covered.
#
# CLAUDE.md HAD THE GAP HALF-RIGHT AND THAT WAS THE TRAP. It said a
# fast-forward "creates NO COMMIT, so the post-commit hook never fires" and
# called that "the one case the hook cannot cover for you". Both halves
# mislead: it is not one case, and the reason is not the absence of a commit.
# A merge COMMIT does not fire post-commit either. A reader who merged and saw
# a commit appear had every reason to think the safety net had run.
#
# post-merge COVERS BOTH MERGE SHAPES — git runs it after any successful
# merge, fast-forward and merge-commit alike. (Its one argument is 1 for a
# squash merge, 0 otherwise; we push either way, so it is not read.)
#
# THE TWO PUSHES, and why they are two. `--all` pushes BRANCHES ONLY —
# measured 2026-08-10, when the backup held 10 local tags' worth of nothing:
# 0 of them, including all 7 `circle/<OT>` tags, the per-circle provenance
# markers this backup exists to protect. Git refuses `--all --tags` in one
# command, so it is two. NOT `--mirror`: a mirror propagates a local deletion
# to the backup disk, which is the one thing a disk-failure safeguard must
# never do. These two are additive — a ref deleted here survives there.
def _backup_push_hook(kind: str, mark: str, when: str, prelude: str = "") -> str:
    """The body both backup-push hooks share. `kind` is the git hook name,
    used for the warning prefix; `when` completes "…after every <when>".

    `prelude` is shell that runs BEFORE the backup push, and exists so
    post-merge can carry the ledger fold without this becoming two
    generators. THAT PROPERTY IS LOAD-BEARING: these two hooks ARE the
    disk-failure safeguard, and a divergence between them is silent by
    construction, because nothing reads a backup until something has already
    been lost. Composing keeps one body; forking would not.

    ORDER MATTERS, and only one way round works. The fold makes a COMMIT, and
    a commit fires post-commit, which pushes to backup. Running the fold first
    therefore gets the fold onto the backup disk by way of its own hook; the
    push below then carries the merge itself. Reversed, the fold's commit
    would sit unpushed until the next commit happened to come along."""
    return f'''#!/bin/sh
{mark}
{prelude}
# Pushes every branch and tag to the local `backup` remote after every {when}.
# `backup` was added 2026-08-09 pointing at a bare repo on a different
# physical drive (C:/GitBackups/InnerCircling), so a disk failure on the
# working copy does not also take the history with it.
#
# THIS HOOK AND ITS TWIN ARE GENERATED FROM ONE FUNCTION in
# coordinator/gitrepo.py — _backup_push_hook(). Editing this file changes
# nothing that survives the next `--git-setup`; edit the generator.
#
# GIT RUNS post-commit FOR A COMMIT AND post-merge FOR A MERGE, and never
# one for the other — not even for a merge commit, which looks like a
# commit and is not one to a hook. Both are needed; neither covers the
# other. That gap left the backup a whole merge behind on 2026-08-19.
#
# NEVER FAILS THE {kind.split('-')[1].upper()}. A backup push that could block would turn
# "the backup drive is unplugged" into "I cannot work right now" — the wrong
# failure mode for a safety net. Warns and exits 0 regardless.
#
# Silent on success, loud on failure — a hook that prints every time trains
# a reader to stop reading its output.
if git remote get-url backup >/dev/null 2>&1; then
    if ! {{ git push backup --all --quiet && git push backup --tags --quiet; }} 2>/tmp/inner-circling-backup-push.log; then
        echo "  {kind}: WARNING — backup push to 'backup' remote failed." >&2
        echo "  {kind}: see /tmp/inner-circling-backup-push.log" >&2
    fi
fi
exit 0
'''


# post-commit v2 — v1 was HAND-INSTALLED, with no template here at all. That
# is precisely why the post-merge gap survived: the hook nobody could see in
# the source was the hook nobody checked, and `ensure_hooks()` managed only
# pre-commit. v2 is byte-equivalent in behaviour to what v1 did; the version
# bump exists so the installer REPLACES the hand-written file rather than
# finding a matching mark and leaving two different programs in agreement
# about their name — v8's lesson, applied to the hook v8 did not cover.
POST_COMMIT_MARK = "# inner-circling post-commit v2"
POST_COMMIT_FAMILY = "# inner-circling post-commit v"
POST_COMMIT = _backup_push_hook("post-commit", POST_COMMIT_MARK, "commit")

POST_MERGE_MARK = "# inner-circling post-merge v2"
POST_MERGE_FAMILY = "# inner-circling post-merge v"

# v2, R-NEW 2026-08-24: THE LEDGER FOLD RUNS HERE.
#
# `coordinator/assign_ids.py --write` was the one step in the whole
# branch-and-merge mechanism that a human had to remember, and on 2026-08-24
# two separate merges both forgot it. check_rulings.py then refused master —
# correctly, that is the tripwire — and the repair fell to the operator, who
# is the person in this project least equipped to run an ordered sequence of
# git commands. The design was never the problem; its last step being manual
# was.
#
# THE REASON IT WAS MANUAL DOES NOT APPLY TO THIS HOOK. assign_ids.py has
# always said, correctly, that no hook can catch it: a clean `git merge`
# creates a commit WITHOUT firing pre-commit. That is a fact about
# pre-commit. git runs post-merge for exactly the event that leaves a fold
# owing, and this repository has had a post-merge hook since 2026-08-19. It
# was only ever carrying the backup push.
#
# EVERY GUARD IS IN THE PYTHON, NOT HERE. `--commit` refuses off master and
# refuses inside a worktree (`.git/hooks/` is SHARED with every worktree, so
# `git merge master` run inside one fires this same hook, in a tree where
# `.venv` does not exist and master is not checked out). A guard written in
# this file would be a guard no probe could reach; in assign_ids.py,
# test_assign_ids.py holds it — and that suite is the only thing that can,
# since nothing else runs at the moment ids move.
#
# IT CANNOT FAIL THE MERGE. git ignores post-merge's exit status, and the
# merge has already happened by the time this runs. A failure here is loud
# and leaves the folded ledgers in the working tree, uncommitted.
_FOLD_STEP = '''
# --- the ledger fold, before the backup push (see _backup_push_hook) ---
if [ -x .venv/Scripts/python.exe ]; then
    if ! .venv/Scripts/python.exe coordinator/assign_ids.py --commit; then
        echo "  post-merge: assign_ids --commit FAILED." >&2
        echo "  post-merge: the fold may be WRITTEN and UNCOMMITTED — check" >&2
        echo "  post-merge: 'git status', fix what the gate named, commit." >&2
    fi
fi
'''

POST_MERGE = _backup_push_hook("post-merge", POST_MERGE_MARK, "merge",
                               prelude=_FOLD_STEP)


def _sh_n(body: str, label: str, log) -> bool:
    """`sh -n` over one hook template. True if it parsed, False if `sh` is
    absent (the validator's absence is not evidence of a broken template).
    Raises GitError on a real parse failure.

    Split out 2026-08-19 when POST_MERGE joined PRE_COMMIT: two templates
    now need the same gate, and a second copy of it is the shape that lets
    one of them quietly stop being checked."""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                     encoding="utf-8", newline="\n") as f:
        f.write(body)
        tmp = f.name
    try:
        try:
            r = subprocess.run(["sh", "-n", tmp], capture_output=True,
                               text=True, timeout=30)
        except OSError:
            log("warn", f"sh not on PATH — {label} template syntax check skipped")
            return False
        if r.returncode != 0:
            raise GitError(f"{label} template fails sh -n — refusing to "
                           f"install a hook the shell cannot parse:\n"
                           f"{(r.stderr or r.stdout).strip()}")
        return True
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _hook_syntax_check(log, pre_commit: bool = True) -> None:
    """`sh -n` over the PRE_COMMIT template, before any install. Raises
    GitError on a parse failure — installing a hook the shell refuses
    turns every future commit into a hard failure (v38's own origin
    story). If no `sh` is on PATH (a non-Git-Bash console), the check
    is SKIPPED WITH A WARNING rather than failed: the validator's
    absence is not evidence the template is broken, and git-for-Windows
    ships the sh that will actually run the hook.

    `pre_commit=False` CHECKS POST_MERGE ALONE, for the caller that is
    not going to install a pre-commit hook. Added 2026-08-24, and found
    by running --git-setup in a real bundle rather than reasoning about
    it: the execution layer below RUNS the template against this repo,
    and in a tree without coordinator/tests/ that run fails on the
    template's own first line, so ensure_hooks() raised here — before
    reaching the guard that exists to skip the install. Validating a
    program nobody is about to install, by running it, is the check
    getting in front of its own decision."""
    # POST_MERGE gets `sh -n` and NOTHING MORE, deliberately. The execution
    # layer below runs a template for real against this repo; running
    # POST_MERGE for real would push to the backup remote as a side effect of
    # a syntax check. A validator with a side effect is not one.
    _sh_n(POST_MERGE, "POST_MERGE", log)
    if not pre_commit:
        return
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                     encoding="utf-8", newline="\n") as f:
        f.write(PRE_COMMIT)
        tmp = f.name
    try:
        try:
            r = subprocess.run(["sh", "-n", tmp], capture_output=True,
                               text=True, timeout=30)
        except OSError:
            log("warn", "sh not on PATH — hook template syntax check skipped")
            return
        if r.returncode != 0:
            raise GitError(f"PRE_COMMIT template fails sh -n — refusing to "
                           f"install a hook the shell cannot parse:\n"
                           f"{(r.stderr or r.stdout).strip()}")
        # EXECUTION LAYER, added v40. sh -n proved insufficient the same
        # day it shipped: v38's own changelog carried an un-escaped
        # two-character escape inside the f-string, Python rendered it
        # as a real newline, and the orphaned comment tail became an
        # executable line opening a stray quoted string — syntactically
        # VALID overall, so -n stayed green, while every hook run
        # printed a bash warning to stderr and executed prose as a
        # (luckily inert) command. So: when NOTHING is staged, run the
        # template for real against this repo and require exit 0 with
        # an EMPTY stderr — the defect class announces itself only at
        # execution, and only on stderr (the checks' own output goes to
        # stdout). With something staged the run would exercise real
        # gates on a mid-edit tree, so the layer is skipped with a
        # warning rather than made to lie.
        rc_staged, staged = run("diff", "--cached", "--name-only",
                                read_only=True)
        if rc_staged == 0 and not staged.strip():
            try:
                x = subprocess.run(["sh", tmp], cwd=str(ROOT),
                                   capture_output=True, text=True,
                                   encoding="utf-8", errors="replace",
                                   timeout=300)
            except OSError:
                log("warn", "sh vanished mid-check — execution layer skipped")
                return
            if x.returncode != 0 or x.stderr.strip():
                raise GitError(
                    "PRE_COMMIT template misbehaves when RUN (exit "
                    f"{x.returncode}; stderr below) — refusing to install:\n"
                    f"{x.stderr.strip() or x.stdout.strip()}")
        else:
            log("warn", "files are staged — hook template execution check "
                        "skipped (sh -n still passed)")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def ensure_hooks(log) -> None:
    """Install the pre-commit and post-merge hooks if absent, and UPDATE AN
    OUT-OF-DATE ONE. Never overwrites a hook this project did not write — a
    human may have put one there deliberately.

    It only reported until v8, and that let the two drift: the hook on disk
    and the template here both said v7 and ran different checks. A version
    mark that is never compared is a comment. So an existing hook of this
    family at a different version is REPLACED, and the replacement is
    announced rather than done quietly.

    SYNTAX-GATED since v38: the template is `sh -n`-checked before any
    install — v37 shipped an unterminated case pattern (a scripted
    edit's literal two-character "\\n"), and the broken hook then FAILED
    every commit rather than running its checks. A template sh cannot
    parse is refused here, loudly, instead of written into .git/hooks.

    THE BACKUP HOOKS ARE DONE FIRST, ON PURPOSE. The pre-commit block below
    is a chain of early returns — the FIRST of which is the ordinary case, a
    pre-commit already at this mark. Calling _ensure_backup_hooks at the tail
    would have installed them only on a tree that happened to be missing its
    pre-commit hook, i.e. almost never, while reading like it ran always."""
    # THE DISCRIMINATOR IS READ FIRST because the syntax check below RUNS
    # the pre-commit template, and in a tree that has no suites that run
    # fails on the template's own first line — see _hook_syntax_check's
    # `pre_commit` parameter. The backup hooks are still installed and
    # still validated either way; they are recipient-safe (no `backup`
    # remote, no push) and cost a tree without suites nothing.
    # THE TEMPLATE IS VALIDATED EVERYWHERE AGAIN, v80. `pre_commit=dev_tree`
    # was added 2026-08-24 because the execution layer RUNS the template
    # against this repo, and in a tree without coordinator/tests/ that run
    # failed on the template's own first line. `run` skips a script the tree
    # does not have, so the run now completes in a bundle — and a hook about
    # to be installed there is exactly one worth validating first.
    dev_tree = (ROOT / "coordinator" / "tests").is_dir()
    _hook_syntax_check(log)
    d = ROOT / ".git" / "hooks"
    if not d.is_dir():
        log("warn", "no .git/hooks directory; skipping pre-commit hook")
        return
    _ensure_backup_hooks(d, log)
    # THE PRE-COMMIT BATTERY IS A DEVELOPMENT-TREE MECHANISM, and until
    # 2026-08-24 it was installed into any tree that ran --git-setup. The
    # template invokes the probe suites and the operator-only checkers BY
    # PATH, with no existence test — `coordinator/tests/*`, `ui/tests/*`,
    # `work/tools/*`, `packaging/*`, `check_lint.py`, `check_rulings.py`
    # and kin — and NONE of those ship in a distributed bundle. Its very
    # first line, `python coordinator/check_line_endings.py --staged`, is
    # UNCONDITIONAL, so in a bundle every commit failed at line one.
    #
    # THE WORST OF THAT WAS NOT THE HUMAN'S COMMIT. transcript_store's
    # commit_circle() runs through the same hook at every /close, so a
    # recipient who ran --git-setup would have had every circle silently
    # refused at the moment it was committed — R130's exact shape, rebuilt
    # in every bundle.
    #
    # `coordinator/tests/` IS THE DISCRIMINATOR because it is the thing
    # the hook actually invokes, not a proxy for it. A lab clone has the
    # directory and gets the full battery; a bundle does not and gets
    # none. NOT INSTALLING IS ANNOUNCED — a hook that quietly is not there
    # is the same defect class as a check that quietly stops checking,
    # which is what v8 and v11 were.
    # THE DISCRIMINATOR IS GONE, v80 (2026-08-26), and the reason it existed
    # went with it. Everything above is the account of why a bundle got no
    # battery: the template named 72 scripts by path with no existence test,
    # so in a tree that ships 6 of them every commit — the human's, and every
    # /close, which commits through the same hook — failed at the first line.
    #
    # `run` and `quiet` end that. A script this tree does not have is skipped;
    # one it HAS still fails the commit when it fails. Measured before this
    # line was written: a real bundle, cloned fresh, `--git-setup` run in it,
    # the battery installed, and a commit touching self/ and coordinator/ went
    # through green — it ran the corruption sweep, the issue gate, the
    # self-check, the practices check and the projection, and skipped the 66
    # scripts that are not part of the product.
    #
    # RULED BY THE OPERATOR, 2026-08-26: a recipient's circle closes are gated
    # by the gates that ship, because a corrupted register is worth catching
    # as the circle commits rather than at the next open. The announcements
    # were made honest first (v80's NOTE deferral) — a hook that says it
    # linted every module when it linted none is worse on a stranger's screen
    # than on ours.
    if not dev_tree:
        log("note", "coordinator/tests/ is absent — this is a distributed "
                    "bundle. The pre-commit battery IS installed and runs "
                    "the gates that ship (the corruption sweep, the issue "
                    "gate, the self-check, the practices check, the "
                    "projection); the probe suites and dev-only checkers "
                    "are skipped one by one, not by refusing the commit.")
    p = d / "pre-commit"
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="replace")
        if HOOK_MARK in text:
            log("ok", "pre-commit hook installed (gate runs on any issues/ commit)")
            return
        if HOOK_FAMILY in text:
            old = next((l.strip() for l in text.splitlines()
                        if HOOK_FAMILY in l), "an earlier version")
            p.write_text(PRE_COMMIT, encoding="utf-8", newline="\n")
            log("did", f"replaced {old!r} with {HOOK_MARK!r} — an out-of-date "
                       f"hook of ours runs different checks than this file "
                       f"describes")
            return
        log("warn", f"a pre-commit hook exists and is not ours; leaving it alone "
                    f"— add the gate call by hand, see {HOOK_MARK}")
        return
    p.write_text(PRE_COMMIT, encoding="utf-8", newline="\n")
    try:
        p.chmod(0o755)          # a no-op on Windows; git for Windows runs it anyway
    except OSError:
        pass
    log("did", "installed .git/hooks/pre-commit — the gate now runs on any "
               "commit touching issues/")


# The two backup-push hooks, in the order they are installed. A list rather
# than two calls: adding a third git hook to this safeguard should be one
# entry, not another copy of the installer.
BACKUP_HOOKS = (
    ("post-commit", lambda: POST_COMMIT, lambda: POST_COMMIT_MARK,
     lambda: POST_COMMIT_FAMILY),
    ("post-merge", lambda: POST_MERGE, lambda: POST_MERGE_MARK,
     lambda: POST_MERGE_FAMILY),
)


def _ensure_backup_hooks(d: pathlib.Path, log) -> None:
    """Install or update .git/hooks/post-commit and .git/hooks/post-merge —
    the backup pushes, one per git event that can move a ref.

    SAME THREE-WAY DECISION AS pre-commit, and for the same reason: ours at
    this mark is left alone, ours at a DIFFERENT mark is replaced (a version
    mark that is never compared is a comment — v8's lesson), and a hook this
    project did not write is never touched.

    NOT MERGED WITH pre-commit's block: these answer a different question
    (has the backup got this? / does this commit pass?) and fail differently
    (never blocks anything / blocks the commit). pre-commit also has a
    syntax-and-execution gate these do not need — running one of these for
    real would push to the backup remote as a side effect of a check."""
    for name, body, mark, family in BACKUP_HOOKS:
        _ensure_one_backup_hook(d, name, body(), mark(), family(), log)


def _ensure_one_backup_hook(d: pathlib.Path, name: str, body: str, mark: str,
                            family: str, log) -> None:
    p = d / name
    if p.is_file():
        text = p.read_text(encoding="utf-8", errors="replace")
        if mark in text:
            log("ok", f"{name} hook installed (backup push)")
            return
        if family in text:
            old = next((l.strip() for l in text.splitlines()
                        if family in l), "an earlier version")
            p.write_text(body, encoding="utf-8", newline="\n")
            log("did", f"replaced {old!r} with {mark!r}")
            return
        log("warn", f"a {name} hook exists and is not ours; leaving it alone "
                    f"— add the backup push by hand, see _backup_push_hook() "
                    f"in gitrepo.py")
        return
    p.write_text(body, encoding="utf-8", newline="\n")
    try:
        p.chmod(0o755)
    except OSError:
        pass
    log("did", f"installed .git/hooks/{name} — the backup disk now learns "
               f"about this event")


def ensure_ignore(log) -> list[str]:
    """Append any missing REQUIRED_IGNORES. Never removes or reorders what is
    already there — the file may hold entries a human added deliberately."""
    p = ROOT / ".gitignore"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    have = {l.strip() for l in text.splitlines() if l.strip()}
    added: list[str] = []
    chunks: list[str] = []
    for header, pats in REQUIRED_IGNORES:
        missing = [x for x in pats if x not in have]
        if missing:
            chunks.append(header + "\n" + "\n".join(missing))
            added += missing
    if not added:
        log("ok", ".gitignore covers every required path")
        return []
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        if text and not text.endswith("\n"):
            f.write("\n")
        f.write("\n" + "\n\n".join(chunks) + "\n")
    log("did", f".gitignore += {', '.join(added)}")
    return added


def untrack_ignored(log) -> list[str]:
    """Drop from the INDEX any tracked path that .gitignore now excludes. The
    working file is untouched (`--cached`) and history is untouched — the blob
    stays reachable from older commits. This is the one index-editing operation
    that is safe to automate: nothing is lost, and leaving e.g. an 11MB tool
    database tracked means re-storing it in full on every commit it changes."""
    rc, out = run("ls-files", "--cached", "--ignored", "--exclude-standard",
                  read_only=True)
    paths = [l for l in out.splitlines() if l.strip()] if rc == 0 else []
    if not paths:
        log("ok", "no tracked path is covered by .gitignore")
        return []
    for chunk in (paths[i:i + 200] for i in range(0, len(paths), 200)):
        run("rm", "--cached", "--quiet", "--", *chunk, check=True)
    log("did", f"un-tracked {len(paths)} ignored path(s): "
               f"{', '.join(sorted({p.split('/')[0] for p in paths}))}")
    log("note", "history still holds their old blobs; that is intentional. "
                "Shrinking history is a manual filter-repo operation.")
    return paths


# ------------------------------------------------------- remote classification
# THE INVARIANT IS NOT "NO REMOTE". It is that this material never leaves this
# machine. Those two coincided until 2026-08-09 09:21, when Self added a
# `backup` remote pointing at a bare repository on a second physical disk —
# a disk-failure safeguard, and exactly what the rule is meant to permit.
#
# WHAT THE LITERAL RULE COST. `commit_paths` calls this, so from 09:21 every
# circle close silently failed to commit. `commit_circle` is non-fatal by
# design, so it printed and the circle closed clean. circle_2026-08-09_1520
# is the one live circle that closed in that window: its transcript, seven
# short_terms and close report sat UNTRACKED and were swept up by hand in
# 972a5bb, and `circle/2026-08-09_1520` was never tagged. A guard enforcing
# the letter of a rule against the thing the rule exists to allow.
#
# Ruled 2026-08-10, option (b) of three: classify by SHAPE, then by DRIVE
# TYPE. Shape alone was rejected because a mapped network drive (`Z:` ->
# `\\server\share`) is a filesystem path by shape and a network hop in fact,
# and this project's whole reason for being local is that the material is
# private. FAILS CLOSED: anything it cannot positively classify as a fixed or
# removable local volume is refused.
_SCHEME = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*)://")
_SCP = re.compile(r"^[^/\\:]+@[^/\\:]+:")          # git@host:path

# GetDriveTypeW. 2 REMOVABLE and 3 FIXED are on this machine; 4 REMOTE is a
# network share and is the case shape-matching alone would have admitted.
_DRIVE = {0: "UNKNOWN", 1: "NO_ROOT_DIR", 2: "REMOVABLE", 3: "FIXED",
          4: "REMOTE", 5: "CDROM", 6: "RAMDISK"}
_DRIVE_OK = (2, 3)


def _drive_type(path: str) -> tuple[int, str]:
    """(code, name) for the volume a path sits on. (0, 'UNKNOWN') off Windows
    or on any error — which the caller must treat as a refusal, not a pass."""
    if sys.platform != "win32":
        return 0, "UNKNOWN"
    try:
        import ctypes
        root = pathlib.Path(path).resolve().anchor
        if not root:
            return 1, "NO_ROOT_DIR"
        code = int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)))
        return code, _DRIVE.get(code, f"code {code}")
    except Exception:                                            # noqa: BLE001
        return 0, "UNKNOWN"


def classify_remote(url: str) -> tuple[bool, str]:
    """(stays_on_this_machine, why). The `why` is printed either way — a
    remote that passes should say WHY it passed, so a reader can check the
    judgement rather than trust it."""
    u = (url or "").strip()
    if not u:
        return False, "empty URL — cannot classify"
    m = _SCHEME.match(u)
    if m and m.group(1).lower() != "file":
        return False, f"{m.group(1)}:// — a network protocol"
    if m:
        # file:// forms. Strip the scheme but NEVER a slash that belongs
        # to the path: the old `file://(localhost)?/?` ate one slash, so
        # git's UNC-in-file-URL spelling file:////server/share became
        # /server/share — which the UNC test below missed and _drive_type
        # then resolved onto the CURRENT drive: a network share classified
        # "local volume (FIXED)". R130 fails closed — every hosted or UNC
        # file:// form is refused before any drive probe (2026-08-19,
        # review tier 2 #20; test_remote_classify.py pins each spelling).
        rest = u[m.end():]
        if rest.lower() == "localhost" or rest.lower().startswith("localhost/"):
            rest = rest[len("localhost"):]
        if rest.startswith("//") or rest.startswith("\\\\"):
            return False, "UNC path in a file:// URL — another machine"
        if rest.startswith("/"):
            u = rest[1:]                # file:///C:/x -> C:/x
        elif re.match(r"^[A-Za-z]:($|[/\\])", rest):
            u = rest                    # file://C:/x — a drive, not a host
        elif rest:
            return False, (f"file:// names a host "
                           f"({rest.split('/', 1)[0]}) — another machine")
        else:
            return False, "empty file:// URL — cannot classify"
        if not u:
            return False, "empty file:// URL — cannot classify"
    elif _SCP.match(u):
        return False, "user@host:path — ssh"
    if u.startswith("\\\\") or u.startswith("//"):
        return False, "UNC path — another machine"
    code, name = _drive_type(u)
    if code in _DRIVE_OK:
        return True, f"local volume ({name})"
    return False, (f"volume is {name} — only FIXED and REMOVABLE are on this "
                   f"machine")


def refuse_remote(log) -> bool:
    """True if ANY configured remote could take this material off the machine.

    Named for what it does at the call sites, which is refuse. It no longer
    refuses a remote for existing — see the block above."""
    bad = []
    for name in remotes():
        rc, url = run("remote", "get-url", name, read_only=True)
        url = url.strip() if rc == 0 else ""
        ok, why = classify_remote(url)
        if ok:
            log("ok", f"remote {name} -> {url} — stays on this machine, {why}")
        else:
            bad.append((name, url or "(unreadable)", why))
    if not bad:
        return False
    for name, url, why in bad:
        log("fail", f"remote {name} -> {url} could take this material OFF "
                    f"this machine: {why}. This repository is private "
                    f"therapeutic material (docs/NIGHTLY_DESIGN.md §6). "
                    f"Run: git remote remove {name}")
    return True


# ------------------------------------------------- unconfigured identity
# The operator, 2026-08-25 (R349), after the
# fresh install Inner-Circling-2026-08-25_1309's first circle printed git's
# own "Author identity unknown" refusal at the open: the failure is CAUGHT
# before staging, the commit is skipped, and the reply is his kind note —
# reported the first time the error is encountered and not after that, per
# circle.
_UNCONFIGURED_REPORTED = False

UNCONFIGURED_TEXT = ("I see git is not configured. git is optional; adding "
                     "it helps support recovery should there be any failure. "
                     "It is local only, nothing leaves your machine. See "
                     "README.md for details.")


def identity_known() -> bool:
    """Will `git commit` accept an author here? `git var GIT_AUTHOR_IDENT`
    fails exactly when `git commit` would refuse with "Author identity
    unknown", and consults every source git itself does — config at any
    scope, GIT_AUTHOR_*/EMAIL, a host whose address auto-detects.
    resolve_identity() is NOT this test: $IFS_GIT_NAME in .env satisfies it
    without configuring git, and the commit still fails.

    Never raises — this sits on the /close path, where an uncaught GitError
    is a crash at the end of every circle (the 2026-08-24 missing-binary
    lesson in commit_paths() below)."""
    try:
        return run("var", "GIT_AUTHOR_IDENT", read_only=True)[0] == 0
    except GitError:
        return False


def report_unconfigured(log) -> None:
    """The kind note, once per process. circle.py's main() resets the flag
    at each run, which makes "once per process" mean once per circle —
    one UI process can run main() more than once (resume)."""
    global _UNCONFIGURED_REPORTED
    if _UNCONFIGURED_REPORTED:
        return
    _UNCONFIGURED_REPORTED = True
    log("note", UNCONFIGURED_TEXT)


def reset_unconfigured_report() -> None:
    global _UNCONFIGURED_REPORTED
    _UNCONFIGURED_REPORTED = False


# ---------------------------------------------------------------- commit
def _unstage(rel: list[str], log) -> None:
    """B32, 2026-08-15. Put back exactly what THIS call staged, after its own
    commit failed to land.

    Before this, a failed commit left its paths in the index and the next
    unrelated `git commit` swept them into someone else's change — silent in
    both directions: the circle was not committed and nothing said so, and its
    files landed in a commit that never meant to carry them.

    `rel` is only ever the paths this call staged itself; anything the human
    had already staged is excluded by the caller and never touched here.
    """
    if not rel:
        return
    rc, out = run("reset", "-q", "HEAD", "--", *rel)
    if rc != 0:
        # Unborn HEAD — there is no commit to reset against, so the index
        # entries are new rather than modified. Dropping them from the index
        # is the equivalent operation, and --cached leaves the files on disk.
        rc, out = run("rm", "-q", "--cached", "--", *rel)
    if rc == 0:
        log("did", f"unstaged {len(rel)} path(s) after the failed commit")
    else:
        log("warn", f"could not unstage after the failed commit: {out}. "
                    f"Run `git reset HEAD -- <paths>` before committing "
                    f"anything else, or these will be swept into it.")


def commit_paths(paths: list[pathlib.Path], message: str, log,
                 tag: str | None = None) -> bool:
    """Stage and commit ONLY the given paths. Never `git add -A`: an automated
    run must not sweep up whatever the human was editing at the time."""
    # NO GIT AT ALL IS A SUPPORTED TREE SINCE 2026-08-24 (the operator:
    # "Tier 1"), and it did not used to reach this line. is_repo() shells
    # out, so a machine with no git BINARY raises GitError from run()'s
    # OSError arm instead of answering False — uncaught here, uncaught in
    # transcript_store.commit_circle(), and therefore a CRASH at the end of
    # every /close rather than the warn-and-continue this function is built
    # to give. A missing repository was handled; a missing git was not, and
    # the two look identical to a caller.
    try:
        repo = is_repo()
    except GitError as e:
        log("warn", f"git is not usable here ({e}) — nothing committed. "
                    f"The files themselves are written; only the history "
                    f"step is skipped.")
        return False
    if not repo:
        log("warn", "not a git repository — nothing committed. "
                    "Run: python coordinator/circle_audit.py --git-setup")
        return False
    if not assert_isolated(log) or refuse_remote(log):
        return False
    # git IS here but nobody told it who commits — the fresh-install case.
    # Caught BEFORE staging: the raw refusal reads as breakage in a tree
    # where git is optional, and a failed commit would also leave the index
    # for _unstage() to repair. Skipped, with the kind note, once.
    if not identity_known():
        report_unconfigured(log)
        return False
    rel = []
    for p in paths:
        try:
            if p.exists():
                rel.append(p.resolve().relative_to(ROOT).as_posix())
        except ValueError:
            log("warn", f"outside the repository, skipped: {p}")
    if not rel:
        log("warn", "no existing paths to commit")
        return False
    # B32. WHAT WAS ALREADY STAGED BEFORE WE TOUCHED THE INDEX. Captured so a
    # failed commit can put the index back exactly as it found it — and no
    # further. Unstaging a path the HUMAN had staged (possibly with content
    # that differs from the working tree) would destroy their work to clean up
    # ours, which is worse than the leak this fixes.
    rc, out = run("diff", "--cached", "--name-only", "--", *rel,
                  read_only=True)
    pre_staged = set(out.splitlines()) if rc == 0 else set(rel)
    ours = [r for r in rel if r not in pre_staged]
    run("add", "--", *rel, check=True)
    rc, _ = run("diff", "--cached", "--quiet", read_only=True)
    if rc == 0:
        log("ok", "nothing changed in those paths — no commit made")
        return True
    rc, out = run("commit", "-m", message, "--only", "--", *rel)
    if rc != 0:
        log("fail", f"commit failed: {out}")
        _unstage(ours, log)
        return False
    log("did", f"commit {head()} — {message}")
    if tag:
        rc, out = run("tag", tag)
        log("did" if rc == 0 else "warn",
            f"tag {tag}" if rc == 0 else f"tag {tag} not created: {out}")
    return True


# ----------------------------------------------------------------- cli
def main() -> int:
    """`--identity` only. A read-only window onto resolve_identity(), so the
    question "who will this commit as, and why" can be answered without
    running --git-setup, which writes."""
    import argparse
    ap = argparse.ArgumentParser(
        description="git surface for Inner Circling — see docs/configuration.md")
    ap.add_argument("--identity", action="store_true",
                    help="print the resolved git author name and email, with "
                         "the source of each, and change nothing")
    args = ap.parse_args()
    if not args.identity:
        ap.print_help()
        return 0
    ok = True
    for key, (value, src) in zip(("user.name", "user.email"),
                                 resolve_identity()):
        if value is None:
            ok = False
            print(f"  {key:<12} UNSET  "
                  f"(set ${ENV_GIT_NAME}/${ENV_GIT_EMAIL} or git config)")
        else:
            print(f"  {key:<12} {value}   <- {src}")

    # THE CONSOLE NAME TOO, because "who am I" has two answers here and
    # having to remember two commands to get them is how they drift apart.
    # REPORTED, NOT CHAINED: IFS_USER_NAME is deliberately NOT a fallback
    # for git user.name. They are the same person and often a different
    # string — a given name is shown at the console, a full name authors a
    # commit — and silently borrowing one for the other would write an
    # authorship this project cannot then distinguish from a chosen one.
    #
    # NARROWED 2026-08-11: a literal name is forbidden PII, so it is never
    # written to a transcript any more — the console name below is local
    # display only, not "who wrote the record". The transcript tag is now
    # always [Self]:, unconditionally.
    try:
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import identity as _ID
        v, vsrc = _ID.user_name_source()
        print(f"  {'console name':<12} {v}   <- {vsrc}   (local display only)")
        print(f"  {'':<12} transcript tag [{_ID.DISPLAY}]:   (fixed)")
    except Exception as e:                                   # pragma: no cover
        print(f"  {'console name':<12} unavailable ({e})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
