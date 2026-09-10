#!/usr/bin/env python3
"""
dream_history_manager.py — DREAM_HISTORY ::= DREAMING( prior DREAM_HISTORY + latest
(dream_history.py until 2026-09-03 — B99 stage 18c under R435: a register's one reader/writer is <CLASS>_manager.py)
DREAM ). R193/R194 ruled it, R319 kept the derivation and struck the
sending, R359 ruled the bootstrap, B45 is the build.

WHAT THIS IS. Self's dream corpus (self/dreams.toml, section="dream", never
pruned — R194) gains a BOUNDED standing summary: section="history" records
in the SAME file, one dated record per derivation, append-only, each under
1000 words and each naming the source dream ids it folded — so any summary
sits beside its dated sources and can be re-derived and checked (R194's
condition). The newest history record IS the current DREAM_HISTORY; older
ones are the account of how it evolved.

NO BLOCK WIRING — R195 is absolute and R319 struck the BLOCK 3 destination
R193 had named: NO PART EVER READS THIS, and nothing reads dream_history_latest_read()
but this module's own CLI. Do not look for a route into a prompt and do not
build one.

THE SHAPE, ruled R359: ONE bootstrap derivation over the whole corpus, then
one fold per future dream — DREAMING(prior + latest), the production read
literally from the bootstrap forward. Each derivation asks for THE WHOLE
replacement history (bounded: it must not grow with the corpus), which is
mid_term PROMPT v9's own lesson applied here from the start.

THE ONE WRITER. This module appends history records; the dream corpus rows
are never written by anything (parts/*/dreams.toml is frozen in
register_gate.REGISTERS; self/dreams.toml's corpus half has the same
nothing-writes-it status, and this module preserves it — history rows only).

GUARDS, all inherited from the day's lessons: a reply that stops at
max_tokens is REFUSED, never written (R354 — thinking spends from the same
budget); a reply over 1000 words is truncated whitespace-aware and reported;
a bootstrap refuses when any history record already exists.

    python coordinator/dream_history_manager.py               state, writes nothing
    python coordinator/dream_history_manager.py --bootstrap   the one R359 bootstrap (model call)
    python coordinator/dream_history_manager.py --fold        fold every unfolded dream (model calls)
    python coordinator/dream_history_manager.py --show        the current DREAM_HISTORY, whole
    python coordinator/dream_history_manager.py --selftest    pure helpers, no API
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import LLM_response_disassembler as RD                         # noqa: E402
import record_paths as _RP                                         # noqa: E402

TABLE = "dreams"
ORDER = ("id", "date", "title", "section", "sources", "content")
WORD_CAP = 1000
MAX_TOKENS = 6000     # the visible reply targets <1000 words (~1,300 tok);
                      # the rest is the thinking's room (R354's sizing rule).

SYSTEM = """\
You are Self's DREAM_HISTORY derivation — the DREAMING-stage re-derivation of
a standing summary. Given the prior DREAM_HISTORY (or nothing, at bootstrap)
and one or more dream synthesis records, produce THE WHOLE REPLACEMENT
DREAM_HISTORY: one standing account, UNDER 1000 WORDS, of what Self's
dreaming corpus has concluded — bounded, so it must not grow with the corpus.
Carry forward what still matters from the prior history, fold in what the new
record or records conclude, and let what has completed compress to a line.
Prefer the records' own words for what they themselves named. Plain prose —
no headers, no per-record lists. Output the history text alone, nothing
else."""


def _now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def dream_history_locate() -> pathlib.Path:
    return _RP.record_dir(ROOT, "self") / "dreams.toml"


def _doc() -> dict:
    """The document a tree with no self/dreams.toml reads — an empty corpus,
    ids from SD-0001. The register name is the live file's own. B111
    (2026-09-06): the file never ships (one person's dreams), so a recipient's
    first run met a file-not-found where every other manager builds its empty
    shape. Nothing writes this back on a read; --bootstrap on it reports an
    empty corpus and exits 1, as before."""
    return {"register": "self_dreams", "next_id": 1, TABLE: []}


def _load() -> dict:
    import REGISTER_CLASS as SS
    p = dream_history_locate()
    return SS.register_read(p) if p.is_file() else _doc()


def _save(doc: dict) -> None:
    import REGISTER_CLASS as SS
    SS.register_write(dream_history_locate(), doc, TABLE, ORDER)


def dream_history_corpus_read(doc: dict | None = None) -> list[dict]:
    doc = doc if doc is not None else _load()
    rows = [r for r in doc.get(TABLE, []) if r.get("section") == "dream"]
    return sorted(rows, key=lambda r: (r.get("date", ""), r.get("id", "")))


def dream_history_read(doc: dict | None = None) -> list[dict]:
    doc = doc if doc is not None else _load()
    return [r for r in doc.get(TABLE, []) if r.get("section") == "history"]


def dream_history_latest_read(doc: dict | None = None) -> dict | None:
    hs = dream_history_read(doc)
    return hs[-1] if hs else None


def dream_history_covered_read(doc: dict | None = None) -> set[str]:
    return {sid for h in dream_history_read(doc) for sid in h.get("sources", [])}


def dream_history_unfolded_read(doc: dict | None = None) -> list[dict]:
    doc = doc if doc is not None else _load()
    got = dream_history_covered_read(doc)
    return [d for d in dream_history_corpus_read(doc) if d.get("id") not in got]


# truncate_words() MOVED to LLM_response_disassembler.message_word_cap_read(), 2026-09-02 —
# a read of the reply, beside every other one.
def dream_history_render(doc: dict, content: str, sources: list[str],
                   title: str) -> tuple[dict, dict]:
    """PURE — one new section="history" record on a COPY of `doc`, the
    register's own next_id minting the SD- id. The corpus rows are not
    touched; that is this module's one-writer promise."""
    import copy
    doc = copy.deepcopy(doc)
    n = doc.get("next_id", 1)
    rec = {"id": f"SD-{n:04d}", "date": _now_date(), "title": title,
           "section": "history", "sources": sorted(sources),
           "content": content.strip()}
    doc.setdefault(TABLE, []).append(rec)
    doc["next_id"] = n + 1
    return doc, rec


def _render_dream(d: dict) -> str:
    return f"[{d.get('id')}] {d.get('date')} — {d.get('title')}\n{d.get('content', '')}"


def _call(user: str, client=None):
    """The Reply, burst (LLM_response_disassembler); client injectable so
    no test reaches the network — coalesce._call's own shape."""
    # THROUGH THE TRANSPORT SINCE 2026-08-28 (stage 1 of the provider
    # socket) — same move, and the same reason, as coalesce._call beside it:
    # the key resolution here was a second hand-rolled copy, and a fold had
    # no retry ladder and reached no meter. The injection contract this
    # docstring names is unchanged.
    import llm_client as LC
    return LC.stream_call_once(SYSTEM, user, MAX_TOKENS, kind="dream_fold",
                        client=client)


def _derive(prior: str | None, dreams: list[dict], client=None,
            say=print) -> str | None:
    parts = []
    if prior:
        parts.append(f"# The prior DREAM_HISTORY\n{prior}")
    else:
        parts.append("# The prior DREAM_HISTORY\n(none — this is the "
                     "bootstrap over the whole corpus)")
    parts.append("# Dream synthesis record(s) to fold\n\n"
                 + "\n\n".join(_render_dream(d) for d in dreams))
    reply = _call("\n\n".join(parts), client=client)
    if reply.truncated:
        # R354's rule: a truncated reply is not a record.
        say("  REFUSED — the reply stopped at max_tokens; a truncated "
            "history is not written")
        return None
    if reply.empty:
        say("  REFUSED — empty reply; nothing written")
        return None
    text, cut = RD.message_word_cap_read(reply.text, WORD_CAP)
    if cut:
        say(f"  reply over {WORD_CAP} words — truncated whitespace-aware, "
            f"kept")
    return text


def dream_history_bootstrap(client=None, say=print) -> int:
    doc = _load()
    if dream_history_read(doc):
        # R359: the bootstrap derivation runs exactly once.
        say("  REFUSED — a DREAM_HISTORY record already exists; the "
            "bootstrap runs once. Use --fold for new dreams.")
        return 2
    dreams = dream_history_corpus_read(doc)
    if not dreams:
        say("  nothing to bootstrap — the corpus is empty")
        return 1
    say(f"  bootstrap: deriving one history over {len(dreams)} dream "
        f"record(s)...")
    content = _derive(None, dreams, client=client, say=say)
    if content is None:
        return 1
    doc2, rec = dream_history_render(doc, content,
                               [d["id"] for d in dreams],
                               "DREAM_HISTORY (bootstrap)")
    _save(doc2)
    say(f"  wrote {rec['id']} — {len(content.split())} words over "
        f"{len(rec['sources'])} sources")
    return 0


def dream_history_fold(client=None, say=print) -> int:
    doc = _load()
    if not dream_history_read(doc):
        # R359 again: --fold has nothing to fold into until the bootstrap ran.
        say("  REFUSED — no history yet; run --bootstrap first")
        return 2
    pending = dream_history_unfolded_read(doc)
    if not pending:
        say("  nothing unfolded — the history is current")
        return 0
    for d in pending:
        doc = _load()
        prior = dream_history_latest_read(doc)
        say(f"  folding {d['id']} ({d.get('date')})...")
        content = _derive(prior["content"], [d], client=client, say=say)
        if content is None:
            return 1
        doc2, rec = dream_history_render(doc, content, [d["id"]],
                                   f"DREAM_HISTORY (through {d['id']})")
        _save(doc2)
        say(f"  wrote {rec['id']} — {len(content.split())} words")
    return 0


def selftest() -> int:
    fails: list[str] = []

    def case(name: str, ok: bool) -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            fails.append(name)

    doc = {"register": "self_dreams", "next_id": 3, TABLE: [
        {"id": "SD-0001", "date": "2026-06-23", "title": "a",
         "section": "dream", "content": "x"},
        {"id": "SD-0002", "date": "2026-06-24", "title": "b",
         "section": "dream", "content": "y"}]}
    case("corpus sees both dreams, date-ordered",
         [d["id"] for d in dream_history_corpus_read(doc)] == ["SD-0001", "SD-0002"])
    case("no histories yet", dream_history_latest_read(doc) is None)
    case("everything unfolded before a bootstrap",
         [d["id"] for d in dream_history_unfolded_read(doc)] == ["SD-0001", "SD-0002"])
    d2, rec = dream_history_render(doc, "the account", ["SD-0001", "SD-0002"],
                             "DREAM_HISTORY (bootstrap)")
    case("render mints the next SD id as a history record",
         rec["id"] == "SD-0003" and rec["section"] == "history"
         and d2["next_id"] == 4)
    case("the corpus rows are untouched by the render",
         [r["id"] for r in dream_history_corpus_read(d2)] == ["SD-0001", "SD-0002"])
    case("after the bootstrap nothing is unfolded", dream_history_unfolded_read(d2) == [])
    d2[TABLE].append({"id": "SD-0004", "date": "2026-08-27", "title": "c",
                      "section": "dream", "content": "z"})
    case("a new dream is the one unfolded row",
         [d["id"] for d in dream_history_unfolded_read(d2)] == ["SD-0004"])
    case("latest_history is the newest history record",
         dream_history_latest_read(d2)["id"] == "SD-0003")
    # the word-cap cases moved with word_cap() to
    # coordinator/tests/test_llm_response_disassembler.py, 2026-09-02
    print(f"\n  SELF-TEST: {'PASS' if not fails else 'FAIL'} "
          f"({8 - len(fails)} of 8)")
    return 1 if fails else 0


def main() -> int:
    import argparse
    # R193/R319/R359 are the rulings behind this register and its one-shot
    # bootstrap. They are named here rather than in description=/help=, which
    # argparse prints to a recipient who has no rulings/. 2026-09-09.
    ap = argparse.ArgumentParser(
        description="DREAM_HISTORY — the bounded summary over Self's dream "
                    "corpus")
    ap.add_argument("--bootstrap", action="store_true",
                    help="the one bootstrap derivation (a real model "
                         "call; refuses if a history exists). Default: off.")
    ap.add_argument("--fold", action="store_true",
                    help="fold every unfolded dream, one derivation each "
                         "(real model calls). Default: off.")
    ap.add_argument("--show", action="store_true",
                    help="print the current DREAM_HISTORY whole. Default: off.")
    ap.add_argument("--selftest", action="store_true",
                    help="pure helpers, no API. Default: off.")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.bootstrap:
        return dream_history_bootstrap()
    if a.fold:
        return dream_history_fold()
    doc = _load()
    if a.show:
        h = dream_history_latest_read(doc)
        print(h["content"] if h else "(no DREAM_HISTORY yet — run "
                                     "--bootstrap)")
        return 0
    hs = dream_history_read(doc)
    print(f"  corpus         {len(dream_history_corpus_read(doc))} dream record(s)")
    print(f"  histories      {len(hs)} record(s)"
          + (f", newest {hs[-1]['id']} ({hs[-1]['date']})" if hs else ""))
    print(f"  unfolded       {len(dream_history_unfolded_read(doc))} dream(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
