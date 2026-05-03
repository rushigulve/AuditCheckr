"""
Core data models for AuditCheckr.

All four Word annotation types (Comments, ScreenTips, Footnotes, Endnotes)
are represented by the unified `Annotation` dataclass. The `kind` field
drives serialization and reporting — no per-type branching downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AnnotationKind  = Literal["comment", "screentip", "footnote", "endnote"]
BlockType       = Literal["paragraph", "heading", "table_cell"]
ChunkType       = Literal["equal", "insert", "delete", "replace"]
AnnotationDelta = Literal["added", "removed", "changed", ""]


@dataclass
class Annotation:
    """Unified model for all four Word annotation types."""

    kind:   AnnotationKind
    body:   str          # annotation text content
    anchor: str          # the text this annotation is attached to

    # Comment-specific (None for other kinds)
    author: str | None = None
    date:   str | None = None

    # Footnote / Endnote-specific
    number: int | None = None


@dataclass
class ContentBlock:
    index:       int
    text:        str        # raw paragraph text
    block_type:  BlockType
    style:       str        # Word style name e.g. "Heading 1"
    annotations: list[Annotation] = field(default_factory=list)
    raw_text:    str = ""


@dataclass
class DocumentModel:
    source_id: str
    blocks:    list[ContentBlock] = field(default_factory=list)


@dataclass
class DiffChunk:
    chunk_type:       ChunkType
    block_a:          ContentBlock | None
    block_b:          ContentBlock | None
    similarity:       float           = 1.0   # 0–1, meaningful for "replace"
    annotation_delta: AnnotationDelta = ""
    annotation_kind:  str             = ""    # which kind changed


@dataclass
class DiffResult:
    source_a_id: str
    source_b_id: str
    chunks:      list[DiffChunk] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return sum(1 for c in self.chunks if c.chunk_type != "equal")

    @property
    def has_differences(self) -> bool:
        return self.total_changes > 0
