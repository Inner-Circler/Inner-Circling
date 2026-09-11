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
            # The pointer to docs/configuration.md came out of this message on
            # 2026-09-09: that file does not ship, and both ways to set the value
            # are already named in the sentence itself.
            log("warn", f"{key} is not set anywhere — git will refuse to "
                        f"commit. Set ${ENV_GIT_NAME}/${ENV_GIT_EMAIL} in "
                        f".env, or `git config --global {key} ...`.")

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
    # The citation of docs/NIGHTLY_DESIGN.md §6 came out of this refusal on
    # 2026-09-09: it carries the reasoning, it does not ship, and the sentence
    # stands without it.
    for name, url, why in bad:
        log("fail", f"remote {name} -> {url} could take this material OFF "
                    f"this machine: {why}. This repository is private "
                    f"therapeutic material. "
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
    # A PATH THAT IS GONE IS STILL COMMITTED WHEN GIT TRACKS IT — the deletion is the change.
    # /part-delete removes a folder and then commits it, and this loop kept only paths that
    # exist, so that commit found nothing and the deletion sat unstaged (found 2026-09-11,
    # R548). A gone path git never tracked is still skipped.
    rel = []
    for p in paths:
        try:
            r = p.resolve().relative_to(ROOT).as_posix()
        except ValueError:
            log("warn", f"outside the repository, skipped: {p}")
            continue
        if p.exists():
            rel.append(r)
        else:
            rc, out = system_git_run("ls-files", "--", r, read_only=True)
            if rc == 0 and out.strip():
                rel.append(r)
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
    # docs/configuration.md is this tree's own and does not ship — 2026-09-09.
    ap = argparse.ArgumentParser(
        description="git surface for Inner Circling")
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
