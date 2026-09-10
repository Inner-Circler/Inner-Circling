# GITREPO(1)

## NAME
gitrepo.py — the project's git surface: repository setup, identity resolution, ignore/attributes/hook maintenance, and path-scoped commits, shared by circle.py and circle_audit.py

## SYNOPSIS
    python coordinator/gitrepo.py
    python coordinator/gitrepo.py --identity

(All other functionality — `system_git_repo_ensure`, `system_git_config_ensure`, `system_git_attributes_ensure`, `system_git_hooks_ensure`, `system_git_ignore_ensure`, `system_git_ignored_untrack`, `system_git_paths_commit`, etc. — is a library API called from `circle.py` and `circle_audit.py`, not exposed as its own CLI verbs beyond `--identity`.)

## DESCRIPTION
This module centralizes every git operation the project performs automatically, and is explicit about what it deliberately does *not* automate, because each excluded category is one where an unattended script could destroy something a human wanted:

1. **Remotes** — never added by a script, and never one that could take this material off the machine. The repository is private therapeutic material. Committing operations refuse to run if any configured remote fails `system_git_remote_classify()` — a remote on a fixed or removable local volume passes (a second-disk backup is the intended case, R130, 2026-08-10); a network protocol, an `ssh` `user@host:path`, a UNC path, a mapped network drive, or anything unclassifiable is refused.
2. **History rewriting** — `filter-repo`, rebase, `reset --hard`, `commit --amend` are never invoked. Irreversible operations are left to a deliberate, manual, backed-up action by a human.
3. **Rollback** — checkout, revert, restore. Whether last night's dreaming run was *wrong* is a judgement no invariant can make; the scripts (elsewhere) print the exact command and stop rather than run it.
4. **`git add -A` during an automated run.** A machine commit stages only the exact paths that run produced, via `system_git_paths_commit()`, so a nightly run at 01:11 cannot sweep up whatever a human happened to be editing at midnight.

Everything else routine — repo init, git config (name/email/autocrlf), `.gitignore`/`.gitattributes` upkeep, and un-tracking paths that should never have been tracked — is automated and lives here.

**THE HOOK TEMPLATES ARE NOT HERE ANY MORE, 2026-09-09.** `PRE_COMMIT`, `HOOK_MARK`, `POST_COMMIT`, `POST_MERGE`, `_hook_syntax_check()` and `system_git_hooks_ensure()` moved to **`coordinator/git_hook_script.py`** — 2,676 lines, most of it `/bin/sh` in a Python string, with a different audience: this surface is called by nine modules and the templates by `circle_audit.py --git-setup` alone. See `coordinator/docs/git_hook_script.md`. Anything below that describes the hook's own shape describes that file now.

## MAIN
This file has no `main()` function in the conventional sense used elsewhere in the project; its `if __name__ == "__main__":` block calls a function literally named `main()`, but that function only implements the `--identity` read-only CLI. All other capability is a library surface with no dispatcher.

    if (the "--identity" flag was not given) then {
        print the argparse help text and return 0.
    } else {
        {
            resolve (user.name, user.email) via system_git_identity_resolve(), which prefers, in order: explicit flag (not offered by this narrow CLI), $IFS_GIT_NAME/$IFS_GIT_EMAIL, git's own configured user.name/user.email (local then global), or unset.
        }
        for each of the two keys: if (its resolved value is None) then { print it as UNSET with instructions and mark the overall result not-ok; } else { print the value and its source. }
        {
            attempt to import identity.py and print the resolved circle display name (`user_name_source()`) alongside its transcript tag, catching any exception broadly so a missing/broken identity module degrades to "unavailable" rather than crashing --identity.
        }
        if (the git-identity source was the ruled $UserName variable) then { print a note that it is the OS login on Windows, not a chosen name. }
        return 0 if both git identity values resolved, else 1.
    }

## COMMAND-LINE ARGUMENTS
- (none) — prints argparse's generated help and exits 0.
- `--identity` — print the resolved git author name/email (with source) and the resolved circle display name (with source), changing nothing. Exit 0 if both git values are set, 1 if either is unset. Default: off.

## DEPENDENCIES
Standard library: `os`, `pathlib`, `subprocess`, `sys`, `argparse`, `__future__`. External program: `git` (invoked via `subprocess.run` for every operation — version check, rev-parse, remote, status, config, init, add, diff, commit, tag, rm, ls-files). Optional third-party: `python-dotenv` (`from dotenv import load_dotenv`), used best-effort to load `.env` for `IFS_GIT_NAME`/`IFS_GIT_EMAIL`; absence is tolerated silently. Sibling module: `identity` (imported locally inside `main()`, aliased `_ID`) for the circle display name.

## EXTERNAL FILES
Read:
- `ROOT/.env`, best-effort, via `_load_env()`, whenever `system_git_config_ensure()` or `main()`'s identity resolution runs.
- `ROOT/.gitattributes`, in `system_git_attributes_ensure()`, to check whether the `* -text` rule is already present.
- `ROOT/.gitignore`, in `system_git_ignore_ensure()`, to check which required ignore patterns are missing.
- `ROOT/.git/hooks/pre-commit`, in `system_git_hooks_ensure()`, to check whether an inner-circling hook (and which version) is already installed.
- The git index/working tree generally, via the various `git` subcommands (`status`, `config`, `remote`, `rev-parse`, `ls-files`).

Written:
- `ROOT/.gitattributes` — appended with `* -text` by `system_git_attributes_ensure()` if not already present.
- `ROOT/.gitignore` — appended with any missing entries from `REQUIRED_IGNORES` by `system_git_ignore_ensure()`; existing entries are never removed or reordered.
- `ROOT/.git/hooks/pre-commit` — written by `system_git_hooks_ensure()` if absent, or replaced if it is an out-of-date version of this project's own hook (identified by a shared `HOOK_FAMILY` marker comment); a hook belonging to someone else (no recognized marker) is left untouched with a warning.
- The git index — via `git add`, `git rm --cached`, `git commit`, `git tag`, `git config`, `git init`, called from `system_git_repo_ensure()`, `system_git_config_ensure()`, `system_git_ignored_untrack()`, and `system_git_paths_commit()`.

## NETWORK ACCESS
None. All operations are local `git` subprocess calls; no remote is ever added or fetched from by this module, and it refuses committing operations (`system_git_paths_commit()`, via `system_git_remote_refuse()`) if any configured remote could take the material off this machine. A remote on a local fixed or removable volume is permitted and is reported with the reason it passed.

## HUMAN I/O
Stdout, via the `log(status, message)` callback that every `ensure_*` / `system_git_paths_commit` function accepts from its caller (this module never constructs its own logger) — statuses observed being passed include `"ok"`, `"did"`, `"warn"`, `"fail"`, `"note"`. `main()` itself prints directly. No stdin. Exit codes from `main()`: 0 or 1 as described above; other functions return booleans or lists rather than process exit codes, since they are library calls.

## OPERATION

### `system_git_run(*args, check=False)`
(`run()` before the B99 re-homing, 2026-09-03. Its six siblings in the next heading were swept then; this one was missed until 2026-09-09 — audit-register 2026-09-09 `#42`.)
    {
        Invoke `git <args>` in ROOT, capturing combined stdout+stderr, with a 120-second timeout. Raises GitError if git itself is not runnable (OSError), if the 120s timeout expires (subprocess kills git first; the message warns a stale `.git/index.lock` may remain — until 2026-08-19 TimeoutExpired escaped raw through every "non-fatal by design" caller), or if `check=True` and the exit code is nonzero.
    }

### `system_git_is_available()`, `system_git_is_repo()`, `system_git_toplevel_read()`,
### `system_git_remotes_read()`, `system_git_is_dirty()`, `system_git_head_read()`
    {
        Thin wrappers over `system_git_run()` answering, respectively: is git installed and runnable; is ROOT (or an ancestor) a git repo; the git top-level directory if any; the configured remote names; the porcelain-status dirty lines; the short HEAD sha or "(no commits)".
    }

### `system_git_isolated_assert(log)`
    if (there is no enclosing git repository) then {
        log a failure and return False.
    } else if (the enclosing repository's top level is not exactly ROOT) then {
        log a failure explaining that a parent repository would mix histories, with the fix (`git init` in ROOT), and return False.
    } else {
        log ok with the current HEAD and return True.
    }
This exists because git searches upward for `.git`, so a stray repository at a parent directory (or a home-directory dotfiles repo) would silently redirect every git command here onto a larger, possibly remote-bearing repository.

### `system_git_repo_ensure(log)`
    if (already a repo) then {
        return system_git_isolated_assert(log).
    } else {
        run `git init`, log it, then return system_git_isolated_assert(log).
    }

### `_load_env()`
    {
        Best-effort `.env` load via python-dotenv; a missing package or missing file is silently fine.
    }

### `_configured(key)`
    {
        Return the current value of a git config key, or None if unset/unreadable.
    }

### `system_git_identity_resolve(name=None, email=None)`
    {
        For (name, email) independently, in order of precedence: an explicit function argument (from a CLI flag, not offered by this file's own narrow CLI but available to callers like circle_audit.py); then $IFS_GIT_NAME/$IFS_GIT_EMAIL (shell or .env); then git's own local-then-global user.name/user.email; then unset (None). No hardcoded fallback identity exists deliberately — a hardcoded default was previously discovered sitting as an argparse default in nightly.py (circle_audit.py's own name until its 2026-08-19 rename), and the module's docstring treats a wrong-but-present default as worse than an explicit unset, since it would commit history under someone else's name.
    }

### `system_git_config_ensure(log, name, email)`
    {
        Resolve identity via system_git_identity_resolve(). For each of user.name/user.email whose source is "unset", log a warning that git will refuse to commit until it's configured.
    }
    for each of core.autocrlf ("false", required), user.name, user.email:
    if (the wanted value is None) then { skip it. }
    else if (the current git config already equals the wanted value) then { skip it. }
    else if (it's a user.* key, already has *some* value, and the wanted value came from an explicit flag or environment variable) then {
        log a warning that the existing identity is NOT overwritten, and tell the operator the manual command to change it themselves.
    } else if (it's a user.* key with an existing value whose source is git config itself) then {
        log ok, "already set, left alone".
    } else {
        run `git config <key> <value>` and log it.
    }
An existing git identity is never silently overwritten, by design — item 2 of the not-automated list, generalized to configuration rather than history.

### `system_git_attributes_ensure(log)`
    if (`.gitattributes` already contains the literal line `* -text`) then {
        log ok.
    } else {
        append it (with a leading blank line if the file is nonempty and lacks a trailing newline) and log the write.
    }

### `system_git_hooks_ensure(log)`
    if (`.git/hooks` does not exist) then {
        log a warning and skip.
    } else if (`.git/hooks/pre-commit` exists already) then {
        if (it contains the current HOOK_MARK) then { log ok, unchanged. }
        else if (it contains any HOOK_FAMILY marker, i.e. an older version of this project's own hook) then { overwrite it with the current template and log the replacement, naming the old version string found. }
        else { log a warning that a foreign hook exists and is left alone. }
    } else {
        write the template, chmod 0o755 (a no-op on Windows, tolerated via a caught OSError), and log the install.
    }
The pre-commit hook template (`PRE_COMMIT`; its version is `HOOK_MARK` in this file, v137 on 2026-09-04 — this sentence said "currently v9" until then, wrong by 128 versions, so read the constant and not this page) itself, once installed, resolves its interpreter (`.venv/Scripts/python.exe`, `.venv/bin/python`, the main tree's `.venv` via git-common-dir from a worktree, then bare `python`), runs `file_line_endings_verify.py --staged` unconditionally, then one `case "$FILES" in ...` block per trigger — among them `memory/issue_gate.py`/`test_issue_gate.py` (if `issues/` touched), the record, practice and budget verifiers (if `parts/` or `self/` touched), `logbook_ruling_verify.py` (if `rulings/`, `progress.md`, `work/pending/` or `work/instrument/LOG.md` touched), `prompt_capture.py --verify` (if `prompts/` touched), and `system_lint_verify.py` (if `coordinator/`, `memory/`, `ui/`, `packaging/`, `.claude/skills/` or `work/graph/` touched) — and on a refusal writes `work/diagnostics/gate_<time>.md` through `gate_report.py`. The `case` blocks are the one complete list; this is documentation of the hook's *shape*, not of gitrepo.py's own runtime behavior, since the hook runs later, in a separate `sh` process, at commit time.

### `system_git_ignore_ensure(log)`
    {
        Read `.gitignore`, compute the set of missing patterns from REQUIRED_IGNORES (secrets, venv, caches, temp workspaces, the tool database directory, run logs — deliberately excluding `work/sandbox/` (was `coordinator/sandbox/` until R176, 2026-08-15) as a directory-form entry per a 2026-08-03/08-07 ruling, since a directory-form ignore would defeat the negated re-inclusions the project relies on).
    }
    if (nothing is missing) then {
        log ok and return an empty list.
    } else {
        append the missing chunks (grouped under their header comments), log what was added, and return the list of added patterns.
    }

### `system_git_ignored_untrack(log)`
    {
        List every currently tracked path that `.gitignore` now excludes (`git ls-files --cached --ignored --exclude-standard`).
    }
    if (none) then {
        log ok and return an empty list.
    } else {
        remove them from the index only (`git rm --cached`, in batches of 200 to avoid command-length limits), log the count and top-level directories affected, log a note that old blobs remain in history, and return the untracked paths.
    }

### `system_git_remote_classify(url)`
    if (the URL is empty) then refuse: it cannot be classified.
    if (the URL carries a scheme other than file://) then refuse: a network protocol.
    if (the URL is a file:// form) then {
        strip the scheme (and a bare `localhost` authority) but NEVER a
        slash that belongs to the path — 2026-08-19, review tier 2 #20:
        the old stripping ate one slash, so git's UNC-in-file-URL
        spelling file:////server/share resolved onto the CURRENT drive
        and a network share classified "local volume (FIXED)".
        if (what remains begins // or \) then refuse: UNC, another machine.
        if (it begins with a single /) then drop that slash (file:///C:/x).
        else if (it begins with a drive letter, C:) then keep it (file://C:/x).
        else if (anything else remains) then refuse: file:// names a host.
        else refuse: an empty file:// URL.
    }
    if (the URL is user@host:path) then refuse: ssh.
    if (the URL begins \ or //) then refuse: a UNC path, another machine.
    otherwise ask Windows GetDriveTypeW for the volume the path sits on, and
    allow ONLY FIXED and REMOVABLE. Anything else — REMOTE (a mapped network
    drive), NO_ROOT_DIR, UNKNOWN, off-Windows — is refused. Fails closed.
    Returns (stays_on_this_machine, why); the reason is printed either way, so
    a remote that PASSES says why it passed.

### `system_git_remote_refuse(log)`
    for each configured remote, read its URL and classify it.
    log an OK line for each remote that stays on this machine, naming the reason.
    if (any remote failed) then {
        log a failure per remote naming the URL, the reason and the removal
        command, return True (meaning "refuse").
    } else {
        return False.
    }

### `system_git_paths_commit(paths, message, log, tag=None)`
    if (ROOT is not a git repository) then {
        log a warning and return False.
    } else if (system_git_isolated_assert fails, or system_git_remote_refuse returns True) then {
        return False (each has already logged its own reason).
    } else {
        {
            resolve each given path to a ROOT-relative posix string if it exists and is actually inside ROOT (paths outside ROOT are skipped with a warning, via a caught ValueError from relative_to).
        }
        if (no paths remain) then {
            log a warning and return False.
        } else {
            stage exactly those paths (`git add --`); check `git diff --cached --quiet`.
            if (nothing is staged after all) then {
                log ok, "nothing changed", return True.
            } else {
                commit with `--only` restricted to exactly those paths.
                if (the commit failed) then { log a failure with git's output and return False. }
                else {
                    log the new HEAD and the message; if a tag name was given, attempt to create it and log success or warning accordingly.
                    return True.
                }
            }
        }
    }

## BUGS
None found.
