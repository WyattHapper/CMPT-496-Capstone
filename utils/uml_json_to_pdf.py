"""
Generate a professional PDF report from a JSON UML summary file.

Expected input shape:
- path
- summary
- dependencies
- functions
- types
  - name
  - kind
  - description
  - properties
  - methods
  - enum_values
  - inherits_from
  - plantuml
- relationships
- external_relationships
- relationship_plantuml

The script renders PlantUML snippets to PNGs and builds a client-ready PDF
with a title page, an overview section, a relationship diagram, and one
section per type with the type diagram shown above the explanation.

Usage:
    python uml_json_to_pdf.py summary.json
    python uml_json_to_pdf.py summary.json -o report.pdf
    python uml_json_to_pdf.py summary.json --title "ConsoleTable UML Report"
    python uml_json_to_pdf.py summary.json --plantuml-jar /path/to/plantuml.jar

Dependencies:
    pip install reportlab

PlantUML rendering:
- Preferred: `plantuml` command available on PATH
- Fallback: `java -jar /path/to/plantuml.jar`
"""

from __future__ import annotations

import os
import argparse
import html
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ACCENT = colors.HexColor("#2E5BFF")
ACCENT_DARK = colors.HexColor("#183A9E")
ACCENT_SOFT = colors.HexColor("#EAF0FF")
TEXT = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#6B7280")
BORDER = colors.HexColor("#D5DDF0")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a UML JSON summary file into a polished PDF report."
    )
    parser.add_argument("input", help="Path to the JSON summary file.")
    parser.add_argument(
        "-o",
        "--output",
        help="Output PDF path. Defaults to the input file name with .pdf extension.",
    )
    parser.add_argument(
        "--title",
        help="Custom report title. Defaults to '<stem> UML Report'.",
    )
    parser.add_argument(
        "--plantuml-cmd",
        help="PlantUML command to use, e.g. 'plantuml'. Defaults to auto-detection.",
    )
    parser.add_argument(
        "--plantuml-jar",
        help="Path to plantuml.jar. Used if the plantuml command is unavailable.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary generated PlantUML and PNG files for inspection.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def safe_text(value: Any) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    return text if text else "—"


def ensure_start_end_uml(snippet: str) -> str:
    snippet = snippet.strip()
    if not snippet:
        return "@startuml\n@enduml\n"
    if "@startuml" not in snippet:
        snippet = f"@startuml\n{snippet}\n@enduml\n"
    elif "@enduml" not in snippet:
        snippet = f"{snippet}\n@enduml\n"
    return snippet


def get_plantuml_runner(args: argparse.Namespace) -> list[str]:
    if args.plantuml_cmd:
        return [args.plantuml_cmd]

    if shutil.which("plantuml"):
        return ["plantuml"]

    if args.plantuml_jar:
        if not shutil.which("java"):
            raise RuntimeError(
                "Java is not available on PATH, so --plantuml-jar cannot be used."
            )
        return ["java", "-jar", args.plantuml_jar]

    raise RuntimeError(
        "Could not find PlantUML. Install the `plantuml` command or pass "
        "--plantuml-jar /path/to/plantuml.jar."
    )


def render_plantuml(
    snippet: str,
    stem: str,
    temp_dir: Path,
    args: argparse.Namespace,
) -> Optional[Path]:
    snippet = ensure_start_end_uml(snippet)
    if snippet.strip() == "@startuml\n@enduml":
        return None

    puml_path = temp_dir / f"{stem}.puml"
    png_path = temp_dir / f"{stem}.png"
    puml_path.write_text(snippet, encoding="utf-8")

    base_cmd = get_plantuml_runner(args)

    # Try Graphviz-backed rendering first. If Graphviz is unavailable, fall back
    # to PlantUML's smetana renderer for broader portability.
    cmd_candidates = [
        [*base_cmd, "-tpng", str(puml_path)],
        [*base_cmd, "-Playout=smetana", "-tpng", str(puml_path)],
    ]

    last_error: Optional[subprocess.CalledProcessError] = None
    for cmd in cmd_candidates:
        try:
            subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            break
        except subprocess.CalledProcessError as exc:
            last_error = exc
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""

            if (
                "dot executable does not exist" in stderr.lower()
                or "graphviz" in stderr.lower()
            ):
                continue

            raise RuntimeError(
                f"PlantUML failed for {puml_path.name}.\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            ) from exc
    else:
        if last_error is not None:
            stderr = (
                last_error.stderr.decode("utf-8", errors="replace")
                if last_error.stderr
                else ""
            )
            stdout = (
                last_error.stdout.decode("utf-8", errors="replace")
                if last_error.stdout
                else ""
            )
            raise RuntimeError(
                "PlantUML could not render diagrams. Graphviz 'dot' was unavailable "
                "and the fallback renderer also failed.\n"
                f"STDOUT:\n{stdout}\n"
                f"STDERR:\n{stderr}"
            ) from last_error

    if not png_path.exists():
        generated = list(temp_dir.glob(f"{stem}*.png"))
        if generated:
            return generated[0]
        raise RuntimeError(f"PlantUML did not create {png_path.name}.")

    return png_path


def build_styles() -> StyleSheet1:
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            leading=31,
            alignment=TA_CENTER,
            textColor=colors.white,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            alignment=TA_CENTER,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=ACCENT_DARK,
            spaceBefore=8,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubsectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=TEXT,
            spaceBefore=6,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=TEXT,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallMuted",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=MUTED,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CardLabel",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=ACCENT_DARK,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Mono",
            parent=styles["BodyText"],
            fontName="Courier",
            fontSize=8.5,
            leading=10,
            textColor=TEXT,
        )
    )
    return styles


def page_frame(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    width, height = LETTER

    canvas.setFillColor(colors.white)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(
        doc.leftMargin,
        height - 0.55 * inch,
        width - doc.rightMargin,
        height - 0.55 * inch,
    )

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(ACCENT_DARK)
    canvas.drawString(doc.leftMargin, height - 0.42 * inch, "UML Design Report")

    canvas.setFont("Helvetica", 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(width - doc.rightMargin, 0.42 * inch, f"Page {doc.page}")
    canvas.restoreState()


def title_page(canvas, doc) -> None:  # type: ignore[no-untyped-def]
    canvas.saveState()
    width, height = LETTER

    canvas.setFillColor(ACCENT_DARK)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)

    canvas.setFillColor(ACCENT)
    canvas.rect(0, height - 2.2 * inch, width, 0.7 * inch, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 28)
    canvas.drawCentredString(width / 2, height - 3.0 * inch, doc.report_title)

    canvas.setFont("Helvetica", 12)
    canvas.drawCentredString(width / 2, height - 3.45 * inch, doc.report_subtitle)

    canvas.setStrokeColor(colors.white)
    canvas.setLineWidth(1)
    canvas.line(
        1.35 * inch,
        height - 3.8 * inch,
        width - 1.35 * inch,
        height - 3.8 * inch,
    )

    canvas.setFont("Helvetica", 11)
    canvas.drawCentredString(
        width / 2,
        1.1 * inch,
        "Prepared automatically from structured UML summary data",
    )
    canvas.restoreState()


def image_flowable(
    image_path: Optional[Path],
    max_width: float,
    max_height: float,
    styles: StyleSheet1,
) -> Any:
    if image_path is None or not image_path.exists():
        return Paragraph("<i>Diagram unavailable</i>", styles["SmallMuted"])

    reader = ImageReader(str(image_path))
    width, height = reader.getSize()
    scale = min(max_width / width, max_height / height, 1.0)
    return Image(str(image_path), width=width * scale, height=height * scale)


def bullet_list(items: Iterable[str], styles: StyleSheet1) -> list[Paragraph]:
    out: list[Paragraph] = []
    for item in items:
        out.append(Paragraph(f"• {html.escape(item)}", styles["Body"]))
    return out


def build_member_table(title: str, rows: list[list[Any]], styles: StyleSheet1) -> Table:
    header_style = ParagraphStyle(
        name=f"{title}Header",
        parent=styles["Body"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=ACCENT_DARK,
        spaceAfter=0,
    )

    cell_style = ParagraphStyle(
        name=f"{title}Cell",
        parent=styles["Body"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=10.5,
        textColor=TEXT,
        spaceAfter=0,
        wordWrap="CJK",
    )

    # Detect whether this is a 2-column or 3-column table
    col_count = max(len(r) for r in rows)

    if col_count == 2:
        col_widths = [2.1 * inch, 4.9 * inch]
    else:
        col_widths = [1.35 * inch, 1.55 * inch, 4.10 * inch]

    table_data: list[list[Any]] = [
        [Paragraph(html.escape(title), header_style)] + [""] * (col_count - 1)
    ]

    for row in rows:
        padded = list(row[:col_count])
        while len(padded) < col_count:
            padded.append("")

        table_data.append(
            [Paragraph(str(cell), cell_style) for cell in padded]
        )

    tbl = Table(table_data, colWidths=col_widths, hAlign="LEFT")
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT_SOFT),
                ("TEXTCOLOR", (0, 0), (-1, 0), ACCENT_DARK),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("SPAN", (0, 0), (-1, 0)),
                ("GRID", (0, 0), (-1, -1), 0.35, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    return tbl


def format_property(prop: dict[str, Any]) -> list[str]:
    visibility = safe_text(prop.get("visibility"))
    lifecycle = "static" if prop.get("is_static") else "instance"
    description = safe_text(prop.get("description"))

    return [
        html.escape(prop.get("name", "Unnamed")),
        html.escape(f"{visibility} • {lifecycle}"),
        html.escape(description),
    ]


def format_method(method: dict[str, Any]) -> list[str]:
    visibility = safe_text(method.get("visibility"))
    member_kind = "constructor" if method.get("is_constructor") else "method"
    lifecycle = "static" if method.get("is_static") else "instance"
    return_type = safe_text(method.get("return_type"))

    params = method.get("parameters") or []
    param_parts: list[str] = []
    for p in params:
        pname = safe_text(p.get("name"))
        ptype = safe_text(p.get("type"))
        if ptype == "—":
            param_parts.append(pname)
        else:
            param_parts.append(f"{pname}: {ptype}")

    signature = ", ".join(param_parts) if param_parts else "no parameters"

    meta = f"{visibility} • {member_kind} • {lifecycle}"
    if return_type != "—":
        meta += f" • returns {return_type}"

    description = safe_text(method.get("description"))
    detail = (
        f"{html.escape(description)}<br/>"
        f"<font name='Courier'>{html.escape(signature)}</font>"
    )

    return [
        html.escape(method.get("name", "Unnamed")),
        html.escape(meta),
        detail,
    ]


def build_dependency_list(items: list[str], styles: StyleSheet1) -> list[Any]:
    flows: list[Any] = []
    for item in items:
        flows.append(Paragraph(f"• {html.escape(item)}", styles["Body"]))
    return flows


def type_summary_block(
    type_info: dict[str, Any],
    diagram_path: Optional[Path],
    styles: StyleSheet1,
) -> list[Any]:
    left: list[Any] = []

    kind = safe_text(type_info.get("kind"))
    left.append(
        Paragraph(
            f"<b>{html.escape(type_info.get('name', 'Unnamed'))}</b> "
            f"<font color='#6B7280'>({html.escape(kind)})</font>",
            styles["SubsectionTitle"],
        )
    )
    left.append(
        Paragraph(
            html.escape(safe_text(type_info.get("description"))),
            styles["Body"],
        )
    )

    inherits = type_info.get("inherits_from") or []
    if inherits:
        left.append(Paragraph("Base types", styles["CardLabel"]))
        left.extend(bullet_list([str(x) for x in inherits], styles))

    enum_values = type_info.get("enum_values") or []
    if enum_values:
        left.append(Paragraph("Enum values", styles["CardLabel"]))
        left.extend(bullet_list([str(x) for x in enum_values], styles))

    properties = type_info.get("properties") or []
    methods = type_info.get("methods") or []

    if properties:
        left.append(Spacer(1, 0.06 * inch))
        left.append(
            build_member_table(
                "Properties",
                [format_property(p) for p in properties],
                styles,
            )
        )

    if methods:
        left.append(Spacer(1, 0.08 * inch))
        left.append(
            build_member_table(
                "Methods",
                [format_method(m) for m in methods],
                styles,
            )
        )

    member_count = len(properties) + len(methods)

    if member_count >= 12:
        diag_max_width = 6.2 * inch
        diag_max_height = 8.2 * inch
        diag_col_width = 6.4 * inch
    elif member_count >= 6:
        diag_max_width = 5.8 * inch
        diag_max_height = 7.2 * inch
        diag_col_width = 6.0 * inch
    else:
        diag_max_width = 4.8 * inch
        diag_max_height = 6.0 * inch
        diag_col_width = 5.0 * inch

    diagram = image_flowable(
        diagram_path,
        max_width=diag_max_width,
        max_height=diag_max_height,
        styles=styles,
    )
    diagram_card = Table([[diagram]], colWidths=[diag_col_width], hAlign="LEFT")
    diagram_card.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story: list[Any] = [diagram_card, Spacer(1, 0.14 * inch)]
    story.extend(left)
    return story


def build_story(
    data: dict[str, Any],
    image_paths: dict[str, Optional[Path]],
    title: str,
    styles: StyleSheet1,
) -> list[Any]:
    story: list[Any] = []

    # Title page placeholders; drawn in canvas callbacks.
    story.append(Spacer(1, 6.0 * inch))
    story.append(PageBreak())

    story.append(Paragraph("Executive Overview", styles["SectionTitle"]))
    summary = data.get("summary") or "No summary available."
    story.append(Paragraph(html.escape(summary), styles["Body"]))
    story.append(Spacer(1, 0.1 * inch))

    types = data.get("types") or []

    type_kinds = sorted(
        {safe_text(t.get("kind", "unknown")).lower() for t in types}
    )

    type_summary = ", ".join(type_kinds) if type_kinds else "—"

    meta_rows = [
        ["Source file", html.escape(safe_text(data.get("path")))],
        ["Types", html.escape(type_summary)],
        ["Relationships", str(len(data.get("relationships") or []))],
        ["Dependencies", str(len(data.get("dependencies") or []))],
    ]
    story.append(build_member_table("Overview", meta_rows, styles))
    story.append(Spacer(1, 0.14 * inch))

    dependencies = data.get("dependencies") or []
    if dependencies:
        story.append(Paragraph("Dependencies", styles["SubsectionTitle"]))
        story.extend(build_dependency_list(dependencies, styles))
        story.append(Spacer(1, 0.12 * inch))

    story.append(Paragraph("Relationship Diagram", styles["SectionTitle"]))
    rel_img = image_flowable(
        image_paths.get("relationship_plantuml"),
        max_width=6.7 * inch,
        max_height=6.7 * inch,
        styles=styles,
    )
    rel_table = Table([[rel_img]], colWidths=[7.0 * inch], hAlign="LEFT")
    rel_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(rel_table)
    story.append(Spacer(1, 0.16 * inch))

    relationships = data.get("relationships") or []
    if relationships:
        story.append(Paragraph("Included Relationships", styles["SubsectionTitle"]))
        rel_rows = [
            [
                html.escape(safe_text(r.get("source", "?"))),
                html.escape(safe_text(r.get("relationship_type", "?"))),
                html.escape(safe_text(r.get("target", "?"))),
            ]
            for r in relationships
        ]
        story.append(build_member_table("Relationships", rel_rows, styles))
        story.append(Spacer(1, 0.12 * inch))

    story.append(PageBreak())
    story.append(Paragraph("Type Details", styles["SectionTitle"]))

    types = data.get("types") or []
    for idx, type_info in enumerate(types):
        story.extend(type_summary_block(type_info, image_paths.get(f"type_{idx}"), styles))
        story.append(Spacer(1, 0.16 * inch))
        if idx != len(types) - 1:
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.6,
                    color=BORDER,
                    spaceBefore=4,
                    spaceAfter=10,
                )
            )

    return story


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    
    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1
    
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_path.with_suffix(".pdf")
    )

    data = load_json(input_path)
    styles = build_styles()

    source_path_text = safe_text(data.get("path"))
    source_name = (
        Path(source_path_text).name if source_path_text != "—" else input_path.stem
    )
    report_title = args.title or f"{source_name} UML Report"
    report_subtitle = source_path_text

    temp_ctx = tempfile.TemporaryDirectory(prefix="uml_pdf_")
    temp_dir = Path(temp_ctx.name)

    image_paths: dict[str, Optional[Path]] = {}
    try:
        image_paths["relationship_plantuml"] = render_plantuml(
            data.get("relationship_plantuml", ""),
            "relationship_diagram",
            temp_dir,
            args,
        )

        for idx, type_info in enumerate(data.get("types") or []):
            image_paths[f"type_{idx}"] = render_plantuml(
                type_info.get("plantuml", ""),
                f"type_{idx}_{type_info.get('name', 'type')}",
                temp_dir,
                args,
            )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=LETTER,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.8 * inch,
            bottomMargin=0.7 * inch,
            title=report_title,
            author="OpenAI",
        )
        doc.report_title = report_title  # type: ignore[attr-defined]
        doc.report_subtitle = report_subtitle  # type: ignore[attr-defined]

        story = build_story(data, image_paths, report_title, styles)
        doc.build(story, onFirstPage=title_page, onLaterPages=page_frame)

    finally:
        if args.keep_temp:
            print(f"Kept temporary files in: {temp_dir}")
            temp_ctx.cleanup = lambda: None  # type: ignore[assignment]
        else:
            temp_ctx.cleanup()

    print(f"PDF written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())