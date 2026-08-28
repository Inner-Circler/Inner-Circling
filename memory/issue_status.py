#!/usr/bin/env python3
"""
issue_status.py — change a node's status. Operation 7 of `operations.md`,
with its two consequences (8 and 9) written by the same act.

    python memory/issue_status.py nNNNN nMMMM --to lead \
        --ruled "the words that decided it"

    --dry-run     show the three writes and touch nothing
    --source REF  the circle or session the ruling was made in

WHY THIS IS A PROGRAM AND NOT A HAND EDIT. `operations.md` measures that a
status change is never one write. It is three:

    7  status = "lead"              the DECISION.        Self's.
    8  nNNNN.toml -> L_n9999.toml   the file rename.     Clerical.
    9  a description_history line   the audit trail.     Clerical.

Rows 8 and 9 are consequences: they follow deterministically from 7 and
carry no judgement at all. Done by hand they are three chances to write two
of the three and believe the job finished — and the graph would then be
INTERNALLY INCONSISTENT IN A WAY THE GATE CATCHES ONLY FOR THE RENAME. A
missing history line is silent, and it is the one field that records why any
of the rest is as it is.

**A consequence must never be able to occur without its decision.** Here the
inverse also holds: the decision can no longer occur without its
consequences, because one call performs all three or none.

CLOSURE IS CHECKED BEFORE ANYTHING IS WRITTEN. An edge is legal only when
both ends are live (`issue_gate`), so demoting a node out of `live` can
invalidate an edge belonging to a node this command was never pointed at.
That is refused rather than repaired: retiring an edge is a separate ruling
(row 13), and inferring it from a status change would be this program making
a decision.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "coordinator"))  # atomic_write/identity et al.
import identity as ID                                          # noqa: E402
import issue_schema as S                                       # noqa: E402

# WINDOWS CONSOLES DEFAULT TO cp1252 AND RAISE on the em-dashes and
# arrows this project prints. Degrade instead of crashing: a probe that
# dies formatting its own PASS message reports a failure that is not
# there, which is how three suites read as broken for a week.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


ROOT = S.ROOT


def _load_all() -> dict[str, tuple[pathlib.Path, dict]]:
    out = {}
    for p in S.nodes():
        d = S.load(p)
        out[d["id"]] = (p, d)
    return out


def _closure_breaks(g, moving: set[str], to: str) -> list[str]:
    """Edges that would be left with a non-live end. Both directions: an
    edge naming this node lives in the OTHER node's file, and a check that
    only walked the moving nodes' own edges would miss every one of them."""
    if to == "live":
        return []
    bad = []
    for nid, (_, d) in sorted(g.items()):
        for e in d.get("edges", []):
            if e.get("status") == "retired":
                continue
            ends = {nid, e["target"]}
            if not (ends & moving):
                continue
            # the other end must still be live afterwards
            others = ends - moving
            if all(g[o][1]["status"] == "live" for o in others if o in g):
                who = "its own" if nid in moving else f"{nid}'s"
                bad.append(f'{nid} --{e["type"]}--> {e["target"]} '
                           f'[{e.get("status")}] ({who} file)')
    return bad


def _history_line(to: str, ruled: str, source: str, today: str) -> str:
    # THE FIXED DISPLAY NAME, not the configured one. R132, 2026-08-11: a
    # literal name is forbidden PII, and this line is written INTO a node
    # whose provenance text reaches every part's prompt directly
    # (circle.py::build_briefing() via check_issues.block(), since
    # self/circle_briefing.md's retirement the same day). Before R132 this
    # called ID.user_name(), which is exactly the personalization channel
    # that ruling closes for anything prompt-facing. Old entries already
    # written with a personal name are left as they are — this only changes
    # what gets written from here on.
    bits = [f"- **{today}** — Status → `{to}`. **Ruled by {ID.DISPLAY}**"]
    if source:
        bits.append(f" in `{source}`")
    bits.append(".")
    if ruled:
        bits.append(f' His words: *"{ruled}"*')
    return "".join(bits)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("nodes", nargs="+", metavar="issue")  # R279: the usage line says the class
    ap.add_argument("--to", required=True, choices=sorted(S.STATUSES))
    ap.add_argument("--ruled", default="")
    ap.add_argument("--source", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    g = _load_all()
    moving = set(a.nodes)
    if unknown := moving - set(g):
        print(f"  no such issue: {', '.join(sorted(unknown))}")
        return 2

    already = [n for n in sorted(moving) if g[n][1]["status"] == a.to]
    if already:
        print(f"  already `{a.to}`: {', '.join(already)}")
        return 2

    if breaks := _closure_breaks(g, moving, a.to):
        print(f"  REFUSED — {len(breaks)} issue-relationship(s) would be left with an end "
              f"that is not live:")
        for b in breaks:
            print(f"    {b}")
        print("  Retire the issue-relationship first (its own ruling), then re-run.")
        return 1

    today = _dt.date.today().isoformat()
    line = _history_line(a.to, a.ruled, a.source, today)
    moves: list[tuple[pathlib.Path, pathlib.Path]] = []

    for nid in sorted(moving):
        old, doc = g[nid]
        was = doc["status"]          # BEFORE the mutation. Read after, it
        new = S.path_for(nid, a.to)  # printed `lead -> lead` — the same dict
        doc["status"] = a.to
        hist = doc.get("description_history", "").rstrip("\n")
        doc["description_history"] = f"{hist}\n\n{line}\n"
        print(f"  {nid}  {was!r:>10} -> {a.to!r}")
        print(f"      {old.name} -> {new.name}")
        print(f"      + {line[:64]}...")
        if a.dry_run:
            continue
        # git mv FIRST so the rename is recorded as a rename rather than a
        # delete plus an add, then rewrite in place. The reverse order loses
        # the file's history at every status change.
        if old != new:
            # OSError IS THE THIRD CASE, and it was the one that crashed.
            # `git mv` failing gives a RETURN CODE — untracked file, no
            # repository — and the rename below covers it. git not being
            # INSTALLED gives an OSError from subprocess itself, which
            # never reaches that line, so a status change died on a
            # machine with no git rather than falling back. Since
            # 2026-08-24 git is optional here by ruling; a plain rename is
            # the correct outcome in a tree that keeps no history, and the
            # only thing lost is git seeing the change as a rename rather
            # than a delete plus an add.
            try:
                rc = subprocess.run(
                    ["git", "mv", str(old.relative_to(ROOT)),
                     str(new.relative_to(ROOT))],
                    cwd=str(ROOT), capture_output=True, text=True,
                    encoding="utf-8").returncode
            except OSError:                       # git not installed
                rc = 1
            if rc:                                # untracked, or no repo
                old.rename(new)
        S.save(new, doc)
        moves.append((old, new))

    if a.dry_run:
        print("\n  --dry-run: nothing written")
        return 0

    print()
    # THE FOURTH WRITE USED TO BE THE BRIEFING, and it was missed on the
    # first run: self/circle_briefing.md projected the LIVE set and every
    # part read it, so a node demoted here went on being presented to the
    # room as a live issue until the next nightly regenerated it. Retired
    # 2026-08-11 -- circle.py's build_briefing() reads issues/*.toml
    # directly at prompt-assembly time, so a status change is reflected the
    # moment the next circle opens. No projection step, nothing to trigger.
    #
    # `issue_draw.py issues/` also dropped from this chain, 2026-08-13:
    # issue_draw.py was a development tool -- a picture for a human to read,
    # nothing a part or a gate ever reads back -- so it moved to work/graph/
    # beside its own output and is no longer auto-regenerated HERE.
    #
    # IT IS AUTO-REGENERATED AGAIN SINCE 2026-08-27, from a different place
    # and on a different trigger: circle.py redraws it at every live /close
    # whose graph moved (ui/issue_draw.py --if-stale), so a status change
    # made in a circle reaches the picture at that circle's close. This
    # chain still does not run it, and should not -- once per circle, not
    # once per ruling. A status change made OUTSIDE a circle leaves the
    # picture stale until the next live close, or until it is run by hand:
    #     python ui/issue_draw.py issues/
    # memory/, not coordinator/ — both scripts moved with the issue-graph
    # code (R203) and this chain kept the old directory: every real status
    # change reported "FAILED" and neither ever ran. The tests never saw it
    # because test_issue_status_cmd.py mocks subprocess.run on this path.
    for script in ("issue_index.py", "issue_gate.py"):
        r = subprocess.run([sys.executable, f"memory/{script.split()[0]}"]
                           + script.split()[1:],
                           cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
        tail = (r.stdout + r.stderr).strip().splitlines()
        print(f"  {script}")
        for ln in tail[-2:]:
            print(f"    {ln.strip()}")
        if r.returncode:
            print(f"\n  {script} FAILED — the writes are on disk and the "
                  f"graph may be inconsistent. `git checkout issues/ self/` "
                  f"reverts.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
