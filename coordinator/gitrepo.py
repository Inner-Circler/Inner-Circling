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
       version silently blocked every circle close for a day. system_git_remote_classify()
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
       message about dreaming. system_git_paths_commit() takes an explicit list.
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
# system_git_ignore_ensure() and un-tracked by system_git_ignored_untrack() if already indexed.
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
    # TRANSACTION_CLASS.py's staging/transaction root (shared with inter_circle.py);
    # work/circle_audit/ is the renamed audit's own lock/snapshot home.
    ("# Temp workspaces — staging, caches, locks, snapshots", [
        "work/nightly/", "work/circle_audit/", "work/issue_trial/"]),
    ("# Tool working databases — rewritten constantly, ~11MB each time", [
        ".fileintel/"]),
    # Derived output. Left untracked these show as dirty forever, which is noise in
    # exactly the check meant to catch real uncommitted work. Automated runs never
    # commit them anyway, and git history already records what each run did.
    ("# Run logs — derived, one per run", ["work/logs/circle_audit*.log"]),
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
# A GIT FAILURE'S OUTPUT LEADS WITH SOMEBODY ELSE'S SUCCESS — 2026-09-09, the
# operator, reading a close: *"'commit failed: OK' is worse than awkward... what
# does it mean?"*, over this line:
#
#     !! commit failed: OK    no CR and no NUL in 76 path(s) ...
#
# `system_git_run` returns stdout+stderr merged, and `git commit` runs the
# pre-commit hook as a child whose output passes straight through. The hook
# announces every check it PASSES, so the merged text opens with a wall of OK
# and whatever actually refused is at the END. Printing that text after the
# words "commit failed:" reads as though OK were the reason.
#
# THE TAIL IS WHERE A FAILURE REPORTS, and the head is where a success does. So
# the message names the exit code (which was not shown at all), then the last
# few lines that are not a hook's own pass marker.
_PASS_MARKERS = ("  OK ", "  ok ", "  did ", "  DID ", "  note ", "  NOTE ")


def _failure_tail(out: str, keep: int = 6) -> list[str]:
    """The last `keep` lines of a git failure that are not a pass marker."""
    lines = [ln.rstrip() for ln in out.splitlines() if ln.strip()]
    meat = [ln for ln in lines
            if not any(ln.startswith(m) or ln.lstrip().startswith(m.strip())
                       for m in _PASS_MARKERS)]
    return (meat or lines)[-keep:]


def system_git_failure_explain(out: str) -> str:
    """One line naming the likeliest cause, for the head of a failure report.

    NAMED, NEVER GUESSED AT LENGTH: each branch is a string git or this
    project's own hook actually emits. Anything unrecognised says so rather
    than inventing a diagnosis — an honest "no reason given" beats a confident
    wrong one, which is the whole defect this replaces."""
    low = out.lower()
    if "index.lock" in low:
        return ("another git process holds .git/index.lock (it is SHARED with "
                "every worktree) — report it, never remove it silently")
    if "pre-commit" in low and "refus" in low:
        return "the pre-commit hook refused; its reason is below"
    if "nothing to commit" in low or "no changes added" in low:
        return "git found nothing to commit in those paths"
    if "please tell me who you are" in low or "user.email" in low:
        return "git has no identity configured for this repository"
    if "hook" in low:
        return "a git hook exited non-zero; its last output is below"
    return "git gave no recognised reason; its last output is below"


def system_git_run(*args: str, check: bool = False, read_only: bool = False) -> tuple[int, str]:
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


def system_git_is_available() -> bool:
    try:
        return system_git_run("--version", read_only=True)[0] == 0
    except GitError:
        return False


def system_git_is_repo() -> bool:
    return system_git_run("rev-parse", "--git-dir", read_only=True)[0] == 0


def system_git_is_main_checkout() -> bool:
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
# path circle_is_processed() lives on and the one most worth rehearsing.
LAB_SEGMENT = "lab"


def system_git_tag_name_read(*parts: str) -> str:
    """The tag this TREE should write. `tag_name("dream", ot)` ->
    `dream/<ot>` in the main checkout, `dream/lab/<ot>` anywhere else.

    THE INVARIANT, and the only thing the spelling has to satisfy: NO TAG
    WRITTEN FROM A LAB TREE MAY EVER BE BYTE-EQUAL TO ONE THE MAIN TREE WOULD
    WRITE. The tag namespace is the one thing a worktree does not isolate —
    files are contained by construction (record_paths.ROOT derives from __file__),
    refs are not, because `.git` is shared and every worktree reads one
    namespace. circle_is_processed() is the double-dream guard and it reads
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
    if system_git_is_main_checkout():
        return "/".join(parts)
    return "/".join((parts[0], LAB_SEGMENT) + parts[1:])


def system_git_toplevel_read() -> pathlib.Path | None:
    rc, out = system_git_run("rev-parse", "--show-toplevel", read_only=True)
    if rc != 0 or not out.strip():
        return None
    return pathlib.Path(out.strip()).resolve()


def system_git_isolated_assert(log) -> bool:
    """True if the repository root IS this project folder.

    git commands walk UP the directory tree looking for .git, so if a repository
    were ever created at a parent directory (or a home-directory
    dotfiles repo), every command here would silently start operating on that
    larger repository instead — mixing this project's history with other
    projects', and putting private material in a repo that might well have a
    remote. Checked before anything that commits."""
    top = system_git_toplevel_read()
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


def system_git_remotes_read() -> list[str]:
    rc, out = system_git_run("remote", read_only=True)
    return out.split() if rc == 0 and out.strip() else []


def system_git_is_dirty() -> list[str]:
    rc, out = system_git_run("status", "--porcelain", read_only=True)
    return [l for l in out.splitlines() if l.strip()] if rc == 0 else []


def system_git_head_read() -> str:
    rc, out = system_git_run("rev-parse", "--short", "HEAD", read_only=True)
    return out if rc == 0 else "(no commits)"


# ---------------------------------------------------------------- setup
def system_git_repo_ensure(log) -> bool:
    if system_git_is_repo():
        if not system_git_isolated_assert(log):
            return False
        log("ok", f"git repository is this folder only (HEAD {system_git_head_read()})")
        return True
    system_git_run("init", check=True)
    log("did", f"git init in {ROOT}")
    return system_git_isolated_assert(log)


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
    rc, out = system_git_run("config", key, read_only=True)
    return out.strip() or None if rc == 0 else None


def system_git_identity_resolve(name: str | None = None,
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


def system_git_config_ensure(log, name: str | None, email: str | None) -> None:
    (name, name_src), (email, email_src) = system_git_identity_resolve(name, email)
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
        rc, have = system_git_run("config", key, read_only=True)
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
        system_git_run("config", key, want, check=True)
        log("did", f"git config {key} {want}  (from {src})")


def system_git_attributes_ensure(log) -> None:
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
# corrected body, since system_git_hooks_ensure() reinstalls on HOOK_MARK alone.
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
# circle_observation register (R256). git merged the constant clean,
# because both sides made the IDENTICAL edit; that is the silent half of
# the same defect R238/R239 rule for ids, arriving here in the one
# constant whose whole job is to say "the installed hook is out of
# date". The merged TEMPLATE carried both invocation blocks while the
# INSTALLED hook carried only master's, and system_git_hooks_ensure() would never
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
# ALLOW entry, and its reason is REPLACED, 2026-09-08 (audit-register.md #16/#42).
#
# THE OLD REASON HAD EXPIRED. It read "16 of its checks are stale against B51(3) and R202
# and it is wired only once those are realigned" — and B51 is closed; it no longer appears
# in NEXT.md at all. An ALLOW entry whose condition has been met reads as an oversight, and
# the next person to check would have wired it.
#
# I CLAIMED IT DID NOT TERMINATE. THAT WAS WRONG, and the correction is the useful part.
# Written 2026-09-08 on a ten-minute run that produced no output; the operator then ruled
# "diagnose and wire", and the diagnosis says otherwise. (The name that stood here instead of
# "the operator" is why this file's own shipped-surface gate refused the first commit of this
# comment — sanitize.py, 1 HIGH, owner-name. R253 working exactly as ruled, on the file that
# carries the hook that runs it.)
# The suite prints its plan and then paces itself
# at 10-20 SECONDS PER LINE, by design, over 93 scripted lines — 15 to 31 minutes, silent in
# between. Ten minutes was simply not a long enough wait. `--fast` collapses the delay and is
# the mode to iterate in; its own usage block says so at :10-11.
#
# THE REAL REASON IS THE ONE THIS ENTRY GAVE ALL ALONG: its checks are stale. Run with
# --fast, 20 pass and 15 FAIL — against the "16 of its checks are stale" this entry has said
# since it was written. What had expired was only its PRECONDITION ("wired once B51(3) and
# R202 are realigned"): B51 is closed, and the realignment is still owed.
#
# IN A WORKTREE IT NEEDS ONE MORE THING FIRST, and this is documented friction rather than a
# defect: checkout gives every work/sandbox/circles/ transcript a new mtime, so circle_state
# reports several circles open and the run times out waiting for "transcript: ". Age them —
# `.venv/Scripts/python.exe .claude/skills/run-inner-circling/driver.py age-transcripts` —
# exactly as test_circle_engine.py needs.
#
# Its own header (ui/tests/circle_test.py:28-52) documents a SEPARATE reason two verbs are
# excluded from it: /issue-apply and the node-id-first /issue status shell out with no
# --dry-run and no root override, so nothing in-process can redirect them at a scratch copy.
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
# R325) and prompt_build.part_identity_tail_render() renders a part's recorded
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
# v85, 2026-08-27 — --simple joins the redraw. The diagram gained a
# readable cut (call/spawn arcs only, constant reads to the table); it is a
# RENDERING mode, so it shares --check's fingerprint and needs no dump of
# its own, but its .svg/.html rot exactly as the other four would if this
# case did not regenerate them together. Ten artifacts now, not six.
# ui/ JOINS THE TRIGGER in the same version, ruled by the operator: the
# diagram has drawn ui/ since R316 while this case still named the two
# directories it had when written. One install, so one number.
# WRITTEN AS v81 ON THE BRANCH AND RENUMBERED HERE: master reached v84 while
# the branch was open, which is the ordinary case for a version that is a
# single integer in one file. The number is taken at the MERGE, exactly as
# an R-number is (R238) — a branch that keeps one ships a stale mark, and a
# stale mark means system_git_hooks_ensure() installs nothing.
# Installed from the main checkout after the merge (--git-setup), never
# from the worktree that wrote it.
# v87, 2026-08-27 (R365) — a case for ui/tests/test_issue_draw.py. It
# moved work/graph/ -> ui/, started shipping, and is now RUN BY circle.py at
# every live /close. Its own trigger has to include coordinator/circle.py,
# which *ui/* does not match, because the half that breaks packaging is the
# CALL SITE's path literal and it lives there. The redraw is gated
# `if args.live:`, so no dry-run end-to-end suite can reach it.
# v107, audit-register.md #14 — three new .claude/skills/ cases (install,
# my_commit, publish), landed with test_hook_template.py's widened suites()
# in the same commit; see that case block's own comment.
# v108, audit-register.md #40(b) — six suites added as self-triggers on
# their own case blocks (test_issue_gate.py, test_backfill.py,
# test_convergence_queue.py, test_issue_prompt_projection.py,
# test_spend_report.py, test_strip_malformed_annotations.py); see those
# case blocks' own comments.
# v110, B97 (2026-09-02) — the venv-sharing fix becomes $PY's own default.
# A worktree has no .venv of its own, so `PY=".venv/..."` fell through to
# bare `python` (the system interpreter, no anthropic, no tomli) unless a
# session prepended the main tree's .venv to PATH by hand. $PY now tries the
# MAIN TREE's .venv, found via git-common-dir, before that last resort —
# the same lookup coordinator/system_lint_verify.py's venv_python() and
# .claude/skills/my_commit/my_commit.py's own venv-finder already use.
# ALSO v110, found blocking the same commit: the Block 1-4 assembly split
# (group_context/group_attention/parts_prompt_projection/role_attention/
# role_context/topic_prompt_projection/group_add, all 2026-09-02) had shipped six
# passing suites wired into nothing — test_hook_template.py's stray-suite
# check refuses this, and nothing had touched gitrepo.py since they landed
# to trip it. A new case block below wires all six.
# v134, 2026-09-04: two branches landed the same night — B91's grounding check
# (its suite wired here as v133) and B100's logbook_/transaction renames (as
# v132). The marks were assigned apart on purpose so the merge would CONFLICT
# here rather than fuse two different hook bodies under one mark; this is the
# reconciled mark, and --git-setup after the merge installs it.
# v135, the same night: B96's short_term_manager case (its branch took v134 in
# parallel with the two above; the merge reconciled it here, one step up).
# v136, B95 (R433, 2026-09-04): the RULING record — rulings/R<nnn>.toml through
# coordinator/ruling_manager.py — and its suite; the RULINGS.md trigger below
# became rulings/ at the same build. Taken one above v135 on purpose: a
# parallel branch holds v135, and the merge reconciles here, not by fusing.
# v137, B101 (R447, 2026-09-04): work/instrument/LOG.md joins the logbook
# trigger — the E rule in logbook_ruling_verify.py holds it to shape, and a
# branch's E entry is a work/pending/instrument/ fragment the same checker
# reads (the *work/pending/* leg already covers it).
# v138, 2026-09-04: the audit's subject-to-trigger gaps closed — nine module
# paths join the cases whose suites already cover them (audit-register #2, #6,
# #11). No new suite; the durable check (test_hook_template asserting every
# suite's subject reaches its case) is queued in NEXT.md.
# v139, B104, 2026-09-04: live_probe.py retired — no production caller (the
# three suites its man page named as callers were retired 2026-08-09..15,
# quote_verify.py never imported it, work/graph/test_coordinator_draw.py
# already asserted it offline). Its case dropped along with the module,
# its man page and its own suite.
# v140, B103, 2026-09-04: memory/issue_prompt_projection.py joins the
# practice case's trigger — the one real gap test_hook_template.py's new
# fifth property (subject-to-trigger) found once built. See that property's
# own docstring for the mechanism (hook simulation via fnmatch, not a
# substring guess).
# v141, B103, audit-register 2026-09-04 #5: a new case for
# .claude/skills/run-inner-circling/driver.py + its new suite,
# test_driver.py — the argv-assembly probe the register named as missing,
# alongside its sibling skills' own cases just above.
# v152, B117 stage 6 (2026-09-07): the groups/ case (every group's tree checked), the band's
# engine probe beside the lookup's own, groups/groups.toml as a delegate trigger.
# v153, B120 stage 1 (R468, 2026-09-07): groups/groups.toml retired for groups/<name>/group.toml —
# the delegate trigger names the descriptor, live and shipped.
# v154 (2026-09-07): work/tools/test_htmlify_spy.js joins the htmlify trigger. It is the fake layout
# the contents spy is RUN against, so editing it alone must run the suite it belongs to — a fixture
# outside its own trigger is the "triggered but uninvoked" defect from the other side.
# v156, D101 (2026-09-07): docs/BNF.md is GENERATED. The grammar's sources — docs/PRODUCT_BNF.md and
# every groups/<name>/GROUP_BNF.md — and its composition share one trigger, and the guard runs ahead
# of the conformance harness: a verdict on a docs/BNF.md that is not its sources' composition is a
# verdict on a file nobody wrote.
# v158, 2026-09-07. Three arms, one cause: a path or a file moved and whatever matched the old one
# went quiet rather than loud. (1) work/tools/test_storage_audit.py shipped with its tool and was
# wired to nothing, failing the stray-suite check on master and blocking the one file able to fix it
# — the fourth recurrence of that shape. (2) A *test_*.py* arm now runs the stray-suite detector, so
# the commit that ADDS a suite is the commit that catches it stranded. (3) The packaging arm gains
# scan.py and the three never-ship LISTS: packaging/ignore.txt fired no check at all, which is how
# its record patterns stayed root-anchored through B117 while every delegate-less record path
# resolved `root` — copy the live bytes into the bundle — instead of `blocked`.
# v159, 2026-09-07 (audit #17). Body change is a COMMENT only — the v138 case's stated ground for
# riding atomic_write.py on this trigger ("test_TRANSACTION_CLASS exercises it, crash states
# included") was false from v138 until now. The suite gained the case that makes it true; the mark
# moves because the rendered body did, and an unbumped mark leaves the installed hook stale in a
# way only HOOK_MARK's own difference would have caught.
# v174, 2026-09-07 (R485): coordinator/ifs_model.py -> coordinator/record_model.py. The
# name is the only thing that was IFS about it; the RECORD it models is every group's. TWO arms
# carry the literal path — the register-gate case and the SHORT_TERM case — so renaming one and
# not the other would leave a case matching nothing, silently, which is this changelog's most
# frequent entry.
#
# v162, 2026-09-07 (R486): coordinator/vetting.py ->
# coordinator/proposal_vetting.py and coordinator/roster.py -> coordinator/part_roster.py, under
# R435. FIVE arms carry a literal path between them — the annotation-surface case, the
# practice/annotation case, the roster case, the record-paths case, and two `run` lines — and the
# same trap as v174 above applies to every one of them.
#
# v163, 2026-09-08 (E36): a case for packaging/conform_packaging.py and its new
# suite. The script had NO trigger at all, which is how a default action that
# spends money and overwrites the publish gate's record kept an unimplemented
# --help — nothing ran a probe over its arguments because there was no probe
# and nothing would have invoked one.
HOOK_MARK = "# inner-circling pre-commit v174"
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
# v9 replaces the inline ast.parse with coordinator/system_lint_verify.py. TWO
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
# template — the one system_git_hooks_ensure() actually installs — still had all four.
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
# circles/circle_observation_log.toml, a real register with its own module and
# its own suite. BOTH ends added, because v45 is the standing lesson here —
# a new module inside a trigger whose case never INVOKES its probe reports
# nothing and looks green. The *self/* glob already caught the data file;
# it never caught coordinator/circle_observation_manager.py.
#
# v63 AND NOT v62, deliberately. .git/hooks is shared with every worktree,
# and the installed hook already read v62 while master's template read v61
# — an uncommitted bump in the main checkout, on no branch this sweep could
# see. Two templates at v62 with different bodies is the silent case:
# system_git_hooks_ensure() reinstalls only when HOOK_MARK DIFFERS, so the tree that
# already says v62 would skip the reinstall and this file's new trigger
# would never install. Skipping a number costs nothing here — HOOK_MARK is
# a version, not a contiguous register — while sharing one costs a trigger
# that reports nothing. If the other v62 lands after this, the two
# templates CONFLICT on this line, which is the outcome to want.
#
# check_best_practices.py, circle.py or REGISTER_CLASS.py — the CODE the
# PRACTICE LIFECYCLE build actually lives in — touched none of those paths
# and the whole block, including its own new tests, silently did not run.
# system_lint_verify.py still caught it (line 413's *coordinator/* case, unchanged)
# but that is compile-and-import only; it would not have caught the
# **Entries: N** tally bug this same build found, which only a real test
# run surfaces. Added to the trigger: check_best_practices.py, circle.py,
# REGISTER_CLASS.py (the practice register's one reader/writer, per its own
# module docstring), and the two new test files themselves — editing a
# test without touching what it tests must not silently stop running it.
#
# v15 (v14 was superseded same-session, before ever being committed) adds
# test_remember_manager.py, test_strip_malformed_markers.py, and test_self_mark.py
# to the SAME case block v13 fixed — all three exercise
# circle.py's annotation system directly (remember_apply/
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
# pre-existing gap as test_remember_manager.py's own v14 fix: this file existed,
# tested real behavior, and was simply never wired in. Caught now because
# this session's vet-loop generalization (request retired from
# unruled_proposals()/convergence_queue(), each gaining its own coalesce/stage
# path — see v17) rewrote a chunk of what it covers.
#
# v19 adds coordinator/mark_proposals.py and coordinator/test_mark_
# proposal_manager.py to both trigger and invocation, same reason as v17 — a
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
# `ui/circling.py --selftest`: system_lint_verify.py's own SCOPE was
# `coordinator/` and `scripts/` only, and neither self-test (circling.py
# --selftest, ui/tests/test_circle_engine.py) was invoked anywhere but by hand.
# Same shape as v13's gap, one directory later. ui/*.py joins the
# compile+pyflakes case below, and a new case runs both self-tests —
# test_circle_engine.py needs `anthropic` (it imports circle.py), so
# unlike every other invocation in this hook it is called through
# `.venv/Scripts/python.exe` explicitly rather than bare `python`, which
# system_lint_verify.py's own docstring already measured as the system 3.10 on
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
# unconditional file_line_endings_verify (stdlib-only, and the one check that
# must run even where .venv does not exist yet) and system_lint_verify (stdlib-
# only, and it resolves .venv itself, by its own docstring — that
# self-resolution is the reason bare python was survivable here at all).
# v51 also closes v49's recorded debt: test_help_system.py (claimed by
# v35's comment, invoked by nothing) joins the practice case's pattern
# and body, run green — 77 checks — before wiring.
#
# v50 RETARGETS the lint trigger onto system_lint_verify.CODE_DIRS — memory/ in,
# scripts/ out — and wires coordinator/tests/test_system_lint_verify.py beside the lint
# it guards. The trigger was a hand-copy of the code-directory policy and
# had rotted (the 2026-08-18 review's tier 3 #25): memory/ has held
# running code since R203 while the pattern still named scripts/, empty
# of code since 2026-08-18 — so a commit touching only memory/ ran no
# lint at all (the very NameError class system_lint_verify was built for, in the
# one directory the trigger could not see), while the scripts/ leg
# triggered a linter that does not scan it. The policy now has ONE owner
# (system_lint_verify.CODE_DIRS, stdlib-only and importable from every checker,
# bare-python included); file_line_endings_verify and ruling_sweep derive from
# it, and test_system_lint_verify asserts the agreement — this sh pattern
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
# (1) NEW coordinator/tests/test_TRANSACTION_CLASS.py + coordinator/tests/test_nightly_lock.py,
# narrow-triggered on TRANSACTION_CLASS.py/nightly.py and themselves (the v46
# shape: both build their own temp trees — and rebind nightly.LOCK — so
# they need no other path to have moved and can never race a real
# nightly). The machinery they pin shipped with NO probe at all, and the
# review found four defects in exactly the states nothing exercised:
# transaction_rollback (journal_rollback then) could not roll back a created file, verify() compared
# the disk against itself, release_lock() deleted another run's live
# lock, and phase0 pinned may_commit=False. The crash states are reached
# by a scripted os.replace failure — the only way they are reachable.
#
# (2) coordinator/transcript_store.py and coordinator/part_mid_term_manager.py join the
# practice/annotation case's PATTERN and BODY with their suites.
# transcript_store left circle.py in phase 1 step 3 (2026-08-16) without
# taking a trigger entry along — the per-stage obligation v31 names — so
# a commit touching only it ran system_lint_verify and nothing else; the resume
# leak fixed one commit ago is precisely what that gap left unwatched.
# part_mid_term_manager.py and test_part_mid_term_manager.py were never in any trigger either.
# Both suites are invoked through the venv interpreter, like every
# post-v40 addition: proven under it, and never hostage to what bare
# `python` resolves to.
#
# v47 CLOSES B49's TWO TRIGGER GAPS, found by /presweep 2026-08-17, asked
# for 2026-08-18. Both are the v13 failure shape, in its two
# distinct forms — and the second form is the one this changelog keeps
# rediscovering.
#
# (1) TRIGGER ONLY. coordinator/remember_manager.py and coordinator/tests/test_remember_manager.py
# were absent from the practice/annotation trigger PATTERN while the body
# already invoked test_remember_manager.py (added 2026-08-12 beside the E06
# bracket-annotation fix). So the suite ran often, but only ever as a
# PASSENGER — when some other path in that long case matched. A commit
# touching remember_manager.py alone fired system_lint_verify.py and nothing else. That was
# masked on 2026-08-17's D23 commit because circle.py, vetting.py,
# record_model.py, parts/ and self/ all match the same case. Masking is not
# coverage, and a part's own private memory register is a poor place to
# learn the difference.
#
# (2) TRIGGER AND INVOCATION BOTH. work/tools/test_bnf_conformance.py was
# in no trigger at all and called from nowhere — the whole v45 defect
# rather than half of it, so both halves land here. It is invoked BEFORE
# bnf_conformance.py in the same case: the probe checks the harness, and a
# broken harness's verdict on docs/BNF.md is not evidence of anything.
# work/tools/ also sits outside system_lint_verify.py's own SCOPE, so nothing
# compiled either file automatically until now.
#
# NOT DONE HERE, deliberately, and recorded so the next presweep does not
# re-report them as new: work/tools/bnf_register_intake.toml is still
# outside this case's pattern, and work/tools/ is still outside
# file_line_endings_verify.py's SCOPE_DIRS. Both are B49's own awareness-only
# footnote; neither was asked for.
#
# v46 ADDS a case for coordinator/tests/test_record_verify.py, 2026-08-18. The
# corruption gate (coordinator/record_verify.py) and its probe shipped that
# day covered by NO invocation at all: system_lint_verify.py compiles them under the
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
# own /close handling, which also runs coordinator/circle_close_verify.py and, live,
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
# same disambiguation family as v42's issue_prompt_projection.py neighbor and
# /help issue-relationship (R218/R219). The practice/annotation trigger's
# explicit pattern follows the rename or a commit touching only the
# renamed module silently stops running the suites that cover it — the
# v13 failure shape.
#
# v42 FOLLOWS check_issues.py to memory/issue_prompt_projection.py —
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
# system_git_hooks_ensure() only reinstalls when HOOK_MARK differs, fixing the
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
# identity read-layer, minimal case, circle_briefing_build, the four-block
# assembly, prompt_messages_render) out of circle.py, and prompt blocks'
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
# with coordinator/proposal_manager.py + test_proposal_manager.py, in both trigger and
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
# synthesis at /close, R167/R168), circle_history_manager.py (the CH- register),
# relationships.py (present since R185 but never a trigger — the v22 gap
# shape, caught here), record_model.py (now carries the register gate,
# R188), and their suites test_inter_circle.py + test_register_gate.py.
# Both suites are network-free: canned model outputs, staging-only, live
# registers byte-verified untouched.
#
# v27 REMOVES coordinator/tests/test_quote_verify.py from invocation — retired
# 2026-08-15 with quote_verify's `relationships` target (ruled: "retire 1
# and 2, successor for 3"); the suite's whole subject was that target, and
# leaving the call would fail every parts/-touching commit on a file that
# no longer exists, the v23/v8/v11 shape again. The LIVE-CITED successor
# lands in the register gate (docs/REGISTER_GATE_DESIGN.md), whose own
# probe suite joins this hook when built. v27 also ADDS
# coordinator/topic_manager.py and coordinator/tests/test_topic_manager.py to trigger and
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
# v25 adds coordinator/block_overlap_verify.py and its own probe suite
# (B39/R158): content delivered in a LOWER-numbered, broader prompt block
# must not repeat in a HIGHER-numbered, more specific one. Triggered on
# the block SOURCES as well as the checker itself — process_core.md, the
# practices register, and parts/ all feed system_blocks(), so a repeat can
# be introduced by editing content that never touches the checker. Added
# from the start rather than shipped once and caught missing later.
#
# v24 adds coordinator/logbook_next_verify.py and coordinator/tests/test_logbook_next_verify.py
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
# that is not incidental to the gap above — system_git_hooks_ensure() managed pre-commit
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
# A WORKTREE HAS NO .venv OF ITS OWN — v110, B97, 2026-09-02. Resolve the
# MAIN TREE's .venv via git-common-dir before falling back to bare python;
# same lookup coordinator/system_lint_verify.py's venv_python() and
# .claude/skills/my_commit/my_commit.py's own venv-finder already use.
if [ ! -x "$PY" ]; then
    GCD=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
    if [ -n "$GCD" ]; then
        MAIN_ROOT=$(dirname "$GCD")
        MPY="$MAIN_ROOT/.venv/Scripts/python.exe"
        [ -x "$MPY" ] || MPY="$MAIN_ROOT/.venv/bin/python"
        [ -x "$MPY" ] && PY="$MPY"
    fi
fi
[ -x "$PY" ] || PY="python"

# AND A SCRIPT THIS TREE DOES NOT HAVE IS NOT A FAILURE. The published package
# ships 6 of the 72 scripts named below — the probes and the dev gates are not
# part of the product — so before v78 a recipient who ran `--git-setup` got a
# hook that refused every commit, naming a test file they were never sent. The
# gates they DO have still run, and still fail the commit when they fail.
# WHERE A REFUSAL GOES — v86, 2026-08-27, ruled by the operator. A check that
# refuses is the moment its reader is most stuck, and the checkers speak to a
# developer. So the output is CAPTURED as well as shown, and on a non-zero exit
# coordinator/gate_report.py writes work/diagnostics/gate_<time>.md — ordinary
# language on the screen, the technical account and a prompt the person may
# choose to send in the file. It opens no socket; the sending is theirs.
#
# STREAMED AND CAPTURED BOTH. `cmd | tee` would report tee's exit status, so
# the status is carried out of the pipeline through a file — POSIX, and it
# keeps a long check printing as it goes rather than in one lump at the end.
GATE_OUT="${{TMPDIR:-/tmp}}/ic-gate-out.$$"
GATE_RC="${{TMPDIR:-/tmp}}/ic-gate-rc.$$"
trap 'rm -f "$GATE_OUT" "$GATE_RC"' EXIT

refused() {{   # $1 = exit code, rest = the check and its arguments
    code="$1"; shift
    if [ -f coordinator/gate_report.py ]; then
        "$PY" coordinator/gate_report.py --code "$code" --out "$GATE_OUT" -- "$@"
    fi
    exit 1
}}

run() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    # THE STATUS HAS TO SURVIVE `set -e` — v92, 2026-08-28. A pipeline stage
    # is a SUBSHELL and inherits errexit, so a FAILING probe killed the brace
    # group before `echo $?` could run. rc then read whatever the PREVIOUS
    # probe left in the file — and the first check of every invocation
    # (file_line_endings_verify) passes and leaves "0" behind. So from the second
    # probe onward a red gate printed its failure IN FULL and the commit went
    # through anyway. Live from v81 (2026-08-27) to here; found 2026-08-28 by
    # a lab merge whose battery said FAIL and committed.
    # Two guards, because either alone suffices and neither is obvious:
    #   `set +e` inside the group  the TRUE exit code is recorded
    #   `rm -f` before it          a group that dies anyway leaves NO file,
    #                              and a missing file reads as 1 rather than
    #                              as the last probe's success. FAILS CLOSED.
    rm -f "$GATE_RC"
    {{ set +e; "$PY" "$@" 2>&1; echo $? > "$GATE_RC"; }} | tee "$GATE_OUT"
    rc=$(cat "$GATE_RC" 2>/dev/null || echo 1)
    [ "$rc" = "0" ] || refused "$rc" "$@"
}}

# AND THE SAME, FOR A SCRIPT WHOSE OWN OUTPUT IS NOISE. `run X >/dev/null`
# at the call site redirected system_git_run() ITSELF, so the note it was about to print
# went with it — one announcement silently absent from the dev tree's own
# hook run, which is how this was caught.
quiet() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    # `|| rc=$?` TESTS the status, so errexit does not fire — v92. This half
    # always DID refuse: the bare command tripped `set -e`, which exits the
    # hook non-zero. It refused SILENTLY, though — the exit happened before
    # `cat "$GATE_OUT"` and before gate_report, so the reader got a failed
    # commit and not one word about which check failed or why. The refusal
    # was never the defect here; the missing account of it was.
    rc=0
    "$PY" "$@" > "$GATE_OUT" 2>&1 || rc=$?
    [ "$rc" = "0" ] || {{ cat "$GATE_OUT"; refused "$rc" "$@"; }}
}}

# v104, 2026-09-01. ADVISORY ONLY — the one case here that never refuses,
# unlike system_git_run()/quiet() above. Some checks decide what BLOCKS a commit;
# this one exists because packaging/scaffold_staleness.py's own answer
# ("might be stale") is a REMINDER, not a verdict — resolving it means
# running packaging/conform_packaging.py, which costs a real paid model
# call, and a commit hook may not spend that for you. The hard gate for
# this same check lives at publish time instead (publish.py's own
# preflight), which is the one moment staleness actually reaches a user.
advise() {{
    [ -f "$1" ] || return 0
    if [ -n "$NOTE" ]; then printf '%s\n' "$NOTE"; NOTE=""; fi
    "$PY" "$@" || true
}}

# FIRST, and unconditional. `.gitattributes` sets `* -text`, so a CR that
# reaches a commit is a CR that reaches every sha256 downstream of it —
# nothing normalises it away. Three files were converted wholesale on
# 2026-08-07 and every other check passed.
run coordinator/file_line_endings_verify.py --staged
# v152, B117 stage 6 (R467, 2026-09-07): A RECORD IS A GROUP'S TREE, and there is more than one.
# The corruption sweep walks every groups/<name>/ itself; the self-check and the issue gate
# are per group, so each group present beside the default gets its own run — a damaged file in
# groups/band/ refuses a commit exactly as one in groups/ifs/ does. The default group's own
# runs are the two cases below (unchanged); this loop covers the others.
case "$FILES" in *groups/*)
    NOTE="  pre-commit: a group's record touched — every group's tree is checked"
    run coordinator/record_verify.py
    for gdir in groups/*/; do
        gname="${{gdir#groups/}}"; gname="${{gname%/}}"
        [ "$gname" = "ifs" ] && continue
        [ -d "$gdir/parts" ] || continue
        run coordinator/circle_audit.py --selfcheck --group "$gname"
        [ -d "$gdir/issues" ] && run memory/issue_gate.py "$gdir/issues"
    done
esac

case "$FILES" in *issues/*|*coordinator/tests/test_issue_gate.py*\
|*memory/issue_gate.py*|*memory/issue_schema.py*)
    # v138, audit-register 2026-09-04 #2: the gate and THE ONE READER/WRITER
    # OF A NODE were gated by nothing but the lint sweep — this case fired on
    # the DATA and on the suite, never on the two modules. Added to the trigger.
    NOTE="  pre-commit: issues/ or its gate/schema touched"
    run memory/issue_gate.py
    run coordinator/tests/test_issue_gate.py
esac

# v174, 2026-09-09, the operator's ruling ("Narrow it"). THE RECORD'S OWN CHECKS, SPLIT
# OUT FROM THE CODE SUITES BELOW. One case used to carry both: its 92 patterns matched
# either a record path or one of 88 module paths, and matching EITHER ran all 43
# invocations. So a live close — whose two commits carry short_terms, the registers and
# nothing else — ran 37 test suites for modules the commit could not have changed.
# Measured on circle 2026-09-09_1122: 57 scripts fired per commit, and re-running them
# took ~85s against a phase of 57.28s, so the battery WAS the phase.
#
# THE SPLIT IS BY WHAT A CHECK READS, NOT BY WHERE ITS FILE LIVES. This case runs
# whatever reads the RECORD, so it keeps the full union trigger and fires exactly as
# often as the old single case did. The case below keeps the module patterns alone.
# A commit touching code AND records fires both, and nothing runs twice: the seven
# invocations here are not repeated there.
#
# test_inter_circle.py IS HERE, AND IT IS THE EXPENSIVE ONE (~24s). It stays on the
# record trigger because it REHEARSES against the newest CLOSED circle —
# `ots[-1]` after filtering for a close report — and snapshots every live register to
# prove the rehearsal wrote nothing. A records-only commit is precisely when a new
# closed circle has appeared, so this is the moment its rehearsal has something new to
# say. Moving it below would have been the largest single saving and the one real loss
# of detection; it is not a code-only suite despite being a suite.
#
# THE OTHER EIGHT SUITES THAT READ OUTSIDE THEIR OWN TEMP TREE stay below, deliberately:
# four read `packaging/scaffold/` and four read `coordinator/process_core.md`, and a
# close commit touches neither. Their triggers cover those paths in the case below.
# TWO FLAGS, ONE MODULE LIST. The record checks must ALSO fire for a code change — a
# module that reads the record is exactly where a record check earns its keep — so the
# naive split (two cases, two pattern lists) would have needed the 88 module patterns
# written twice and kept in step by hand. That is the duplicate-fact defect
# system_unique_home_verify.py exists to refuse, in a file it cannot see into. Flags
# instead: the record trigger is the data patterns OR the module list, and the module
# list is written once.
#
# `if`, NOT a `&&` with a brace group — the hook runs under `set -e`, where a && whose
# test fails is a non-zero command at the top level and kills the hook. The two blocks
# below are the whole reason this is spelled out.
IC_RECORD=""
IC_CODE=""
case "$FILES" in *parts/*|*self/*|*circles/*.toml*)
    IC_RECORD=1
esac

# v174: THE CODE SUITES. Module paths only — the three record patterns
# (*parts/*, *self/*, *circles/*.toml*) are gone from this trigger and live in the case
# above. `*packaging/scaffold/groups/*` replaces the two narrower scaffold patterns this
# case used to carry, so a scaffold edit under parts/, circles/ or issues/ still reaches
# test_scaffold_delegates.py — those were previously reached only by the `*parts/*` and
# `*self/*` patterns now removed, which is the one gap this split could have opened.
case "$FILES" in *groups/*/group.toml*\
|*coordinator/practice_manager.py*|*coordinator/practice_verify.py*|*coordinator/circle.py*\
|*coordinator/command_surface.py*|*coordinator/llm_client.py*\
|*coordinator/prompt_build.py*|*coordinator/annotations.py*|*coordinator/propose_lifecycle.py*\
|*coordinator/remember_expand.py*|*coordinator/tests/test_remember_expand.py*\
|*coordinator/recall_index.py*|*coordinator/tests/test_recall_index.py*\
|*coordinator/embed_store.py*|*coordinator/process_core.md*\
|*coordinator/help_system.py*|*coordinator/commands.py*\
|*coordinator/proposal_vetting.py*|*coordinator/circle_rounds.py*\
|*coordinator/REGISTER_CLASS.py*|*coordinator/tests/test_practice_verify.py*\
|*coordinator/tests/test_practice_annotations.py*|*coordinator/proposal_manager.py*\
|*coordinator/tests/test_proposal_manager.py*|*coordinator/topic_manager.py*\
|*coordinator/tests/test_topic_manager.py*|*coordinator/inter_circle.py*\
|*coordinator/part_dreaming.py*|*coordinator/circle_synthesis.py*\
|*coordinator/tests/test_inter_circle.py*|*coordinator/circle_history_manager.py*\
|*packaging/scaffold/groups/*|*coordinator/tests/test_scaffold_delegates.py*\
|*coordinator/JOURNAL_CLASS.py*|*coordinator/tests/test_journal_class.py*\
|*coordinator/tests/test_circle_history_manager.py*\
|*coordinator/tests/test_part_dreaming_grounding.py*\
|*coordinator/circle_observation_manager.py*\
|*coordinator/tests/test_circle_observation_manager.py*\
|*coordinator/circle_journal_manager.py*\
|*coordinator/tests/test_circle_journal_manager.py*\
|*coordinator/setting_manager.py*|*coordinator/tests/test_setting_manager.py*\
|*coordinator/system_setting_verify.py*\
|*coordinator/process_core.md*\
|*coordinator/providers.py*|*coordinator/tests/test_providers.py*\
|*coordinator/backfill.py*|*coordinator/tests/test_register_gate.py*\
|*coordinator/record_model.py*|*coordinator/register_gate.py*|*coordinator/tests/test_annotations.py*\
|*coordinator/remember_manager.py*|*coordinator/tests/test_remember_manager.py*\
|*coordinator/remember_prompt_projection.py*|*coordinator/remember_list_projection.py*\
|*coordinator/quote_as_lands.py*|*coordinator/tests/test_quote_as_lands.py*\
|*coordinator/process_core.md*|*coordinator/part_roster.py*\
|*coordinator/tests/test_annotation_exemplars.py*\
|*coordinator/transcript_store.py*|*coordinator/tests/test_transcript_store.py*\
|*coordinator/part_mid_term_manager.py*|*coordinator/tests/test_part_mid_term_manager.py*\
|*coordinator/tests/test_proposal_vetting.py*|*coordinator/tests/test_issue_commands.py*\
|*coordinator/tests/test_circle_rounds_display.py*|*coordinator/llm_client.py*\
|*coordinator/token_count.py*|*coordinator/tests/test_token_count.py*\
|*coordinator/tests/test_llm_client.py*\
|*coordinator/tests/test_issue_status_cmd.py*|*coordinator/tests/test_help_system.py*\
|*coordinator/tests/test_dispatch_partition.py*|*coordinator/tests/test_issue_add.py*\
|*coordinator/tests/test_backfill.py*\
|*coordinator/tests/test_issue_prompt_projection.py*|*coordinator/tests/test_spend_report.py*\
|*coordinator/tests/test_strip_malformed_annotations.py*\
|*coordinator/LLM_response_disassembler.py*\
|*coordinator/tests/test_llm_response_disassembler.py*\
|*memory/issue_status.py*|*memory/issue_commands.py*|*coordinator/PROPOSE_CLASS.py*\
|*coordinator/process_core_prompt_projection.py*|*coordinator/quote_verify.py*\
|*memory/issue_prompt_projection.py*)
    IC_RECORD=1
    IC_CODE=1
esac

# THE RECORD'S OWN CHECKS. Fires for a record change OR a code change, so this is
# exactly as often as the single case fired before the split.
if [ -n "$IC_RECORD" ]; then
    NOTE="  pre-commit: the record, or code that reads it, was touched"
    run coordinator/circle_audit.py --selfcheck
    run coordinator/practice_verify.py
    run coordinator/logbook_ruling_verify.py
    run memory/issue_prompt_projection.py
    run coordinator/quote_verify.py
    run coordinator/system_setting_verify.py
    run coordinator/tests/test_inter_circle.py
fi

if [ -n "$IC_CODE" ]; then
    # v138, audit-register 2026-09-04 #2/#6/#11: five modules whose SUITES this
    # case already invokes (test_issue_status_cmd, test_issue_commands,
    # test_proposal_manager, test_practice_verify, quote_verify itself) were
    # gated only by the lint sweep because their own paths were not in this
    # pattern — editing the PROPOSE grammar or the one atomic status writer
    # ran no suite. Subject-to-trigger, the missing fifth property.
    # v140, B103, 2026-09-04: memory/issue_prompt_projection.py was the one
    # real gap the fifth property (test_hook_template.py) found once built —
    # it already triggered test_working_set_manager.py (a separate, real
    # reason) but never its OWN suite, test_issue_prompt_projection.py,
    # which this case invokes.
    # v107, audit-register.md #40(b): the five suites above (test_backfill,
    # test_convergence_queue, test_issue_prompt_projection, test_spend_report,
    # test_strip_malformed_annotations) were invoked here but not
    # self-triggering — editing only the test file, with no change to its
    # subject, fired nothing. 73 of 80 suites in the tree self-trigger;
    # these were exceptions, not a deliberate design (test_spend_report.py's
    # own comment reasoned its subjects already fire this case, which
    # covers a subject change but not a test-only edit).
    NOTE="  pre-commit: parts/, self/ (incl. self/best_practices.toml), or its
  implementation (practice_manager.py, practice_verify.py/circle.py/REGISTER_CLASS.py/
  proposal_manager.py)
  touched"
    # live_probe.py, test_check_issues.py, test_working_set.py DROPPED —
    # retired 2026-08-09, see the v11 note.
    # v51: EVERY invocation of project code goes through the venv — the
    # standing rule ("never the system interpreter") this hook violated
    # on ~20 lines while its own comments measured bare `python` as the
    # system 3.10. Four blocks had already been rerouted one incident at
    # a time; the rest carried the same exposure (anything importing
    # anthropic, pyflakes, or tomli on 3.10). The two stdlib-only checks
    # DESIGNED for bare python keep it: file_line_endings_verify (must run
    # even where .venv does not exist yet) and system_lint_verify (resolves
    # .venv itself, by its own docstring).
    # v52: nightly.py is renamed circle_audit.py (the 2026-08-19 ruling). The
    # fallback exists ONLY for the merge window, while a live tree may
    # still carry the old name; a v53 may drop it.
    # v105: markers.py is renamed annotations.py (D-e, 2026-09-01) — the
    # trigger glob and the two invocation lines below follow the module;
    # no merge-window fallback needed, unlike v52, because a stale-named
    # invocation here fails loudly (file not found) rather than silently.
    # (Renumbered from this branch's own v103/v104 at the merge — v103 and
    # v104 were independently taken on master by the test_redaction.py
    # wiring and the scaffold-staleness advisory; this tree's redundant
    # copy of the former was dropped rather than kept as a duplicate case.)
    # v174: circle_audit --selfcheck moved to the RECORD case above — it reads
    # parts/ and self/, so it belongs on the trigger that fires for them.
    # v130, 2026-09-03: settings.py -> setting_manager.py + system_setting_verify.py (B99's
    # residue, Q-6); the case runs the verifier and the register's suite.
    # v129, 2026-09-03: redaction.py -> redaction_manager.py + stream_redaction.py (the pipeline,
    # the Ticker's session redaction folded in) — stage 18d; test_redaction.py covers both.
    # v128, 2026-09-03: the nine registers' modules are <CLASS>_manager.py (stage 18c) —
    # proposal, proposal_group, topic, remember, circle_history, circle_observation,
    # instrument, part_mid_term, dream_history; suites and man pages with them.
    # v132, 2026-09-04 (B100, R445): ledger_ruling_verify.py -> logbook_ruling_verify.py and
    # ledger_next_verify.py -> logbook_next_verify.py, their suites with them — LOGBOOK is the
    # BNF's word for the four development files, LEDGER a memory's shape (R444). Trigger and
    # invocation lines both follow.
    # v127, 2026-09-03: self_schema.py -> REGISTER_CLASS.py, propose_class.py -> PROPOSE_CLASS.py,
    # transaction.py -> TRANSACTION_CLASS.py with their suites (stage 18b, Q-5).
    # v126, 2026-09-03: the nine check_*.py verifiers are *_verify.py (B99 stage 18a) —
    # file_line_endings, record, circling, block_overlap, quote, system_lint,
    # system_unique_home, ledger_ruling, ledger_next; suites and man pages with them.
    # v125, 2026-09-03: remember_manager.py's two projections are remember_prompt_projection.py and
    # remember_list_projection.py (stage 17b); test_remember_manager.py covers all three.
    # v124, 2026-09-03: the four *_projection.py are *_prompt_projection.py (F5, stage 17a),
    # suites and the man page with them.
    # v123, 2026-09-03: system_layer_verify (no upward imports, F7/R10) and
    # system_name_verify (a new public def carries its class word, R441) ride
    # system_lint_verify's trigger — B99 stage 16.
    # v133, 2026-09-04: B91 — part_dream()'s grounding check (a silent part's
    # memory, the overlap heuristic) has its own suite; it rides this case
    # because part_dreaming.py already triggers it.
    # v122, 2026-09-03: circling.py's self_test() is ui/tests/test_circling_selftest.py
    # (stage 15); the hook runs the file, not the flag.
    # v121, 2026-09-03: rounds.py -> circle_rounds.py with its suite (stage 13, R7).
    # v120, 2026-09-03: circle_close.py is the close STEP (12b) and joins the
    # open-time-reports case; the verifier's own case runs test_circle_close_verify.
    # v119, 2026-09-03: circle_close.py -> circle_close_verify.py, with its suite
    # (cohesion re-homing stage 12a, R435); the bare name is the close step's now.
    # v118, 2026-09-03: part_dreaming.py and circle_synthesis.py join inter_circle's
    # trigger — DREAMING and SYNTHESIS moved out of the driver (stage 11, B99).
    # v115, 2026-09-03: register_gate.py joins the trigger — record_model.py's gate half
    # (record_tree_compare, REGISTERS, the register checks) moved there (stage 9, B99).
    # v114, 2026-09-03: propose_lifecycle.py joins the trigger — annotations.py's
    # PROPOSE staging half moved there (cohesion re-homing stage 8, B99); its
    # suites (test_proposal_manager, test_convergence_queue, test_annotations ...) are
    # already invoked by this case.
    # v113, 2026-09-03: check_best_practices.py SPLIT into practice_manager.py (the
    # register, stage 7a) and practice_verify.py (this verifier, stage 7b — R435,
    # R440). Both join the trigger; the invocations follow the verifier's new name.
    # v174: practice_verify, logbook_ruling_verify, issue_prompt_projection and
    # quote_verify all READ the record, so they moved to the record case above.
    # Their SUITES stay here — those build their own bytes and test the code.
    run coordinator/tests/test_practice_verify.py
    run coordinator/tests/test_practice_annotations.py
    run coordinator/tests/test_issue_prompt_projection.py
    # test_quote_verify.py RETIRED 2026-08-15 with the relationships
    # target (v27) — successor probes arrive with the register gate.
    run coordinator/tests/test_topic_manager.py
    run coordinator/tests/test_register_gate.py
    # v62: the CIRCLE_OBSERVATION register (R256). Its own suite,
    # because test_register_gate.py runs on bytes it builds itself and so
    # cannot notice that the 30 migrated records are still whole.
    run coordinator/tests/test_circle_observation_manager.py
    # v142, B94, 2026-09-04: the CIRCLE_JOURNAL register. Its own suite, same
    # reason as circle_observation's above — test_register_gate.py alone cannot
    # exercise render_new()'s provenance/chain discipline or the scaffold
    # round trip. The suite landed one commit before this case wired it in —
    # the exact "triggered and uninvoked" defect v45 named, caught this time
    # before a second commit, not after one.
    run coordinator/tests/test_circle_journal_manager.py
    # v174: test_inter_circle.py moved to the RECORD case above — alone among the
    # suites here it rehearses against the newest CLOSED circle and snapshots every
    # live register, so a records-only commit is exactly when it has something new
    # to check. It is also the most expensive script either case runs (~24s).
    # v133, 2026-09-04: B91's grounding check on a part's DREAMING memory.
    run coordinator/tests/test_part_dreaming_grounding.py
    # v56, B54: the transcript safety net. Its detect+repair moved out of
    # circle_audit's phase structure so the LIVE close path could reach it at
    # all, so its probe rides the case its two callers already trigger.
    run coordinator/tests/test_backfill.py
    # v111, 2026-09-02: the reply's one reader. Every suite in this case
    # that fakes a model call now hands back its Reply, so the module rides
    # the case those suites already trigger.
    run coordinator/tests/test_llm_response_disassembler.py
    # v146, 2026-09-06 (B109): every packaging/scaffold/self/*.toml delegate loads to
    # the document its manager builds when the file is absent. Deterministic and free,
    # where the ~$1 LLM audit that had been the only check is neither -- it waved a
    # header comment into proposals.toml that broke exactly this.
    run coordinator/tests/test_scaffold_delegates.py
    # v146 also: B105 (2026-09-05) landed these two suites on a worktree branch and
    # never wired them in; the fast-forward merge fired no pre-commit, so nothing
    # noticed until test_hook_template.py ran for this very edit -- the "triggered
    # and uninvoked" defect v45 named, one more time.
    run coordinator/tests/test_journal_class.py
    run coordinator/tests/test_circle_history_manager.py
    # test_remember_manager.py/test_strip_malformed_markers.py were missing from
    # this list — both exercise circle.py's annotation system directly
    # (remember_apply/apply_self_remember/extract_markers/route_markers/
    # strip_malformed_markers) and belong exactly where circle.py already
    # triggers this case. Added 2026-08-12 alongside the E06 bracket-
    # annotation fix these two files cover.
    run coordinator/tests/test_remember_manager.py
    # v57: QUOTE-AS-MARK (R155, routed 2026-08-19). NEW MODULE, added to
    # the trigger AND the invocation in the same change — v19's rule, and
    # v45's lesson about the other order (triggered, uninvoked, crashing
    # unnoticed for a day). It rides this case because its subjects are
    # already here: circle.py's Self> loop calls it, and it writes
    # through remember_manager.py, whose cap it changed.
    # v109: quote_as_mark.py is renamed quote_as_lands.py (D77, ruling,
    # 2026-09-01) — the module's own name still carried the retired word
    # MARK; "lands" was already its live vocabulary (LANDS_CLASS,
    # lands_text(), the record's own class = "lands"). No merge-window
    # fallback, same reasoning as v105 (annotations.py): a stale-named
    # invocation here fails loudly rather than silently.
    run coordinator/tests/test_quote_as_lands.py
    # v63: the ANNOTATION SURFACE (R254/R255). process_core.md and
    # part_roster.py join THIS case because they are what the parts are
    # actually taught. Both were already triggered elsewhere — v45's
    # block-overlap case and the owner-name sweep for process_core.md, the
    # roster case for part_roster.py — but by nothing that reads the GRAMMAR,
    # so a change rewriting every part's annotation instructions ran no
    # probe that could tell whether the forms still parsed. The suite
    # parses process_core.md's OWN exemplars through the real grammar, so
    # the taught form and the parsed form cannot drift apart: that
    # divergence is E09's shape, and it very nearly recurred the hour
    # R254 was built. Added to trigger AND invocation together — v19's
    # rule, and v45's lesson about the other order.
    run coordinator/tests/test_annotation_exemplars.py
    run coordinator/tests/test_strip_malformed_annotations.py
    # v131, B98 (2026-09-04): test_convergence_queue.py RETIRED with
    # proposal_convergence_queue() — no production caller; the last-stance,
    # unanimity and issue_cmds rules it pinned live in proposal_coalesce()
    # and are pinned by test_proposal_manager.py, which took its two
    # remaining cases (edge normalisation by type; the 1520 grammar check).
    run coordinator/tests/test_proposal_manager.py
    run coordinator/tests/test_annotations.py
    # v96, 2026-08-29: tier A recall — the match rule, spans, caps,
    # every degrade row, the BLOCK-4-only placement invariant.
    run coordinator/tests/test_remember_expand.py
    # v98, 2026-08-30 (R400-R402): part-initiated recall — the grammar,
    # the corpora, the throttle, the resume round-trip, and the two
    # structural journal-unawareness greps. FAKE embedder: the gate
    # needs neither model nor network.
    run coordinator/tests/test_recall_index.py
    # v66: the room/record split in rounds.py — see the v66 note above.
    run coordinator/tests/test_circle_rounds_display.py
    # v66: Self's retry ladder over the transport — see the v66 note above.
    run coordinator/tests/test_llm_client.py
    # v93: work/logs/spend_<OT>.json (R380). ITS SUBJECT RUNS
    # ONLY AT A LIVE CLOSE — a dry-run circle takes the `not live` branch on
    # the function's first line, so test_circle_engine.py exercises the guard
    # and never the write. Added to the TRIGGER and the INVOCATION together,
    # which is v19's rule and v45's lesson; its subjects, circle.py and
    # llm_client.py, already fire this case.
    run coordinator/tests/test_spend_report.py
    # v93: the settings register (R379) and the length rule it now owns.
    # test_setting_manager.py SHIPPED UNINVOKED — it merged to master with no case
    # naming it, so from the day it was written it reported nothing, which is
    # precisely the v45 defect it would itself have caught elsewhere. Found by
    # test_hook_template.py's stray-suite check, which only runs when this
    # file is touched. process_core.md joins the trigger because setting_manager.py
    # now gates its length rule against a literal being typed back in.
    # v174: system_setting_verify moved to the RECORD case above — it reads
    # self/settings.toml. Its suite stays here.
    run coordinator/tests/test_setting_manager.py
    # v94: the provider socket (R382 stage 2, R383's closed registry). Its
    # subjects — llm_client.py, prompt_build.py, circle.py — already fire this
    # case; trigger and invocation land together, v19's rule.
    run coordinator/tests/test_providers.py
    # v67: the counter that replaced chars//4 — see the v67 note above.
    run coordinator/tests/test_token_count.py
    # v48: the resume parser's room/record split and the mid_term lock
    # toggle; v49: the vetting approval contracts and the two suites
    # v36's comment always claimed here.
    run coordinator/tests/test_transcript_store.py
    run coordinator/tests/test_part_mid_term_manager.py
    run coordinator/tests/test_proposal_vetting.py
    run coordinator/tests/test_issue_commands.py
    run coordinator/tests/test_issue_status_cmd.py
    # v168, audit-register.md #3 (2026-09-08). test_issue_status_cmd.py asserts commands.py's
    # ORCHESTRATION with subprocess.run patched, and says so in its own header — so the writer
    # below it (the rename, the status field, the history line, the untracked-file fallback) was
    # executed by nothing. This suite drives it for real on a synthetic node in a temp directory
    # under work/, and asserts the name and the field move TOGETHER, which is the half-apply the
    # gap could ship.
    run coordinator/tests/test_issue_status_write.py
    # v51 closes v49's recorded debt: test_help_system was claimed by
    # v35's comment and invoked by nothing — 77 checks, run green before
    # wiring, riding the case its subject (help_system.py) already
    # triggers.
    run coordinator/tests/test_help_system.py
    # v68: the two probes the 2026-08-21 series added (see HOOK_MARK's note).
    run coordinator/tests/test_dispatch_partition.py
    run coordinator/tests/test_issue_add.py
fi

# v110, found while building B97: the Block 1-4 assembly split of 2026-09-02
# (group_context.py/group_attention.py out of prompt_build.py;
# parts_prompt_projection.py, role_attention.py, role_context.py,
# topic_prompt_projection.py out of the modules they were named for; group_add.py
# new) shipped six passing suites and wired none of them in -- test_hook_
# template.py's stray-suite check catches exactly this, and would have caught
# it the day it landed had anything touched gitrepo.py since. All six run
# green (checked before adding this block, not assumed). group_add.py's own
# trigger is here rather than a dedicated block like test_issue_gate.py's,
# because group_context.py/group_attention.py already needed one and a
# second block for one more roster-shaped file was not a real split.
case "$FILES" in *coordinator/group_manager.py*|*coordinator/group_context.py*\
|*coordinator/group_attention.py*|*coordinator/parts_prompt_projection.py*\
|*coordinator/role_attention.py*|*coordinator/role_context.py*\
|*coordinator/topic_prompt_projection.py*|*coordinator/prompt_build.py*\
|*coordinator/tests/test_group_manager.py*|*coordinator/tests/test_parts_prompt_projection.py*\
|*coordinator/tests/test_prompt_build.py*|*coordinator/tests/test_role_attention.py*\
|*coordinator/tests/test_role_context.py*|*coordinator/tests/test_topic_prompt_projection.py*)
    NOTE="  pre-commit: the Block 1-4 assembly split (group_context/group_attention/
  parts_prompt_projection/role_attention/role_context/topic_prompt_projection/group_manager) touched"
    run coordinator/tests/test_group_manager.py
    run coordinator/tests/test_parts_prompt_projection.py
    run coordinator/tests/test_prompt_build.py
    run coordinator/tests/test_role_attention.py
    run coordinator/tests/test_role_context.py
    run coordinator/tests/test_topic_prompt_projection.py
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

# v72, R320 (2026-08-23): `work/pending/` joins this trigger. A branch's ruling
# and progress note live THERE now, not at the two logbooks' tails, so a commit
# that adds one must reach the checker that validates it -- otherwise the
# first reading of a malformed pending entry is the merge, which is the one
# moment no hook fires and the reader is not its author. progress.md is here
# for the branch-write refusal, which is the other half of the same rule.
# v136, B95 (R433, 2026-09-04): *RULINGS.md* became *rulings/* — the logbook is
# a directory of R<nnn>.toml files, and a commit adding one on a branch (an
# RNEW-<slug>.toml) must reach the checker that holds it to shape and to the
# branch rule, for the same reason the pending entries did.
# v137, B101 (R447, 2026-09-04): *work/instrument/LOG.md* joins — the fourth
# LOGBOOK, held to the E rule (ids contiguous, dates forward, the three fields)
# and to the branch-write refusal; its pending kind, work/pending/instrument/,
# is inside the *work/pending/* leg already.
case "$FILES" in *rulings/*|*progress.md*|*work/pending/*|*work/instrument/LOG.md*\
|*coordinator/logbook_ruling_verify.py*|*coordinator/tests/test_logbook_ruling_verify.py*)
    NOTE="  pre-commit: rulings/, progress.md, LOG.md, or a pending entry touched"
    run coordinator/logbook_ruling_verify.py
    run coordinator/tests/test_logbook_ruling_verify.py
esac

# v53, B55: the assign step is the one place ids change, and it runs at a
# `git merge` -- which fires NO pre-commit hook. Nothing here can guard the
# assignment itself; what it CAN do is keep the script and its probe honest
# on the way in.
case "$FILES" in *coordinator/assign_ids.py*|*coordinator/tests/test_assign_ids.py*\
|*coordinator/ruling_sweep.py*)
    # v138, audit-register 2026-09-04 #11: ruling_sweep.py is what test_assign_ids
    # reaches for the cross-branch sweep, and had no trigger of its own.
    NOTE="  pre-commit: the id assign step touched"
    run coordinator/tests/test_assign_ids.py
esac

case "$FILES" in *NEXT.md*|*coordinator/logbook_next_verify.py*\
|*coordinator/tests/test_logbook_next_verify.py*)
    NOTE="  pre-commit: NEXT.md or its checker touched"
    run coordinator/logbook_next_verify.py
    run coordinator/tests/test_logbook_next_verify.py
esac

case "$FILES" in *coordinator/block_overlap_verify.py*|*coordinator/tests/test_block_overlap_verify.py*|*coordinator/process_core.md*|*coordinator/prompt_build.py*|*self/best_practices.toml*|*parts/*)
    NOTE="  pre-commit: a prompt block source or its overlap checker touched"
    # Through the venv, not bare `python`: this checker imports circle.py,
    # which imports anthropic, and the hook's `python` is the system 3.10
    # (measured in system_lint_verify.py's docstring). Same reason ui/ is called
    # this way below.
    run coordinator/block_overlap_verify.py
    run coordinator/tests/test_block_overlap_verify.py
esac

case "$FILES" in *docs/BNF.md*|*docs/PRODUCT_BNF.md*|*GROUP_BNF.md*|*work/tools/bnf_compose.py*|*work/tools/test_bnf_compose.py*)
    NOTE="  pre-commit: the grammar's SOURCES or its composition touched"
    # THE GUARD RUNS BEFORE THE CONFORMANCE HARNESS BELOW, and the order is the
    # point: docs/BNF.md is GENERATED (D101), so a conformance verdict on a
    # docs/BNF.md that is not its sources' composition is a verdict on a file
    # nobody wrote. Its own probe runs first, for the same reason the harness's
    # does — a guard that cannot fail is not evidence either.
    run work/tools/test_bnf_compose.py
    run work/tools/bnf_compose.py --check
esac

case "$FILES" in *docs/BNF.md*|*work/tools/bnf_conformance.py*|*work/tools/bnf_known_gaps.toml*|*work/tools/test_bnf_conformance.py*|*work/graph/prompt_grammar_draw.py*)
    NOTE="  pre-commit: docs/BNF.md or its conformance harness touched"
    # The harness's own probe runs FIRST (v47): a broken harness's verdict
    # on docs/BNF.md is not evidence, so checking it before trusting it is
    # the only order that means anything.
    run work/tools/test_bnf_conformance.py
    run work/tools/bnf_conformance.py
    # v101, 2026-08-30: THE GRAMMAR PICTURE IS NO LONGER REDRAWN OR STAGED
    # HERE. v91 added that because prompt_grammar.svg/.html were tracked and
    # nothing kept them current, so they sat stale at HEAD while every gate
    # passed. The operator's answer to the whole class was to stop tracking
    # the drawings — *"stop saving them"* — which removes the staleness the
    # redraw existed to cure, and with it the conflict it caused: a tracked
    # picture that two branches both rewrite conflicts every time, and the
    # question git then asks ("which drawing?") has no human answer.
    # Regenerate by hand when you want to look at one:
    #     python work/graph/prompt_grammar_draw.py
esac

case "$FILES" in *coordinator/dream_history_manager.py*|*coordinator/tests/test_dream_history_manager.py*)
    NOTE="  pre-commit: DREAM_HISTORY touched"
    # R359/B45 — the one writer of Self's history records; its suite proves
    # the bootstrap-once/fold-per-dream contract and that refusals write
    # nothing.
    run coordinator/tests/test_dream_history_manager.py
esac

case "$FILES" in *coordinator/proposal_group_manager.py*|*coordinator/tests/test_proposal_group_manager.py*)
    NOTE="  pre-commit: the proposal coalesce touched"
    # test_proposal_group_manager runs the module selftest itself, then the write path,
    # hash guard and ruled-group survival; test_vetting covers the loop the
    # coalesce presents into. R356/B69, and E22 for why the model call
    # lives at circle.py's checkpoints rather than in the loop these
    # suites drive.
    run coordinator/tests/test_proposal_group_manager.py
    run coordinator/tests/test_proposal_vetting.py
esac

case "$FILES" in *work/tools/htmlify.py*|*work/tools/test_htmlify.py*|*work/tools/test_htmlify_spy.js*)
    NOTE="  pre-commit: htmlify (the JOURNAL of rendered LEDGERs, B113) touched"
    # v148, B113 (R461, R462): the probe holds the palette rule (no hex literal in the
    # tool; every colour a var(--ROLE) palette.py defines), opens-from-disk (no URL, no
    # CR), and the journal's rules (a ledger is never edited in place; --remove; the
    # index's previous/next). The lint runs through system_lint_verify's leg above.
    run work/tools/test_htmlify.py
esac

case "$FILES" in *work/tools/memory_probe.py*|*work/tools/test_memory_probe.py*)
    NOTE="  pre-commit: the B68 probe harness touched"
    # The suite is the tool's LAB GUARD (every mutating verb refuses off the
    # lab branch); a probe tool whose guard quietly stopped guarding could
    # seed a record or open a live circle in the main tree. R351/R354.
    run work/tools/test_memory_probe.py
esac

case "$FILES" in *work/tools/storage_audit.py*|*work/tools/test_storage_audit.py*)
    NOTE="  pre-commit: the storage audit touched"
    # v158. The suite shipped with the tool (744cfa6, 2026-09-07) and was wired
    # to nothing, so test_hook_template.py's stray-suite check failed on master
    # from that commit onward — blocking the next commit to gitrepo.py, which is
    # the one file able to fix it. Fourth recurrence of that shape: v99
    # (circle_delta), v100 (phase_clock), v103 (redaction_manager). The
    # *test_*.py* arm below is the structural half, so a NEW suite now runs the
    # detector that would have caught it.
    run work/tools/test_storage_audit.py
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

# THE CLOSE STEP GETS A CLOSE RUN — audit-register.md #3, 2026-09-08.
#
# ui/tests/test_circle_engine.py is the ONLY suite in the tree that drives a full /close:
# short_terms collected and written, the .toml located and parsed back with all four
# sections, the close path reaching commit_sandbox. It rode `*ui/*|*coordinator/seam.py*`
# and nothing else — so a commit to coordinator/circle_close.py, WHICH IS THE CLOSE STEP,
# fired test_close_marker, test_short_term_manager, the four system_*_verify gates and two
# packaging scripts, and not one collection of a short_term. A commit to circle.py fired
# 50-odd suites and none of the five UI ones.
#
# test_close_marker.py does import circle_close and call it for real, which is why
# test_hook_template's property 5 accepts it — but what it asserts is the marker/report
# DECISION TABLE. This is exactly the blind spot that meta-gate documents about itself:
# "A SECONDARY-SUBJECT CLAIM IS A CLAIM, and nothing here checks one."
# SUBJECT_OF["test_circle_engine.py"] is "circling", so circle.py and circle_close.py are
# the secondary subject nothing verified.
#
# ITS OWN CASE, NOT AN ADDITION TO THE ui/ ONE, and the cost is why. That case runs FIVE
# suites including two more real dry-run circles; hanging it off every circle.py commit
# would make the commonest commit in this tree noticeably slower for four suites nobody
# asked for. This runs the one that drives a close.
case "$FILES" in *coordinator/circle_close.py*|*coordinator/circle.py*)
    NOTE="  pre-commit: the close step or its driver touched — running a real dry-run close"
    run ui/tests/test_circle_engine.py
esac

# v170, audit-register.md 2026-09-09, the record-integrity band. circle.py's REFUSALS —
# the corruption gate's, the API check's, the reduced-roster confirmation and every
# argument refusal including R360's mode requirement — were executed by nothing, because
# no suite could set --live: circle.py builds its client only when not dry-run, every
# suite is dry-run, so `if args.live` and `if client is not None` were unreachable by
# construction. test_circle_argv.py sets both with two stubs and asserts each refusal's
# exit code AND that no transcript appeared. Fast: no model call, no thread, no circle.
case "$FILES" in *coordinator/circle.py*|*coordinator/tests/test_circle_argv.py*\
|*coordinator/record_verify.py*|*coordinator/llm_client.py*)
    NOTE="  pre-commit: circle.py's refusals or a gate they consult touched"
    run coordinator/tests/test_circle_argv.py
esac

case "$FILES" in *coordinator/*|*memory/*|*ui/*|*packaging/*|*.claude/skills/*|*work/graph/*|*work/tools/*htmlify.py*)
    NOTE="  pre-commit: code touched — compiling and linting every module"
    # THE work/tools LEG NOW NAMES ITS GLOB — audit-register.md #8, 2026-09-08. It read
    # `*work/tools/*`, which fires on all 24 .py files in that directory, while the SCOPE
    # below reaches 2. So 22 files triggered a linter that never looked at them, and nothing
    # else compiles them either: work/ is deliberately outside CODE_DIRS, so
    # file_line_endings_verify.SCOPE_DIRS does not reach them. The trigger was NARROWED
    # rather than the scope widened, which is what the v148 comment below already argues
    # for: a lint gate that fails on a file the change never touched is a gate someone
    # bypasses. This is the v50 defect one directory later — a trigger claiming coverage the
    # scope does not deliver — and the agreement probe could not see it, because it compared
    # DIRECTORY NAMES and discarded the glob. It compares the glob now.
    #
    # v148, B113: work/tools/ joins the TRIGGER because a LEG joined system_lint_verify's
    # SCOPE — ("work/tools", "*htmlify.py"), the tool and its probe and nothing else in
    # that directory (memory_probe.py carries an unused import today, and a whole-directory
    # leg would have refused every commit until someone cleaned a file this change never
    # touched). test_system_lint_verify holds this pattern to CODE_DIRS + the legs.
    # v54, B57(3): .claude/skills/ joins the TRIGGER because it joined
    # system_lint_verify's SCOPE — the run skill's driver.py is 850 lines that open
    # a real circle and was linted only by a human remembering to. It is a
    # SCOPE leg, not a CODE_DIR: CODE_DIRS also drives
    # file_line_endings_verify.SCOPE_DIRS, and .claude/ is CRLF by convention.
    # test_system_lint_verify asserts this pattern against CODE_DIRS + EXTRA_LEGS.
    # v50: the pattern IS system_lint_verify.CODE_DIRS — memory/ joined (it held
    # running code since R203 with no lint trigger at all, so an
    # undefined name there committed clean) and scripts/ left (no code
    # since 2026-08-18; system_lint_verify's own SCOPE dropped it then, and a
    # trigger for a directory the linter does not scan is a dead leg).
    # test_system_lint_verify asserts this pattern and CODE_DIRS stay one thing.
    run coordinator/system_lint_verify.py
    # v95: ONE FACT, ONE HOME. The same value declared in two modules is the
    # defect this project records more often than any other — record_model's
    # REGISTERS says so twice in its own comments, and every instance so far
    # was found by a person reading code. Rides system_lint_verify's trigger because
    # its subject is the same: every module in the tree. Trigger and
    # invocation together, v19's rule.
    run coordinator/system_unique_home_verify.py
    run coordinator/tests/test_system_unique_home_verify.py
    # v123: THE LAYERS and THE CLASS WORD. grammar -> registers -> orchestration -> ui,
    # no upward import beyond the pairs the verifier names with a reason; and a NEW
    # public def starts with a class word the BNF defines, today's residue
    # grandfathered in system_name_grandfather.txt (a ceiling: --prune only shrinks it).
    # Both read every module, so they ride this trigger, v19's rule.
    run coordinator/system_layer_verify.py
    run coordinator/tests/test_system_layer_verify.py
    run coordinator/system_name_verify.py
    run coordinator/tests/test_system_name_verify.py
    run coordinator/tests/test_system_lint_verify.py
esac

case "$FILES" in *coordinator/file_line_endings_verify.py*\
|*coordinator/tests/test_file_line_endings_verify.py*)
    # v77, 2026-08-25. The CR/NUL gate runs on every commit (the
    # unconditional line at the top), but nothing ran the probe that proves
    # it still REFUSES — and the NUL half was added the day a NUL sat in a
    # committed README with every gate green. A checker whose own probe is
    # never invoked is the v45 shape: triggered and uninvoked reports
    # nothing.
    NOTE="  pre-commit: the CR/NUL gate touched — asserting it still refuses"
    run coordinator/tests/test_file_line_endings_verify.py
esac

case "$FILES" in *coordinator/gate_report.py*\
|*coordinator/tests/test_gate_report.py*)
    # v86, 2026-08-27. The note a refused check leaves TELLS its reader the
    # block carries no name, no circle words and no record contents — and then
    # invites them to send it. A claim like that is worth nothing unless
    # something fails when it stops being true.
    NOTE="  pre-commit: the diagnostic note touched — asserting what it does
  and does not carry"
    run coordinator/tests/test_gate_report.py
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
#     system_lint_verify's CODE_DIRS did not include it, so the script that REFUSES
#     to draw a wrong picture was the one file nothing checked. It is in the
#     lint trigger above now (as an EXTRA_LEG, not a CODE_DIR — see
#     system_lint_verify's own note on why), and its probe runs here.
#
# (c) THE DIAGRAMS WENT STALE SILENTLY — and this hook answered that by
#     redrawing and staging them on every commit that moved the module graph.
#     RETIRED v101, 2026-08-30, because the cure cost more than the disease:
#     ten TRACKED artifacts rewritten by any commit touching coordinator/,
#     memory/ or ui/ python meant two branches editing unrelated modules
#     conflicted on all ten, and the operator was left holding a question
#     with no human answer. He removed the premise instead — the drawings are
#     untracked now, so they cannot be stale IN GIT and cannot conflict.
#     Staleness on disk is a person's to notice and one command to fix.
#     History of what this used to do, kept because the trigger's SHAPE was
#     twice the lesson: ui/ joined it at v85 after an edit to ui/circling.py
#     moved the graph without firing --check (a trigger that had stopped
#     covering its subject — v45's lesson from the other side), and it grew
#     from six artifacts to ten in the same pass.
case "$FILES" in *coordinator/circle.py*|*coordinator/circle_close.py*|*coordinator/tests/test_close_marker.py*)
    NOTE="  pre-commit: circle.py's open-time failure reports touched"
    run coordinator/tests/test_close_marker.py
esac

# v167, audit-register.md #4 (2026-09-08). discard_unspoken() had ZERO references in the tree
# outside its own definition — its two primitives were unit-covered, which is what made the
# ASSEMBLY's gap invisible. The suite drives circle.py's real pre-warm failure path with a stubbed
# stream_prewarm (reached in dry-run: it takes args.dry_run as a parameter) and asserts no
# transcript survives. It is triggered on circle.py itself because the mechanism IS circle.py's,
# and on transcript_store.py because circle_transcript_discard_empty is what it calls.
case "$FILES" in *coordinator/circle.py*|*coordinator/transcript_store.py*\
|*coordinator/tests/test_discard_unspoken.py*)
    NOTE="  pre-commit: the no-trace discard touched"
    run coordinator/tests/test_discard_unspoken.py
esac

# v134, B96 (R434, 2026-09-04): the SHORT_TERM record is .toml, through ONE
# reader/writer. Its suite runs whenever the manager, the suite, or any of the
# three modules that write or read a record through it move — the close step,
# the safety net, dreaming — and whenever the legacy-.md contract could shift
# (record_model owns the four headings and R248's mark).
case "$FILES" in *coordinator/short_term_manager.py*|*coordinator/tests/test_short_term_manager.py*|*coordinator/circle_close.py*|*coordinator/backfill.py*|*coordinator/part_dreaming.py*|*coordinator/record_model.py*)
    NOTE="  pre-commit: the SHORT_TERM record's reader/writer, or a module that writes through it, touched"
    run coordinator/tests/test_short_term_manager.py
esac

# v136, B95 (R433, 2026-09-04): the RULING record is one TOML file per ruling
# under rulings/, through ONE reader/writer. The manager's own verify runs on
# every commit that touches a ruling file (a parse failure or a stray is a
# failure of the record, and this is the first reader to say so); its suite
# runs when the manager, the one-time migration, or the suite itself moves.
case "$FILES" in *coordinator/ruling_manager.py*|*coordinator/ruling_migrate.py*|*coordinator/tests/test_ruling_manager.py*|*rulings/*)
    NOTE="  pre-commit: the RULING record, its reader/writer, or its suite touched"
    run coordinator/ruling_manager.py
    run coordinator/tests/test_ruling_manager.py
esac

# v106: coordinator/seam.py had no case at all until this one, and no suite
# either (audit-register.md Tier 1 #7, 2026-09-01) -- it fired only
# system_lint_verify/system_unique_home_verify/sanitize/the staleness advisory, so its two
# stated invariants (the closed UI-signal-channel set; only circle.py's
# three named sites open the "circle" read_line channel) were never held by
# anything. Trigger AND invocation land together, v19's rule.
case "$FILES" in *coordinator/seam.py*|*coordinator/tests/test_seam.py*\
|*coordinator/circle.py*)
    NOTE="  pre-commit: seam.py's channel contract touched, or a new
  circle-channel read_line site"
    run coordinator/tests/test_seam.py
esac

case "$FILES" in *work/graph/coordinator_draw.py*|*work/graph/test_coordinator_draw.py*)
    NOTE="  pre-commit: the module diagram's derivations touched"
    run work/graph/test_coordinator_draw.py
esac

# The subsystem picture derives its centre from coordinator_draw AND the two
# sibling drawers' function columns, so a change to any of the three can move
# it — trigger and invocation land together (v19's rule).
case "$FILES" in *work/graph/llm_orchestration_draw.py*|*work/graph/test_llm_orchestration_draw.py*\
|*work/graph/coordinator_draw.py*|*work/graph/prompt_grammar_draw.py*\
|*work/graph/llm_response_data_flow_draw.py*)
    NOTE="  pre-commit: the subsystem picture's derivations touched"
    run work/graph/test_llm_orchestration_draw.py
esac

# THE MODULE-GRAPH REDRAW IS GONE, v101, 2026-08-30. It fired on any commit
# touching coordinator/, memory/ or ui/ python, rewrote ten tracked artifacts
# (~1.85 MB of SVG/HTML/TOML) and `git add`ed them. That is what put merge
# conflicts in front of the operator: two branches editing unrelated modules
# both redrew the same ten files, git asked which drawing to keep, and the
# question has no human answer — the answer is "neither, redraw from the
# merged source". He ruled the cause out of existence rather than the
# symptom: *"stop saving them and do the merges yourself"*.
#
# THE DRAWINGS ARE UNTRACKED NOW, the way work/graph/issue_graph.* already
# was (R365) and for the same stated reason — nothing reads a picture back;
# it is for a person to open, and it is rebuilt from tracked source whenever
# it falls behind. Nothing stored is nothing to conflict over.
#
#     python work/graph/coordinator_draw.py --dump
#     python work/graph/coordinator_draw.py --live --dump
#     python work/graph/coordinator_draw.py --simple
#     python work/graph/coordinator_draw.py --live --simple
#
# AND THE `git add` HAD TO GO WITH THE TRACKING, not after it: `git add` on an
# ignored, untracked path EXITS 1, and both redraw arms ended in `|| exit 1`.
# Left in place for even one commit, this hook would have refused every commit
# touching those paths — in all four worktrees and the lab at once, since
# .git/hooks/ is shared.

case "$FILES" in *coordinator/record_verify.py*|*coordinator/tests/test_record_verify.py*)
    NOTE="  pre-commit: the corruption gate touched — asserting it still refuses"
    run coordinator/tests/test_record_verify.py
esac

case "$FILES" in *coordinator/*|*memory/*|*packaging/*|*process_core.md*)
    NOTE="  pre-commit: shipped surface touched — the owner's name may not enter it"
    quiet packaging/sanitize.py --dry-run
esac

case "$FILES" in *packaging/package.py*|*packaging/test_package.py*|*packaging/sanitize.py*|*packaging/scan.py*|*packaging/ignore.txt*|*packaging/exceptions.toml*|*packaging/runtime_only.txt*)
    NOTE="  pre-commit: the build's refusals touched — asserting they still refuse"
    # v158 widened this from package/test_package/sanitize to the three LISTS and
    # the resolver that reads them. ignore.txt fired NO packaging check at all,
    # which is how its four record patterns stayed root-anchored through B117:
    # they matched nothing, every delegate-less record path resolved `root`
    # (copy the live bytes into the bundle) instead of `blocked`, and no gate
    # looked. runtime_only.txt was repathed in the same move and ignore.txt was
    # not. test_package.py now asserts both halves of resolve()'s branch order.
    run packaging/test_package.py
esac

case "$FILES" in *coordinator/seam.py*|*coordinator/phase_clock.py*|*coordinator/tests/test_progress_indication.py*)
    NOTE="  pre-commit: the >3s progress indication — its cadence, and its silence"
    # v173, 2026-09-09. Its own arm because the mechanism spans three modules
    # that each already trigger a DIFFERENT suite: seam.py runs test_seam,
    # phase_clock.py runs test_phase_clock, and neither would have run this.
    # The clause it protects is the one that can hurt somebody — the beat must
    # stay silent while a person is typing — and that guard is only true
    # because every console read in the tree is inside the WAITING span. A
    # future read added outside it re-opens the hazard silently, which is
    # exactly the kind of thing a probe is for.
    run coordinator/tests/test_progress_indication.py
esac

case "$FILES" in *packaging/shipped_references.py*|*packaging/test_shipped_references.py*)
    NOTE="  pre-commit: the scan for references a recipient cannot resolve"
    # v172, 2026-09-09. Its own arm rather than a place in the list above,
    # because that arm's suite is test_package.py and this module's proof is a
    # different file. A shared arm would have run the wrong probe and reported
    # a pass — the triggered-but-uninvoked shape v45 was written for.
    # The suite is pure: it drives the classifier over synthetic source held in
    # itself and reads the ship set read-only. It makes no model call, writes
    # nothing, and cannot open a circle.
    run packaging/test_shipped_references.py
esac

case "$FILES" in *packaging/conform_packaging.py*|*packaging/test_conform_packaging.py*)
    NOTE="  pre-commit: the argument gate over a script that SPENDS and RECORDS"
    # v163, E36. conform_packaging.py had no trigger of its own and no suite:
    # its DEFAULT action makes up to 2 paid model calls and then writes
    # scaffold_check_state.toml, the record the publish gate reads. `--help`
    # was unimplemented and an unknown argument was simply not
    # --assemble-only, so `--help` ran the whole thing. parse_args is pure, so
    # this suite costs nothing and can never reach the model — which is what
    # makes it a probe that will still be run in a year.
    run packaging/test_conform_packaging.py
esac

case "$FILES" in *packaging/scaffold_staleness.py*|*packaging/test_scaffold_staleness.py*)
    NOTE="  pre-commit: the staleness hash touched — asserting it answers the same in every tree"
    # v164, B124. The sensor below is ADVISORY on purpose, so nothing refused
    # when its answer depended on which directory asked: a gitignored live
    # counterpart put its bytes in the hash in the main checkout and an absence
    # marker in every fresh worktree, and a record made in one read STALE in the
    # other over byte-identical committed content. The hash is the thing to
    # gate, not its reading — this suite holds the tree-independence, and no
    # case triggered on this module at all until it existed.
    run packaging/test_scaffold_staleness.py
esac

# v104, 2026-09-01. ADVISORY: packaging/scaffold/ went stale silently for
# weeks before packaging/conform_packaging.py existed to catch it — nothing
# ever prompted a re-check. This reminds, at commit time, on the same
# trigger as the sanitize case above plus .claude/CLAUDE.md itself (the
# thing conform_packaging.py judges every scaffold file against). It never
# refuses: resolving a real STALE reading costs a paid model call, which a
# commit hook does not get to spend. The hard gate is publish.py's own
# preflight, at the one moment staleness actually reaches a user.
case "$FILES" in *coordinator/*|*memory/*|*packaging/*|*process_core.md*\
|*.claude/CLAUDE.md*)
    NOTE="  pre-commit: scaffold-relevant files touched — checking staleness (advisory)"
    advise packaging/scaffold_staleness.py --check
esac

case "$FILES" in *coordinator/TRANSACTION_CLASS.py*|*coordinator/circle_audit.py*\
|*coordinator/tests/test_TRANSACTION_CLASS.py*|*coordinator/tests/test_circle_audit_lock.py*\
|*coordinator/atomic_write.py*)
    # v138, audit-register 2026-09-04 #2: atomic_write.py is THE UNIVERSAL WRITE
    # PATH (38 call sites) and had no trigger, so it rides this case.
    # v158: the ground given at v138 — "test_TRANSACTION_CLASS exercises it, crash
    # states included" — WAS FALSE FOR THREE DAYS. No suite called record_atomic_write
    # at all; the only mention was a comment. The trigger fired, the suite ran, and the
    # subject was untouched. test_atomic_write_unlinks_its_temp_when_the_swap_fails()
    # now makes the claim true, walking the except-arm the happy path never reaches.
    NOTE="  pre-commit: the audit's transaction/lock machinery, or atomic_write, touched"
    # v48. Both probes build their own temp trees (transaction's crash
    # states via a scripted os.replace failure, the lock cases against a
    # rebound circle_audit.LOCK) — nothing here reads or writes work/nightly
    # or the live registers, so this can never race a real run.
    # v52 merge-window fallback, same shape as the --selfcheck one above.
    run coordinator/tests/test_TRANSACTION_CLASS.py
    run coordinator/tests/test_circle_audit_lock.py
esac

case "$FILES" in *ui/issue_draw.py*|*ui/tests/test_issue_draw.py*|*coordinator/circle.py*)
    NOTE="  pre-commit: the issue picture and the close that draws it"
    # v87, 2026-08-27. issue_draw.py became shipped code the day circle.py
    # started running it at every live /close, and the two halves of that
    # wiring fail in opposite directions: the SCRIPT can break at import
    # time (its sys.path hop to memory/ was wrong for eleven days and
    # nothing noticed, because nothing invoked it), and the CALL SITE can
    # stop naming "ui/issue_draw.py" as a literal, which is the only
    # reason packaging/scan.py ships the script and its man page at all.
    #
    # A CASE OF ITS OWN RATHER THAN A LINE IN THE ui/ CASE BELOW: this must
    # also fire for a commit that touches only coordinator/circle.py, which
    # *ui/* does not match. The redraw runs under `if args.live:`, so
    # test_circle_engine.py — which forces --dry-run — cannot reach it.
    run ui/tests/test_issue_draw.py
esac

# v116, 2026-09-03: THE WORKING SET, characterized before it moves (cohesion
# re-homing stage 10, B99). The probe pins the open-time question, the
# working_sets register, the three id parsers and both neighbour pulls
# against their homes today, and re-points to working_set_manager.py when
# the move landed (10b, v117) — which is when that module joined this pattern
# (test_hook_template refuses a pattern naming a path that does not exist).
case "$FILES" in *coordinator/working_set_manager.py*|*coordinator/tests/test_working_set_manager.py*\
|*coordinator/transcript_store.py*|*memory/issue_index.py*|*ui/issue_draw.py*\
|*memory/issue_prompt_projection.py*|*coordinator/circle.py*)
    NOTE="  pre-commit: the working set — the question, its register, the parsers, the pulls"
    run coordinator/tests/test_working_set_manager.py
esac

case "$FILES" in *ui/*|*coordinator/seam.py*)
    NOTE="  pre-commit: ui/ (or its rebinding surface, seam.py) touched — running its self-tests"
    # test_circling_selftest.py (--selftest until 2026-09-03) needs no real import beyond circle.py
    # itself, but test_circle_engine.py runs a REAL dry-run CircleEngine
    # session (it imports circle.py, which imports anthropic) — bare
    # `python` here is the system 3.10, not the venv (measured in
    # system_lint_verify.py's own docstring), so all three are called through the
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
    run ui/tests/test_circling_selftest.py
    # v168, audit-register.md #7 (2026-09-08). ui_main_loop's `engine is not None` branch — the
    # product path since R314 — had 164 of 165 lines unhit, and the selftest asserted one property
    # about it by READING ITS SOURCE, because the only suite reaching main() replaces the loop
    # with `lambda: 0`. This one calls it with a fake engine and patched module-level I/O, so the
    # alternate-screen contract (entered, and restored in the finally EVEN ON AN EXCEPTION) is
    # executed rather than read.
    run ui/tests/test_ui_main_loop.py
    run ui/tests/test_circle_engine.py
    # v152, B117 stage 6: the same engine on the second GROUP — opened and closed in dry-run,
    # groups/ifs/ proved byte-identical after. Its subject is circling.py, so it rides here;
    # a groups/ change runs it too (the record-safety case).
    run ui/tests/test_circle_engine_band.py
    run ui/tests/test_circling.py --fast
    # v171, R491 (2026-09-08, the operator: "2 - diagnose and wire"), landed 2026-09-09.
    # 518 lines of assertions sat behind the tree's ONE ALLOW entry for its whole
    # existence. The entry's stated condition — "16 of its checks are stale" — was
    # right: 20 passed and 15 failed, and all fifteen were judged one at a time before
    # any was changed. Every one was STALE, none a regression, and each is now dated to
    # the ruling that moved it (R230, R273/R274/R227, R400-R402, B64, B99). The
    # replacements are mutation-tested: three mutants each reverting one of those rulings
    # are each caught.
    # BEFORE IT COULD BE WIRED, one isolation hole had to close. self/settings.toml was
    # in neither the redirect list nor the snapshot, and it is UNTRACKED — so a stray
    # write would have been invisible to git, to the suite and to this hook, in the MAIN
    # checkout where the operator's file lives. --fast for the same reason test_circling
    # takes it: the 10-20s per line exists for a human watching, not for a gate.
    run ui/tests/circle_test.py --fast
    # v96, 2026-08-29: the Ticker flavor's adaptor probe — bridge.py
    # over real stdio, a full dry-run session, the lens RPCs, the
    # reload handshake. Joined at the merge, as the design doc's
    # merge-time follow-up promised.
    run ui/tests/test_ticker_bridge.py
    # v97, 2026-08-29 (R400): the Entries semantic index — local
    # embeddings, FAKE embedder in the probe so the gate needs neither
    # model nor network; the real model is ticking_index.py --selftest,
    # by hand.
    run ui/tests/test_ticking_index.py
    # v102, 2026-08-30: the palette, and the ONE gate that can see the
    # Ticker's CSS. system_unique_home_verify.py reads only Python, so a hex string
    # hand-edited into app.css could drift from the role it was generated
    # from forever with nothing able to notice — --check is what notices.
    # The probe beside it pins the rest: both grounds per role, 4-bit ANSI,
    # and that a drifted app.css really is caught.
    run ui/palette.py --check
    run ui/tests/test_palette.py
esac

case "$FILES" in *parts/*|*coordinator/part_roster.py*|*coordinator/tests/test_part_roster.py*)
    NOTE="  pre-commit: the roster is read from the tree, so the tree can lie"
    # v61. The lament that stood here since v11 — "UNCOVERED again until this
    # gets a replacement" — is answered. The replacement shipped 2026-08-17 as
    # B34 and passed from the day it landed; it was simply never wired. A
    # missing or malformed part.toml shrinks the roster, and a part outside
    # the roster is ABSENT from the circle rather than faulty — downstream,
    # indistinguishable from a part present and silent.
    #
    # circle_audit.py --selfcheck rides the parts/ case above and LOOKS like
    # this gate. It is register_gate.record_tree_verify: register schemas, line
    # endings, long_term.md dream entries. It never calls part_roster.part_verify().
    run coordinator/tests/test_part_roster.py
esac

case "$FILES" in *coordinator/identity.py*|*coordinator/tests/test_identity.py*|*coordinator/prompt_build.py*|*parts/*)
    NOTE="  pre-commit: who Self is, or what a part's recorded context renders to"
    # v75. identity.user_name_read() resolves the Soul's preferred_name first
    # (R325) and prompt_build.part_identity_tail_render() renders [context]
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

case "$FILES" in *coordinator/phase_clock.py*|*coordinator/tests/test_phase_clock.py*|*coordinator/docs/phase_clock.md*)
    # v100, 2026-08-30 — the SECOND stray in one day, and the second merge
    # to be refused by it. phase_clock landed a module, a doc and a probe
    # and wired none of them, exactly as circle_delta had hours earlier;
    # test_hook_template.py's stray-suite check caught both, but only after
    # the work had merged, and the second one refused the lab's pull-main
    # rather than a commit. TWO IN A DAY MAKES IT A PATTERN, not an
    # oversight: a new module's trigger is easy to forget precisely because
    # nothing needs it until someone else's commit touches an unrelated
    # file. The check is doing its job; what is missing is a habit.
    NOTE="  pre-commit: the phase clock touched"
    run coordinator/tests/test_phase_clock.py
esac

case "$FILES" in *coordinator/circle_delta.py*|*coordinator/circling_verify.py*\
|*coordinator/instrument_manager.py*|*coordinator/part_mid_term_project.py*\
|*coordinator/parts_prompt_projection.py*|*coordinator/project_stats.py*\
|*coordinator/prompt_show.py*|*coordinator/quote_as_lands.py*\
|*coordinator/remember_expand.py*|*coordinator/remember_prompt_projection.py*\
|*coordinator/ruling_migrate.py*|*coordinator/token_count.py*\
|*coordinator/topic_prompt_projection.py*|*memory/issue_index.py*\
|*coordinator/circle_history_manager.py*|*coordinator/circle_journal_manager.py*\
|*coordinator/circle_observation_manager.py*|*coordinator/circle_state.py*\
|*coordinator/dream_history_manager.py*|*coordinator/identity.py*\
|*coordinator/part_mid_term_manager.py*|*coordinator/part_roster.py*\
|*coordinator/proposal_group_manager.py*|*coordinator/proposal_manager.py*\
|*coordinator/redaction_manager.py*|*coordinator/remember_manager.py*\
|*coordinator/setting_manager.py*|*coordinator/topic_manager.py*\
|*memory/issue_schema.py*|*memory/issue_commands.py*|*packaging/scan.py*\
|*coordinator/ruling_sweep.py*|*coordinator/gitrepo.py*\
|*ui/ticker/lens_index.py*|*ui/ticker/ticking_index.py*\
|*coordinator/tests/test_entry_points.py*)
    # v144, 2026-09-04 (audit-register.md #13). Fourteen shipping __main__ entry points had
    # no exerciser at all before this suite — several have their own suite, and every one of
    # those exercises library functions while leaving the __main__ block dark. This trigger
    # and its invocation land together, same rule v99's own comment states two blocks below.
    #
    # THE SECOND FOURTEEN, 2026-09-08 (audit-register.md #8). ENTRY_POINTS grew by fourteen
    # register managers and readers on 2026-09-07 and this case did not, so the suite ran for
    # 13 of the 27 modules it covers — editing setting_manager.py fired 52 checks and not this
    # one. test_hook_template.py now PARSES ENTRY_POINTS and fails if any listed path does not
    # reach here, so the next time the list grows the gate says so instead of the trigger
    # quietly covering less.
    NOTE="  pre-commit: an untested-until-now __main__ entry point touched"
    run coordinator/tests/test_entry_points.py
esac

case "$FILES" in *coordinator/circle_delta.py*|*coordinator/tests/test_circle_delta.py*|*coordinator/docs/circle_delta.md*)
    # v99, 2026-08-30. circle_delta landed with a probe and NO trigger, so
    # test_hook_template.py's stray-suite check had been failing on master
    # for every commit that touched coordinator/gitrepo.py — the arm above
    # is what runs that check, so the omission blocked the one file able to
    # fix it. A TRIGGER AND ITS INVOCATION LAND TOGETHER; v45's lesson is
    # the same rule seen from the other side, where a triggered suite was
    # never invoked and reported nothing while looking green.
    NOTE="  pre-commit: the per-circle delta report touched"
    run coordinator/tests/test_circle_delta.py
esac

case "$FILES" in *coordinator/redaction_manager.py*|*coordinator/stream_redaction.py*|*coordinator/tests/test_redaction.py*)
    # v103, 2026-09-01. THE THIRD IN THIS SHAPE — v99 (circle_delta) and v100
    # (phase_clock) were the first two. redaction_manager.py landed with its probe
    # (55133f1, R422) and no trigger, so test_hook_template.py's stray-suite
    # check had been failing on master for every commit touching
    # coordinator/gitrepo.py since — the arm below is what runs that check,
    # so the omission blocked the one file able to fix it, same as v99.
    NOTE="  pre-commit: the redaction registry touched"
    run coordinator/tests/test_redaction.py
esac

case "$FILES" in *test_*.py*)
    # v158, THE STRUCTURAL HALF. A commit that ADDS a suite is the one commit
    # that can strand it, and until now it fired nothing: the stray-suite
    # detector lives in the arm below, whose trigger is gitrepo.py and its own
    # four suites, so a new suite elsewhere went unnoticed until the NEXT
    # gitrepo.py commit — which the failure then blocked. That has now happened
    # four times (v99 circle_delta, v100 phase_clock, v103 redaction_manager,
    # v158 storage_audit), each time costing the same diagnosis.
    #
    # ONLY test_hook_template.py runs here, deliberately. It is the detector;
    # the three heavier suites in the arm below stay keyed to the hook module
    # itself, so touching an ordinary suite does not drag in the whole set.
    # A commit touching BOTH gitrepo.py and a suite runs this one twice — the
    # arm below names it too. That is accepted rather than factored out: the
    # suite is read-only and quick, and collapsing the two triggers into one
    # would re-couple the detector to the hook module, which is the coupling
    # that stranded four suites in the first place.
    NOTE="  pre-commit: a suite touched — the stray-suite detector"
    run coordinator/tests/test_hook_template.py
esac

case "$FILES" in *coordinator/gitrepo.py*|*coordinator/tests/test_gitrepo_unstage.py*|*coordinator/tests/test_remote_classify.py*|*coordinator/tests/test_hook_template.py*|*coordinator/tests/test_hook_gate.py*)
    NOTE="  pre-commit: the hook's own module touched"
    # v61. Until now editing PRE_COMMIT ran no shell check at commit time:
    # *coordinator/* fires system_lint_verify, which compiles the PYTHON and cannot
    # see the rendered SHELL. _hook_syntax_check() existed and was called by
    # nothing but --git-setup. That is the v37/v38 incident's own shape.
    run coordinator/tests/test_hook_template.py
    run coordinator/tests/test_gitrepo_unstage.py
    run coordinator/tests/test_remote_classify.py
    # v92, 2026-08-28. The three above READ the template; this one RUNS it.
    # Every assertion about system_git_run()/quiet() was a substring search until now,
    # which is exactly why v81's swallowed failures survived a green
    # battery — the line the search looked for was present and unreachable.
    run coordinator/tests/test_hook_gate.py
esac

case "$FILES" in *coordinator/instrument_manager.py*|*self/instruments.toml*|*coordinator/tests/test_instrument_manager.py*)
    NOTE="  pre-commit: the instruments register or its reader touched"
    # v92, 2026-08-28. instrument_manager.py and its suite arrived 2026-08-27 with
    # NO trigger at all, so test_hook_template.py had been reporting
    # `STRAY: test_instrument_manager.py` ever since — into a battery that was
    # swallowing the report. Two defects that hid each other: the gate could
    # not refuse, and what it was trying to say was that a gate was missing.
    # self/instruments.toml is in the trigger for the reason
    # close_contract.toml and turn_contract.toml are in theirs — it is DATA a
    # human edits, and BLOCK 3's <profile> can be loosened without touching a
    # .py. self/ never ships, so an installed bundle has neither file and
    # system_git_run() skips the suite.
    run coordinator/tests/test_instrument_manager.py
esac

case "$FILES" in *coordinator/circling_verify.py*|*coordinator/circling_contract.toml*|*coordinator/tests/test_circling_verify.py*|*docs/BNF.md*)
    NOTE="  pre-commit: the CIRCLING grammar or its guards touched"
    # v90, R368 item 1. docs/BNF.md is IN THE TRIGGER because the
    # grammar lives there and the guards live in the TOML beside the
    # checker: circling_verify asserts the two still name the same set,
    # so an edit to EITHER can break the agreement while touching
    # nothing the other case matches.
    run coordinator/tests/test_circling_verify.py
esac

case "$FILES" in *coordinator/write_guard.py*|*coordinator/tests/test_write_guard.py*|*coordinator/circle_state.py*|*coordinator/tests/test_circle_state.py*|*coordinator/circle_close_verify.py*|*coordinator/tests/test_circle_close_verify.py*|*coordinator/close_contract.toml*|*coordinator/tests/test_close_postcondition.py*|*coordinator/transcript_store.py*\
|*coordinator/record_paths.py*|*coordinator/tests/test_record_paths.py*|*coordinator/part_roster.py*\
|*ui/tests/test_circle_engine_band.py*|*groups/*)
    # v138, audit-register 2026-09-04 #2: record_paths.py DECIDES WHERE EVERY
    # WRITE LANDS and had no trigger; test_write_guard reads it, so it rides here.
    # v150, B117 stage 1 (R466/R467, 2026-09-07): record_paths.group_tree() is the one lookup
    # every record path asks; its own probe rides here, and part_roster.py (which reads PARTS_DIR
    # from it) triggers it too.
    # v152, B117 stage 6: a group's record (groups/<name>/) triggers this case too, and the
    # band's engine probe — a real dry-run circle on the second group, opened and closed, with
    # every file under groups/ifs/ proved byte-identical after — rides beside the lookup's own.
    NOTE="  pre-commit: a record-safety module touched"
    run coordinator/tests/test_record_paths.py
    run ui/tests/test_circle_engine_band.py
    # v61. Three modules that decide whether the record survives, none of
    # which had a suite before 2026-08-19: the write guard (nothing imported
    # it at all), the open-circle guard (E12's subject), and the close
    # verifier (whose exit code decides whether a close reports clean).
    run coordinator/tests/test_write_guard.py
    run coordinator/tests/test_circle_state.py
    run coordinator/tests/test_circle_close_verify.py
    # v89, R368: the close report read as a POSTCONDITION —
    # `--postcondition` against the transcript each report names.
    # close_contract.toml is DATA, so a commit can loosen every
    # postcondition in the project without touching a .py; it needs
    # its own trigger for the same reason turn_contract.toml does.
    run coordinator/tests/test_close_postcondition.py
esac

case "$FILES" in *coordinator/REGISTER_CLASS.py*|*coordinator/tests/test_REGISTER_CLASS.py*)
    NOTE=""
    run coordinator/tests/test_REGISTER_CLASS.py
esac

case "$FILES" in *coordinator/command_surface.py*|*coordinator/tests/test_dev_mode.py*)
    NOTE=""
    run coordinator/tests/test_dev_mode.py
esac

# v160, R483 (2026-09-07): what a part may put in a
# [proposed: ...] bracket lives on FIVE surfaces now, and this is the one that
# holds them together. The trigger is deliberately wide — every input the suite
# reads — because the drift it catches is between files that no single edit
# touches together. A group's layer is hand-written markdown, so the code and
# the rulebook agreed by memory alone until audit-register.md #12 measured them
# three verbs apart with nothing failing.
case "$FILES" in *coordinator/command_surface.py*|*coordinator/annotations.py*\
|*coordinator/process_ifs.md*|*coordinator/process_band.md*|*coordinator/process_core.md*\
|*groups/*/group.toml*|*packaging/scaffold/coordinator/process_ifs.md*\
|*coordinator/tests/test_proposable_surfaces.py*)
    NOTE=""
    run coordinator/tests/test_proposable_surfaces.py
esac

case "$FILES" in *coordinator/prompt_capture.py*|*coordinator/tests/test_prompt_capture.py*|*coordinator/turn_contract.toml*|*coordinator/tests/test_turn_contract.py*)
    NOTE=""
    run coordinator/tests/test_prompt_capture.py
    # v88, R368: the WIRE CONTRACT and the probe that proves it still
    # refuses. turn_contract.toml is DATA read by prompt_capture, so a
    # commit that touches only the TOML changes what every capture is
    # checked against while touching no .py at all — it needs its own
    # trigger or the contract could be loosened silently.
    run coordinator/tests/test_turn_contract.py
    # v84: AND the OTHER suite that calls verify(). test_llm_client.py builds
    # a capture and asserts `verify() == 0`, so a new assertion inside
    # verify() can break it — and on 2026-08-27 one did. R362 landed the
    # projection assertion in prompt_capture.py, whose only trigger was the
    # case above, so the suite it broke was never invoked; the gate went red
    # on master and ten commits landed over it before a docs pass tripped
    # circle.py's own trigger and found it. Cheap to run, and the exposure is
    # exactly the v45 lesson: a change also needs its TRIGGER checked.
    run coordinator/tests/test_llm_client.py
esac

# v107, audit-register.md #14. FOUR .claude/skills/ suites existed, ran
# green standalone, and were invisible to test_hook_template.py's own
# stray-suite detector -- suites() globbed coordinator/tests/, ui/tests/,
# work/tools/ and work/graph/, never .claude/skills/ or packaging/. Widened
# in the SAME commit as these three case blocks (test_hook_template.py's own
# v45 lesson: a detector fix and the wiring it exposes as missing land
# together, or the gate goes red on the detector fix alone). Three are
# wired directly, fast and self-contained; test_pull_main.py stays an ALLOW
# entry instead — it fires real commits inside temp git repos as part of
# its own assertions, which would mean every pull-main commit running the
# whole pre-commit battery nested inside itself.
case "$FILES" in *.claude/skills/install-package/install.py*\
|*.claude/skills/install-package/test_install.py*)
    NOTE="  pre-commit: the install skill touched"
    run .claude/skills/install-package/test_install.py
esac

case "$FILES" in *.claude/skills/my_commit/my_commit.py*\
|*.claude/skills/my_commit/test_my_commit.py*)
    NOTE="  pre-commit: the my_commit skill touched"
    run .claude/skills/my_commit/test_my_commit.py
esac

case "$FILES" in *.claude/skills/publish-package/publish.py*\
|*.claude/skills/publish-package/test_publish.py*)
    NOTE="  pre-commit: the publish skill touched"
    run .claude/skills/publish-package/test_publish.py
esac

# v147, 2026-09-06 (B110): the publish gate's content check done by the session (R459),
# as a driver. Its one danger is recording a check that did not happen; the probe holds
# every refusal that prevents it.
case "$FILES" in *.claude/skills/scaffold-check/scaffold_check.py*\
|*.claude/skills/scaffold-check/test_scaffold_check.py*)
    NOTE="  pre-commit: the scaffold-check skill touched"
    run .claude/skills/scaffold-check/test_scaffold_check.py
esac

# v149, B115 (R464, 2026-09-07): BLOCK 1 is two layers — the universal rulebook and the group's
# own layer file, composed by process_core_prompt_projection. The probe holds the universal layer
# to assuming no group and holds the IFS layer over it to the pre-split rulebook's own sha256.
case "$FILES" in *coordinator/process_core.md*|*coordinator/process_ifs.md*\
|*coordinator/process_band.md*\
|*coordinator/process_core_prompt_projection.py*\
|*coordinator/tests/test_process_core_layers.py*)
    NOTE="  pre-commit: BLOCK 1's layers touched — the byte-identity probe runs"
    run coordinator/tests/test_process_core_layers.py
esac

# B103, audit-register 2026-09-04 #5: 850 lines that open a real circle,
# joined the lint scope as an EXTRA_LEG at hook v54 and got nothing else —
# adjacent to #14 above, which wired the four SIBLING skills' suites; this
# one had no suite to wire until test_driver.py.
case "$FILES" in *.claude/skills/run-inner-circling/driver.py*\
|*.claude/skills/run-inner-circling/test_driver.py*)
    NOTE="  pre-commit: the run-inner-circling driver touched"
    run .claude/skills/run-inner-circling/test_driver.py
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
    post-merge can carry the logbook fold without this becoming two
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
# physical drive, so a disk failure on the working copy does not also
# take the history with it.
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
#
# THE TWO PUSHES ARE SEQUENCED, NEVER CHAINED. They were joined by `&&` until
# 2026-08-30, so a single unpushable BRANCH withheld every TAG — and the tags
# are the RECORD (circle/<OT>, dream/<OT>). It cost nothing that day only by
# luck: the rejection came from a worktree branch that had been `git reset`
# past a sandbox commit already on the disk, and no tag had been minted since
# the last good push, so the disk stayed current by coincidence rather than by
# design. The next live close would have minted a tag the disk never saw,
# while the console said only what it had already said three times.
#
# `git push --all` IS NOT ATOMIC — every ref it can advance, it advances, and
# it still exits non-zero for the one it cannot. So a rejection means "one ref
# is stuck", never "the backup got nothing"; that is why master reached the
# disk in the same run that printed the warning. Both pushes now run
# unconditionally and the warning fires if EITHER failed.
if git remote get-url backup >/dev/null 2>&1; then
    {{
        git push backup --all --quiet
        _all_rc=$?
        git push backup --tags --quiet
        _tag_rc=$?
    }} 2>/tmp/inner-circling-backup-push.log
    if [ "$_all_rc" -ne 0 ] || [ "$_tag_rc" -ne 0 ]; then
        echo "  {kind}: WARNING — backup push to 'backup' remote failed" \\
             "(branches rc=$_all_rc, tags rc=$_tag_rc)." >&2
        echo "  {kind}: see /tmp/inner-circling-backup-push.log" >&2
    fi
fi
exit 0
'''


# post-commit v2 — v1 was HAND-INSTALLED, with no template here at all. That
# is precisely why the post-merge gap survived: the hook nobody could see in
# the source was the hook nobody checked, and `system_git_hooks_ensure()` managed only
# pre-commit. v2 is byte-equivalent in behaviour to what v1 did; the version
# bump exists so the installer REPLACES the hand-written file rather than
# finding a matching mark and leaving two different programs in agreement
# about their name — v8's lesson, applied to the hook v8 did not cover.
# v3 — 2026-08-30: the two pushes are sequenced, not chained. Under v2 a
# single unpushable branch short-circuited the tag push, so the RECORD tags
# could be withheld by an unrelated worktree branch. Both marks move together
# because both hooks are one generator; a bump on one alone would install a
# fixed body beside an unfixed one and the divergence would be silent, which
# is the exact property _backup_push_hook()'s docstring exists to protect.
POST_COMMIT_MARK = "# inner-circling post-commit v3"
POST_COMMIT_FAMILY = "# inner-circling post-commit v"
POST_COMMIT = _backup_push_hook("post-commit", POST_COMMIT_MARK, "commit")

POST_MERGE_MARK = "# inner-circling post-merge v4"
POST_MERGE_FAMILY = "# inner-circling post-merge v"

# v2, R338 (2026-08-24): THE LOGBOOK FOLD RUNS HERE.
#
# `coordinator/assign_ids.py --write` was the one step in the whole
# branch-and-merge mechanism that a human had to remember, and on 2026-08-24
# two separate merges both forgot it. logbook_ruling_verify.py then refused master —
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
# and leaves the folded logbooks in the working tree, uncommitted.
_FOLD_STEP = '''
# --- the logbook fold, before the backup push (see _backup_push_hook) ---
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
    template's own first line, so system_git_hooks_ensure() raised here — before
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
        rc_staged, staged = system_git_run("diff", "--cached", "--name-only",
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


def system_git_hooks_ensure(log) -> None:
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
    # `work/tools/*`, `packaging/*`, `system_lint_verify.py`, `logbook_ruling_verify.py`
    # and kin — and NONE of those ship in a distributed bundle. Its very
    # first line, `python coordinator/file_line_endings_verify.py --staged`, is
    # UNCONDITIONAL, so in a bundle every commit failed at line one.
    #
    # THE WORST OF THAT WAS NOT THE HUMAN'S COMMIT. transcript_store's
    # circle_commit() runs through the same hook at every /close, so a
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


def system_git_ignore_ensure(log) -> list[str]:
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


def system_git_ignored_untrack(log) -> list[str]:
    """Drop from the INDEX any tracked path that .gitignore now excludes. The
    working file is untouched (`--cached`) and history is untouched — the blob
    stays reachable from older commits. This is the one index-editing operation
    that is safe to automate: nothing is lost, and leaving e.g. an 11MB tool
    database tracked means re-storing it in full on every commit it changes."""
    rc, out = system_git_run("ls-files", "--cached", "--ignored", "--exclude-standard",
                  read_only=True)
    paths = [l for l in out.splitlines() if l.strip()] if rc == 0 else []
    if not paths:
        log("ok", "no tracked path is covered by .gitignore")
        return []
    for chunk in (paths[i:i + 200] for i in range(0, len(paths), 200)):
        system_git_run("rm", "--cached", "--quiet", "--", *chunk, check=True)
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
# circle close silently failed to commit. `circle_commit` is non-fatal by
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


def system_git_remote_classify(url: str) -> tuple[bool, str]:
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


def system_git_remote_refuse(log) -> bool:
    """True if ANY configured remote could take this material off the machine.

    Named for what it does at the call sites, which is refuse. It no longer
    refuses a remote for existing — see the block above."""
    bad = []
    for name in system_git_remotes_read():
        rc, url = system_git_run("remote", "get-url", name, read_only=True)
        url = url.strip() if rc == 0 else ""
        ok, why = system_git_remote_classify(url)
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


def system_git_identity_is_known() -> bool:
    """Will `git commit` accept an author here? `git var GIT_AUTHOR_IDENT`
    fails exactly when `git commit` would refuse with "Author identity
    unknown", and consults every source git itself does — config at any
    scope, GIT_AUTHOR_*/EMAIL, a host whose address auto-detects.
    system_git_identity_resolve() is NOT this test: $IFS_GIT_NAME in .env satisfies it
    without configuring git, and the commit still fails.

    Never raises — this sits on the /close path, where an uncaught GitError
    is a crash at the end of every circle (the 2026-08-24 missing-binary
    lesson in system_git_paths_commit() below)."""
    try:
        return system_git_run("var", "GIT_AUTHOR_IDENT", read_only=True)[0] == 0
    except GitError:
        return False


def system_git_unconfigured_report(log) -> None:
    """The kind note, once per process. circle.py's main() resets the flag
    at each run, which makes "once per process" mean once per circle —
    one UI process can run main() more than once (resume)."""
    global _UNCONFIGURED_REPORTED
    if _UNCONFIGURED_REPORTED:
        return
    _UNCONFIGURED_REPORTED = True
    log("note", UNCONFIGURED_TEXT)


def system_git_unconfigured_report_reset() -> None:
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
    rc, out = system_git_run("reset", "-q", "HEAD", "--", *rel)
    if rc != 0:
        # Unborn HEAD — there is no commit to reset against, so the index
        # entries are new rather than modified. Dropping them from the index
        # is the equivalent operation, and --cached leaves the files on disk.
        rc, out = system_git_run("rm", "-q", "--cached", "--", *rel)
    if rc == 0:
        log("did", f"unstaged {len(rel)} path(s) after the failed commit")
    else:
        log("warn", f"could not unstage after the failed commit: {out}. "
                    f"Run `git reset HEAD -- <paths>` before committing "
                    f"anything else, or these will be swept into it.")


def system_git_paths_commit(paths: list[pathlib.Path], message: str, log,
                 tag: str | None = None) -> bool:
    """Stage and commit ONLY the given paths. Never `git add -A`: an automated
    run must not sweep up whatever the human was editing at the time."""
    # NO GIT AT ALL IS A SUPPORTED TREE SINCE 2026-08-24 (the operator:
    # "Tier 1"), and it did not used to reach this line. system_git_is_repo() shells
    # out, so a machine with no git BINARY raises GitError from system_git_run()'s
    # OSError arm instead of answering False — uncaught here, uncaught in
    # transcript_store.circle_commit(), and therefore a CRASH at the end of
    # every /close rather than the warn-and-continue this function is built
    # to give. A missing repository was handled; a missing git was not, and
    # the two look identical to a caller.
    try:
        repo = system_git_is_repo()
    except GitError as e:
        log("warn", f"git is not usable here ({e}) — nothing committed. "
                    f"The files themselves are written; only the history "
                    f"step is skipped.")
        return False
    if not repo:
        log("warn", "not a git repository — nothing committed. "
                    "Run: python coordinator/circle_audit.py --git-setup")
        return False
    if not system_git_isolated_assert(log) or system_git_remote_refuse(log):
        return False
    # git IS here but nobody told it who commits — the fresh-install case.
    # Caught BEFORE staging: the raw refusal reads as breakage in a tree
    # where git is optional, and a failed commit would also leave the index
    # for _unstage() to repair. Skipped, with the kind note, once.
    if not system_git_identity_is_known():
        system_git_unconfigured_report(log)
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
    rc, out = system_git_run("diff", "--cached", "--name-only", "--", *rel,
                  read_only=True)
    pre_staged = set(out.splitlines()) if rc == 0 else set(rel)
    ours = [r for r in rel if r not in pre_staged]
    system_git_run("add", "--", *rel, check=True)
    rc, _ = system_git_run("diff", "--cached", "--quiet", read_only=True)
    if rc == 0:
        log("ok", "nothing changed in those paths — no commit made")
        return True
    rc, out = system_git_run("commit", "-m", message, "--only", "--", *rel)
    if rc != 0:
        log("fail", f"commit failed (git exit {rc}) — {system_git_failure_explain(out)}")
        for ln in _failure_tail(out):
            log("fail", f"    {ln}")
        _unstage(ours, log)
        return False
    log("did", f"commit {system_git_head_read()} — {message}")
    if tag:
        rc, out = system_git_run("tag", tag)
        log("did" if rc == 0 else "warn",
            f"tag {tag}" if rc == 0 else f"tag {tag} not created: {out}")
    return True


# ----------------------------------------------------------------- cli
def main() -> int:
    """`--identity` only. A read-only window onto system_git_identity_resolve(), so the
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
                                 system_git_identity_resolve()):
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
