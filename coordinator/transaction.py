#!/usr/bin/env python3
"""
transaction.py — phases 7-9 of NIGHTLY_DESIGN.md: commit, verify, record.

WHAT THIS GUARANTEES, AND WHAT IT CANNOT

    `os.replace()` is atomic per file on NTFS. There is no multi-file atomic
    commit on any filesystem, so a true all-or-nothing swap of 20 files is not
    available. What IS available, and what this implements, is a swap that is
    always **detectable** and **completable**:

        1  write JOURNAL (every intended replace, with sha256 either side), fsync
        2  copy each live file to rollback/, fsync
        3  os.replace() each staged file over its live path
        4  fsync
        5  delete JOURNAL

    A crash anywhere between 1 and 5 leaves the JOURNAL on disk. Every later run
    refuses to start while it exists, and offers two deterministic repairs —
    finish, or roll back — each a pure file operation with a known sha256 on both
    sides. No judgement, no model, no guessing.

    So the worst case is a tree that is *known to be* half-swapped and
    mechanically repairable, rather than a tree that is quietly half-written and
    nobody notices for six weeks.

STAGING
    Only CHANGED files are staged. candidate_tree() overlays them on the live
    tree to produce a full candidate for ifs_model.compare_trees(), so the
    invariant gate sees the complete before/after picture rather than a fragment.

ROOT IS A PARAMETER
    Every path is derived from the root passed in, so the whole commit/rollback
    path can be exercised against a throwaway copy of the tree. A transaction
    system that has only ever been tested on the real data is not a tested one.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import shutil

import ifs_model as M
from atomic_write import atomic_write

JOURNAL_NAME = "JOURNAL"


def _fsync_file(p: pathlib.Path) -> None:
    try:
        fd = os.open(p, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass                      # best effort; not available for all paths


def _rmtree_retry(p: pathlib.Path, tries: int = 3, backoff: float = 0.5) -> None:
    """shutil.rmtree with a bounded retry — AUTHORIZED 2026-08-16 after
    the mechanism behind every test_inter_circle 'collision' this session
    was traced: a transient Windows lock (antivirus-scan class) on a
    freshly written staging file breaks the teardown mid-walk with
    WinError 145, and the RESIDUE then poisons every subsequent run of
    the same (root, run_id) until one recovers. Three attempts, half a
    second apart, outlast the scan; the FINAL failure still raises —
    a teardown that cannot complete after three tries is a real
    condition, not a flake to swallow."""
    import time
    for i in range(tries):
        try:
            shutil.rmtree(p)
            return
        except OSError:
            if i == tries - 1:
                raise
            time.sleep(backoff)


def _fsync_dir(p: pathlib.Path) -> None:
    # Directory fsync is POSIX-only; on Windows opening a directory fails. The
    # per-file fsync above is what carries the durability guarantee there.
    if os.name == "nt":
        return
    try:
        fd = os.open(p, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


class Transaction:
    """One nightly run's staged output and its commit."""

    def __init__(self, root: pathlib.Path, run_id: str):
        self.root = pathlib.Path(root).resolve()
        self.run_id = run_id
        self.dir = self.root / "work" / "nightly" / run_id
        self.staging = self.dir / "staging"
        self.rollback = self.dir / "rollback"
        self.candidate = self.dir / "candidate"
        self.journal = self.dir / JOURNAL_NAME
        # Set by commit(): the JOURNAL's own entries, sha_new hashed from
        # STAGING before the swap. record_committed() writes these — see
        # its docstring for why it must never re-hash the live tree.
        self._committed_entries: list[dict] | None = None

    # ---------------------------------------------------------------- stage
    def stage(self, rel: str, data: bytes) -> pathlib.Path:
        """Record the exact bytes intended for <root>/<rel>."""
        dest = self.staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    def staged(self) -> list[str]:
        if not self.staging.is_dir():
            return []
        return sorted(p.relative_to(self.staging).as_posix()
                      for p in self.staging.rglob("*") if p.is_file())

    def changed(self) -> list[str]:
        """Staged paths whose bytes actually differ from the live file. A run that
        stages an identical file should not commit it — an unchanged file in a
        commit is noise in every future diff."""
        out = []
        for rel in self.staged():
            live = self.root / rel
            new = (self.staging / rel).read_bytes()
            if not live.is_file() or live.read_bytes() != new:
                out.append(rel)
        return out

    # ---------------------------------------------------------------- validate
    def candidate_tree(self) -> pathlib.Path:
        """Live tree with the staged files overlaid — what the tree WOULD be."""
        if self.candidate.exists():
            _rmtree_retry(self.candidate)
        for p in M._tree_files(self.root):
            if p.is_file():
                q = self.candidate / p.relative_to(self.root)
                q.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, q)
        for p in (self.root / "self").glob("narrative_*.md"):
            q = self.candidate / "self" / p.name
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
        # TOML registers (docs/REGISTER_GATE_DESIGN.md, R188): copied so the
        # register gate sees every register in the candidate — an unstaged
        # one arrives byte-identical (compare_register reports it unchanged,
        # and FROZEN actually gets verified rather than skipped).
        for p, _spec in M._register_paths(self.root):
            q = self.candidate / p.relative_to(self.root)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)
        for rel in self.staged():
            q = self.candidate / rel
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.staging / rel, q)
        return self.candidate

    def validate(self, today: str | None = None,
                 first_synthesis: bool = False) -> list[M.Finding]:
        return M.compare_trees(self.root, self.candidate_tree(), today=today,
                               first_synthesis=first_synthesis)

    # ---------------------------------------------------------------- commit
    def commit(self, log) -> bool:
        """Phase 7. Returns False and leaves the tree untouched on any refusal."""
        rels = self.changed()
        if not rels:
            log("ok", "nothing differs from the live tree — no commit needed")
            self._committed_entries = []
            return True
        if self.journal.exists():
            log("fail", f"a JOURNAL already exists at {self.journal} — resolve it "
                        f"before committing again")
            return False

        entries = []
        for rel in rels:
            live = self.root / rel
            new = (self.staging / rel).read_bytes()
            old = live.read_bytes() if live.is_file() else None
            entries.append({
                "rel": rel,
                "sha_new": M.sha(new),
                "sha_old": M.sha(old) if old is not None else None,
                "bytes_new": len(new),
                "bytes_old": len(old) if old is not None else None,
            })

        # 1. journal first, so a crash from here on is detectable — and
        # ATOMICALLY (2026-08-19, review tier 2 #21): the JOURNAL is the
        # detectability mechanism itself, and a plain write_text torn by
        # a crash left half-written JSON that every later commit refused
        # while all three --journal-* repairs crashed in json.loads.
        # atomic_write fsyncs the temp file and os.replace()s it in, so
        # the JOURNAL either exists whole or not at all.
        self.dir.mkdir(parents=True, exist_ok=True)
        atomic_write(self.journal, json.dumps({
            "run_id": self.run_id,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
            "root": self.root.as_posix(),
            "entries": entries,
        }, indent=2) + "\n")
        log("did", f"JOURNAL written for {len(entries)} file(s)")

        # 2. back up every live file we are about to overwrite
        for e in entries:
            live = self.root / e["rel"]
            if not live.is_file():
                continue
            b = self.rollback / e["rel"]
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(live, b)
            _fsync_file(b)
        log("did", f"rollback copies taken")

        # 3. the swap itself
        done = 0
        for e in entries:
            src, dst = self.staging / e["rel"], self.root / e["rel"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            _fsync_file(dst)
            done += 1
        _fsync_dir(self.root)
        log("did", f"replaced {done} file(s) in the live tree")

        # 5. only now is the swap no longer in progress
        self._committed_entries = entries
        self.journal.unlink()
        return True

    # ---------------------------------------------------------------- verify
    def verify(self, log) -> bool:
        """Phase 8. Re-read from disk and compare to what we meant to write. A
        write that silently did not land is the failure this exists to catch, and
        it cannot be caught by checking the value we just wrote in memory."""
        jr = self.dir / "committed.json"
        if not jr.is_file():
            log("warn", "no committed.json — nothing to verify")
            return True
        entries = json.loads(jr.read_text(encoding="utf-8"))["entries"]
        bad = []
        for e in entries:
            live = self.root / e["rel"]
            data = live.read_bytes() if live.is_file() else None
            if data is None or M.sha(data) != e["sha_new"]:
                bad.append(e["rel"])
        if bad:
            for rel in bad:
                log("fail", f"{rel}: on-disk content does not match what was "
                            f"committed — the write did not land")
            log("note", f"rollback copies are in "
                        f"{self.rollback.relative_to(self.root).as_posix()}")
            return False
        log("ok", f"re-read {len(entries)} file(s) from disk; every sha256 matches")
        return True

    def record_committed(self) -> None:
        """Phase 9's record: rel -> sha256 of the bytes this run MEANT to
        write, carried from the JOURNAL entries commit() hashed from STAGING
        before the swap — never re-read from the live tree. Until 2026-08-19
        this re-hashed the tree after the swap, which made verify() compare
        the disk against itself: a replace that silently left wrong bytes
        hashed as 'matching' on both sides, and phase 8 could not fail on
        the one defect it exists to catch. The staging files themselves are
        gone by now (os.replace consumed them), so the in-memory entries are
        the only surviving record of the intent."""
        if self._committed_entries is None:
            raise RuntimeError("record_committed() before a successful commit()")
        (self.dir / "committed.json").write_text(json.dumps({
            "run_id": self.run_id,
            "committed": datetime.datetime.now().isoformat(timespec="seconds"),
            "entries": [{"rel": e["rel"], "sha_new": e["sha_new"]}
                        for e in self._committed_entries],
        }, indent=2) + "\n", encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- recovery
def find_journals(root: pathlib.Path) -> list[pathlib.Path]:
    d = pathlib.Path(root) / "work" / "nightly"
    return sorted(d.glob(f"*/{JOURNAL_NAME}")) if d.is_dir() else []


def journal_report(jpath: pathlib.Path) -> tuple[dict, list[tuple[str, str]]]:
    """(journal, [(rel, state)]) where state is 'old' | 'new' | 'other' | 'absent'.
    Everything the repair needs is derivable from sha256 — no guessing which
    files were reached before the crash.

    Raises ValueError (not a raw JSONDecodeError traceback) on a JOURNAL
    that does not parse, with the repair guidance in the message —
    commit() writes the JOURNAL atomically since 2026-08-19, so a torn
    one can no longer be created here, but one damaged by something else
    still deserves a diagnosis rather than a crash in the diagnostic."""
    try:
        j = json.loads(jpath.read_text(encoding="utf-8"))
    except ValueError as e:
        raise ValueError(
            f"the JOURNAL at {jpath} does not parse ({e}). If the run "
            f"crashed while WRITING it, no live file had been touched yet "
            f"and deleting the JOURNAL is the whole repair — but the "
            f"journal write has been atomic since 2026-08-19, so on a "
            f"newer run the file was damaged AFTER being written whole: "
            f"investigate before deleting anything.") from e
    root = pathlib.Path(j["root"])
    states = []
    for e in j["entries"]:
        p = root / e["rel"]
        if not p.is_file():
            states.append((e["rel"], "absent"))
            continue
        s = M.sha(p.read_bytes())
        states.append((e["rel"],
                       "new" if s == e["sha_new"]
                       else "old" if s == e["sha_old"]
                       else "other"))
    return j, states


def journal_finish(jpath: pathlib.Path, log) -> bool:
    """Complete the interrupted swap: replace anything still holding old bytes."""
    j, states = journal_report(jpath)
    root, staging = pathlib.Path(j["root"]), jpath.parent / "staging"
    for rel, state in states:
        if state == "new":
            continue
        src = staging / rel
        if not src.is_file():
            log("fail", f"{rel} is '{state}' but its staged copy is gone — cannot "
                        f"finish; roll back instead")
            return False
        os.replace(src, root / rel)
        _fsync_file(root / rel)
        log("did", f"completed replace: {rel}")
    jpath.unlink()
    log("ok", "swap completed; JOURNAL removed")
    return True


def journal_rollback(jpath: pathlib.Path, log) -> bool:
    """Undo the interrupted swap: restore anything not still holding old bytes.

    A file the transaction CREATED (sha_old null in the JOURNAL) has no
    rollback copy — commit() rightly backed up nothing, because there was
    nothing — and its rolled-back state is ABSENT: the restore is deletion.
    Until 2026-08-19 this loop demanded a copy for every non-'old' entry,
    so a transaction that created any file could never be rolled back —
    it failed mid-loop with the JOURNAL kept, and after the partial restore
    journal_finish failed too (the restored files' staged copies were
    consumed by the original swap), leaving the JOURNAL unclearable by
    either of the doc's 'two deterministic repairs'."""
    j, states = journal_report(jpath)
    root, backup = pathlib.Path(j["root"]), jpath.parent / "rollback"
    created = {e["rel"] for e in j["entries"] if e["sha_old"] is None}
    for rel, state in states:
        if state == "old":
            continue
        if rel in created:
            if state != "absent":
                (root / rel).unlink(missing_ok=True)
                log("did", f"removed created file: {rel}")
            continue
        src = backup / rel
        if not src.is_file():
            log("fail", f"{rel} is '{state}' but no rollback copy exists — cannot "
                        f"restore it")
            return False
        shutil.copy2(src, root / rel)
        _fsync_file(root / rel)
        log("did", f"restored: {rel}")
    jpath.unlink()
    log("ok", "swap rolled back; JOURNAL removed")
    return True
