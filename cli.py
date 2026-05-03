"""
AuditCheckr CLI

Usage examples:

  # Compare two local files, output HTML + JSON reports
  python cli.py \\
      --provider-a local --path-a ./docs/contract_v1.docx \\
      --provider-b local --path-b ./docs/contract_v2.docx \\
      --reporter html json \\
      --output ./reports/

  # Compare scanning a directory (first .docx found in each)
  python cli.py \\
      --provider-a local --path-a ./source_a/ \\
      --provider-b local --path-b ./source_b/ \\
      --reporter html
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

from auditcheckr import extractor, differ
from auditcheckr.providers import get_provider
from auditcheckr.reporters import get_reporter


@click.command()
@click.option("--provider-a", default="local", show_default=True,
              help="Provider type for Document A (local | sharepoint | s3).")
@click.option("--path-a", required=True,
              help="Path or identifier for Document A.")
@click.option("--provider-b", default="local", show_default=True,
              help="Provider type for Document B (local | sharepoint | s3).")
@click.option("--path-b", required=True,
              help="Path or identifier for Document B.")
@click.option("--reporter", "-r", multiple=True, default=["html", "json"],
              show_default=True,
              help="Reporter(s) to use. Can pass multiple: -r html -r json")
@click.option("--output", "-o", default="./reports", show_default=True,
              help="Output directory for reports.")
def main(provider_a, path_a, provider_b, path_b, reporter, output):
    """AuditCheckr — Legal document diff tool."""

    click.echo(f"\n{'─'*55}")
    click.echo(f"  ⚖️  AuditCheckr")
    click.echo(f"{'─'*55}")

    # ── Fetch documents ───────────────────────────────────────────────────
    click.echo(f"\n  📄 Fetching Document A  [{provider_a}]  {path_a}")
    prov_a = get_provider(provider_a, path=path_a)
    docs_a = prov_a.list_documents()
    if not docs_a:
        click.secho("  ✗ No documents found for source A.", fg="red")
        sys.exit(1)
    bytes_a = prov_a.fetch_document(docs_a[0])

    click.echo(f"  📄 Fetching Document B  [{provider_b}]  {path_b}")
    prov_b = get_provider(provider_b, path=path_b)
    docs_b = prov_b.list_documents()
    if not docs_b:
        click.secho("  ✗ No documents found for source B.", fg="red")
        sys.exit(1)
    bytes_b = prov_b.fetch_document(docs_b[0])

    # ── Extract ───────────────────────────────────────────────────────────
    click.echo("\n  🔍 Extracting content & annotations …")
    doc_a = extractor.extract(bytes_a, source_id=docs_a[0])
    doc_b = extractor.extract(bytes_b, source_id=docs_b[0])

    click.echo(f"     A: {len(doc_a.blocks)} blocks  |  "
               f"B: {len(doc_b.blocks)} blocks")

    # ── Diff ──────────────────────────────────────────────────────────────
    click.echo("\n  ⚙️  Running diff …")
    result = differ.diff(doc_a, doc_b)

    if result.has_differences:
        click.secho(f"  ⚠  {result.total_changes} difference(s) found.", fg="yellow")
    else:
        click.secho("  ✓  Documents are identical.", fg="green")

    # ── Report ────────────────────────────────────────────────────────────
    click.echo(f"\n  📊 Writing reports to: {output}")
    for rep_name in reporter:
        rep = get_reporter(rep_name)
        out_path = rep.report(result, output)
        click.secho(f"     [{rep_name}] → {out_path}", fg="cyan")

    click.echo(f"\n{'─'*55}\n")


if __name__ == "__main__":
    main()
