#!/usr/bin/env python3
"""
circle_open_verify.py — the OPEN STEP's verifier: what an open left behind, written down.

    circle_open.circle_open_verifier_run()     in-process, at the end of every open, after
                                               the opening round
    python coordinator/circle_open_verify.py --open-time <OT>
                                               by hand, for one circle

REPORT ONLY. R535, 2026-09-10, the operator's words: *"1 - report only."*
It writes one file and refuses nothing:

    work/logs/open_<OT>.json            a live circle
    work/sandbox/logs/open_<OT>.json    a dry run — which writes only under work/sandbox/

The live one is FILED WITH ITS CIRCLE (R537): .gitignore re-includes
open_*.json beside close_*.json, and transcript_store.circle_commit_paths() stages it in the
close's own commit; circle_audit.py's phase 2 reads it back, and warns without failing. A dry
run's stays under work/sandbox/logs/, which nothing commits.

WHAT "REPORT ONLY" MEANS, exactly, because each half has its own way to fail:

    circle_open() acts on nothing this returns;
    nothing here raises into the open — the caller wraps the call, the import included;
    nothing here calls seam.fail() — circle.py turns a fail() into a non-zero exit, and a
        verifier that moves the exit code has refused by another route.

IN-PROCESS, where its twin circle_close_verify.py is shelled out to at every close. A fresh
process resolves the record through its own --group, and E33 is what happened the first time
one was not told which: the band's close looked in the wrong group's circles/. Called from
inside the open, the group is already bound and WS.WORKING_SETS already follows it. The price
is that nothing on the in-process path may print() — the Ticker bridge reads stdout as its
NDJSON protocol — so the caller emits, through the seam, and only in dev mode.

THE POSTCONDITIONS live in coordinator/open_contract.toml, where each one's `says` is a
sentence a reader can check and change. An id the contract names that nothing here evaluates,
or one evaluated here that the contract does not name, is itself in the report — so the file
cannot drift from the code in either direction without saying so.

READING AN OPEN CIRCLE'S TRANSCRIPT, and why circle_state's guard does not apply here. That
guard exists because a partial transcript is well-formed and reads as a finished one. Nothing
here draws a conclusion from how much a transcript says — only that its header line names its
own open time, which is as true of a partial transcript as of a finished one.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime

COORD = pathlib.Path(__file__).resolve().parent
# THE BOOTSTRAP TRAVELS WITH THE FILE. Run as a script, Python puts coordinator/ on sys.path and
# nothing else, and transcript_store reaches memory/ — the persistence layer since 2026-09-09.
# record_verify.py lost exactly these lines when it moved there, and could not start as a script
# until they were put back. In-process both are already present and this loop does nothing.
for _p in (COORD, COORD.parent / "memory"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import record_paths as _RP                                           # noqa: E402

OPEN_CONTRACT = COORD / "open_contract.toml"


def _rel(p: "pathlib.Path | None") -> "str | None":
    """A path as the report records it: relative to the tree when it is inside it."""
    if p is None:
        return None
    try:
        return pathlib.Path(p).resolve().relative_to(_RP.ROOT.resolve()).as_posix()
    except ValueError:
        return pathlib.Path(p).as_posix()


def circle_open_contract_read() -> dict:
    """open_contract.toml, or {} when absent — and the report says so out loud, R368's rule for
    the close contract applied to its twin. A fourth identical body beside circle_close_verify's,
    circling_verify's and prompt_capture's, for the reason the close's own docstring gives: each
    verifier owns its contract, and a shared helper would need a home none of them has."""
    try:
        import tomllib as _toml
    except ModuleNotFoundError:                              # pragma: no cover
        import tomli as _toml                                # type: ignore
    try:
        with OPEN_CONTRACT.open("rb") as fh:
            return _toml.load(fh)
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------- the four checks
# Each takes (ot, live, transcript, capture, parts) and returns (result, detail). Their
# imports are lazy, so a module that will not import fails ITS check and no other.

def _transcript_check(ot, live, transcript, capture, parts):
    import transcript_store as TS
    if transcript is None or not pathlib.Path(transcript).is_file():
        return "fail", f"no transcript at {_rel(transcript)}"
    try:
        head_ot, _topic, _rows = TS.circle_transcript_parse(
            pathlib.Path(transcript).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return "fail", f"{_rel(transcript)} does not parse as a transcript — {e}"
    if head_ot != ot:
        return "fail", f"{_rel(transcript)}'s header names {head_ot}, not {ot}"
    return "pass", ""


def _working_set_check(ot, live, transcript, capture, parts):
    if not live:
        return ("not_applicable", "a dry run records no working set — working_set_record() "
                                  "returns before the append")
    import working_set_manager as WS
    rows = WS.working_set_entry_read(ot)
    if len(rows) == 1:
        return "pass", ""
    where = _rel(WS.WORKING_SETS)
    if not rows:
        return "fail", f"{where} has no entry for {ot}"
    return "fail", f"{where} has {len(rows)} entries for {ot}; an open time is minted once"


def _capture_check(ot, live, transcript, capture, parts):
    if not live:
        return "not_applicable", "a non-live run captures nothing — prompt_capture_write() returns None"
    if capture is None:
        return "fail", "no capture directory — the prompt capture did not run, or failed"
    import prompt_capture as PCAP
    capture = pathlib.Path(capture)
    if not (capture / PCAP.MANIFEST).is_file():
        return "fail", f"{_rel(capture)} has no {PCAP.MANIFEST}"
    fails: list = []
    notes: list = []
    # THE ONE READER OF A CAPTURE, never a second: _verify_dir is what `prompt_capture --verify`
    # runs per directory. Private, and called across the module boundary on purpose — the public
    # prompt_capture_verify() prints its findings, and nothing on this path may print.
    PCAP._verify_dir(capture, fails, notes)
    if fails:
        more = f" (+{len(fails) - 5} more)" if len(fails) > 5 else ""
        return "fail", "; ".join(fails[:5]) + more
    return "pass", "; ".join(notes)


def _roster_check(ot, live, transcript, capture, parts):
    if not live:
        return "not_applicable", "a non-live run captures nothing — there is no roster to read"
    if not parts:
        return "not_applicable", "no roster was given to check the capture against"
    import prompt_capture as PCAP
    if capture is None or not (pathlib.Path(capture) / PCAP.MANIFEST).is_file():
        return "fail", "no capture manifest to read the roster from"
    have = set(PCAP.prompt_manifest_read(pathlib.Path(capture)).get("parts") or {})
    want = set(parts)
    if have == want:
        return "pass", ""
    bits = []
    if want - have:
        bits.append("missing from the capture: " + ", ".join(sorted(want - have)))
    if have - want:
        bits.append("in the capture but not the circle: " + ", ".join(sorted(have - want)))
    return "fail", "; ".join(bits)


def _checks() -> tuple:
    return (("transcript_names_its_open_time", _transcript_check),
            ("working_set_recorded", _working_set_check),
            ("capture_is_whole", _capture_check),
            ("capture_covers_every_part", _roster_check))


def circle_open_postcondition_verify(ot: str, live: bool, transcript, capture,
                                     parts) -> "list[dict]":
    """Every postcondition against one open. One row each: {id, result, detail}, result one of
    pass / fail / not_applicable. A check that RAISES is a failed row naming the exception, so
    one broken check can neither hide the others nor escape into the caller."""
    rows = []
    for pid, fn in _checks():
        try:
            result, detail = fn(ot, live, transcript, capture, parts)
        except Exception as e:                               # noqa: BLE001
            result, detail = "fail", f"the check itself raised — {type(e).__name__}: {e}"
        rows.append({"id": pid, "result": result, "detail": detail})
    return rows


def circle_open_contract_agree(rows: "list[dict]", contract: dict) -> "list[str]":
    """Where the evaluated rows and the contract disagree, as sentences. Empty is agreement."""
    if not contract:
        return [f"{OPEN_CONTRACT.name} is missing or unreadable — nothing here was checked "
                f"against it"]
    named = [p.get("id") for p in contract.get("postcondition", []) if isinstance(p, dict)]
    evaluated = [r["id"] for r in rows]
    out = [f"the contract names {i}, which nothing here evaluates"
           for i in named if i not in evaluated]
    out += [f"{i} is evaluated here, but the contract does not name it"
            for i in evaluated if i not in named]
    return out


def circle_open_report_write(report: dict, live: bool,
                             root: "pathlib.Path | None" = None) -> pathlib.Path:
    """work/logs/open_<OT>.json, or work/sandbox/logs/ for a dry run. `root` is for probes,
    which must write nothing in the tree. LF on every machine: text mode writes CRLF on Windows."""
    base = pathlib.Path(root) if root is not None else _RP.ROOT
    logs = base / "work" / "logs" if live else base / "work" / "sandbox" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"open_{report['open_time']}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def circle_open_verify(ot: str, live: bool, transcript, capture, parts,
                       root: "pathlib.Path | None" = None) -> "tuple[dict, str]":
    """Check one open, write its report, return (report, where it was written). The ONE entry
    point circle_open() calls. REPORT ONLY — see the module docstring for what that rules out."""
    rows = circle_open_postcondition_verify(ot, live, transcript, capture, parts)
    disagree = circle_open_contract_agree(rows, circle_open_contract_read())
    failed = [r["id"] for r in rows if r["result"] == "fail"]
    report = {
        "open_time": ot,
        "checked_at": datetime.now().strftime("%Y-%m-%d_%H%M%S"),
        "live": bool(live),
        "group": _RP.group_read(),
        "transcript": _rel(transcript),
        "capture": _rel(capture),
        "parts": sorted(parts or []),
        "verifier": "circle_open_verify.py",
        "result": "fail" if failed or disagree else "pass",
        "failed": failed,
        "contract": disagree,
        "note": ("REPORT ONLY — nothing here stops a circle or changes its exit code "
                 "(R535)."),
        "postconditions": rows,
    }
    where = circle_open_report_write(report, live, root)
    return report, (_rel(where) or str(where))


def main(argv: "list[str] | None" = None) -> int:
    # Only as a script: an in-process import must not reconfigure the UI's stdout.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(
        description="The open step's verifier: what an open left behind. Report only.")
    ap.add_argument("--open-time", required=True, help="the circle to check, YYYY-MM-DD_HHMM")
    ap.add_argument("--dry-run", action="store_true",
                    help="check a sandbox circle rather than a live one")
    ap.add_argument("--group", default=None, help="read this group's record (groups/<name>/)")
    ap.add_argument("--parts", default=None,
                    help="comma-separated roster the capture must cover")
    ap.add_argument("--capture", default=None,
                    help="the capture directory's name under work/prompts/ (a resumed "
                         "circle's is <OT>_resume_<k>)")
    ap.add_argument("--write-report", action="store_true", help="also write the report file")
    args = ap.parse_args(argv)
    if args.group:
        _RP.group_set(args.group)
    live = not args.dry_run
    ot = args.open_time

    # The transcript's path has ONE home, circle_open.circle_transcript_path_read(). Imported
    # here and lazily, because circle_open imports this module at the end of every open.
    import circle_open as _CO
    import prompt_capture as PCAP
    transcript = _CO.circle_transcript_path_read(live, ot)
    capture = (PCAP.PROMPTS / (args.capture or ot)) if live else None
    parts = [p for p in (args.parts or "").split(",") if p]
    if not parts:
        prior = (_RP.ROOT / "work" / ("logs" if live else "sandbox/logs") / f"open_{ot}.json")
        try:
            parts = list(json.loads(prior.read_text(encoding="utf-8")).get("parts") or [])
        except (OSError, ValueError):
            parts = []

    rows = circle_open_postcondition_verify(ot, live, transcript, capture, parts)
    disagree = circle_open_contract_agree(rows, circle_open_contract_read())
    print(f"Open-step postconditions — circle {ot} ({'live' if live else 'dry run'})"
          f" — REPORT ONLY")
    for r in rows:
        label = r["result"].replace("_", " ")
        print(f"  {label:<15} {r['id']}" + (f" — {r['detail']}" if r["detail"] else ""))
    for d in disagree:
        print(f"  contract        {d}")
    failed = [r["id"] for r in rows if r["result"] == "fail"]
    print(f"  result: {'fail' if failed or disagree else 'pass'}")
    if args.write_report:
        _report, where = circle_open_verify(ot, live, transcript, capture, parts)
        print(f"  report written: {where}")
    return 1 if failed or disagree else 0


if __name__ == "__main__":
    raise SystemExit(main())
