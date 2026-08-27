#!/usr/bin/env python3
"""
dream_history.py — DREAM_HISTORY ::= DREAMING( prior DREAM_HISTORY + latest
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
R193 had named: NO PART EVER READS THIS, and nothing reads latest_history()
but this module's own CLI. Do not look for a route into a prompt and do not
build one.

THE SHAPE, ruled R359: ONE bootstrap derivation over the whole corpus, then
one fold per future dream — DREAMING(prior + latest), the production read
literally from the bootstrap forward. Each derivation asks for THE WHOLE
replacement history (bounded: it must not grow with the corpus), which is
mid_term PROMPT v9's own lesson applied here from the start.

THE ONE WRITER. This module appends history records; the dream corpus rows
are never written by anything (parts/*/dreams.toml is frozen in
ifs_model.REGISTERS; self/dreams.toml's corpus half has the same
nothing-writes-it status, and this module preserves it — history rows only).

GUARDS, all inherited from the day's lessons: a reply that stops at
max_tokens is REFUSED, never written (R354 — thinking spends from the same
budget); a reply over 1000 words is truncated whitespace-aware and reported;
a bootstrap refuses when any history record already exists.

    python coordinator/dream_history.py               state, writes nothing
    python coordinator/dream_history.py --bootstrap   the one R359 bootstrap (model call)
    python coordinator/dream_history.py --fold        fold every unfolded dream (model calls)
    python coordinator/dream_history.py --show        the current DREAM_HISTORY, whole
    python coordinator/dream_history.py --selftest    pure helpers, no API
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

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


def path() -> pathlib.Path:
    return ROOT / "self" / "dreams.toml"


def _load() -> dict:
    import self_schema as SS
    return SS.load(path())


def _save(doc: dict) -> None:
    import self_schema as SS
    SS.save(path(), doc, TABLE, ORDER)


def corpus(doc: dict | None = None) -> list[dict]:
    doc = doc if doc is not None else _load()
    rows = [r for r in doc.get(TABLE, []) if r.get("section") == "dream"]
    return sorted(rows, key=lambda r: (r.get("date", ""), r.get("id", "")))


def histories(doc: dict | None = None) -> list[dict]:
    doc = doc if doc is not None else _load()
    return [r for r in doc.get(TABLE, []) if r.get("section") == "history"]


def latest_history(doc: dict | None = None) -> dict | None:
    hs = histories(doc)
    return hs[-1] if hs else None


def covered_ids(doc: dict | None = None) -> set[str]:
    return {sid for h in histories(doc) for sid in h.get("sources", [])}


def unfolded(doc: dict | None = None) -> list[dict]:
    doc = doc if doc is not None else _load()
    got = covered_ids(doc)
    return [d for d in corpus(doc) if d.get("id") not in got]


def truncate_words(text: str, cap: int = WORD_CAP) -> tuple[str, bool]:
    words = text.split()
    if len(words) <= cap:
        return text, False
    return " ".join(words[:cap]), True


def render_history(doc: dict, content: str, sources: list[str],
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


def _call(user: str, client=None) -> tuple[str, str]:
    """(text, stop_reason); client injectable so no test reaches the
    network — coalesce._call's own shape."""
    if client is None:
        import llm_client as LC
        from anthropic import Anthropic
        import os
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            env = ROOT / ".env"
            if env.is_file():
                for ln in env.read_text(encoding="utf-8").splitlines():
                    if ln.strip().startswith("ANTHROPIC_API_KEY"):
                        key = ln.split("=", 1)[1].strip().strip('"').strip("'")
        client = Anthropic(api_key=key)
        model = LC.MODEL
    else:
        model = getattr(client, "model", "fake")
    resp = client.messages.create(
        model=model, max_tokens=MAX_TOKENS, system=SYSTEM,
        messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in resp.content
                   if getattr(b, "type", "") == "text").strip()
    return text, getattr(resp, "stop_reason", None) or ""


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
    text, stop = _call("\n\n".join(parts), client=client)
    if stop == "max_tokens":
        say("  REFUSED — the reply stopped at max_tokens; a truncated "
            "history is not written (R354's rule)")
        return None
    if not text:
        say("  REFUSED — empty reply; nothing written")
        return None
    text, cut = truncate_words(text)
    if cut:
        say(f"  reply over {WORD_CAP} words — truncated whitespace-aware, "
            f"kept")
    return text


def bootstrap(client=None, say=print) -> int:
    doc = _load()
    if histories(doc):
        say("  REFUSED — a DREAM_HISTORY record already exists; the "
            "bootstrap runs once (R359). Use --fold for new dreams.")
        return 2
    dreams = corpus(doc)
    if not dreams:
        say("  nothing to bootstrap — the corpus is empty")
        return 1
    say(f"  bootstrap: deriving one history over {len(dreams)} dream "
        f"record(s)...")
    content = _derive(None, dreams, client=client, say=say)
    if content is None:
        return 1
    doc2, rec = render_history(doc, content,
                               [d["id"] for d in dreams],
                               "DREAM_HISTORY (bootstrap)")
    _save(doc2)
    say(f"  wrote {rec['id']} — {len(content.split())} words over "
        f"{len(rec['sources'])} sources")
    return 0


def fold(client=None, say=print) -> int:
    doc = _load()
    if not histories(doc):
        say("  REFUSED — no history yet; run --bootstrap first (R359)")
        return 2
    pending = unfolded(doc)
    if not pending:
        say("  nothing unfolded — the history is current")
        return 0
    for d in pending:
        doc = _load()
        prior = latest_history(doc)
        say(f"  folding {d['id']} ({d.get('date')})...")
        content = _derive(prior["content"], [d], client=client, say=say)
        if content is None:
            return 1
        doc2, rec = render_history(doc, content, [d["id"]],
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
         [d["id"] for d in corpus(doc)] == ["SD-0001", "SD-0002"])
    case("no histories yet", latest_history(doc) is None)
    case("everything unfolded before a bootstrap",
         [d["id"] for d in unfolded(doc)] == ["SD-0001", "SD-0002"])
    d2, rec = render_history(doc, "the account", ["SD-0001", "SD-0002"],
                             "DREAM_HISTORY (bootstrap)")
    case("render mints the next SD id as a history record",
         rec["id"] == "SD-0003" and rec["section"] == "history"
         and d2["next_id"] == 4)
    case("the corpus rows are untouched by the render",
         [r["id"] for r in corpus(d2)] == ["SD-0001", "SD-0002"])
    case("after the bootstrap nothing is unfolded", unfolded(d2) == [])
    d2[TABLE].append({"id": "SD-0004", "date": "2026-08-27", "title": "c",
                      "section": "dream", "content": "z"})
    case("a new dream is the one unfolded row",
         [d["id"] for d in unfolded(d2)] == ["SD-0004"])
    case("latest_history is the newest history record",
         latest_history(d2)["id"] == "SD-0003")
    t, cut = truncate_words("w " * 1200)
    case("over the word cap truncates to exactly the cap",
         cut and len(t.split()) == WORD_CAP)
    t2, cut2 = truncate_words("short text")
    case("under the cap passes untouched", not cut2 and t2 == "short text")
    print(f"\n  SELF-TEST: {'PASS' if not fails else 'FAIL'} "
          f"({10 - len(fails)} of 10)")
    return 1 if fails else 0


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description="DREAM_HISTORY — the bounded summary over Self's dream "
                    "corpus (R193/R319/R359)")
    ap.add_argument("--bootstrap", action="store_true",
                    help="the one R359 bootstrap derivation (a real model "
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
        return bootstrap()
    if a.fold:
        return fold()
    doc = _load()
    if a.show:
        h = latest_history(doc)
        print(h["content"] if h else "(no DREAM_HISTORY yet — run "
                                     "--bootstrap)")
        return 0
    hs = histories(doc)
    print(f"  corpus         {len(corpus(doc))} dream record(s)")
    print(f"  histories      {len(hs)} record(s)"
          + (f", newest {hs[-1]['id']} ({hs[-1]['date']})" if hs else ""))
    print(f"  unfolded       {len(unfolded(doc))} dream(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
