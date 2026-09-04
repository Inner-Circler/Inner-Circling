#!/usr/bin/env python3
"""
atomic_write.py — one atomic text-file commit for the register writers.
docs/HELP_DESIGN.md §6's first atomicity gap, built 2026-08-16 with
phase 1 step 4 of the coordinator partitioning: no register file was
written atomically — `write_text` in place means a crash mid-write
corrupts what was there before, with no protection beyond git. The
standard fix: write the full text to a temp file IN THE SAME DIRECTORY,
then `os.replace()` it over the real path — a rename, not a
write-in-place, atomic on NTFS and POSIX alike.

Validation stays the CALLER's job, and stays IN FRONT: REGISTER_CLASS.register_write
round-trips the rendered text before calling this (validate, then
atomically commit — §6's ordering), issue_schema.issue_write renders and
commits. Nothing here parses anything.

newline="\\n" IS NOT OPTIONAL — `.gitattributes` sets `* -text`, so a
text-mode default write on Windows would put CRLF through every
register (the 2026-08-07 incident class; see write_lf's comment in
transcript_store.py).
"""

from __future__ import annotations

import os
import pathlib


def record_atomic_write(path: pathlib.Path, text: str) -> None:
    # PID-stamped so two processes racing the same register never share
    # a temp file (the §6 concurrency note: the crash is the constant
    # risk, the cross-process race the occasional one — this handles the
    # first fully and keeps the second from corrupting the temp).
    tmp = path.parent / f".{path.name}.tmp{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise
