"""JSON reporter — machine-readable diff log."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import DiffResult
from .base import ReporterBase


def _block_dict(block) -> dict | None:
    if block is None:
        return None
    return {
        "text":  block.text,
        "style": block.style,
        "type":  block.block_type,
        "annotations": [
            {
                "kind":   a.kind,
                "body":   a.body,
                "anchor": a.anchor,
                "author": a.author,
                "date":   a.date,
                "number": a.number,
            }
            for a in block.annotations
        ],
    }


class JsonReporter(ReporterBase):
    reporter_id = "json"

    def report(self, result: DiffResult, output_dir: str) -> str:
        out = Path(output_dir) / "diff_report.json"
        out.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "source_a":        result.source_a_id,
            "source_b":        result.source_b_id,
            "total_changes":   result.total_changes,
            "has_differences": result.has_differences,
            "chunks": [
                {
                    "type":             c.chunk_type,
                    "similarity":       c.similarity,
                    "annotation_delta": c.annotation_delta,
                    "annotation_kind":  c.annotation_kind,
                    "block_a":          _block_dict(c.block_a),
                    "block_b":          _block_dict(c.block_b),
                }
                for c in result.chunks
            ],
        }

        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(out)
