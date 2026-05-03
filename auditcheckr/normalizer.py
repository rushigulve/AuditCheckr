"""
Normalizer: ContentBlock → comparable string

Each ContentBlock is serialized to a single normalized string that
embeds all annotation bodies inline using tagged bracket notation.
The same template-based dispatch works for all four annotation kinds —
no per-type branching in the differ or reporters.
"""
from __future__ import annotations

from .models import Annotation, ContentBlock, DocumentModel

# Template per annotation kind.  Keys must match AnnotationKind literals.
_TEMPLATES: dict[str, str] = {
    "comment":   '[COMMENT by {author} on {date}: "{body}"]',
    "screentip": '[SCREENTIP: "{body}"]',
    "footnote":  '[FOOTNOTE {number}: "{body}"]',
    "endnote":   '[ENDNOTE {number}: "{body}"]',
}


def _fmt_annotation(ann: Annotation) -> str:
    tmpl = _TEMPLATES.get(ann.kind, '[{kind}: "{body}"]')
    return tmpl.format(
        kind=ann.kind,
        body=ann.body,
        author=ann.author or "Unknown",
        date=ann.date   or "—",
        number=ann.number if ann.number is not None else "?",
    )


def _clean(text: str) -> str:
    """Strip formatting noise: smart quotes, excess whitespace."""
    text = (
        text.replace("\u2018", "'").replace("\u2019", "'")
            .replace("\u201c", '"').replace("\u201d", '"')
            .replace("\u2013", "-").replace("\u2014", "--")
    )
    return " ".join(text.split()).strip()


def normalize_block(block: ContentBlock) -> str:
    """Serialize one ContentBlock into a normalized comparable string."""
    parts = [_clean(block.text)]
    for ann in block.annotations:
        parts.append(_fmt_annotation(ann))
    return " ".join(parts)


def normalize(doc: DocumentModel) -> list[str]:
    """Return one normalized string per block in the document."""
    return [normalize_block(b) for b in doc.blocks]
