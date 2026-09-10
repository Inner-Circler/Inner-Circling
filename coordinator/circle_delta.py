#!/usr/bin/env python3
"""circle_delta.py — what ONE circle changed, across the registers, in both
segments: the circle itself, then its inter-circle processing.

    python coordinator/circle_delta.py                 the newest closed circle
    python coordinator/circle_delta.py --ot <OT>       one circle, by open time
    python coordinator/circle_delta.py --series        part memory over every closed circle
    python coordinator/circle_delta.py --json          the payload instead of the report

`--ot <OT>`: report the named circle. Default: the newest work/logs/close_*.json.
`--series`: one line per part per closed circle instead of one circle's full report. Default: off.
`--json`: print the collected payload as JSON instead of the rendered report. Default: off.

THE TWO SEGMENTS ARE NOT ONE WINDOW. "What changed in the course of a circle"
is two different answers stitched together, and every fact below is
attributed to its own segment:

    THE CIRCLE      base .. the commit tagged circle/<OT> — statements,
                    annotations, proposals staged, /issue commands, spend
    PROCESSING      that commit .. the commit tagged dream/<OT> — dreaming's
                    remember rows, synthesis's register writes, the mid_term
                    refresh

READ-ONLY OVER THE RECORD, with one deliberate exception: when the
`circle_stats` setting is on, a run also files its payload as
work/logs/delta_<OT>.json (circle_delta_report_write(), through atomic_write). That file
is a MEMO, not a record — re-derivable from the registers, git and the close
report at any time — so it is gitignored beside dream_<OT>.json, whose
reasoning it shares. Nothing else is written, ever: no register moves, no
commit, no model call.

CIRCLE_STATS is the constant behind the `circle_stats` setting (R405,
2026-08-30): when true, a live /close prints this report and files the memo;
when false, /close stays silent and only a by-hand run reports (and then
writes no file). Default: on. The register overrides it — self/settings.toml,
via /settings-update or the UI settings tab.

THE CLOSE REPORT IS THE GATE, NOT circle_state. A partial transcript is
well-formed, so this module refuses any OT that has no
work/logs/close_<OT>.json rather than reading a transcript that may still be
growing. That is deliberately stricter than circle_state's 45-minute
quiet rule and never wrong in the direction that matters: a close report
exists only after the verifier ran, so the transcript it names is finished
bytes. At a live /close the report is written (run_verifier) before circle_delta_at_close()
fires, so the gate passes exactly when the record is complete.

DREAM EVIDENCE IS ONE-DIRECTIONAL, same as circle_is_processed(): a dream/<OT>
tag (or, in a tree with no git history, work/logs/dream_<OT>.json) means the
circle WAS processed; absence means "no evidence here", never "not
processed" — the 2026-08-02 circles were processed by the retired batch path
and carry no tag. The report prints "no evidence of processing" and leaves
the processing segment empty rather than inventing a verdict.

THE SILENT FLAG IS B54 MADE VISIBLE, PER CIRCLE. A part that spoke but has no
well-formed short_term takes dreaming's silent path — an unchanged document
and an empty memory, legal and non-SUSPECT, so nothing else reports it. Here
it is a flagged row: statements > 0 while the close report says the
short_term is absent or unwell.

WHAT A ROW'S ORIGIN MEANS in parts/<p>/remember.toml: a DREAMT record is
coordinator-minted and id-bearing (MEM-nnnn, render_dreamt); a part's own
live [remember: ...] is id-less. Both cite the circle, so the id is the
discriminator, the same one render_dreamt's own chain rule uses.

UNEXPECTED classifies every path in the two machine commits against the sets
their own writers declare — circle_commit_paths()'s shape for the circle
commit, the staged registers plus mid_term for the dream commit. An
off-matrix path in a machine commit is the silent failure shape this project
gates elsewhere; here it is at least named. A merge commit under either tag
is reported and not classified — a machine commit is single-parent by
construction, so a merge there is itself the finding.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

try:
    import tomllib
except ModuleNotFoundError:                                  # 3.10 and older
    import tomli as tomllib                                  # type: ignore

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
# memory/ too — annotations.py (reached through transcript_store's own
# _split_remember) imports issue_commands from there, same hop circle.py makes.
sys.path.insert(0, str(ROOT / "memory"))
import record_paths as _RP                                         # noqa: E402

LOGS = ROOT / "work" / "logs"

# The default behind the `circle_stats` setting — see the module docstring.
# The register overrides it; circle_delta_is_enabled() is the one read, at use time rather
# than import, so a value changed in the UI's long-lived process is honoured
# at the very next close.
CIRCLE_STATS = True


def circle_delta_is_enabled() -> bool:
    """Is the close-time report (and its memo file) on for this tree?"""
    import setting_manager as SET
    return bool(SET.setting_value_read("circle_stats", CIRCLE_STATS))


class DeltaUnavailable(RuntimeError):
    """The named circle cannot be reported — no close report exists."""


# ----------------------------------------------------------------- git reads
def _git(args: list[str]) -> str | None:
    """One read-only git call, or None. None means "no evidence" — no git
    binary, no history, no such rev — and every caller treats it that way."""
    try:
        r = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=30)
    except Exception:                                          # noqa: BLE001
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def _tag_name(kind: str, ot: str) -> str:
    """The tag this tree would have written — gitrepo.system_git_tag_name_read() knows the
    lab stamp (R245); the literal is only the no-gitrepo fallback."""
    try:
        import gitrepo as G
        return G.system_git_tag_name_read(kind, ot)
    except Exception:                                          # noqa: BLE001
        return f"{kind}/{ot}"


def _find_tag(kind: str, ot: str) -> tuple[str, str | None]:
    """(tag_name, sha-or-None). The tree's own stamped name first — what
    circle_is_processed() reads — then the plain `<kind>/<OT>` as a READ
    fallback: a worktree of the main repository shares the main record but
    tag_name() stamps it `lab/` (R245 is a rule for WRITERS), so without the
    fallback a worktree run would call every processed circle unprocessed.
    The stamped name keeps priority so a lab's own record wins in a lab."""
    name = _tag_name(kind, ot)
    sha = _git(["rev-list", "-n", "1", name])
    if sha is None and name != f"{kind}/{ot}":
        plain_sha = _git(["rev-list", "-n", "1", f"{kind}/{ot}"])
        if plain_sha:
            return f"{kind}/{ot}", plain_sha
    return name, sha


def _commit_files(sha: str) -> list[str]:
    out = _git(["show", "--name-only", "--format=", sha])
    return [ln.strip() for ln in out.splitlines() if ln.strip()] if out else []


def _is_merge(sha: str) -> bool:
    return _git(["rev-parse", "--verify", "-q", f"{sha}^2"]) is not None


def _blob_size(rev: str, rel: str) -> int | None:
    out = _git(["cat-file", "-s", f"{rev}:{rel}"])
    try:
        return int(out) if out else None
    except ValueError:
        return None


# ------------------------------------------------------------ register reads
def _rows(path: pathlib.Path, table: str) -> list[dict]:
    """A register's rows, raw. Absence and damage both read as [] — this is
    a reporter; the gates that refuse damage live elsewhere."""
    try:
        doc = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:                                          # noqa: BLE001
        return []
    rows = doc.get(table)
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _cites(row: dict, ot: str) -> bool:
    """Does this row claim this circle? Registers disagree on the spelling —
    topics/history/remember store the bare OT, proposals and best_practices
    store circle_<OT> — so both are accepted."""
    return row.get("circle") in (ot, f"circle_{ot}")


# ---------------------------------------------------------- pure classifiers
# The dream commit's own writers: the staged registers (inter_circle) plus
# the mid_term refresh. parts/<p>/ entries are matched by basename.
# WHAT INTER_CIRCLE STAGES, SPELLED ONCE — B131, 2026-09-09. It was spelled
# twice, here and inside the rebind below, and that is why the CIRCLE JOURNAL
# was missed when B94 (2026-09-04) added it: inter_circle stages
# `circles/circle_journal.toml` at :619, so every dream commit carrying the
# register was reported as carrying an UNEXPECTED file. The same defect B86
# fixed for the prompt capture, and for the same cost — a classifier that
# cries wolf at every close is one nobody reads on the close that matters.
_DREAM_SELF_REL = (
    "circles/circle_history.toml", "circles/circle_observation_log.toml",
    "circles/circle_journal.toml",
    "self/topics.toml", "self/best_practices.toml", "self/self.md")
DREAM_SELF_FILES = tuple(_RP.record_rel(f) for f in _DREAM_SELF_REL)
DREAM_PART_FILES = ("remember.toml", "mid_term.md")


@_RP.group_follow
def _dream_files_rebind() -> None:
    """The CURRENT group's self/ — B117 stage 5 (2026-09-07); `--group` below calls group_set().
    Reads the one list above, so a register added to inter_circle's write set is added HERE
    once and cannot be half-added again (B131)."""
    global DREAM_SELF_FILES
    DREAM_SELF_FILES = tuple(_RP.record_rel(f) for f in _DREAM_SELF_REL)


def circle_delta_is_silent(statements: int, present: bool, status: str) -> bool:
    """B54's shape: the part spoke, and its short_term is absent or unwell.
    A genuinely silent part (0 statements) writes nothing and is exempt."""
    return statements > 0 and (not present or status != "ok")


def circle_delta_paths_classify(paths: list[str], ot: str) -> list[str]:
    """Paths in the circle commit that circle_commit_paths() would not have
    staged for this OT. Empty means the commit is exactly its own shape."""
    out = []
    for p in paths:
        p = p.replace("\\", "/")
        ok = (p == _RP.record_rel(f"circles/circle_{ot}.md")
              or p == _RP.record_rel(f"circles/commands_{ot}.toml")
              or p == f"work/logs/close_{ot}.json"
              or p.startswith(f"work/prompts/{ot}")
              or (p.startswith(_RP.record_rel("parts") + "/")
                  and p.endswith((f"/short_term_{ot}.toml", f"/short_term_{ot}.md")))
              or p in (_RP.record_rel("circles/working_sets.toml"), _RP.record_rel("self/proposals.toml")))
        if not ok:
            out.append(p)
    return out


def circle_delta_dream_paths_classify(paths: list[str], ot: str) -> list[str]:
    """Paths in the dream commit outside inter_circle's own write set.

    `work/prompts/<ot>/` ADDED 2026-08-31 (B86) — R412/R413 (2026-08-30/31)
    made the dream commit carry the circle's own prompt capture (every
    dreaming/synthesis/mid_term-refresh turn file, and the manifest they
    rewrote), the same allowance circle_delta_paths_classify() already had for
    its own commit. Until this, every live close reported its OWN designed
    capture files as UNEXPECTED — confirmed against circle 2026-08-31_1013,
    where the operator read the "what is this?" line as an alarm rather
    than the designed record it was."""
    out = []
    for p in paths:
        p = p.replace("\\", "/")
        parts_hit = (p.startswith(_RP.record_rel("parts") + "/")
                     and p.split("/")[-1] in DREAM_PART_FILES)
        if not (parts_hit or p in DREAM_SELF_FILES
                or p.startswith(f"work/prompts/{ot}")):
            out.append(p)
    return out


# ------------------------------------------------------------------- collect
def _load_close(ot: str) -> dict:
    p = LOGS / f"close_{ot}.json"
    if not p.is_file():
        raise DeltaUnavailable(
            f"no close report at work/logs/close_{ot}.json — the circle may "
            f"still be open (coordinator/circle_state.py answers that) or it "
            f"never closed; this tool reads closed circles only")
    return json.loads(p.read_text(encoding="utf-8"))


def _statement_counts(ot: str) -> tuple[str, int, dict, str]:
    """(topic, self_statements, per-part statements, raw transcript). Falls
    back to ('', 0, {}, '') when the transcript is missing or unparseable —
    the close report still carries per-part counts."""
    try:
        import transcript_store as TS
        raw = (_RP.record_dir(ROOT, "circles") / f"circle_{ot}.md").read_text(encoding="utf-8")
        _ot, topic, transcript = TS.circle_transcript_parse(raw)
    except Exception:                                          # noqa: BLE001
        return "", 0, {}, ""
    import identity as ID
    per: dict[str, int] = {}
    self_n = 0
    for e in transcript:
        # cmd lines are echoed graph rulings (R079's record-not-room echo),
        # not spoken statements; a Coordinator note is not either.
        if e.get("is_topic") or e.get("cmd") or e.get("speaker") == "__coordinator__":
            continue
        if e.get("speaker") == ID.SELF_ID:
            self_n += 1
        else:
            per[e["speaker"]] = per.get(e["speaker"], 0) + 1
    return topic, self_n, per, raw


def _annotations(raw: str) -> dict:
    try:
        import annotations as MK
        import recall_index as RC
        return {"remember": len(MK.REMEMBER_RE.findall(raw)),
                "ask": sum(1 for _ in MK.ASK_RE.finditer(raw)),
                "recall": len(RC.RECALL_RE.findall(raw))}
    except Exception:                                          # noqa: BLE001
        return {"remember": 0, "ask": 0, "recall": 0}


def _issue_commands(ot: str) -> list[dict]:
    rows = _rows(_RP.record_dir(ROOT, "circles") / f"commands_{ot}.toml", "command")
    return [{"verb": r.get("verb", "?"), "node": r.get("node", "")}
            for r in rows]


def _proposals(ot: str) -> dict:
    try:
        import proposal_manager as PR
        rows = [r for r in PR.proposal_read() if _cites(r, ot)]
    except Exception:                                          # noqa: BLE001
        rows = []
    states: dict[str, int] = {}
    for r in rows:
        s = str(r.get("state", "?"))
        states[s] = states.get(s, 0) + 1
    return {"staged": len(rows), "states": states}


def _spend(ot: str) -> dict | None:
    p = LOGS / f"spend_{ot}.json"
    if not p.is_file():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        return {"calls": doc.get("calls"), "cost": doc.get("cost")}
    except Exception:                                          # noqa: BLE001
        return None


def _part_rows(ot: str, close: dict, dream_sha: str | None,
               dream_files: list[str]) -> list[dict]:
    import part_roster as R
    import remember_manager as RM
    by_part = {p.get("part"): p for p in close.get("parts", [])}
    out = []
    for d in R.DIR_NAMES:
        cp = by_part.get(d) or {}
        stmts = int(cp.get("statements") or 0)
        present = bool(cp.get("present"))
        status = str(cp.get("status") or "")
        row = {"part": d, "tag": R.TAG_BY_DIR.get(d, d), "statements": stmts,
               "short_term_bytes": cp.get("bytes"),
               "short_term_status": status if cp else "absent",
               "silent": circle_delta_is_silent(stmts, present, status)}
        try:
            recs = _rows(RM._real_path(d), RM.TABLE)
        except Exception:                                      # noqa: BLE001
            recs = []
        row["spoken_remember"] = sum(1 for r in recs
                                     if not r.get("id") and _cites(r, ot))
        dre = next((r for r in reversed(recs)
                    if r.get("id") and _cites(r, ot)), None)
        row["dreamt"] = dre is not None
        if dre is not None:
            row["salience"] = dre.get("salience")
            try:
                row["chain_len"] = len(RM.remember_chain_read({RM.TABLE: recs}, dre["id"]))
            except Exception:                                  # noqa: BLE001
                row["chain_len"] = 1
        rel = _RP.record_rel(f"parts/{d}/mid_term.md")
        live = ROOT / rel
        after = live.stat().st_size if live.is_file() else 0
        before = after
        in_dream = bool(dream_sha) and rel in dream_files
        if in_dream:
            after = _blob_size(dream_sha, rel) or after
            before = _blob_size(f"{dream_sha}^", rel) or 0
        row["mid_term_before"] = before
        row["mid_term_after"] = after
        row["mid_term_in_dream"] = in_dream
        out.append(row)
    return out


def _processing(ot: str, dream_sha: str | None,
                dream_files: list[str]) -> dict:
    out: dict = {}
    # circle_history and circle_observation_log live under circles/, not self/ — b857f7c
    # (R480, 2026-09-07) moved the four one-per-circle registers. DREAM_SELF_FILES above
    # was updated with them and this tuple was not, so both reported total:0 against 7 and
    # 31 real rows: _rows() reads an absent file as [], which is indistinguishable from a
    # register that did not move. topics and best_practices are still self/.
    for name, path, table in (
            ("circle_history", _RP.record_dir(ROOT, "circles") / "circle_history.toml", "history"),
            ("circle_observation", _RP.record_dir(ROOT, "circles") / "circle_observation_log.toml",
             "observation"),
            ("topics", _RP.record_dir(ROOT, "self") / "topics.toml", "topic"),
            ("best_practices", _RP.record_dir(ROOT, "self") / "best_practices.toml",
             "practice")):
        rows = _rows(path, table)
        mine = [r for r in rows if _cites(r, ot)]
        entry: dict = {"added": len(mine), "total": len(rows)}
        # ABSENT IS NOT THE SAME AS EMPTY, AND 0/0 IS THE REASSURING ANSWER. The stale
        # self/ paths above reported 0 added / 0 total for two registers that held 7 and
        # 31 rows, and nothing in the report could distinguish that from a quiet circle.
        # A reporter may not refuse, but it can say which file it could not find.
        if not path.is_file():
            try:
                entry["missing"] = path.relative_to(ROOT).as_posix()
            except ValueError:                                 # a snapshot or temp base
                entry["missing"] = str(path)
        if name == "circle_observation" and mine:
            entry["salience"] = mine[-1].get("salience")
        if name == "topics":
            entry["long_term_candidates"] = sum(
                1 for r in mine
                if str(r.get("text", "")).startswith("LONG_TERM CANDIDATE"))
        out[name] = entry
    out["self_md_changed"] = ((_RP.record_rel("self/self.md") in dream_files)
                              if dream_sha else None)
    return out


def circle_delta_collect(ot: str) -> dict:
    """The whole delta for one closed circle, as the payload circle_delta_report_write()
    files. Raises DeltaUnavailable when the circle has no close report."""
    import datetime
    close = _load_close(ot)

    circle_tag, circle_sha = _find_tag("circle", ot)
    if circle_sha is None:
        # R130's signature: a close whose commit silently failed. The commit
        # that ADDED the transcript is the honest fallback anchor.
        circle_sha = _git(["log", "--diff-filter=A", "--format=%H", "-n", "1",
                           "--", _RP.record_rel(f"circles/circle_{ot}.md")])
    dream_tag, dream_sha = _find_tag("dream", ot)
    marker = (LOGS / f"dream_{ot}.json").is_file()
    processed = ("tag" if dream_sha else ("marker" if marker
                                          else "no evidence"))

    topic, self_n, per, raw = _statement_counts(ot)
    part_stmts = sum(int(p.get("statements") or 0)
                     for p in close.get("parts", []))

    dream_files = _commit_files(dream_sha) if dream_sha else []
    circle_files = _commit_files(circle_sha) if circle_sha else []

    unexpected: dict = {}
    if circle_sha:
        unexpected["circle_commit"] = (
            ["(merge commit under the tag — not classified)"]
            if _is_merge(circle_sha) else
            circle_delta_paths_classify(circle_files, ot))
    if dream_sha:
        unexpected["dream_commit"] = (
            ["(merge commit under the tag — not classified)"]
            if _is_merge(dream_sha) else
            circle_delta_dream_paths_classify(dream_files, ot))

    return {
        "ot": ot,
        "written_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "anchors": {"circle_tag": circle_tag, "circle_commit": circle_sha,
                    "dream_tag": dream_tag, "dream_commit": dream_sha,
                    "dream_marker": marker, "processed": processed},
        "circle": {"topic": topic,
                   "statements": {"self": self_n,
                                  "parts": part_stmts or sum(per.values()),
                                  "by_part": per},
                   "annotations": _annotations(raw),
                   "proposals": _proposals(ot),
                   "issue_commands": _issue_commands(ot),
                   "spend": _spend(ot)},
        "processing": _processing(ot, dream_sha, dream_files),
        "parts": _part_rows(ot, close, dream_sha, dream_files),
        "unexpected": unexpected,
    }


# -------------------------------------------------------------------- render
def _b(n) -> str:
    return f"{n:,}" if isinstance(n, int) else "?"


def circle_delta_render(delta: dict) -> list[str]:
    """The report, one string per line, every line within 116 characters."""
    ot = delta.get("ot", "?")
    an = delta.get("anchors", {})
    ci = delta.get("circle", {})
    pr = delta.get("processing", {})
    out = [f"circle_delta — {ot}"]
    proc = an.get("processed", "no evidence")
    if proc == "tag":
        proc_s = f"processed ({an.get('dream_tag')})"
    elif proc == "marker":
        proc_s = f"processed (work/logs/dream_{ot}.json; no tag)"
    else:
        proc_s = "no evidence of processing"
    csha = an.get("circle_commit")
    out.append(f"  anchors: circle commit {csha[:9] if csha else 'none'} · "
               f"{proc_s}")

    st = ci.get("statements", {})
    ann = ci.get("annotations", {})
    out.append("")
    out.append("THE CIRCLE")
    out.append(f"  statements {st.get('parts', 0) + st.get('self', 0)} "
               f"(Self {st.get('self', 0)}) · remember {ann.get('remember', 0)}"
               f" · ask {ann.get('ask', 0)} · recall {ann.get('recall', 0)}")
    props = ci.get("proposals", {})
    if props.get("staged"):
        states = ", ".join(f"{k} {v}"
                           for k, v in sorted(props.get("states", {}).items()))
        out.append(f"  proposals this circle: {props['staged']} ({states})")
    cmds = ci.get("issue_commands", [])
    if cmds:
        shown = " · ".join(f"{c['verb']} {c['node']}".strip() for c in cmds[:4])
        more = f" · +{len(cmds) - 4} more" if len(cmds) > 4 else ""
        out.append(f"  issue commands: {shown}{more}")
    sp = ci.get("spend")
    if sp and sp.get("calls") is not None:
        cost = sp.get("cost")
        out.append(f"  spend: {sp['calls']} call(s)"
                   + (f" · ${cost:.2f}" if isinstance(cost, (int, float))
                      else ""))

    out.append("")
    out.append("PROCESSING")
    if an.get("processed") == "no evidence":
        out.append("  no evidence of processing — a dream tag/marker means "
                   "processed; absence means only that")
        out.append("  (check the registers before re-running anything)")
    else:
        so = pr.get("circle_observation", {})
        so_s = (f" (salience {so['salience']})"
                if so.get("salience") else "")
        tp = pr.get("topics", {})
        lt = tp.get("long_term_candidates", 0)
        out.append(f"  circle_history +{pr.get('circle_history', {}).get('added', 0)}"
                   f" · circle_observation +{so.get('added', 0)}{so_s}"
                   f" · topics +{tp.get('added', 0)}"
                   + (f" (long_term candidates {lt})" if lt else ""))
        smd = pr.get("self_md_changed")
        out.append(f"  best_practices +{pr.get('best_practices', {}).get('added', 0)}"
                   f" · self.md "
                   + ("changed" if smd else
                      ("unchanged" if smd is not None else "(no git evidence)")))

    out.append("")
    out.append("PART MEMORY")
    out.append(f"  {'part':<13} {'spoke':>5} {'short_term':>11} "
               f"{'dreamt':<9} {'chain':>5}  mid_term")
    silent_rows = []
    for row in delta.get("parts", []):
        stb = row.get("short_term_bytes")
        st_s = f"{_b(stb)} B" if stb is not None else "—"
        if row.get("dreamt"):
            dre = row.get("salience") or "yes"
            ch = str(row.get("chain_len", 1))
        else:
            dre, ch = "—", "—"
        b, a = row.get("mid_term_before"), row.get("mid_term_after")
        if row.get("mid_term_in_dream"):
            mt = f"{_b(b)} -> {_b(a)} B"
        else:
            mt = f"{_b(a)} B (unchanged)" if a else "—"
        out.append(f"  {row.get('tag', '?'):<13} {row.get('statements', 0):>5} "
                   f"{st_s:>11} {dre:<9} {ch:>5}  {mt}")
        if row.get("silent"):
            silent_rows.append(row)
    for row in silent_rows:
        out.append(f"  SILENT — {row.get('tag')} spoke "
                   f"{row.get('statements')} time(s) but has no well-formed "
                   f"short_term; the dream took the silent path (B54).")
        out.append("           Backfill BEFORE any re-dream: "
                   "circle_audit.py --backfill")

    ux = delta.get("unexpected", {})
    out.append("")
    out.append("UNEXPECTED")
    if not ux:
        out.append("  (no machine commit found to classify)")
    else:
        clean = True
        for window, paths in sorted(ux.items()):
            for p in paths:
                clean = False
                out.append(f"  {window}: {p}")
        if clean:
            out.append("  none — both machine commits hold exactly their "
                       "writers' own paths")
    return out


def circle_delta_series_render(deltas: list[dict]) -> list[str]:
    out = [f"circle_delta --series — {len(deltas)} closed circle(s)", ""]
    out.append(f"  {'circle':<17} {'part':<13} {'spoke':>5} "
               f"{'short_term':>11} {'dreamt':<9} {'chain':>5}  mid_term")
    for d in deltas:
        if d.get("error"):
            out.append(f"  {d.get('ot', '?'):<17} {d['error']}")
            continue
        ot = d.get("ot", "?")
        if d.get("anchors", {}).get("processed") == "no evidence":
            out.append(f"  {ot:<17} (closed; no evidence of processing)")
        for row in d.get("parts", []):
            stb = row.get("short_term_bytes")
            st_s = f"{_b(stb)} B" if stb is not None else "—"
            dre = (row.get("salience") or "yes") if row.get("dreamt") else "—"
            ch = str(row.get("chain_len", 1)) if row.get("dreamt") else "—"
            mt = (f"{_b(row.get('mid_term_after'))} B"
                  if row.get("mid_term_in_dream") else "·")
            sil = "  SILENT (B54)" if row.get("silent") else ""
            out.append(f"  {ot:<17} {row.get('tag', '?'):<13} "
                       f"{row.get('statements', 0):>5} {st_s:>11} {dre:<9} "
                       f"{ch:>5}  {mt}{sil}")
    return out


# --------------------------------------------------------------------- write
def circle_delta_report_write(ot: str, delta: dict) -> pathlib.Path:
    """work/logs/delta_<OT>.json — the memo. Callers gate on circle_delta_is_enabled();
    this function only writes what it is handed."""
    from atomic_write import record_atomic_write
    LOGS.mkdir(parents=True, exist_ok=True)
    dest = LOGS / f"delta_{ot}.json"
    record_atomic_write(dest, json.dumps(delta, indent=2) + "\n")
    return dest


def circle_delta_at_close(ot: str, emit) -> None:
    """The /close hook — print the report and file the memo, both behind the
    circle_stats setting. FAILS OPEN: the circle's record is the transcript
    and the short_terms; a reporting fault must never fail a close."""
    try:
        if not circle_delta_is_enabled():
            return
        delta = circle_delta_collect(ot)
        emit("")
        for line in circle_delta_render(delta):
            emit(line)
        dest = circle_delta_report_write(ot, delta)
        emit(f"  delta recorded: {dest.name}")
    except Exception as e:                                     # noqa: BLE001
        emit(f"  circle_delta skipped ({type(e).__name__}: {e})")


# ---------------------------------------------------------------------- main
def circle_delta_series_read() -> list[dict]:
    out = []
    for p in sorted(LOGS.glob("close_*.json")):
        ot = p.stem[len("close_"):]
        try:
            out.append(circle_delta_collect(ot))
        except Exception as e:                                 # noqa: BLE001
            out.append({"ot": ot, "error": f"{type(e).__name__}: {e}"})
    return out


def _newest_ot() -> str | None:
    reports = sorted(LOGS.glob("close_*.json"))
    return reports[-1].stem[len("close_"):] if reports else None


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="what one circle changed, "
                                             "across the registers")
    ap.add_argument("--ot", help="the circle's open time "
                                 "(default: the newest close report)")
    ap.add_argument("--group", default=None,
                    # B117 stage 5 — in the comment, not in help=, which ships.
                    help="report a circle of this GROUP's record (groups/<name>/). "
                         "Default: the ifs group.")
    ap.add_argument("--series", action="store_true",
                    help="part memory over every closed circle")
    ap.add_argument("--json", action="store_true",
                    help="print the payload as JSON instead of the report")
    args = ap.parse_args(argv)
    if args.group:
        _RP.group_set(args.group)           # B117 stage 5: this group's record, before any read

    if args.series:
        deltas = circle_delta_series_read()
        print(json.dumps(deltas, indent=2) if args.json
              else "\n".join(circle_delta_series_render(deltas)))
        return 0

    ot = args.ot or _newest_ot()
    if not ot:
        print("no close report under work/logs/ — nothing to report on")
        return 1
    try:
        delta = circle_delta_collect(ot)
    except DeltaUnavailable as e:
        print(f"  {e}")
        return 1
    print(json.dumps(delta, indent=2) if args.json
          else "\n".join(circle_delta_render(delta)))
    if circle_delta_is_enabled():
        dest = circle_delta_report_write(ot, delta)
        print(f"\n  delta recorded: {dest.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
