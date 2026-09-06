#!/usr/bin/env python3
"""
topic_prompt_projection.py — the BLOCK 2 projection of the TOPIC register: what
(topics_projection.py until 2026-09-03 — F5 under R435: a PROMPT projection says so in its name)
group_attention.py's circle_briefing_build() carries forward from
coordinator/topic_manager.py's open rows.

    python coordinator/topic_prompt_projection.py    the projection, as sent

Split out of topics.py, 2026-09-02, on direct instruction — mirroring
memory/issue_prompt_projection.py's own relationship to issue_schema.py: the
register (topic_manager.py) owns entries()/open_topics()/add()/close()/
render_new(), the raw data primitives; this module owns the one further
step of turning open rows into the exact text BLOCK 2 carries.
group_attention.py used to call topic_manager.block() directly — the read this
module's own name now names.

WHY THE SPLIT, NOT JUST A RENAME. topic_manager.py stays the TOPIC register's
one reader/writer — ids, tombstones, the file on disk. Nothing about
that job needs to know it feeds a prompt at all; issue_schema.py already
draws this line the same way. topic_manager.py's own CLI (`--block`) and test
suite were the only other callers of the function that moved; both now
go through here too, so there is exactly one place that turns the
register into BLOCK 2 text.
"""

from __future__ import annotations

import topic_manager as TOP


def topic_block_render() -> str:
    """The BLOCK 2 projection — "" when nothing is open, so an empty
    register leaves circle_objectives byte-identical. MOVED verbatim from
    topics.py's own topic_block_render(), 2026-09-02 — same body, only the module
    prefix on open_topics()/BUDGET changed."""
    es = TOP.topic_open_read()
    if not es:
        return ""
    lines, used, shown = [], 0, 0
    for t in es:
        entry = f"\n- {t['id']} (from circle {t.get('circle', '?')}): {t['text']}\n"
        if used + len(entry) > TOP.BUDGET:
            # break, not continue (2026-08-19, review tier 5 #57):
            # skipping the over-budget newer topic and rendering older
            # ones was fill-packing while the header below claims
            # "{omitted} OLDER omitted from view" and topic_manager.py's own
            # docstring says recency is the only priority lever — the
            # window ends at the first topic that does not fit, same
            # rule as remember._window. Measured before changing: the
            # open register sits well under BUDGET, no live prompt
            # changes a byte.
            break
        lines.append(entry)
        used += len(entry)
        shown += 1
    omitted = len(es) - shown
    head = ("## Topics for this circle's review\n\n"
            f"*From synthesis, UNVETTED — carried here for the room to "
            f"examine, never as a directive. {len(es)} open, {shown} shown "
            f"within a {TOP.BUDGET}-character window"
            + (f", {omitted} older omitted from view" if omitted else "")
            + ".*\n")
    return head + "".join(lines)


def main() -> int:
    print(topic_block_render() or "  (no open topics — projection is empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
