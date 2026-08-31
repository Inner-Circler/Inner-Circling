#!/usr/bin/env python3
"""
embed_store.py — the generic local-embedding store: one cache shape, one
ranking, one model, shared by every local semantic search in the tree.

HOISTED from ui/ticker/ticking_index.py (R400's build) when R402 gave the
mechanics a second consumer: the journal's index (Self's lens) and the
parts' recall index (coordinator/recall_index.py) must rank the same way
and cache the same way, and two copies of a cache format drift on the
first edit to either. This module owns the HOW — sha-invalidated vectors,
cosine, the model, the query prefix, the unavailable-stack error. Each
consumer owns its WHAT: its corpus, its cache path, its reply shape.

THE CACHE IS DERIVED, NEVER THE RECORD. One NDJSON row per embedded chunk
— id, a sha256 of the text, the model name, the vector — rebuilt whenever
a row is missing or its text's sha moved. Deleting a cache costs one
re-embed, nothing else.

THE MODEL IS FETCHED ONCE, on first use, into fastembed's own local cache
(~65 MB). After that everything is offline. A missing fastembed, or a
first use with no network, raises IndexUnavailable with the command that
fixes it — a missing tool is never a silent pass.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# bge's model card: short queries retrieve better with this instruction
# prepended to the QUERY (never to the passages).
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
INSTALL_HINT = ".venv/Scripts/python.exe -m pip install fastembed"


class IndexUnavailable(Exception):
    """The local stack is not usable; the message says what fixes it."""


def real_embedder():
    """texts -> list of vectors, through fastembed. Lazy: the import and
    the model load happen on first search, never at process start."""
    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        raise IndexUnavailable(
            f"local semantic search needs fastembed ({e}) — install it: "
            f"{INSTALL_HINT}") from e
    try:
        model = TextEmbedding(model_name=EMBED_MODEL)
    except Exception as e:                                # noqa: BLE001
        raise IndexUnavailable(
            f"the embedding model {EMBED_MODEL} did not load ({e}) — first "
            f"use downloads it once (~65 MB), so this run may simply lack "
            f"network") from e
    return lambda texts: [[float(x) for x in v] for v in model.embed(texts)]


def sha_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cache(path: pathlib.Path) -> dict:
    """id -> row, last one wins; rows for another model are dropped so a
    model change re-embeds everything rather than mixing spaces."""
    rows = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            if r.get("model") == EMBED_MODEL:
                rows[r["id"]] = r
        except (json.JSONDecodeError, KeyError, TypeError):
            continue                        # a damaged line costs one re-embed
    return rows


def write_cache(path: pathlib.Path, rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows.values()),
                    encoding="utf-8", newline="")


def cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def refresh(records: list, embedder, cache_path: pathlib.Path) -> dict:
    """id -> cache row for every record, embedding only what is missing or
    whose text moved. Writes the cache only when something was embedded.
    Records are dicts carrying at least `id` and a text field named either
    `body` (the journal's spelling) or `text` (the recall corpora's)."""
    def _txt(r: dict) -> str:
        return r.get("body", r.get("text", ""))
    rows = load_cache(cache_path)
    todo = [r for r in records
            if r["id"] not in rows
            or rows[r["id"]]["sha"] != sha_of(_txt(r))]
    if todo:
        vecs = embedder([_txt(r) for r in todo])
        for r, v in zip(todo, vecs):
            rows[r["id"]] = {"id": r["id"], "sha": sha_of(_txt(r)),
                             "model": EMBED_MODEL, "vec": v}
        live = {r["id"] for r in records}
        rows = {i: row for i, row in rows.items() if i in live}
        write_cache(cache_path, rows)
    return rows


def rank(query: str, records: list, embedder,
         cache_path: pathlib.Path, limit: int) -> list:
    """Cosine-ranked copies of the records, each with a `score` in [0, 1].
    Raises IndexUnavailable when the local stack cannot run."""
    if not query.strip() or not records:
        return []
    rows = refresh(records, embedder, cache_path)
    qvec = embedder([QUERY_PREFIX + query])[0]
    scored = []
    for r in records:
        row = rows.get(r["id"])
        if row is None:
            continue
        out = dict(r)
        out["score"] = round(max(0.0, min(1.0, cosine(qvec, row["vec"]))), 4)
        scored.append(out)
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]
