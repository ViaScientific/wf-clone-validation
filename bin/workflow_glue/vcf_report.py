#!/usr/bin/env python
"""Generate an aggregated HTML report from VCF files."""
from collections import OrderedDict
import html
import json
import re
from pathlib import Path

from .util import wf_parser  # noqa: ABS101


TABLE_COLUMNS = (
    "Chrom",
    "Position",
    "Reference",
    "Alternate",
    "Quality",
    "Filter",
    "Info",
    "Sample",
)


def load_manifest(path: Path):
    """Load manifest entries describing which VCFs to include."""
    data = json.loads(path.read_text())
    if not isinstance(data, list):  # pragma: no cover - defensive guard
        raise ValueError("Manifest must be a list of entries")
    entries = []
    for item in data:
        alias = item.get("alias", "unknown")
        category = item.get("category", "unknown")
        filename = item.get("filename")
        if not filename:
            continue
        entries.append({
            "alias": alias,
            "category": category,
            "filename": filename,
        })
    return entries


def parse_vcf(path: Path):
    """Parse a VCF file and return variant rows."""
    variants = []
    if not path.exists():
        return variants
    with path.open() as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip().split("\t")
            if len(fields) < 8:  # pragma: no cover - ignore malformed lines
                continue
            chrom, pos, _var_id, ref, alts, qual, filt, info = fields[:8]
            samples = fields[9:]
            sample_data = " | ".join(samples)
            for alt in alts.split(","):
                variants.append({
                    "Chrom": chrom,
                    "Position": pos,
                    "Reference": ref,
                    "Alternate": alt,
                    "Quality": qual,
                    "Filter": filt,
                    "Info": info,
                    "Sample": sample_data,
                })
    return variants


def build_html(entries, output_path: Path):
    """Render the aggregated HTML report."""
    counts = OrderedDict()
    grouped = OrderedDict()

    natural_tokeniser = re.compile(r"(\d+)")

    def sort_key(value):
        """Return a case-insensitive natural sort key for sample aliases."""
        alias, category, _filename = value
        tokens = []
        for part in natural_tokeniser.split(str(alias)):
            if part.isdigit():
                tokens.append(int(part))
            else:
                tokens.append(part.lower())
        return tokens, str(category).lower()

    for entry in entries:
        alias = entry["alias"]
        category = entry["category"]
        filename = Path(entry["filename"])
        key = (alias, category, filename)
        variants = parse_vcf(filename)
        counts[key] = len(variants)
        grouped[key] = variants

    ordered_keys = sorted(grouped.keys(), key=sort_key)

    doc = [
        "<!DOCTYPE html>",
        "<html lang=\"en\">",
        "<head>",
        "<meta charset=\"utf-8\">",
        "<title>Aggregated Variant Summary</title>",
        "<style>body{font-family:Arial,sans-serif;margin:1.5rem;}",
        "h1,h2{color:#1f3c88;} table{border-collapse:collapse;width:100%;margin-bottom:1.5rem;}",
        "th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;} tbody tr:nth-child(even){background:#f7f9fc;}",
        ".summary-table{width:auto;margin-bottom:2rem;} .summary-table th, .summary-table td{padding:0.4rem 0.8rem;}\n</style>",
        "</head>",
        "<body>",
        "<h1>Aggregated Variant Summary</h1>",
    ]

    if not counts:
        doc.append("<p>No VCF files were provided.</p>")
    else:
        doc.append("<h2>Overview</h2>")
        doc.append("<table class=\"summary-table\">")
        doc.append("<thead><tr><th>Sample</th><th>Context</th><th>Variants</th></tr></thead>")
        doc.append("<tbody>")
        for alias, category, filename in ordered_keys:
            count = counts[(alias, category, filename)]
            doc.append(
                "<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                    html.escape(str(alias)),
                    html.escape(str(category)),
                    count,
                )
            )
        doc.append("</tbody></table>")

        for alias, category, filename in ordered_keys:
            variants = grouped[(alias, category, filename)]
            title = f"{alias} — {category}"
            doc.append("<h2>{}</h2>".format(html.escape(title)))
            if not variants:
                doc.append("<p>No variants were recorded in {}.</p>".format(
                    html.escape(filename.name)
                ))
                continue
            doc.append("<table>")
            doc.append("<thead><tr>{}</tr></thead>".format(
                "".join(f"<th>{html.escape(col)}</th>" for col in TABLE_COLUMNS)
            ))
            doc.append("<tbody>")
            for variant in variants:
                row_html = "".join(
                    "<td>{}</td>".format(
                        html.escape(str(variant.get(col, "")))
                    )
                    for col in TABLE_COLUMNS
                )
                doc.append(f"<tr>{row_html}</tr>")
            doc.append("</tbody></table>")

    doc.extend(["</body>", "</html>"])
    output_path.write_text("\n".join(doc))


def main(args):
    """CLI entrypoint."""
    manifest_path = Path(args.manifest)
    entries = load_manifest(manifest_path)
    build_html(entries, Path(args.output))


def argparser():
    """Argument parser factory."""
    parser = wf_parser("vcf_report")
    parser.add_argument(
        "--manifest",
        required=True,
        help="JSON manifest describing the VCF files",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Destination HTML file",
    )
    return parser


if __name__ == "__main__":  # pragma: no cover - CLI entry
    parser = argparser()
    main(parser.parse_args())
