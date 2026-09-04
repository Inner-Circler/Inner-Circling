#!/usr/bin/env python3
"""
token_count.py — what a prompt actually costs, asked of the model service
rather than guessed. R260, 2026-08-20.

    python coordinator/token_count.py --stats     what the cache holds

EVERY TOKEN FIGURE THIS PROJECT PRINTED WAS `len(text) // 4`. Measured on
2026-08-20 against `prewarm`'s own `cache_creation_input_tokens` for circle
2026-08-20_0845, the real ratio for this corpus is ~3.0 characters per token,
so every figure ran ~30% under what was billed — and the two surfaces that
printed one disagreed with each other in different units besides. R260:
*ask the model service for the real count.*

`POST /v1/messages/count_tokens` is that service. It takes the same `system`
and `messages` a real request takes, cache_control blocks included (verified
2026-08-20 against the live endpoint, not inferred), and returns one
`input_tokens` for the whole request.

ONE NUMBER FOR THE WHOLE REQUEST IS THE PROBLEM THIS MODULE SOLVES. The four
prompt blocks have to be reported separately — that is what /status is for —
so this counts CUMULATIVE PREFIXES and differences them:

    envelope        count(no system at all)
    block 1         count([b1])          - envelope
    block 2         count([b1,b2])       - count([b1])
    block 3         count([b1,b2,b3])    - count([b1,b2])
    block 4         count([b1..b4])      - count([b1,b2,b3])

THE SUBTRACTION IS EXACT, and that is a property of the request shape rather
than luck: `system` is a LIST OF BLOCKS and each block is tokenized on its own,
so no token can straddle a boundary. Differencing text concatenated inside one
block would not be safe and is not done anywhere here.

MEASURED ONCE, THEN FREE. Every prefix is keyed by the sha256 of its own text
and kept in work/token_counts.json, so the two blocks every part shares are
counted once per CHANGE rather than once per part — and a circle whose
practices, briefing and distillates have not moved since the last open pays
for nothing but its seven BLOCK 4 tails. A first run on a cold cache costs 17
requests; the run after it usually costs 7.

WRITES ARE ATOMIC AND THE FILE IS DISPOSABLE. Losing it costs one re-count and
nothing else, which is why it lives under work/ and is not a register: it holds
no claim about the project, only an answer the service already gave.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import seam                                                    # noqa: E402
from atomic_write import record_atomic_write                          # noqa: E402
from record_paths import ROOT                                         # noqa: E402

CACHE_PATH = ROOT / "work" / "token_counts.json"

# The smallest legal request. `messages` is required, so the envelope is
# whatever the service charges for that plus the request scaffolding —
# measured once and subtracted, so a block's number is the block's own.
_PROBE = [{"role": "user", "content": "."}]
_ENVELOPE_KEY = "envelope"

# ~3.0 CHARACTERS PER TOKEN, measured 2026-08-20 across the seven parts of
# circle 2026-08-20_0845 (block-3 chars against prewarm's real
# cache_creation_input_tokens: 3.06, 3.00, 3.05, 3.07, 3.12, 3.15, and 2.93
# for child's three blocks together). USED ONLY WHERE NO COUNT CAN BE HAD —
# a dry run, or a service that will not answer — and every caller that falls
# back to it must SAY SO rather than print the number as measured. It is not
# a replacement for the count; it is what a sandbox prints.
CHARS_PER_TOKEN = 3.0


def prompt_tokens_estimate(text: str) -> int:
    """The fallback, named so a caller cannot use it by accident."""
    return int(len(text) / CHARS_PER_TOKEN)


def _key(blocks: list[dict]) -> str:
    h = hashlib.sha256()
    for b in blocks:
        h.update(b.get("text", "").encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def _load() -> dict:
    try:
        d = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        # A cache that will not parse is a cache to rebuild, not an error to
        # raise: nothing downstream of it is a claim about the project.
        return {}


def _save(d: dict) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        record_atomic_write(CACHE_PATH, json.dumps(d, indent=1, sort_keys=True) + "\n")
    except OSError:
        pass          # a lost cache costs one re-count; never a failed circle


def _ask(client, blocks: list[dict], model: str) -> int:
    kw = {"model": model, "messages": _PROBE}
    if blocks:
        kw["system"] = blocks
    return client.messages.count_tokens(**kw).input_tokens


def block_tokens(client, blocks: list[dict], model: str,
                 dry: bool = False) -> tuple[list[int], bool]:
    """([tokens per block], measured) for one part's four blocks.

    `measured` is False when the numbers are estimates — a dry run, or a
    service that would not answer. THE CALLER MUST SAY WHICH IT GOT; that is
    the whole reason this returns a flag instead of a bare list.

    NEVER RAISES. A circle must not fail because a size report could not be
    produced, so any transport failure degrades to the estimate and reports
    itself once."""
    if dry or client is None:
        return [prompt_tokens_estimate(b.get("text", "")) for b in blocks], False

    cache = _load()
    dirty = False
    try:
        if _ENVELOPE_KEY not in cache:
            cache[_ENVELOPE_KEY] = _ask(client, [], model)
            dirty = True
        prev = cache[_ENVELOPE_KEY]
        out: list[int] = []
        for i in range(len(blocks)):
            k = _key(blocks[:i + 1])
            if k not in cache:
                cache[k] = _ask(client, blocks[:i + 1], model)
                dirty = True
            out.append(cache[k] - prev)
            prev = cache[k]
    except Exception as e:                                     # noqa: BLE001
        seam.emit("command",
                  f"  (token counts estimated — the counting service said "
                  f"{type(e).__name__})")
        return [prompt_tokens_estimate(b.get("text", "")) for b in blocks], False
    if dirty:
        _save(cache)
    return out, True


def main() -> int:
    cache = _load()
    n = len(cache) - (1 if _ENVELOPE_KEY in cache else 0)
    print(f"\n  {CACHE_PATH.relative_to(ROOT)}")
    print(f"  {n} counted prefix(es)"
          + (f", envelope {cache[_ENVELOPE_KEY]} token(s)"
             if _ENVELOPE_KEY in cache else ", no envelope measured yet"))
    print("\n  Delete it to re-count; nothing else reads it.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
