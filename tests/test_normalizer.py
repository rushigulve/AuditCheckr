"""Tests for normalizer.py"""
from __future__ import annotations

from auditcheckr.models import Annotation, ContentBlock
from auditcheckr.normalizer import normalize_block


def _block(text: str, annotations=None) -> ContentBlock:
    return ContentBlock(
        index=0, text=text, block_type="paragraph",
        style="Normal", annotations=annotations or [], raw_text=text,
    )


def test_plain_text_normalized():
    b = _block("Hello   World")
    assert normalize_block(b) == "Hello World"


def test_smart_quotes_cleaned():
    b = _block("\u201cContract\u201d and \u2018terms\u2019")
    result = normalize_block(b)
    assert '"Contract"' in result
    assert "'terms'" in result


def test_comment_embedded():
    ann = Annotation(kind="comment", body="Needs revision", anchor="text",
                     author="Alice", date="2025-01-10")
    b = _block("Some clause.", [ann])
    result = normalize_block(b)
    assert "[COMMENT by Alice on 2025-01-10" in result
    assert "Needs revision" in result


def test_screentip_embedded():
    ann = Annotation(kind="screentip", body="Force Majeure definition", anchor="FM")
    b = _block("See FM clause.", [ann])
    result = normalize_block(b)
    assert "[SCREENTIP:" in result
    assert "Force Majeure definition" in result


def test_footnote_embedded():
    ann = Annotation(kind="footnote", body="See statute §42", anchor="ref", number=3)
    b = _block("Refer to statute.", [ann])
    result = normalize_block(b)
    assert "[FOOTNOTE 3:" in result
    assert "§42" in result


def test_endnote_embedded():
    ann = Annotation(kind="endnote", body="Ibid.", anchor="ref", number=1)
    b = _block("As stated before.", [ann])
    result = normalize_block(b)
    assert "[ENDNOTE 1:" in result
    assert "Ibid." in result


def test_multiple_annotations():
    anns = [
        Annotation(kind="comment",   body="Check this",   anchor="x", author="Bob", date="2025-02-01"),
        Annotation(kind="screentip", body="Hover info",   anchor="x"),
    ]
    b = _block("Clause text.", anns)
    result = normalize_block(b)
    assert "[COMMENT" in result
    assert "[SCREENTIP" in result
