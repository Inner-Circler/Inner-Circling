#!/usr/bin/env python3
"""
write_guard.py — the coordinator's write-safety gate. Phase 1 step 2 of
the coordinator partitioning (2026-08-16); until then WriteGuard and
_within lived in circle.py. Verbatim move: the class body and its
helper are unchanged, only their path constants now come from record_paths.py.

The guard is MODE-SCOPED, not path-scoped: sandbox mode may write only
under work/sandbox/, live mode adds exactly the current circle's own
transcript, short_terms, remember registers and prompt captures —
nothing else, ever. It raises rather than warns; a refused write is a
crash, which is the point.
"""

from __future__ import annotations

import pathlib

from record_paths import ROOT, SANDBOX, PART_TAGS, record_dir


class WriteGuard:
    """Refuses any write outside the allowed set for the current mode."""

    def __init__(self, live: bool, open_time: str):
        self.live = live
        self.ot = open_time

    def check(self, p: pathlib.Path) -> pathlib.Path:
        rp = p.resolve()
        if _within(rp, SANDBOX):
            return rp
        if not self.live:
            raise RuntimeError(
                f"REFUSING write outside work/sandbox (sandbox mode): {rp}"
            )
        if rp == (record_dir(ROOT, "circles") / f"circle_{self.ot}.md").resolve():
            return rp
        parts_dir = record_dir(ROOT, "parts").resolve()
        if (
            _within(rp, parts_dir)
            and rp.parent.parent == parts_dir
            and rp.parent.name in PART_TAGS
            # .toml since R434 (B96, 2026-09-04); .md is what a resumed
            # pre-B96 close still writes into. Spelled here rather than
            # asked of short_term_manager: this is the grammar layer.
            and rp.name in (f"short_term_{self.ot}.toml", f"short_term_{self.ot}.md")
        ):
            return rp
        # parts/<part>/remember.toml — a part's own REMEMBER register.
        # Unlike short_term above, this is not per-OT: the same file
        # accumulates across every circle, so the filename is fixed rather
        # than stamped with self.ot.
        if (
            _within(rp, parts_dir)
            and rp.parent.parent == parts_dir
            and rp.parent.name in PART_TAGS
            and rp.name == "remember.toml"
        ):
            return rp
        # self/remember.toml — Self's own REMEMBER register (B48,
        # 2026-08-17, R206). Same standing as a part's own file above:
        # accumulates across circles, filename fixed, not stamped with
        # self.ot. Scoped to this one file, not the whole self/ directory
        # — matching the precision every other rule here already uses.
        if rp == (record_dir(ROOT, "self") / "remember.toml").resolve():
            return rp
        # work/prompts/<OT>/ — the emitted system prompts, this circle's
        # only. Moved up from ROOT/prompts/ 2026-08-08 (a packaging root, not
        # code, has no business owning a coordinator-only output directory),
        # then moved again to work/prompts/, R176, 2026-08-15 — coordinator/
        # is product domain and this is transcript-derived content.
        if _within(rp, ROOT / "work" / "prompts" / self.ot):
            return rp
        # work/prompts/<OT>_resume_<k>/ — a resumed sitting re-emits the
        # program, and it may differ from the one the circle opened with if a
        # part's files changed in between. Kept as a sibling so
        # prompt_capture --verify's glob over prompts/* covers it without
        # knowing resume exists.
        pd = (ROOT / "work" / "prompts").resolve()
        if rp.is_relative_to(pd) and len(rp.relative_to(pd).parts) >= 1 \
                and rp.relative_to(pd).parts[0].startswith(f"{self.ot}_resume_"):
            return rp
        raise RuntimeError(f"REFUSING write outside the live allow-list: {rp}")


def _within(child: pathlib.Path, parent: pathlib.Path) -> bool:
    try:
        child.relative_to(parent.resolve())
        return True
    except ValueError:
        return False
