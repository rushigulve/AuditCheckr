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

# Set to True to dump the full raw XML of every paragraph.
# Use this when tips are not being detected — it shows exactly
# what Word is storing in the file.
DUMP_FULL_XML = False

# Set to True to dump the /customXml/ folder from the docx ZIP.
# Knowledge Coach tips are stored here, not in document.xml.
# Run this once to see the structure, then we can write extraction code.
DUMP_CUSTOM_XML = False

# Set to True to scan word/document.xml for all <w:sdt> Content Controls.
# Tips invisible to para.runs (e.g. Knowledge Coach SDTs) will show here.
DUMP_SDT = False

# ── Helpers ───────────────────────────────────────────────────────────────────

def dump_custom_xml(path: str) -> None:
    """
    Dump every file in the /customXml/ folder inside the .docx ZIP.
    Knowledge Coach stores its tip/guidance data here as proprietary XML.
    Run with DUMP_CUSTOM_XML=True to see the raw structure.
    """
    import zipfile
    from lxml import etree

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  CUSTOM XML PARTS  —  {path}")
    print(sep)

    with zipfile.ZipFile(path, "r") as zf:
        custom_files = [n for n in zf.namelist() if n.startswith("customXml/") and n.endswith(".xml")]
        if not custom_files:
            print("  No customXml/ files found in this document.")
            print("  Tips may be stored elsewhere (e.g. word/document.xml SDTs).")
        for fname in sorted(custom_files):
            print(f"\n  ── File: {fname} ──")
            raw = zf.read(fname)
            try:
                root = etree.fromstring(raw)
                print(etree.tostring(root, pretty_print=True).decode())
            except Exception:
                print(raw.decode(errors="replace"))
    print(sep)


def dump_sdt_elements(path: str) -> None:
    """
    Read word/document.xml directly and print every <w:sdt> element.
    Content Controls (SDTs) are invisible to para.runs — Knowledge Coach
    tips that live in SDTs will appear here even if all other diagnostics
    missed them.  Each entry shows the alias, tag, and visible text.
    """
    import zipfile
    from lxml import etree

    _W   = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    SDT  = f"{{{_W}}}sdt"
    SDTP = f"{{{_W}}}sdtPr"
    SDTC = f"{{{_W}}}sdtContent"
    ALIAS = f"{{{_W}}}alias"
    TAG   = f"{{{_W}}}tag"
    W_VAL = f"{{{_W}}}val"

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  CONTENT CONTROLS (w:sdt)  —  {path}")
    print(sep)

    with zipfile.ZipFile(path, "r") as zf:
        raw = zf.read("word/document.xml")

    root = etree.fromstring(raw)
    sdts = root.findall(f".//{SDT}")
    print(f"  Found {len(sdts)} SDT element(s).\n")

    for i, sdt in enumerate(sdts):
        pr = sdt.find(SDTP)
        alias = tag = ""
        if pr is not None:
            a = pr.find(ALIAS)
            t = pr.find(TAG)
            if a is not None: alias = a.get(W_VAL, "")
            if t is not None: tag   = t.get(W_VAL, "")

        content_el = sdt.find(SDTC)
        text = ""
        if content_el is not None:
            text = "".join(
                (e.text or "") for e in content_el.iter(f"{{{_W}}}t")
            ).strip()

        print(f"  SDT [{i}]  alias={alias!r}  tag={tag!r}")
        print(f"    text : {text[:200]!r}")
        # Print full XML capped at 600 chars so output stays readable
        full_xml = etree.tostring(sdt, pretty_print=True).decode()
        print(f"    xml  :\n{full_xml[:600]}")
        if len(full_xml) > 600:
            print("    ... (truncated)")
        print()

    print(sep)


def inspect_raw(path: str, label: str) -> None:
    """
    Print every paragraph exactly as python-docx reads it — before
    our extractor logic runs.
    """
    import io
    from docx import Document
    doc = Document(path)
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


def inspect_xml_tips(path: str) -> None:
    """
    Diagnostic: scan every paragraph for any element that looks like
    an annotation or tip and print its raw XML.

    This tells us EXACTLY what Word is storing so we can figure out
    why tips are not being picked up.  Looks for:
      - w:hyperlink           (ScreenTips live here as w:tooltip)
      - w:commentReference    (Comments)
      - w:footnoteReference / w:endnoteReference
    If none found, and DUMP_FULL_XML=True, prints full XML of every paragraph.
    """
    from docx import Document
    from docx.oxml.ns import qn
    from lxml import etree

    doc = Document(path)
    sep = "-" * 60
    TAGS = {
        qn("w:hyperlink"), qn("w:commentReference"),
        qn("w:footnoteReference"), qn("w:endnoteReference"),
    }
    found_any = False

    print(f"\n{sep}")
    print(f"  XML TIP DIAGNOSTIC  {path}")
    print(sep)

    for i, para in enumerate(doc.paragraphs):
        hits = [elem for elem in para._p.iter() if elem.tag in TAGS]
        if hits:
            found_any = True
            raw = "".join(r.text for r in para.runs)
            print(f"\n  Para [{i}]: {raw[:80]!r}")
            for elem in hits:
                print(f"  TAG : {elem.tag}")
                print(etree.tostring(elem, pretty_print=True).decode())

    if not found_any:
        print("\n  No hyperlinks/comments/footnotes found in body paragraphs.")
        print("  Set DUMP_FULL_XML = True to see complete XML for all paragraphs.")

    if DUMP_FULL_XML:
        print(f"\n{sep}  FULL XML DUMP  {sep}")
        for i, para in enumerate(doc.paragraphs):
            raw = "".join(r.text for r in para.runs).strip()
            if raw:
                print(f"\n  Para [{i}]: {raw[:60]!r}")
                print(etree.tostring(para._p, pretty_print=True).decode())
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

if DEBUG_INSPECT:
    inspect_raw(PATH_A, f"Document A  →  {PATH_A}")
    inspect_raw(PATH_B, f"Document B  →  {PATH_B}")
    # Scan for tips/hyperlinks/annotations in raw XML — use this to
    # diagnose why tips are not showing up in extraction results.
    inspect_xml_tips(PATH_A)
    inspect_xml_tips(PATH_B)

if DUMP_CUSTOM_XML:
    dump_custom_xml(PATH_A)
    dump_custom_xml(PATH_B)

if DUMP_SDT:
    dump_sdt_elements(PATH_A)
    dump_sdt_elements(PATH_B)

# Pass paths directly — no open() / bytes round-trip needed
doc_a = extractor.extract(PATH_A, strip_review_markup=STRIP_REVIEW_MARKUP)
doc_b = extractor.extract(PATH_B, strip_review_markup=STRIP_REVIEW_MARKUP)

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
