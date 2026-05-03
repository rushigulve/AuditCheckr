"""
run.py — Quick runner for AuditCheckr.

1. Set PATH_A and PATH_B to your two Word documents.
2. Set OUTPUT_DIR to where you want the reports saved.
3. Run:  python run.py

WHY open(..., "rb")?
  .docx files are ZIP archives containing XML — not plain text.
  "rb" = read binary, so Python reads raw bytes without trying to
  decode them. python-docx then unzips and parses the XML internally.
"""
from auditcheckr import extractor, differ
from auditcheckr.reporters.html_reporter import HtmlReporter
from auditcheckr.reporters.json_reporter import JsonReporter

# ── Configure these ───────────────────────────────────────────────────────────

PATH_A     = r"C:\path\to\document_v1.docx"
PATH_B     = r"C:\path\to\document_v2.docx"
OUTPUT_DIR = r"C:\path\to\reports"

# Set to True if the documents are in Word "review mode" (tracked changes
# visible). Replicates Word's behaviour of hiding Show Markup → Insertions
# and Deletions: accepted insertions are kept, deleted text is dropped.
STRIP_REVIEW_MARKUP = False

# Set to True to print every block of text the program reads from each
# document before comparison. Useful for verifying what was extracted
# and checking if unwanted formatting noise is leaking through.
DEBUG_INSPECT = True

# ── Helpers ───────────────────────────────────────────────────────────────────

def inspect_raw(docx_bytes: bytes, label: str) -> None:
    """
    Print every paragraph exactly as python-docx reads it — before
    our extractor logic runs. Use this to spot formatting noise or
    tracked-change text that is leaking into the raw paragraphs.
    """
    import io
    from docx import Document
    doc = Document(io.BytesIO(docx_bytes))
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  RAW PARAGRAPHS — {label}")
    print(f"  ({len(doc.paragraphs)} paragraphs total, before extraction)")
    print(sep)
    for i, para in enumerate(doc.paragraphs):
        raw = "".join(run.text for run in para.runs)
        style = para.style.name if para.style else "Normal"
        if raw.strip():
            print(f"  [{i:>3}] [{style:<22}] {raw}")
        else:
            print(f"  [{i:>3}] [{style:<22}] (empty)")
    print(sep)


def inspect(doc, label: str) -> None:
    """Pretty-print all extracted blocks and their annotations."""
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  EXTRACTED TEXT — {label}")
    print(f"  ({len(doc.blocks)} blocks, strip_review_markup={STRIP_REVIEW_MARKUP})")
    print(sep)
    for b in doc.blocks:
        tag = f"[{b.block_type.upper():<10}] [{b.style:<20}]"
        print(f"\n  {tag}")
        print(f"  TEXT : {b.text}")
        for ann in b.annotations:
            detail = ""
            if ann.author: detail += f" by {ann.author}"
            if ann.number is not None: detail += f" #{ann.number}"
            print(f"  ANN  : [{ann.kind.upper()}]{detail} → {ann.body[:80]}")
    print(sep)

# ── Run ───────────────────────────────────────────────────────────────────────

bytes_a = open(PATH_A, "rb").read()
bytes_b = open(PATH_B, "rb").read()

if DEBUG_INSPECT:
    inspect_raw(bytes_a, f"Document A  →  {PATH_A}")
    inspect_raw(bytes_b, f"Document B  →  {PATH_B}")

doc_a = extractor.extract(bytes_a, source_id=PATH_A, strip_review_markup=STRIP_REVIEW_MARKUP)
doc_b = extractor.extract(bytes_b, source_id=PATH_B, strip_review_markup=STRIP_REVIEW_MARKUP)

if STRIP_REVIEW_MARKUP:
    print("[mode] Review markup stripped — comparing accepted/final text")
else:
    print("[mode] Standard extraction — comparing raw document text")

if DEBUG_INSPECT:
    inspect(doc_a, f"Document A  →  {PATH_A}")
    inspect(doc_b, f"Document B  →  {PATH_B}")
    print()

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
