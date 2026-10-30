"""Generate the HCLTech synopsis and Vakta project report from verified outputs.

Run after EDA, backend tests, frontend build, and retrieval evaluation have saved
summaries in backend/outputs. Requires requirements-docs.txt.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[2]
DELIVERABLES = ROOT / "deliverables"
EDA_DIR = ROOT / "backend/outputs/eda"
OUTPUT_DIR = DELIVERABLES
SYNOPSIS_TEMPLATE = ROOT / "Project_Synopsis_Template.docx"
TODAY = date.today().strftime("%d %B %Y")


class EvidenceError(RuntimeError):
    pass


def read_verified_outputs() -> tuple[dict[str, Any], int, int, str, str]:
    summary_path = EDA_DIR / "summary.json"
    test_path = ROOT / "backend/outputs/test-results.txt"
    build_path = ROOT / "backend/outputs/frontend-build-results.txt"
    retrieval_path = ROOT / "backend/outputs/retrieval-evaluation.txt"
    for path in (summary_path, test_path, build_path, retrieval_path):
        if not path.is_file():
            raise EvidenceError(f"Required verified output is missing: {path.relative_to(ROOT)}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    test_text = test_path.read_text(encoding="utf-8")
    build_text = build_path.read_text(encoding="utf-8")
    retrieval_text = retrieval_path.read_text(encoding="utf-8")
    test_match = re.search(r"(\d+) passed", test_text)
    if not test_match:
        raise EvidenceError("The backend test output does not contain a passing-test count")
    if "error" in build_text.casefold() or not re.search(r"built in", build_text, re.IGNORECASE):
        raise EvidenceError("The frontend build output does not show a successful Vite production build")
    retrieval_match = re.search(
        r"Results over (\d+) samples: HitRate@3=([0-9.]+), Recall@3=([0-9.]+)", retrieval_text
    )
    if not retrieval_match:
        raise EvidenceError("The retrieval evaluation output does not contain the expected measured summary")
    retrieval_count = int(retrieval_match.group(1))
    retrieval_hit_rate = retrieval_match.group(2)
    retrieval_recall = retrieval_match.group(3)
    return summary, int(test_match.group(1)), retrieval_count, retrieval_hit_rate, retrieval_recall


def set_cell_shading(cell, fill: str) -> None:
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_text(cell, text: str, bold: bool = False, color: str | None = None) -> None:
    cell.text = text
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(2)
        for run in paragraph.runs:
            run.font.name = "Calibri"
            run.font.size = Pt(8.5)
            run.bold = bold
            if color:
                run.font.color.rgb = RGBColor.from_string(color)


def add_page_field(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    value = OxmlElement("w:t")
    value.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, separate, value, end])


def configure_document(document: Document, title: str, report: bool = False) -> None:
    section = document.sections[0]
    section.top_margin = Inches(0.65 if report else 0.7)
    section.bottom_margin = Inches(0.65 if report else 0.7)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.32)

    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.2 if report else 10.5)
    normal.font.color.rgb = RGBColor(42, 58, 64)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12

    for style_name, size, color in (
        ("Heading 1", 20 if report else 17, "145B62"),
        ("Heading 2", 14, "287F88"),
        ("Heading 3", 11.5, "35545C"),
    ):
        style = document.styles[style_name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(8)
        style.paragraph_format.space_after = Pt(5)
        style.paragraph_format.keep_with_next = True

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.text = title
    for run in header.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(96, 119, 126)

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer.add_run("Vakta | HCLTech Career Shaper Programme • Project 30     Page ")
    add_page_field(footer)
    for run in footer.runs:
        run.font.name = "Calibri"
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(96, 119, 126)

    document.core_properties.title = title
    document.core_properties.author = "Manus AI"
    document.core_properties.subject = "HCLTech Career Shaper Programme, Project 30"
    document.core_properties.keywords = "Vakta, student support, RAG, HCLTech, AIML"


def add_body(document: Document, text: str, *, bold_lead: str | None = None):
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.widow_control = True
    if bold_lead and text.startswith(bold_lead):
        lead = paragraph.add_run(bold_lead)
        lead.bold = True
        paragraph.add_run(text[len(bold_lead):])
    else:
        paragraph.add_run(text)
    return paragraph


def add_bullets(document: Document, items: Iterable[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.add_run(item)


def add_table(document: Document, headers: list[str], rows: list[list[str]], font_size: float = 8.3):
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Light Shading Accent 1"
    table.autofit = True
    for index, label in enumerate(headers):
        set_cell_text(table.rows[0].cells[index], label, bold=True, color="FFFFFF")
        set_cell_shading(table.rows[0].cells[index], "145B62")
    for values in rows:
        cells = table.add_row().cells
        for index, value in enumerate(values):
            set_cell_text(cells[index], value)
            for run in cells[index].paragraphs[0].runs:
                run.font.size = Pt(font_size)
    document.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def add_figure(document: Document, path: Path, caption: str, width: float = 6.4) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    shape = paragraph.add_run().add_picture(str(path), width=Inches(width))
    shape._inline.docPr.set("descr", caption)
    shape._inline.docPr.set("title", caption)
    caption_paragraph = document.add_paragraph()
    caption_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption_paragraph.paragraph_format.space_after = Pt(5)
    run = caption_paragraph.add_run(caption)
    run.italic = True
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(77, 101, 108)


def draw_box(ax, x: float, y: float, width: float, height: float, title: str, detail: str = "", fill: str = "#edf4f4") -> None:
    from matplotlib.patches import FancyBboxPatch

    box = FancyBboxPatch((x, y), width, height, boxstyle="round,pad=0.05,rounding_size=0.12",
                         linewidth=1.25, edgecolor="#287f88", facecolor=fill)
    ax.add_patch(box)
    ax.text(x + width / 2, y + height * 0.62, title, ha="center", va="center", fontsize=10,
            fontweight="bold", color="#143c42", wrap=True)
    if detail:
        ax.text(x + width / 2, y + height * 0.28, detail, ha="center", va="center", fontsize=7.5,
                color="#425c63", wrap=True)


def draw_arrow(ax, start: tuple[float, float], end: tuple[float, float], label: str = "", color: str = "#516c73") -> None:
    ax.annotate("", xy=end, xytext=start, arrowprops={"arrowstyle": "->", "lw": 1.5, "color": color})
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.16, label,
                ha="center", va="bottom", fontsize=7, color="#425c63")


def make_diagrams() -> tuple[Path, Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    assets = DELIVERABLES / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    architecture = assets / "vakta_architecture.png"
    fig, ax = plt.subplots(figsize=(13.5, 7.2))
    ax.set_xlim(0, 13.4)
    ax.set_ylim(0, 8)
    ax.axis("off")
    ax.set_title("Vakta system block diagram", fontsize=17, fontweight="bold", loc="left", color="#143c42", pad=14)

    draw_box(ax, 0.2, 3.7, 1.7, 1.1, "Student", "question / follow-up", "#eef2fb")
    draw_box(ax, 2.35, 3.7, 2.0, 1.1, "React 19 + Vite", "chat, sources, feedback, opt-out", "#e8f4f3")
    draw_box(ax, 4.9, 3.7, 2.1, 1.1, "FastAPI", "Pydantic request validation", "#e4f0f2")
    draw_box(ax, 7.55, 5.8, 2.1, 1.1, "Intent + sentiment", "7 rule-based intents; local lexicon", "#f4f1e8")
    draw_box(ax, 7.55, 3.7, 2.1, 1.1, "Query embedder", "Sentence Transformers", "#e8f4f3")
    draw_box(ax, 10.25, 3.7, 2.2, 1.1, "FAISS search", "cosine-similarity top-k", "#e8f4f3")
    draw_box(ax, 10.25, 1.35, 2.2, 1.1, "Evidence gate", "threshold / no-evidence fallback", "#f4f1e8")
    draw_box(ax, 7.55, 1.35, 2.1, 1.1, "Groq generation", "only with evidence + server key", "#f8ece8")
    draw_box(ax, 4.9, 1.35, 2.1, 1.1, "Answer + sources", "or transparent limitation response", "#e8f4f3")
    draw_box(ax, 7.55, 7.05, 2.1, 0.7, "FAQ / PDF files", "extract → clean → chunk", "#f0f0f6")
    draw_box(ax, 10.25, 7.05, 2.2, 0.7, "Chunk embeddings", "metadata retained in FAISS", "#f0f0f6")
    draw_box(ax, 0.2, 1.35, 3.0, 1.1, "In-memory telemetry", "metadata only; opt-out skips write", "#eef2fb")

    draw_arrow(ax, (1.9, 4.25), (2.35, 4.25))
    draw_arrow(ax, (4.35, 4.25), (4.9, 4.25), "question + opt-out header")
    draw_arrow(ax, (7.0, 4.35), (7.55, 4.25))
    draw_arrow(ax, (7.0, 4.55), (7.55, 6.05), "triage signal")
    draw_arrow(ax, (9.65, 4.25), (10.25, 4.25))
    draw_arrow(ax, (11.35, 3.7), (11.35, 2.45), "retrieved passages")
    draw_arrow(ax, (10.25, 1.9), (9.65, 1.9), "relevant")
    draw_arrow(ax, (7.55, 1.9), (7.0, 1.9))
    draw_arrow(ax, (5.95, 3.7), (5.95, 2.45), "response")
    draw_arrow(ax, (7.55, 7.05), (8.2, 6.9))
    draw_arrow(ax, (9.65, 7.4), (10.25, 7.4))
    draw_arrow(ax, (11.35, 7.05), (11.35, 4.8), "index")
    draw_arrow(ax, (4.9, 3.8), (3.2, 2.45), "opt-in metadata only")
    ax.text(10.1, 0.55, "No ticketing or staff-notification integration is configured; escalation is a local flag only.",
            ha="center", fontsize=8.2, color="#8a4f3e")
    fig.savefig(architecture, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    data_flow = assets / "vakta_data_flow_l0.png"
    fig, ax = plt.subplots(figsize=(13.2, 4.8))
    ax.set_xlim(0, 13.2)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    ax.set_title("Level 0 data-flow diagram", fontsize=17, fontweight="bold", loc="left", color="#143c42", pad=14)
    draw_box(ax, 0.3, 2.6, 1.7, 1.0, "Student", "question", "#eef2fb")
    draw_box(ax, 2.55, 2.6, 2.0, 1.0, "Vakta client", "React UI + local opt-out", "#e8f4f3")
    draw_box(ax, 5.15, 2.6, 2.0, 1.0, "Vakta API", "intent / sentiment / policy", "#e4f0f2")
    draw_box(ax, 7.75, 2.6, 2.0, 1.0, "Knowledge index", "FAISS over FAQ/PDF chunks", "#e8f4f3")
    draw_box(ax, 10.35, 2.6, 2.2, 1.0, "Groq API", "only relevant context + key", "#f8ece8")
    draw_box(ax, 5.15, 0.45, 2.6, 0.9, "Local telemetry", "intent/confidence/flag/rating only", "#eef2fb")
    draw_arrow(ax, (2.0, 3.1), (2.55, 3.1))
    draw_arrow(ax, (4.55, 3.1), (5.15, 3.1), "question + opt-out header")
    draw_arrow(ax, (7.15, 3.1), (7.75, 3.1), "query embedding")
    draw_arrow(ax, (9.75, 3.1), (10.35, 3.1), "retrieved evidence only")
    draw_arrow(ax, (10.35, 2.8), (7.15, 2.8), "answer + citations", color="#287f88")
    draw_arrow(ax, (5.8, 2.6), (6.2, 1.35), "opt-in metadata")
    ax.text(8.9, 1.0, "If evidence is absent, the API responds with a limitation notice and skips Groq.\nOpt-out skips telemetry writes. Human handoff is not connected.",
            ha="center", va="center", fontsize=8.5, color="#425c63")
    fig.savefig(data_flow, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return architecture, data_flow


def fill_synopsis(summary: dict, test_count: int, retrieval_count: int, hit_rate: str, recall: str,
                  architecture: Path, data_flow: Path) -> Path:
    if not SYNOPSIS_TEMPLATE.is_file():
        raise EvidenceError("The supplied HCLTech synopsis template is missing")
    document = Document(str(SYNOPSIS_TEMPLATE))
    configure_document(document, "Vakta | HCLTech Project 30 Synopsis")

    values = {
        "Project Title": "Vakta — AI-Powered Chatbot for University Student Support",
        "Project No.": "30",
        "Domain": "Digital-Data-AI / AIML",
        "Difficulty": "Intermediate",
        "Duration": "4 Weeks",
        "Format": "Individual Project (1 Learner)",
        "Learner Name": "Not supplied in project materials",
        "Roll Number": "Not supplied in project materials",
        "College / Campus": "Not supplied in project materials",
        "Mentor Name": "Not supplied in project materials",
        "Submission Date": "Not supplied in project materials",
    }
    for row in document.tables[0].rows:
        label = row.cells[0].text.strip()
        if label in values:
            set_cell_text(row.cells[1], values[label], bold=(label in {"Project Title", "Project No."}))

    paragraphs = document.paragraphs
    replacements = {
        0: "Vakta — Project Synopsis",
        1: "HCLTech Career Shaper Programme | III Year Industry Project | Academic Year 2025–26",
        5: (
            "University students often need quick answers to repeated questions about admissions, courses, fees, exams, "
            "housing, library services, and grievances. Information may be spread across FAQs and policy documents, while "
            "a helpdesk may not be available at every moment. This project demonstrates a chatbot that classifies support "
            "intent, retrieves relevant university-document excerpts, and generates evidence-grounded answers."
        ),
        6: "2. Proposed Solution & Approach",
        7: (
            "Vakta is a responsive React/Vite chatbot backed by a FastAPI service. A rule-based classifier covers seven "
            "support intents, and a lightweight local lexicon estimates sentiment to guide tone and unresolved-case triage. "
            "The backend chunks FAQs/PDF text, embeds it with Sentence Transformers, searches a FAISS index, and calls "
            "Groq only when evidence clears the configured threshold and the server-side key is available. The answer "
            "includes source references; when evidence is absent, the app states that limitation. Escalation is a local "
            "flag only—no staff ticket or notification integration is connected."
        ),
        8: "3. System Architecture",
        9: "Level 0 data flow and system block diagram (both generated from the implemented project):",
        10: "4. Technology Stack",
        11: (
            "Frontend / UI: React 19, Vite, Tailwind CSS\n"
            "Backend / Logic: Python, FastAPI, Pydantic\n"
            "Database: None; in-memory telemetry only\n"
            "AI/ML Framework: Sentence Transformers, FAISS, Groq API, seven-intent rule classifier, local sentiment lexicon\n"
            "Visualisation: Matplotlib EDA PNG charts\n"
            "Hardware: No special hardware specified; exact workstation/GPU details were not supplied"
        ),
        12: "5. Dataset Used",
        13: (
            "Dataset file name: backend/data/dataset.csv\n"
            "Number of rows: 5,000 (500 supplied + 4,500 synthetic metadata rows)\n"
            "Number of columns: 6 (the supplied schema)\n"
            "Key columns: session_id, intent, confidence_score, escalated, user_rating; additional field: user_query_type\n"
            "Additional data collected: No raw user_query or bot_response fields exist in the supplied CSV; none were fabricated."
        ),
        14: "6. Key Results & Metrics",
        15: (
            f"Metric 1: Dataset validation — {summary['quality']['combined_row_count']:,} rows, "
            f"{summary['quality']['missing_cells']} missing cells, {summary['quality']['duplicate_session_ids']} duplicate IDs; "
            "the first 500 source row values match the preserved source copy.\n"
            f"Metric 2: Retrieval — HitRate@3 {hit_rate}, Recall@3 {recall} across {retrieval_count} hand-labeled sample questions; "
            "small demonstration sample only.\n"
            f"Metric 3: Backend tests — {test_count} tests passed; live Groq generation was not invoked in this verification run.\n"
            "Business value achieved: A tested academic prototype demonstrates FAQ retrieval and transparent answers; it is not a deployed university helpdesk."
        ),
        16: "7. Challenges Faced & How Resolved",
        17: (
            "Challenge 1: The brief lists seven chat-log fields, while the supplied CSV has six and lacks question/answer text. "
            "Resolution: preserve the six-column source and add a field-by-field crosswalk; do not fabricate missing conversations.\n"
            "Challenge 2: Escalation and generated metadata could be mistaken for real staff handoff or real feedback. "
            "Resolution: label escalation as local-only, distinguish 4,500 synthetic rows, and document that ratings are not verified live feedback."
        ),
        18: "8. References",
        19: (
            "1. HCLTech Career Shaper Programme, Project Brief, Project 30 (provided document, 2025–26).\n"
            "2. Lewis et al., ‘Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,’ NeurIPS 2020, https://arxiv.org/abs/2005.11401\n"
            "3. Reimers & Gurevych, ‘Sentence-BERT,’ EMNLP-IJCNLP 2019, https://aclanthology.org/D19-1410/\n"
            "4. Johnson, Douze & Jégou, ‘Billion-scale similarity search with GPUs,’ 2017, https://arxiv.org/abs/1702.08734"
        ),
        20: "9. Ethical Compliance Declaration",
        21: (
            "UNSIGNED DRAFT — the learner must review the source licence and applicable privacy requirements before signing. "
            "No legal-compliance determination is made in this draft.\n"
            "☐ All dataset usage complies with the source licence.\n"
            "☐ No personally identifiable information (PII) is stored without consent.\n"
            "☐ AI tools used for code/writing are disclosed in the report appendix.\n"
            "☐ This project complies with the DPDP Act 2023 where applicable.\n\n"
            "Learner Signature: _________________________    Date: ________________"
        ),
        23: "Prepared 27 October 2026 | HCLTech Career Shaper Programme 2025–26 | Project 30",
    }
    for index, text in replacements.items():
        if index >= len(paragraphs):
            raise EvidenceError(f"Synopsis template paragraph index {index} no longer exists")
        paragraphs[index].text = text

    diagram_paragraph = paragraphs[9]
    diagram_paragraph.add_run().add_break()
    first_shape = diagram_paragraph.add_run().add_picture(str(data_flow), width=Inches(6.0))
    first_shape._inline.docPr.set("descr", "Level 0 flow from student question through React, FastAPI, FAISS, and conditional Groq response.")
    first_shape._inline.docPr.set("title", "Level 0 data flow")
    diagram_paragraph.add_run().add_break()
    second_shape = diagram_paragraph.add_run().add_picture(str(architecture), width=Inches(6.0))
    second_shape._inline.docPr.set("descr", "System block diagram showing classifier, sentiment, embeddings, FAISS, evidence gate, Groq, and opt-out telemetry.")
    second_shape._inline.docPr.set("title", "System block diagram")

    output = OUTPUT_DIR / "Vakta_HCLTech_Project_Synopsis.docx"
    document.save(output)
    return output


def add_contents_page(document: Document) -> None:
    document.add_heading("Contents", level=1)
    for title in (
        "1. Executive summary and objectives",
        "2. Architecture and data flow",
        "3. Technical approach: intent, sentiment, RAG, and escalation",
        "4. Dataset and provenance",
        "5. EDA — data composition and confidence",
        "6. EDA — escalation, ratings, and query types",
        "7. API behavior, testing, security, and privacy",
        "8. Verified results, limitations, and future scope",
        "Appendix A. Ethical declaration and AI assistance disclosure",
        "References",
    ):
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(3)
        paragraph.add_run(title)


def create_report(summary: dict, test_count: int, retrieval_count: int,
                  hit_rate: str, recall: str, architecture: Path) -> Path:
    document = Document()
    configure_document(document, "Vakta | HCLTech Project 30 Report", report=True)

    # Cover page
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(48)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("VAKTA")
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(32)
    run.font.color.rgb = RGBColor(20, 91, 98)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("AI-Powered Chatbot for University Student Support")
    run.bold = True
    run.font.size = Pt(19)
    run.font.color.rgb = RGBColor(36, 67, 75)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("HCLTech Career Shaper Programme · III Year Industry Project · Project 30")
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(69, 101, 107)
    document.add_paragraph()
    add_table(document, ["Project detail", "Verified value"], [
        ["Domain", "Digital-Data-AI / AIML"],
        ["Format / duration", "Individual project · 4 weeks"],
        ["Academic year", "2025–26"],
        ["Learner identity", "Not present in the supplied project files"],
        ["Document prepared", TODAY],
        ["Project state", "Academic prototype; not deployed as an operational university service"],
    ], font_size=9)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(24)
    run = p.add_run("Implementation report with verified dataset, test, build, and retrieval evidence")
    run.italic = True
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(72, 99, 104)
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(52)
    run = p.add_run("Prepared with AI assistance; learner review and ethical declaration signature remain required.")
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(115, 124, 128)

    # Contents page
    document.add_page_break()
    add_contents_page(document)

    # 1. Executive summary
    document.add_page_break()
    document.add_heading("1. Executive summary and objectives", level=1)
    add_body(document,
        "Vakta is a full-stack academic prototype for common university student-support questions. "
        "The React 19 and Vite client connects to a Python FastAPI backend. The backend uses a seven-intent rule-based "
        "classifier and a lightweight local sentiment heuristic. It retrieves FAQ/PDF excerpts using Sentence Transformers "
        "embeddings and a FAISS similarity index, then sends the question and retrieved evidence to Groq only when the "
        "evidence threshold is met and a backend-only key is configured. A response includes source metadata. If evidence "
        "is missing, the prototype reports that limitation instead of asking the language model to guess. This architecture "
        "reflects the general retrieval-plus-generation approach described in RAG research [1].")
    add_body(document,
        "The work responds to the supplied HCLTech brief, which asks for an NLP helpdesk demonstration with intent "
        "classification, FAQ retrieval, sentiment analysis, human escalation, measurable validation, and structured "
        "documentation [4]. The delivered implementation covers the seven support domains and its tests verify the local "
        "API and retrieval plumbing. The verification did not invoke a live Groq request because the previously supplied "
        "credential must be rotated before future use. No real university policy corpus or ticketing connection is configured.")
    document.add_heading("Objectives", level=2)
    add_bullets(document, [
        "Route questions across admissions, schedule, fees, exams, grievance, hostel, and library intents.",
        "Retrieve and cite the most relevant FAQ/PDF chunks; return a limitation response when the evidence gate is not met.",
        "Use a transparent sentiment heuristic only as a tone/triage cue, never as factual evidence.",
        "Honor session-analytics opt-out for both chat and feedback; keep telemetry free of raw questions and answers.",
        "Validate dataset integrity, provide graphical EDA, run automated tests/builds, and document project limits.",
    ])
    document.add_heading("Scope", level=2)
    add_body(document,
        "Vakta is not an authenticated student portal, official policy source, deployed service, or staffed helpdesk. "
        "Local escalation flags do not create a ticket or notify a person. The HCL source dataset lacks raw questions and "
        "bot responses; this report does not manufacture those conversations. Generated rows are metadata simulations only.")

    # 2. Architecture and data flow
    document.add_page_break()
    document.add_heading("2. Architecture and data flow", level=1)
    add_body(document,
        "The browser sends a validated question, a bounded recent-turn context, and—when analytics are disabled—" 
        "the `X-Telemetry-Opt-Out` header to `/api/chat`. FastAPI classifies intent and sentiment, embeds a retrieval "
        "query, and searches a FAISS inner-product index of normalized document vectors. Each indexed passage retains its "
        "document title, relative source, chunk identifier, and optional PDF page. A relevance threshold separates evidence "
        "from unsupported questions. This project uses Sentence-BERT-style semantic sentence representations for matching [2].")
    add_figure(document, architecture, "Figure 1. Implemented Vakta components, evidence gate, and metadata-only telemetry.", width=6.55)
    add_body(document,
        "The RAG generation call occurs only when at least one retrieved item passes the configured threshold and "
        "`GROQ_API_KEY` is available on the server. The model receives the question, retrieved excerpts, recent user "
        "questions for reference resolution, and an optional negative-tone cue. Retrieved text remains the only factual "
        "evidence. FAISS supports nearest-neighbor vector search; the project uses a modest local index rather than "
        "reproducing the scale of the cited research [3].")
    add_body(document,
        "When a user opts out, the frontend suppresses the saved session ID, sends the opt-out header for both chat and "
        "feedback, and the API returns the answer without recording telemetry. An explicit human request, grievance, or "
        "unresolved negative case can be flagged locally. No outbound staff notification is implemented.")

    # 3. Methodology
    document.add_page_break()
    document.add_heading("3. Technical approach: intent, sentiment, RAG, and escalation", level=1)
    document.add_heading("Intent classification", level=2)
    add_body(document,
        "A deterministic rule-based classifier covers admissions, schedule, fees, exams, grievance, hostel, and library. "
        "It assigns an intent, an operational query type, and a heuristic confidence value from matched term weights and "
        "the gap between leading categories. Explicit lexicon rules can be inspected and tested. This design is easy to "
        "explain but it is not a learned model and its confidence is not calibrated. No query text exists in the supplied "
        "HCL CSV, so this project cannot measure intent accuracy, macro-F1, or confusion between categories.")
    document.add_heading("Local sentiment heuristic", level=2)
    add_body(document,
        "The new sentiment module scans a small local positive/negative word list and flips a matched term when one of a "
        "limited set of negators occurs within the previous three tokens. It returns positive, neutral, or negative plus "
        "a bounded heuristic score. A negative signal may add a brief empathetic cue to the Groq prompt. If a sufficiently "
        "confident non-grievance question is negative and retrieval finds no evidence, the response uses an honest local "
        "follow-up flag. Low-confidence intent is clarified first. The lexicon is English-only, misses context, sarcasm, "
        "multilingual phrasing, and many negation constructions, and has no labeled validation set. No sentiment-accuracy "
        "claim is made, and raw text or matched terms are not written to telemetry.")
    document.add_heading("Semantic retrieval and grounded generation", level=2)
    add_body(document,
        "The ingestion path supports the included FAQ JSON and local PDFs. Text is normalized and chunked with source "
        "metadata preserved. Sentence Transformers produces normalized vectors, and FAISS inner-product search returns "
        "the top-k results. The default is top-k 4 and a relevance floor of 0.24. The answer generator is evidence-gated: "
        "the retrieved excerpts, not classifier labels or sentiment, are the factual context. Follow-up user questions can "
        "resolve references but are explicitly excluded as factual evidence. RAG research motivates this architecture, "
        "but it does not guarantee that an individual response is correct [1].")
    document.add_heading("Escalation", level=2)
    add_body(document,
        "Escalation decisions are ordered: explicit human request, grievance intent, low-confidence clarification, "
        "negative sentiment without evidence, then a normal evidence/limitation path. The `escalated` response and telemetry "
        "field indicate only a local workflow flag. Every escalation message now states that this demo cannot create a "
        "ticket or send a message and that no staff member has been notified. A production deployment would require an "
        "authorized handoff integration and clear consent before any ticket is created.")

    # 4. Dataset
    document.add_page_break()
    document.add_heading("4. Dataset, schema, and provenance", level=1)
    add_body(document,
        "The preserved source contains 500 rows. The working `backend/data/dataset.csv` has 5,000 rows: the first 500 "
        "retain the original field values and 4,500 are reproducibly generated metadata rows using seed 42. The separate "
        "`dataset-original-500.csv` remains the baseline. The generation script and EDA both check that the first 500 "
        "combined rows match the preserved source values. Synthetic ratings, confidence scores, and flags are not real "
        "student feedback or observed application outcomes.")
    add_body(document,
        "The official HCLTech project brief describes a seven-field chat log: `session_id`, `user_query`, `intent`, "
        "`confidence_score`, `bot_response`, `escalated`, and `rating` [4]. The supplied CSV instead contains six fields: "
        "`session_id`, `user_query_type`, `intent`, `confidence_score`, `escalated`, and `user_rating`. No raw query or "
        "bot response is present. The project retains the provided six-column dataset and includes a crosswalk; missing "
        "text fields are explicitly marked “not captured,” not fabricated.")
    add_table(document, ["Brief field", "Source mapping", "Status"], [
        ["session_id", "session_id", "Captured; source values preserved"],
        ["user_query", "—", "Not captured; not fabricated"],
        ["intent", "intent", "Captured"],
        ["confidence_score", "confidence_score", "Captured; heuristic, not calibrated"],
        ["bot_response", "—", "Not captured; not fabricated"],
        ["escalated", "escalated", "Captured as numeric 0/1; brief says Y/N"],
        ["rating", "user_rating", "Captured under source name; synthetic rows are simulated"],
        ["Extra source field", "user_query_type", "Preserved; not listed in brief's chat-log line"],
    ], font_size=8.0)
    add_body(document,
        "The completed dictionary describes all six actual fields, their allowed values, data type, nullability, "
        "source/generated status, and interpretation risks. The supplied Kaggle competition files are preserved in "
        "`backend/data/raw/academic_ai_assistant/` but are not ingested by the current FAQ/PDF RAG pipeline.")

    # 5. EDA composition and confidence
    document.add_page_break()
    document.add_heading("5. EDA: intent and confidence distributions", level=1)
    add_body(document,
        "The reproducible EDA script validates the six-column schema, exact row count, unique sequential IDs, numeric "
        "confidence range, allowed categories, missing cells, duplicate rows, and source-prefix equality before plotting. "
        "The combined metadata set contains 5,000 rows. Admissions is the largest category (808 rows, 16.2%); library is "
        "the smallest (569 rows, 11.4%). These are properties of the supplied/synthetic metadata table, not estimates of "
        "real student demand.")
    add_figure(document, EDA_DIR / "01_intent_distribution.png", "Figure 2. Seven-intent distribution over the combined metadata dataset.", width=6.25)
    add_body(document,
        f"Confidence scores range from {summary['confidence']['min']:.3f} to {summary['confidence']['max']:.3f}. "
        f"The mean is {summary['confidence']['mean']:.3f} and median is {summary['confidence']['median']:.3f}. "
        f"The 1.5×IQR rule flags {summary['confidence']['iqr_1_5_outlier_count']} confidence values. This is a statistical "
        "screen, not a semantic anomaly label; the source contains no explicit anomaly field.")
    add_figure(document, EDA_DIR / "02_confidence_distribution.png", "Figure 3. Confidence-score distribution and dataset mean.", width=6.25)

    # 6. EDA escalation and rating
    document.add_page_break()
    document.add_heading("6. EDA: escalation, ratings, and query types", level=1)
    escalated = summary["escalation_counts"].get("1", 0)
    add_body(document,
        f"The dataset contains {escalated:,} escalated flags out of 5,000 records ({escalated / 5000:.1%}). "
        "The generated figure breaks this flag rate down by intent and shows the stored 1–5 rating distribution. "
        "Ratings are dataset values; the synthetic portion is generated, and the file does not prove that these ratings "
        "were submitted through the chatbot. This chart is not an observed staff-handoff success rate.")
    add_figure(document, EDA_DIR / "03_escalation_and_feedback.png", "Figure 4. Escalation flag by intent and stored rating values; ratings are not verified live feedback.", width=6.35)
    add_body(document,
        "The dataset has zero missing cells, duplicate session IDs, and duplicate full rows. IDs run sequentially from "
        "S0001 through S5000. All values are in the documented intent, query-type, escalation, and rating domains. "
        "The confidence field is numeric and within [0, 1]. The synthetic generator contains a 3% internal branch that "
        "can alter an escalation draw, but it does not save an anomaly marker. Consequently the script reports measured "
        "quality checks and Tukey confidence outliers rather than claiming to identify a specific count of injected anomalies.")
    add_figure(document, EDA_DIR / "04_query_type_distribution.png", "Figure 5. Operational query-type distribution over the combined dataset.", width=6.25)

    # 7. API, privacy, and testing
    document.add_page_break()
    document.add_heading("7. API behavior, testing, security, and privacy", level=1)
    document.add_heading("API surface", level=2)
    add_table(document, ["Endpoint", "Purpose", "Behavior"], [
        ["GET /api/health", "Service status", "Retrieval readiness and chunk count; exposes only whether Groq is configured, not the key"],
        ["POST /api/chat", "Question + bounded conversation", "Pydantic validation; answer/sources/context, intent, sentiment, local escalation flag"],
        ["POST /api/feedback", "Rating 1–5", "Updates an in-memory session record when analytics are enabled"],
    ], font_size=8.1)
    add_body(document,
        "The frontend persists only the analytics preference in localStorage. When disabled, it sends the opt-out header "
        "on both chat and feedback. The backend skips creating or mutating a telemetry row for opted-out requests and "
        "returns no new chat session ID. Telemetry contains metadata only and never records raw query/answer text or "
        "sentiment terms. Feedback is range-validated from 1 to 5. Data remains in a small in-memory store and is lost "
        "when the process restarts; no durable database is configured.")
    document.add_heading("Privacy and security boundaries", level=2)
    add_body(document,
        "The app has no student authentication, access control, database retention policy, automatic PII redaction, or "
        "university data agreement. When evidence is available and Groq is configured, the student question and retrieved "
        "passages are sent to the external Groq API. Users should not enter sensitive identifiers or confidential records. "
        "The uploaded archive contained a Groq credential; it was not copied into the project or this report. Treat it as "
        "compromised and revoke/rotate it before enabling live provider calls. Keep any replacement in a server-side secret "
        "or ignored local environment file, never in React or the ZIP.")
    document.add_heading("Automated tests", level=2)
    add_body(document,
        f"The final backend suite passed {test_count} tests. Coverage includes classifier intent rules, document ingestion, "
        "retriever behavior, API schemas, mocked Groq request wiring, escalation wording, feedback validation, the "
        "sentiment heuristic, telemetry opt-out, CORS header allowance, and dataset schema/preservation checks. The "
        "tests do not substitute for user studies, live Groq validation, red-team evaluation, or institutional security review.")

    # 8. Results and limitations
    document.add_page_break()
    document.add_heading("8. Verified results, limitations, and future scope", level=1)
    retrieval_percent = float(hit_rate) * 100
    add_table(document, ["Verification", "Observed result", "Interpretation"], [
        ["Backend tests", f"{test_count} passed", "Automated local suite; not a production certification"],
        ["Frontend build", "Vite production build succeeded", "Compilation only; not evidence of deployment"],
        ["Retrieval evaluation", f"{retrieval_count}/{retrieval_count} expected FAQ IDs in top 3; HitRate@3={hit_rate}; Recall@3={recall}", "Small hand-labeled demonstration set"],
        ["Dataset validation", "5,000 rows; 0 missing cells; 0 duplicate IDs/full rows; original 500 values preserved", "Metadata table includes 4,500 synthetic rows"],
        ["Live Groq call", "Not invoked in this verification run", "Credential rotation and separate provider validation required"],
    ], font_size=8.2)
    add_body(document,
        f"On the eight hand-labeled retrieval samples, HitRate@3 and Recall@3 are both {hit_rate} ({retrieval_percent:.0f}%). "
        "The questions were written around the same small, curated FAQ set, and expected document IDs are manually labeled. "
        "The result should not be generalized to unseen questions, other universities, or answer correctness. There is no "
        "ground-truth question/answer dataset, so no classifier accuracy, sentiment accuracy, answer factuality, latency, "
        "or uptime metric is reported.")
    document.add_heading("Known limitations", level=2)
    add_bullets(document, [
        "The sample FAQ is explicitly illustrative and is not official university policy; real content must be approved and kept current.",
        "The existing dataset has six actual columns even though the project brief describes seven; user_query and bot_response are not captured.",
        "Four thousand five hundred synthetic rows are metadata simulations; results involving their ratings/flags are not real-world behavior.",
        "The small English sentiment lexicon and keyword classifier are not trained or calibrated; multilingual and contextual coverage is unknown.",
        "Local escalation is not a live staff handoff, and the service has no student login or durable records.",
        "Live Groq behavior, model rate limits, provider retention, and production deployment were not verified here.",
    ])
    document.add_heading("Conclusion and future scope", level=2)
    add_body(document,
        "The prototype now demonstrates a connected local chat/API flow, semantic retrieval, evidence-gated generation, "
        "transparent no-evidence responses, simple sentiment-aware handling, and privacy-aware telemetry opt-out. "
        "The next safe steps are to rotate the exposed provider key, obtain institution-approved content and a licensed "
        "complete schema with consented query/response records, evaluate on an independent human-labeled dataset, test "
        "accessibility and PII handling, and only then integrate an authorized ticketing system. A mentor and learner "
        "should complete the ethical declaration before submission.")

    # Appendix and references
    document.add_page_break()
    document.add_heading("Appendix A. Ethical declaration and AI assistance disclosure", level=1)
    add_body(document,
        "The supplied HCLTech brief requires an ethical compliance declaration and calls for an opt-out and clear human "
        "escalation indication [4]. This report is an unsigned draft. The source licence and legal compliance cannot be "
        "certified from the provided files. The learner should verify data permissions and applicable privacy obligations, "
        "then complete and sign the supplied synopsis declaration. The project itself does not establish DPDP Act compliance.")
    add_body(document,
        "AI assistance was used to review and edit source code, analyze project files, and draft this documentation. "
        "The synthetic 4,500-row extension is generated by `backend/scripts/generate_synthetic_dataset.py` with a fixed "
        "seed; no natural-language student queries or chatbot answers were generated. Human review is required before "
        "submission. Learner name, roll number, college/campus, and mentor name were absent from the materials, so the "
        "synopsis identifies them as not supplied rather than inventing them.")
    document.add_heading("References", level=1)
    references = [
        "[1] Patrick Lewis et al. ‘Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.’ NeurIPS 2020. https://arxiv.org/abs/2005.11401",
        "[2] Nils Reimers and Iryna Gurevych. ‘Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.’ EMNLP-IJCNLP 2019, pp. 3982–3992. https://aclanthology.org/D19-1410/",
        "[3] Jeff Johnson, Matthijs Douze, and Hervé Jégou. ‘Billion-scale similarity search with GPUs.’ arXiv:1702.08734, 2017. https://arxiv.org/abs/1702.08734",
        "[4] HCLTech Career Shaper Programme. ‘AI-Powered Chatbot for University Student Support — III Year Industry Project, Project 30, Project Brief.’ User-supplied file, academic year 2025–26.",
    ]
    for reference in references:
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.2)
        paragraph.paragraph_format.first_line_indent = Inches(-0.2)
        paragraph.paragraph_format.space_after = Pt(5)
        paragraph.add_run(reference)

    output = OUTPUT_DIR / "Vakta_HCLTech_Project_Report.docx"
    document.save(output)
    return output


def main() -> None:
    DELIVERABLES.mkdir(parents=True, exist_ok=True)
    summary, test_count, retrieval_count, hit_rate, recall = read_verified_outputs()
    architecture, data_flow = make_diagrams()
    synopsis = fill_synopsis(summary, test_count, retrieval_count, hit_rate, recall, architecture, data_flow)
    report = create_report(summary, test_count, retrieval_count, hit_rate, recall, architecture)
    print(f"Created {synopsis.relative_to(ROOT)}")
    print(f"Created {report.relative_to(ROOT)}")
    print(f"Created {architecture.relative_to(ROOT)}")
    print(f"Created {data_flow.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
