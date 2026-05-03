"""HTML reporter — side-by-side visual diff."""
from __future__ import annotations

from pathlib import Path

from ..models import DiffChunk, DiffResult
from .base import ReporterBase

# ── Inline HTML template (no external files needed) ──────────────────────────
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AuditCheckr — Diff Report</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

  :root {
    --bg:        #0f1117;
    --surface:   #1a1d27;
    --border:    #2a2d3a;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --accent:    #6366f1;

    --ins-bg:    #0d2318;
    --ins-border:#16a34a;
    --ins-text:  #86efac;
    --del-bg:    #2d0f0f;
    --del-border:#dc2626;
    --del-text:  #fca5a5;
    --rep-bg:    #1c1a08;
    --rep-border:#ca8a04;
    --rep-text:  #fde047;
    --eq-bg:     #141720;

    --ann-comment:   #818cf8;
    --ann-screentip: #34d399;
    --ann-footnote:  #fb923c;
    --ann-endnote:   #e879f9;
  }

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    line-height: 1.6;
  }

  header {
    background: linear-gradient(135deg, #1e1b4b 0%, #1a1d27 100%);
    border-bottom: 1px solid var(--border);
    padding: 24px 32px;
  }

  header h1 {
    font-size: 22px;
    font-weight: 700;
    color: #c7d2fe;
    letter-spacing: -0.3px;
  }

  header .meta {
    display: flex;
    gap: 24px;
    margin-top: 10px;
    flex-wrap: wrap;
  }

  header .meta span {
    font-size: 12px;
    color: var(--muted);
  }

  header .meta strong { color: var(--text); }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
  }

  .badge-changes { background: #3730a3; color: #c7d2fe; }
  .badge-clean   { background: #14532d; color: #86efac; }

  .legend {
    display: flex;
    gap: 16px;
    padding: 12px 32px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--muted);
  }

  .legend-dot {
    width: 10px; height: 10px;
    border-radius: 2px;
  }

  .diff-table {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
  }

  .col-header {
    padding: 10px 32px;
    background: var(--surface);
    border-bottom: 2px solid var(--border);
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 0.5px;
    text-transform: uppercase;
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .chunk {
    display: contents;
  }

  .cell {
    padding: 10px 32px;
    border-bottom: 1px solid var(--border);
    min-height: 46px;
    font-size: 13.5px;
  }

  .cell-equal   { background: var(--eq-bg); }
  .cell-insert  { background: var(--ins-bg);  border-left: 3px solid var(--ins-border); color: var(--ins-text); }
  .cell-delete  { background: var(--del-bg);  border-left: 3px solid var(--del-border); color: var(--del-text); }
  .cell-replace { background: var(--rep-bg);  border-left: 3px solid var(--rep-border); color: var(--rep-text); }
  .cell-empty   { background: var(--eq-bg); opacity: 0.3; }

  .ann-tag {
    display: inline-block;
    margin-top: 4px;
    padding: 2px 7px;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10.5px;
    font-weight: 500;
    opacity: 0.9;
    line-height: 1.4;
  }

  .ann-comment   { background: #1e1b4b; color: var(--ann-comment);   border: 1px solid var(--ann-comment);   }
  .ann-screentip { background: #022c22; color: var(--ann-screentip); border: 1px solid var(--ann-screentip); }
  .ann-footnote  { background: #431407; color: var(--ann-footnote);  border: 1px solid var(--ann-footnote);  }
  .ann-endnote   { background: #2e1065; color: var(--ann-endnote);   border: 1px solid var(--ann-endnote);   }

  .sim-pill {
    float: right;
    font-size: 10px;
    color: var(--muted);
    background: #1e2130;
    padding: 1px 6px;
    border-radius: 9999px;
    margin-left: 8px;
  }

  .chunk-type-label {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 2px;
    opacity: 0.7;
  }

  .summary-bar {
    display: flex;
    gap: 24px;
    padding: 14px 32px;
    background: #13151f;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
  }

  .stat { display: flex; flex-direction: column; }
  .stat .val { font-size: 22px; font-weight: 700; color: var(--accent); }
  .stat .lbl { font-size: 11px; color: var(--muted); margin-top: 2px; }
</style>
</head>
<body>

<header>
  <h1>⚖️ AuditCheckr — Legal Document Diff Report</h1>
  <div class="meta">
    <span><strong>Source A:</strong> {source_a}</span>
    <span><strong>Source B:</strong> {source_b}</span>
    <span>{badge}</span>
  </div>
</header>

<div class="summary-bar">
  <div class="stat"><span class="val">{total}</span><span class="lbl">Total Differences</span></div>
  <div class="stat"><span class="val">{inserts}</span><span class="lbl">Insertions</span></div>
  <div class="stat"><span class="val">{deletes}</span><span class="lbl">Deletions</span></div>
  <div class="stat"><span class="val">{replaces}</span><span class="lbl">Modifications</span></div>
  <div class="stat"><span class="val">{ann_changes}</span><span class="lbl">Annotation Changes</span></div>
</div>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#16a34a"></div>Inserted</div>
  <div class="legend-item"><div class="legend-dot" style="background:#dc2626"></div>Deleted</div>
  <div class="legend-item"><div class="legend-dot" style="background:#ca8a04"></div>Modified</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--ann-comment)"></div>Comment</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--ann-screentip)"></div>ScreenTip</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--ann-footnote)"></div>Footnote</div>
  <div class="legend-item"><div class="legend-dot" style="background:var(--ann-endnote)"></div>Endnote</div>
</div>

<div class="diff-table">
  <div class="col-header">Document A — {source_a}</div>
  <div class="col-header">Document B — {source_b}</div>
  {rows}
</div>

</body>
</html>"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _ann_tags(block) -> str:
    if block is None:
        return ""
    parts = []
    for a in block.annotations:
        label = {
            "comment":   f"💬 {_esc(a.author or 'Unknown')}: {_esc(a.body)}",
            "screentip": f"💡 {_esc(a.body)}",
            "footnote":  f"📝 fn{a.number}: {_esc(a.body)}",
            "endnote":   f"📌 en{a.number}: {_esc(a.body)}",
        }.get(a.kind, _esc(a.body))
        parts.append(f'<div class="ann-tag ann-{a.kind}">{label}</div>')
    return "".join(parts)


def _cell(block, css_class: str, chunk_type: str = "", similarity: float = 1.0) -> str:
    if block is None:
        return f'<div class="cell cell-empty"></div>'

    sim_pill = ""
    if chunk_type == "replace":
        pct = int(similarity * 100)
        sim_pill = f'<span class="sim-pill">{pct}% match</span>'

    text_html = f"{sim_pill}{_esc(block.text)}{_ann_tags(block)}"
    return f'<div class="cell {css_class}">{text_html}</div>'


def _render_rows(chunks: list[DiffChunk]) -> str:
    rows = []
    for c in chunks:
        if c.chunk_type == "equal":
            rows.append(_cell(c.block_a, "cell-equal"))
            rows.append(_cell(c.block_b, "cell-equal"))
        elif c.chunk_type == "insert":
            rows.append(_cell(None, "cell-empty"))
            rows.append(_cell(c.block_b, "cell-insert"))
        elif c.chunk_type == "delete":
            rows.append(_cell(c.block_a, "cell-delete"))
            rows.append(_cell(None, "cell-empty"))
        elif c.chunk_type == "replace":
            rows.append(_cell(c.block_a, "cell-replace", "replace", c.similarity))
            rows.append(_cell(c.block_b, "cell-replace", "replace", c.similarity))
    return "\n".join(rows)


# ── Reporter ──────────────────────────────────────────────────────────────────

class HtmlReporter(ReporterBase):
    reporter_id = "html"

    def report(self, result: DiffResult, output_dir: str) -> str:
        out = Path(output_dir) / "diff_report.html"
        out.parent.mkdir(parents=True, exist_ok=True)

        inserts    = sum(1 for c in result.chunks if c.chunk_type == "insert")
        deletes    = sum(1 for c in result.chunks if c.chunk_type == "delete")
        replaces   = sum(1 for c in result.chunks if c.chunk_type == "replace")
        ann_ch     = sum(1 for c in result.chunks if c.annotation_delta)

        if result.has_differences:
            badge = '<span class="badge badge-changes">⚠ Differences Found</span>'
        else:
            badge = '<span class="badge badge-clean">✓ Documents Match</span>'

        src_a = _esc(result.source_a_id)
        src_b = _esc(result.source_b_id)
        html = (
            _TEMPLATE
            .replace("{source_a}",   src_a)
            .replace("{source_b}",   src_b)
            .replace("{badge}",      badge)
            .replace("{total}",      str(result.total_changes))
            .replace("{inserts}",    str(inserts))
            .replace("{deletes}",    str(deletes))
            .replace("{replaces}",   str(replaces))
            .replace("{ann_changes}",str(ann_ch))
            .replace("{rows}",       _render_rows(result.chunks))
        )

        out.write_text(html, encoding="utf-8")
        return str(out)
