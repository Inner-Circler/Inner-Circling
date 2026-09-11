#!/usr/bin/env python3
"""
remember_expand.py — tier A of seed-anchored recall: the pre-fetch at open.

RULED 2026-08-29 (the module name and the go both): at circle open, any seed
in a part's register whose text overlaps the day's topic or focus issues is
quoted in that part's BLOCK 4 with a short excerpt of the circle that minted
it — found by the seed's own `circle` field, a deterministic dereference,
never a search and never a model call. docs/MEMORY_DESIGN.md, "Tier A,
detailed", is the design; the trial protocol beneath it is why `remember_expand_apply()`
takes an ARM and writes a trial log.

READ-ONLY, WITH ONE NAMED EXCEPTION. Nothing here touches a register, a
transcript, or a part file. The one write is the TRIAL LOG —
work/recall_trial/recall_<OT>.json, one file per circle while the arm is on,
coordinator-written like a close report, gitignored, never shipped.

NOTHING HERE MAY COST AN OPEN. Every failure degrades: a seed whose minting
transcript is missing, unparseable, or without a close report contributes
nothing; a blank topic with no working set yields no terms and an empty
pack; any exception anywhere in remember_expand_apply() is caught, reported on the command
channel, and the circle opens without packs. The degrade table is in the
design doc and coordinator/tests/test_remember_expand.py drives every row.

PLACEMENT (R387): content decides the block, and this
content is each part's own private seeds — so BLOCK 4 only, the uncached
per-part tail.

remember_expand_apply() RETURNS {part: pack_text} RATHER THAN WRITING BLOCK 4 ITSELF, since
2026-09-02 — asked directly why a different file was reaching into a block
it does not own. R387 never ruled the MECHANISM, only the PLACEMENT (this
content belongs in BLOCK 4, not BLOCK 2 or BLOCK 3); the direct-write shape
was an implementation choice made alongside that ruling, not required by
it. Every other memory-read path (part_mid_term_manager.py, remember_manager.py,
practice_manager.py, instrument_manager.py, issue_prompt_projection.py, part_roster.py)
already returns text and lets its own block's assembler place it — this
was the one file with write access to a structure it did not own, which
is worse than the direct-mutation shape's own advantage (a single, cheaply
tested confinement: this module could not touch any block but 4). Now
role_attention.py's finalize() is the one and only place that writes
sysblocks[p][3]["text"], matching Block 1/2/3's own shape exactly. The old
confinement test (remember_expand_apply() may not touch any index but 3) is moot under the
new contract — remember_expand_apply() no longer receives sysblocks at all, so there is no
OTHER index left for it to reach; the same guarantee now holds by
construction rather than by a probe checking it.
"""
from __future__ import annotations

import json
import re
import time

import seam
import remember_manager as RM
import part_roster as R
import transcript_store as TS
from record_paths import ROOT, record_dir

# The part-facing heading (the operator's default, accepted 2026-08-29 with
# the module name). Part-facing prose: theirs to reword.
PACK_HEADING = "## From your record, on today's matter"

SEED_QUOTE_CAP = 300     # chars of the seed's own text quoted above its excerpt
EXPAND_N = 2             # seeds expanded per part per circle
# 1200 = what ONE recall delivery may put in front of a part. Here that is
# one seed's excerpt (a pack carries EXPAND_N of them); recall_index
# imports it as its whole-reply budget — SHARED KNOWINGLY (2026-08-30, the
# one-home rule): both were sized by the same question, how much recalled
# text one occasion may spend, and a future resize should move both.
EXPAND_CAP = 1200

# THE ARM IS A FLAG, NOT A FILE — circle.py's --recall-arm, default
# `delivered` since 2026-09-10 (R526); `off` until then.
# The trial protocol flips it per circle, and a flag per invocation cannot
# be forgotten in a settings file between the trial and ordinary use; it
# also rides argv into the record. An unknown value is OFF, the degrade
# direction.
ARMS = ("off", "delivered", "withheld")


# ------------------------------------------------------------------- terms
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'-]{3,}")
_NID_RE = re.compile(r"\bn\d{4}\b")


def remember_terms_read(topic: str, labels: list[str]) -> tuple[set, set]:
    """(words, node ids) drawn from the topic and the focus issues' labels.
    Words shorter than 4 characters are noise, not signal."""
    text = " ".join([topic or ""] + labels).lower()
    return set(_WORD_RE.findall(text)), set(_NID_RE.findall(text))


def remember_labels_read(chosen: "list[str] | None") -> list[str]:
    """The chosen focus nodes' labels, read through issue_schema — the one
    reader. A node that cannot be found or loaded contributes nothing."""
    if not chosen:
        return []
    import sys
    sys.path.insert(0, str(ROOT / "memory"))
    import issue_schema as IS
    out = []
    for p in IS.issue_nodes_read():
        try:
            if IS.issue_id_read(p.stem) in chosen:
                out.append(str(IS.issue_read(p).get("label", "")))
        except Exception:
            continue
    return [x for x in out if x]


# --------------------------------------------------------------- selection
def remember_overlap_read(body: str, words: set, nids: set) -> int:
    low = body.lower()
    hits = sum(1 for w in words if w in low)
    hits += sum(1 for n in nids if n in low)
    return hits


def remember_qualifies(body: str, words: set, nids: set) -> bool:
    """>= 2 distinct term hits, or one exact node-id hit — the design's
    deterministic match rule."""
    low = body.lower()
    if any(n in low for n in nids):
        return True
    return sum(1 for w in words if w in low) >= 2


def _chain_depth(recs: list[dict]) -> dict:
    """id -> how many records this one's chain walks back through. Local and
    cheap rather than reaching into remember_manager.py's private helper."""
    by_id = {r.get("id"): r for r in recs if r.get("id")}
    depth: dict = {}

    def walk(r: dict, seen: frozenset) -> int:
        rid = r.get("id")
        if rid in depth:
            return depth[rid]
        prev = by_id.get(r.get("chain"))
        d = 0 if (prev is None or rid in seen) \
            else 1 + walk(prev, seen | {rid})
        if rid:
            depth[rid] = d
        return d

    for r in recs:
        walk(r, frozenset())
    return depth


def remember_select(records: list[dict], words: set, nids: set,
           exclude_ot: str, cap: int) -> list[dict]:
    """The qualifying seeds, ranked: overlap, then the mechanical salience
    score (salience weight + chain depth — the 2026-08-22 build's own
    components), then recency. Migration rows (class-bearing) and records
    with no circle field are not seeds. The CURRENT circle is excluded —
    its transcript already rides every request via prompt_messages_render."""
    depth = _chain_depth(records)
    scored = []
    for r in records:
        if r.get("class") or not r.get("circle"):
            continue
        if r.get("circle") == exclude_ot:
            continue
        body = str(r.get("text", ""))
        if not remember_qualifies(body, words, nids):
            continue
        sal = RM.SALIENCE_WEIGHT.get(str(r.get("salience", "")), 0)
        scored.append((remember_overlap_read(body, words, nids),
                       sal + depth.get(r.get("id"), 0),
                       str(r.get("date", "")), r))
    scored.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    return [r for _, _, _, r in scored[:cap]]


# ------------------------------------------------------------- dereference
def _closed(ot: str) -> bool:
    return (ROOT / "work" / "logs" / f"close_{ot}.json").is_file()


def remember_span_read(entries: list[dict], seed_text: str, part_tag: str,
              char_cap: int) -> str:
    """The excerpt: the statement best matching the SEED's own terms, two
    before and one after. If nothing matches — dream-authored seeds
    paraphrase — the minting part's last statement there, one neighbor
    either side. Pure over parsed entries; the probe drives it directly."""
    words, nids = remember_terms_read(seed_text, [])
    rows = [e for e in entries if not e.get("is_topic")]
    if not rows:
        return ""
    best, best_hits = None, 0
    for i, e in enumerate(rows):
        hits = remember_overlap_read(str(e.get("text", "")), words, nids)
        if hits > best_hits:
            best, best_hits = i, hits
    if best is None:
        own = [i for i, e in enumerate(rows) if e.get("display") == part_tag]
        if not own:
            return ""
        lo, hi = max(0, own[-1] - 1), min(len(rows), own[-1] + 2)
    else:
        lo, hi = max(0, best - 2), min(len(rows), best + 2)
    out, used = [], 0
    for e in rows[lo:hi]:
        line = f"[{e.get('display', '?')}]: {str(e.get('text', '')).strip()}"
        take = line[:max(0, char_cap - used)]
        if not take:
            break
        out.append(take)
        used += len(take) + 1
    return "\n".join(out)


def remember_dereference(ot: str, seed_text: str, part_tag: str, char_cap: int) -> str:
    """OT -> transcript -> span. Every miss is epsilon, never a raise."""
    try:
        if not _closed(ot):
            return ""
        p = record_dir(ROOT, "circles") / f"circle_{ot}.md"
        if not p.is_file():
            return ""
        _, _, entries = TS.circle_transcript_parse(p.read_text(encoding="utf-8"))
        return remember_span_read(entries, seed_text, part_tag, char_cap)
    except Exception:
        return ""       # a damaged record is the audit's to report


# -------------------------------------------------------------------- pack
def remember_pack_build_from(records: list[dict], part_tag: str, topic: str,
                    labels: list[str], exclude_ot: str) -> tuple[str, list]:
    """(pack text, matched-record log rows). Empty pack when nothing
    qualifies or nothing dereferences."""
    words, nids = remember_terms_read(topic, labels)
    if not words and not nids:
        return "", []
    chosen = remember_select(records, words, nids, exclude_ot, EXPAND_N)
    sections, log = [], []
    for r in chosen:
        excerpt = remember_dereference(str(r["circle"]), str(r.get("text", "")),
                              part_tag, EXPAND_CAP)
        log.append({"circle": r.get("circle"), "date": r.get("date"),
                    "salience": r.get("salience"), "expanded": bool(excerpt),
                    "overlap": remember_overlap_read(str(r.get("text", "")),
                                          words, nids)})
        if not excerpt:
            continue
        quote = str(r.get("text", "")).strip()[:SEED_QUOTE_CAP]
        sections.append(f"Your note (circle {r['circle']}):\n"
                        f"    \"{quote}\"\nFrom that circle:\n{excerpt}")
    if not sections:
        return "", log
    return PACK_HEADING + "\n\n" + "\n\n".join(sections), log


def remember_pack_build(part: str, topic: str, labels: list[str],
               exclude_ot: str) -> tuple[str, list]:
    tag = dict(R.ROSTER).get(part, part)
    return remember_pack_build_from(RM.remember_read(part), tag, topic, labels, exclude_ot)


# ------------------------------------------------------------------- apply
def remember_expand_apply(parts: list[str], topic: str, chosen: "list[str] | None",
          ot: str, arm: "str | None" = None) -> dict[str, str]:
    """The one call site (role_attention.part_attention_finalize(), after the topic is
    known and before the capture/pre-warm). Returns {part: pack_text} for
    every part whose pack should actually reach BLOCK 4 this circle — the
    caller writes it; this module never sees the prompt structure at all.
    `arm` comes from circle.py's --recall-arm; anything unrecognized is
    OFF. NEVER RAISES — every failure degrades to an empty dict, same
    guarantee as before the write moved out of here."""
    delivered: dict[str, str] = {}
    try:
        arm = arm if arm in ARMS else "off"
        if arm == "off":
            return delivered
        labels = remember_labels_read(chosen)
        record = {"ot": ot, "arm": arm, "topic": topic,
                  "chosen": chosen or [], "ts": int(time.time()),
                  "parts": {}}
        packed = total = 0
        for p in parts:
            pack, log = remember_pack_build(p, topic, labels, ot)
            is_delivered = bool(pack) and arm == "delivered"
            record["parts"][p] = {"matched": log, "pack_chars": len(pack),
                                  "delivered": is_delivered, "pack": pack}
            if pack:
                packed += 1
                total += len(pack)
                if is_delivered:
                    delivered[p] = pack
        out = ROOT / "work" / "recall_trial"
        out.mkdir(parents=True, exist_ok=True)
        with open(out / f"recall_{ot}.json", "w", encoding="utf-8",
                  newline="") as f:
            json.dump(record, f, ensure_ascii=False, indent=1)
        seam.emit("command", f"  recall: arm={arm} — packs for {packed}/"
                             f"{len(parts)} part(s), {total} chars")
    except Exception as e:                                   # noqa: BLE001
        seam.emit("command", f"  !! recall pre-fetch failed and was skipped "
                             f"({e}) — the circle opens without packs")
    return delivered


if __name__ == "__main__":
    # a report, not a write: what WOULD match for each part, given a topic
    import argparse
    ap = argparse.ArgumentParser(description="dry report of tier A matching")
    ap.add_argument("topic")
    # `issue ids`, NOT `node ids` — R279, 2026-08-21: "'node' is graph speak ... do not
    # surface 'node'. Replace it with the class of node being referenced." A usage line is
    # named in that ruling's own scope list, and R279's sweep did not reach this module.
    # audit-register.md #34 (undocumented flag) and #35 (the word), both 2026-09-08.
    ap.add_argument("--issues", default="",
                    help="comma-separated issue ids to seed tier A (default: none)")
    a = ap.parse_args()
    ids = [s.strip() for s in a.issues.split(",") if s.strip()]
    labels = remember_labels_read(ids or None)
    for d, _t in R.ROSTER:
        pack, log = remember_pack_build(d, a.topic, labels, exclude_ot="")
        print(f"{d}: {len(log)} matched, pack {len(pack)} chars")
        for row in log:
            print(f"    {row['circle']} overlap={row['overlap']} "
                  f"salience={row['salience']} expanded={row['expanded']}")
