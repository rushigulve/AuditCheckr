"""
Differ: DocumentModel × 2 → DiffResult

Uses stdlib difflib.SequenceMatcher on normalized block strings.
Similarity scoring lets reporters distinguish minor edits (>0.85)
from major rewrites (<0.50).  Annotation-only changes (same text,
different annotations) are detected as a separate delta type.
"""
from __future__ import annotations

import difflib

from .models import ContentBlock, DiffChunk, DiffResult, DocumentModel
from .normalizer import normalize_block


def _annotation_delta(
    ba: ContentBlock | None,
    bb: ContentBlock | None,
) -> tuple[str, str]:
    """
    Compare annotations between two blocks.
    Returns (delta: "added"|"removed"|"changed"|"", dominant_kind).
    """
    if ba is None or bb is None:
        return "", ""

    set_a = {(a.kind, a.body) for a in ba.annotations}
    set_b = {(a.kind, a.body) for a in bb.annotations}

    added   = set_b - set_a
    removed = set_a - set_b

    if not added and not removed:
        return "", ""

    dominant = next(iter({k for k, _ in (added | removed)}), "")

    if added and not removed:
        return "added", dominant
    if removed and not added:
        return "removed", dominant
    return "changed", dominant


def diff(doc_a: DocumentModel, doc_b: DocumentModel) -> DiffResult:
    """
    Paragraph-level diff between two DocumentModels.

    Returns a DiffResult where every block from both documents appears
    in exactly one DiffChunk.  Similarity score is set for "replace"
    chunks; annotation_delta/annotation_kind are set when annotations
    differ regardless of whether body text also changed.
    """
    blocks_a = doc_a.blocks
    blocks_b = doc_b.blocks
    norm_a   = [normalize_block(b) for b in blocks_a]
    norm_b   = [normalize_block(b) for b in blocks_b]

    matcher = difflib.SequenceMatcher(None, norm_a, norm_b, autojunk=False)
    chunks: list[DiffChunk] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":
            for k in range(i2 - i1):
                ba, bb = blocks_a[i1 + k], blocks_b[j1 + k]
                ann_delta, ann_kind = _annotation_delta(ba, bb)
                chunks.append(DiffChunk(
                    chunk_type="equal",
                    block_a=ba, block_b=bb,
                    annotation_delta=ann_delta,
                    annotation_kind=ann_kind,
                ))

        elif tag == "replace":
            a_slice = blocks_a[i1:i2]
            b_slice = blocks_b[j1:j2]
            pairs   = list(zip(a_slice, b_slice))

            for ba, bb in pairs:
                sim = difflib.SequenceMatcher(
                    None, normalize_block(ba), normalize_block(bb)
                ).ratio()
                ann_delta, ann_kind = _annotation_delta(ba, bb)
                chunks.append(DiffChunk(
                    chunk_type="replace",
                    block_a=ba, block_b=bb,
                    similarity=round(sim, 3),
                    annotation_delta=ann_delta,
                    annotation_kind=ann_kind,
                ))

            # Unmatched extras become inserts / deletes
            for ba in a_slice[len(pairs):]:
                chunks.append(DiffChunk(chunk_type="delete", block_a=ba, block_b=None))
            for bb in b_slice[len(pairs):]:
                chunks.append(DiffChunk(chunk_type="insert", block_a=None, block_b=bb))

        elif tag == "delete":
            for ba in blocks_a[i1:i2]:
                chunks.append(DiffChunk(chunk_type="delete", block_a=ba, block_b=None))

        elif tag == "insert":
            for bb in blocks_b[j1:j2]:
                chunks.append(DiffChunk(chunk_type="insert", block_a=None, block_b=bb))

    return DiffResult(source_a_id=doc_a.source_id, source_b_id=doc_b.source_id, chunks=chunks)
