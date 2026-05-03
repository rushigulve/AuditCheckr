"""Tests for differ.py"""
from __future__ import annotations

from auditcheckr.models import Annotation, ContentBlock, DocumentModel
from auditcheckr.differ import diff


def _doc(source_id: str, texts: list[str], anns_per_block: list[list] | None = None) -> DocumentModel:
    anns_per_block = anns_per_block or [[] for _ in texts]
    blocks = [
        ContentBlock(index=i, text=t, block_type="paragraph",
                     style="Normal", annotations=a, raw_text=t)
        for i, (t, a) in enumerate(zip(texts, anns_per_block))
    ]
    return DocumentModel(source_id=source_id, blocks=blocks)


def test_identical_documents_no_changes():
    da = _doc("a.docx", ["Hello world.", "Second paragraph."])
    db = _doc("b.docx", ["Hello world.", "Second paragraph."])
    result = diff(da, db)
    assert not result.has_differences
    assert result.total_changes == 0
    assert all(c.chunk_type == "equal" for c in result.chunks)


def test_inserted_block():
    da = _doc("a.docx", ["Only paragraph."])
    db = _doc("b.docx", ["Only paragraph.", "New paragraph added."])
    result = diff(da, db)
    insert_chunks = [c for c in result.chunks if c.chunk_type == "insert"]
    assert len(insert_chunks) == 1
    assert "New paragraph" in insert_chunks[0].block_b.text


def test_deleted_block():
    da = _doc("a.docx", ["Keep this.", "Delete this."])
    db = _doc("b.docx", ["Keep this."])
    result = diff(da, db)
    delete_chunks = [c for c in result.chunks if c.chunk_type == "delete"]
    assert len(delete_chunks) == 1
    assert "Delete this" in delete_chunks[0].block_a.text


def test_replaced_block():
    da = _doc("a.docx", ["Original clause text here."])
    db = _doc("b.docx", ["Modified clause text here."])
    result = diff(da, db)
    replace_chunks = [c for c in result.chunks if c.chunk_type == "replace"]
    assert len(replace_chunks) == 1
    assert 0.0 < replace_chunks[0].similarity < 1.0


def test_similarity_identical_is_one():
    da = _doc("a.docx", ["Exact same text."])
    db = _doc("b.docx", ["Exact same text."])
    result = diff(da, db)
    assert result.chunks[0].similarity == 1.0


def test_annotation_delta_detected():
    ann = Annotation(kind="comment", body="Review needed", anchor="text",
                     author="Alice", date="2025-01-01")
    da = _doc("a.docx", ["Clause text."], [[ann]])
    db = _doc("b.docx", ["Clause text."], [[]])        # same text, no annotation
    result = diff(da, db)
    # The normalized strings differ (annotation embedded), so it's a replace
    changed = [c for c in result.chunks if c.annotation_delta]
    assert len(changed) >= 1
    assert changed[0].annotation_kind == "comment"


def test_result_source_ids():
    da = _doc("source_a.docx", ["Text"])
    db = _doc("source_b.docx", ["Text"])
    result = diff(da, db)
    assert result.source_a_id == "source_a.docx"
    assert result.source_b_id == "source_b.docx"
