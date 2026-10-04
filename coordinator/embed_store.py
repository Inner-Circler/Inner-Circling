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

THE MODEL IS FETCHED ONCE, on first use, into work/embed_model/ (~65 MB;
MODEL_CACHE, B145 — fastembed's own default was the system temp folder, which
Windows cleans). After that everything is offline. A missing fastembed, or a
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

# WHERE THE MODEL IS KEPT — B145, 2026-10-03. fastembed's default is the system temp folder,
# and on 2026-10-02 Windows emptied it: the model files went, the folder stayed, and every
# local search failed until it was removed by hand. The model lives under this tree's own
# work/ now, gitignored — derived bytes, one download to recreate, never the record.
MODEL_CACHE = pathlib.Path(__file__).resolve().parent.parent / "work" / "embed_model"

# B142: the one outbound fetch besides the model calls, said aloud before it starts.
DOWNLOAD_NOTICE = (f"first use of local search: downloading the embedding model {EMBED_MODEL} "
                   f"(about 65 MB, once) into work/embed_model/ — it lets parts search their "
                   f"own record; offline after this. To decline, open with --recall-arm off.")


class IndexUnavailable(Exception):
    """The local stack is not usable; the message says what fixes it."""


def memory_model_cached_read(cache: "pathlib.Path | None" = None) -> bool:
    """Is the model already on disk? True when the cache holds a model file — an `.onnx`
    anywhere under it. A folder whose files were cleaned away (the 2026-10-02 shape) reads
    as not cached, which is the answer that matters: a download is coming."""
    d = cache or MODEL_CACHE
    return d.is_dir() and any(d.rglob("*.onnx"))


def memory_embedder_read(cache: "pathlib.Path | None" = None):
    """texts -> list of vectors, through fastembed. Lazy: the import and
    the model load happen on first search, never at process start. The model is
    read from (and on first use downloaded into) MODEL_CACHE, or `cache` when a
    probe names one."""
    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        raise IndexUnavailable(
            f"local semantic search needs fastembed ({e}) — install it: "
            f"{INSTALL_HINT}") from e
    d = cache or MODEL_CACHE
    try:
        d.mkdir(parents=True, exist_ok=True)
        model = TextEmbedding(model_name=EMBED_MODEL, cache_dir=str(d))
    except Exception as e:                                # noqa: BLE001
        raise IndexUnavailable(
            f"the embedding model {EMBED_MODEL} did not load ({e}) — first "
            f"use downloads it once (~65 MB), so this run may simply lack "
            f"network") from e
    return lambda texts: [[float(x) for x in v] for v in model.embed(texts)]


def memory_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def memory_cache_read(path: pathlib.Path) -> dict:
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


def memory_cache_write(path: pathlib.Path, rows: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows.values()),
                    encoding="utf-8", newline="")


def memory_cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def memory_refresh(records: list, embedder, cache_path: pathlib.Path) -> dict:
    """id -> cache row for every record, embedding only what is missing or
    whose text moved. Writes the cache only when something was embedded.
    Records are dicts carrying at least `id` and a text field named either
    `body` (the journal's spelling) or `text` (the recall corpora's)."""
    def _txt(r: dict) -> str:
        return r.get("body", r.get("text", ""))
    rows = memory_cache_read(cache_path)
    todo = [r for r in records
            if r["id"] not in rows
            or rows[r["id"]]["sha"] != memory_sha(_txt(r))]
    if todo:
        vecs = embedder([_txt(r) for r in todo])
        for r, v in zip(todo, vecs):
            rows[r["id"]] = {"id": r["id"], "sha": memory_sha(_txt(r)),
                             "model": EMBED_MODEL, "vec": v}
        live = {r["id"] for r in records}
        rows = {i: row for i, row in rows.items() if i in live}
        memory_cache_write(cache_path, rows)
    return rows


def memory_center(vec: list, centroid: list) -> list:
    """vec minus the corpus centroid, re-normalized to unit length. A
    near-zero result (a one-record corpus, identical texts, a query that IS
    the centroid) stays the zero vector, which memory_cosine() scores 0."""
    out = [x - c for x, c in zip(vec, centroid)]
    norm = math.sqrt(sum(x * x for x in out))
    return [x / norm for x in out] if norm > 1e-6 else [0.0] * len(out)


def memory_rank(query: str, records: list, embedder,
         cache_path: pathlib.Path, limit: int, center: bool = False) -> list:
    """Cosine-ranked copies of the records, each with a `score` in [0, 1].
    Raises IndexUnavailable when the local stack cannot run.

    center=False (the default, and recall's): raw cosine. bge's raw cosines
    sit in a narrow high band (~0.5-0.9 for related and unrelated alike),
    and recall_index.FLOOR (0.62) was MEASURED on that scale — keep it.

    center=True (Self's lens, 2026-09-29): mean-centered cosine, the fix
    Ticker's own semantic_search uses. The centroid of THIS corpus's
    vectors (the records passed in, so one per scope) is subtracted from
    the query and every passage, each re-normalized; the common component
    that packs raw cosines together is gone and scores spread over [-1, 1],
    so the pane's min-sim floor separates related from unrelated. Ranking
    uses the signed score; the reported `score` is clamped at 0 — below 0
    means "less related than the corpus average", under any floor the
    slider (0-0.9) can set, and [0, 1] stays the contract the pane reads."""
    if not query.strip() or not records:
        return []
    rows = memory_refresh(records, embedder, cache_path)
    qvec = embedder([QUERY_PREFIX + query])[0]
    hits = [(r, rows[r["id"]]["vec"]) for r in records if r["id"] in rows]
    if center and hits:
        dim, n = len(hits[0][1]), len(hits)
        centroid = [0.0] * dim
        for _, v in hits:
            for i, x in enumerate(v):
                centroid[i] += x
        centroid = [c / n for c in centroid]
        qvec = memory_center(qvec, centroid)
        hits = [(r, memory_center(v, centroid)) for r, v in hits]
    scored = []
    for r, vec in hits:
        sim = memory_cosine(qvec, vec)
        out = dict(r)
        out["score"] = round(max(0.0, min(1.0, sim)), 4)
        scored.append((sim, out))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [out for _, out in scored[:limit]]
