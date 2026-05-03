"""
run.py — Quick runner for AuditCheckr.

1. Set PATH_A and PATH_B to your two Word documents.
2. Set OUTPUT_DIR to where you want the reports saved.
3. Run:  python run.py
"""
from auditcheckr import extractor, differ
from auditcheckr.reporters.html_reporter import HtmlReporter
from auditcheckr.reporters.json_reporter import JsonReporter

# ── Configure these ───────────────────────────────────────────────────────────

PATH_A     = r"C:\path\to\document_v1.docx"
PATH_B     = r"C:\path\to\document_v2.docx"
OUTPUT_DIR = r"C:\path\to\reports"

# ── Run ───────────────────────────────────────────────────────────────────────

bytes_a = open(PATH_A, "rb").read()
bytes_b = open(PATH_B, "rb").read()

doc_a = extractor.extract(bytes_a, source_id=PATH_A)
doc_b = extractor.extract(bytes_b, source_id=PATH_B)

print(f"Doc A: {len(doc_a.blocks)} blocks")
print(f"Doc B: {len(doc_b.blocks)} blocks")

result = differ.diff(doc_a, doc_b)

print(f"\nDifferences found: {result.total_changes}")
for chunk in result.chunks:
    if chunk.chunk_type == "equal":
        continue
    a_text = chunk.block_a.text[:80] if chunk.block_a else "(none)"
    b_text = chunk.block_b.text[:80] if chunk.block_b else "(none)"
    print(f"\n  [{chunk.chunk_type.upper()}]")
    print(f"  A: {a_text}")
    print(f"  B: {b_text}")
    if chunk.annotation_delta:
        print(f"  ↳ Annotation {chunk.annotation_delta}: {chunk.annotation_kind}")

# Write reports
html_path = HtmlReporter().report(result, OUTPUT_DIR)
json_path = JsonReporter().report(result, OUTPUT_DIR)

print(f"\nHTML report → {html_path}")
print(f"JSON report → {json_path}")
