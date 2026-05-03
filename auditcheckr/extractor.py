"""
Extractor: .docx bytes → DocumentModel

Handles all four Word annotation types without any extra libraries
beyond python-docx (which bundles lxml). Footnotes and Endnotes are
read directly from word/footnotes.xml and word/endnotes.xml inside
the docx ZIP, then mapped to their host paragraphs via
w:footnoteReference / w:endnoteReference elements.
"""
from __future__ import annotations

import io
import zipfile
from typing import Optional

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from .models import Annotation, ContentBlock, DocumentModel

# Word XML namespace
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _para_text(para) -> str:
    """Full text of a paragraph including text inside hyperlinks."""
    return "".join(run.text for run in para.runs)


def _notes_from_xml(
    docx_bytes: bytes,
    xml_path: str,
    tag: str,
    kind: str,
) -> dict[str, Annotation]:
    """
    Generic helper: reads word/footnotes.xml or word/endnotes.xml from
    the docx ZIP and returns {note_id: Annotation}.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as zf:
            if xml_path not in zf.namelist():
                return {}
            raw = zf.read(xml_path)
    except Exception:
        return {}

    root = etree.fromstring(raw)
    result: dict[str, Annotation] = {}

    for note in root.findall(f"{{{_W}}}{tag}"):
        nid = note.get(f"{{{_W}}}id", "")
        if nid in ("-1", "0"):          # separator / continuation notes
            continue
        text = "".join(
            t.text or "" for t in note.findall(f".//{{{_W}}}t")
        ).strip()
        if text:
            number = int(nid) if nid.lstrip("-").isdigit() else None
            result[nid] = Annotation(kind=kind, body=text, anchor="", number=number)

    return result


# ── Per-annotation-type extractors ───────────────────────────────────────────

def _extract_comments(doc) -> dict[str, list[Annotation]]:
    """Returns {paragraph_index_str: [Annotation(kind='comment')]}."""
    comments_by_id: dict[str, Annotation] = {}

    try:
        cp = doc.part.comments_part
    except AttributeError:
        cp = None
    if cp is None:
        return {}

    for el in cp._element.findall(qn("w:comment")):
        cid    = el.get(qn("w:id"), "")
        author = el.get(qn("w:author"), "")
        date   = el.get(qn("w:date"), "")[:10]
        body   = " ".join(
            "".join(r.text or "" for r in p.findall(".//" + qn("w:t")))
            for p in el.findall(".//" + qn("w:p"))
        ).strip()
        comments_by_id[cid] = Annotation(
            kind="comment", body=body, anchor="",
            author=author, date=date,
        )

    result: dict[str, list[Annotation]] = {}
    for i, para in enumerate(doc.paragraphs):
        for ref in para._p.findall(".//" + qn("w:commentReference")):
            cid = ref.get(qn("w:id"), "")
            if cid in comments_by_id:
                ann = comments_by_id[cid]
                ann.anchor = _para_text(para)
                result.setdefault(str(i), []).append(ann)
    return result


def _extract_screentips(doc) -> dict[str, list[Annotation]]:
    """Returns {paragraph_index_str: [Annotation(kind='screentip')]}."""
    result: dict[str, list[Annotation]] = {}
    for i, para in enumerate(doc.paragraphs):
        for hl in para._p.findall(".//" + qn("w:hyperlink")):
            tooltip = hl.get(qn("w:tooltip"))
            if tooltip:
                anchor = "".join(
                    t.text or "" for t in hl.findall(".//" + qn("w:t"))
                )
                result.setdefault(str(i), []).append(
                    Annotation(kind="screentip", body=tooltip, anchor=anchor)
                )
    return result


def _extract_note_references(
    doc,
    notes_map: dict[str, Annotation],
    ref_tag: str,
) -> dict[str, list[Annotation]]:
    """
    Generic helper for footnote / endnote references.
    Walks paragraphs looking for w:footnoteReference or w:endnoteReference
    and maps them to the host paragraph.
    """
    result: dict[str, list[Annotation]] = {}
    for i, para in enumerate(doc.paragraphs):
        for ref in para._p.findall(".//" + qn(ref_tag)):
            rid = ref.get(qn("w:id"), "")
            if rid in notes_map:
                ann = notes_map[rid]
                ann.anchor = _para_text(para)
                result.setdefault(str(i), []).append(ann)
    return result


# ── Public API ────────────────────────────────────────────────────────────────

def extract(docx_bytes: bytes, source_id: str) -> DocumentModel:
    """
    Parse a .docx byte blob into a DocumentModel.

    Args:
        docx_bytes: Raw bytes of the .docx file.
        source_id:  Human-readable identifier (filename, URL, etc.).

    Returns:
        A fully populated DocumentModel.
    """
    doc = Document(io.BytesIO(docx_bytes))

    # ── Gather all annotation maps ─────────────────────────────────────────
    comments_map   = _extract_comments(doc)
    screentips_map = _extract_screentips(doc)

    footnotes_data = _notes_from_xml(docx_bytes, "word/footnotes.xml", "footnote", "footnote")
    endnotes_data  = _notes_from_xml(docx_bytes, "word/endnotes.xml",  "endnote",  "endnote")

    footnotes_map  = _extract_note_references(doc, footnotes_data, "w:footnoteReference")
    endnotes_map   = _extract_note_references(doc, endnotes_data,  "w:endnoteReference")

    # ── Build ContentBlock list ────────────────────────────────────────────
    blocks: list[ContentBlock] = []
    idx = 0

    for i, para in enumerate(doc.paragraphs):
        text = _para_text(para).strip()
        if not text:
            continue

        style      = para.style.name if para.style else "Normal"
        block_type = "heading" if style.startswith("Heading") else "paragraph"
        key        = str(i)

        annotations: list[Annotation] = (
            comments_map.get(key, [])
            + screentips_map.get(key, [])
            + footnotes_map.get(key, [])
            + endnotes_map.get(key, [])
        )

        blocks.append(ContentBlock(
            index=idx, text=text, block_type=block_type,
            style=style, annotations=annotations, raw_text=text,
        ))
        idx += 1

    # ── Tables ────────────────────────────────────────────────────────────
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = _para_text(para).strip()
                    if not text:
                        continue
                    blocks.append(ContentBlock(
                        index=idx, text=text, block_type="table_cell",
                        style="Table", annotations=[], raw_text=text,
                    ))
                    idx += 1

    return DocumentModel(source_id=source_id, blocks=blocks)
