"""
Extractor: .docx bytes → DocumentModel

Handles all four Word annotation types without any extra libraries
beyond python-docx (which bundles lxml). Footnotes and Endnotes are
read directly from word/footnotes.xml and word/endnotes.xml inside
the docx ZIP, then mapped to their host paragraphs via
w:footnoteReference / w:endnoteReference elements.

strip_review_markup mode
────────────────────────
Legal documents are often in "review mode" — they contain tracked changes
(<w:ins> insertions and <w:del> deletions) that are visible in Word's
"Show Markup" view.  When strip_review_markup=True the extractor replicates
What MS Word does when you turn off Show Markup → Insertions and Deletions:

  • Text inside <w:ins> (insertions) is KEPT   → accepted
  • Text inside <w:del> (deletions)  is DROPPED → rejected
  • Formatting change elements (<w:rPrChange>, <w:pPrChange>) are ignored

This gives you the clean "final accepted" text for comparison.
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

_DEL_TAG = f"{{{_W}}}del"
_T_TAG   = f"{{{_W}}}t"


def _para_text(para) -> str:
    """Full text of a paragraph including text inside hyperlinks."""
    return "".join(run.text for run in para.runs)


def _para_text_accepted(para) -> str:
    """
    Extract paragraph text with all tracked changes accepted:
      - w:del nodes are removed entirely        (deleted text dropped)
      - w:ins wrappers are unwrapped             (inserted text kept)

    Works on a deep copy of the paragraph XML so the live Document
    object is never mutated.  Falls back to _para_text when no tracked
    changes are present (fast path).
    """
    from copy import deepcopy

    p = para._p

    # Fast path: use etree.tostring which is always reliable
    xml_str = etree.tostring(p, encoding="unicode")
    if f"{{{_W}}}del" not in xml_str and f"{{{_W}}}ins" not in xml_str:
        return _para_text(para)

    # Work on a copy — never mutate the live document
    p_copy = deepcopy(p)
    nsmap = {"w": _W}

    # 1. Drop all deleted text
    for del_node in p_copy.findall(".//w:del", namespaces=nsmap):
        del_node.getparent().remove(del_node)

    # 2. Unwrap w:ins — keep children, discard the wrapper element
    for ins_node in p_copy.findall(".//w:ins", namespaces=nsmap):
        parent = ins_node.getparent()
        children = list(ins_node)          # list() — getchildren() is deprecated
        idx = list(parent).index(ins_node)
        for i, child in enumerate(children):
            parent.insert(idx + i, child)
        parent.remove(ins_node)

    # 3. Collect all remaining w:t text
    return "".join(t.text or "" for t in p_copy.findall(f".//{{{_W}}}t"))


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

def extract(
    docx_bytes: bytes,
    source_id: str,
    strip_review_markup: bool = False,
) -> DocumentModel:
    """
    Parse a .docx byte blob into a DocumentModel.

    Args:
        docx_bytes:          Raw bytes of the .docx file.
        source_id:           Human-readable identifier (filename, URL, etc.).
        strip_review_markup: When True, accept all tracked changes before
                             extracting text (include <w:ins>, drop <w:del>).
                             Use this for documents in Word review/markup mode.

    Returns:
        A fully populated DocumentModel.
    """
    get_text = _para_text_accepted if strip_review_markup else _para_text
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
        text = get_text(para).strip()
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
                    text = get_text(para).strip()
                    if not text:
                        continue
                    blocks.append(ContentBlock(
                        index=idx, text=text, block_type="table_cell",
                        style="Table", annotations=[], raw_text=text,
                    ))
                    idx += 1

    return DocumentModel(source_id=source_id, blocks=blocks)
