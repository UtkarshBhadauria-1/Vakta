from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    title: str
    text: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    page: int | None = None


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    title: str
    text: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    page: int | None = None


def clean_text(text: str) -> str:
    """Normalize extracted text while retaining readable paragraph boundaries."""
    text = unicodedata.normalize("NFKC", text).replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\t\f\v ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_words: int = 180, overlap_words: int = 30) -> list[str]:
    """Split text on word boundaries with a configurable overlap."""
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("Require max_words > overlap_words >= 0")

    words = clean_text(text).split()
    if not words:
        return []

    step = max_words - overlap_words
    chunks: list[str] = []
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + max_words])
        if chunk:
            chunks.append(chunk)
        if start + max_words >= len(words):
            break
    return chunks


def _infer_intent(category: str, text: str) -> str:
    """Map content keywords to one of the 7 HCL intents."""
    lowered = f"{category} {text}".lower()
    if any(k in lowered for k in ("hostel", "housing", "dorm", "mess")):
        return "hostel"
    if any(k in lowered for k in ("library", "study space", "book")):
        return "library"
    if any(k in lowered for k in ("fee", "tuition", "scholarship", "billing", "accounts office", "payment")):
        return "fees"
    if any(k in lowered for k in ("exam", "marksheet", "revaluation", "grade", "attendance")):
        return "exams"
    if any(k in lowered for k in ("schedule", "calendar", "holiday", "timing", "timetable", "convocation", "date")):
        return "schedule"
    if any(k in lowered for k in ("password", "grievance", "complaint", "wifi", "laptop", "lost", "helpdesk")):
        return "grievance"
    if any(k in lowered for k in ("admission", "course", "register", "advising", "faculty", "transcript", "curriculum", "placement")):
        return "admissions"
    return "admissions"


def _serialize_structured_record(
    record: dict[str, Any], path: Path, data_root: Path, index: int
) -> SourceDocument | None:
    """Serialize a single dictionary record (FAQ or structured entity) into a SourceDocument."""
    record_id = str(record.get("document_id") or record.get("id") or f"{path.stem}-{index}").strip()
    source = path.relative_to(data_root).as_posix()
    stem = path.stem.lower()

    # 1. Standard FAQ format (question + answer/text/body)
    if "question" in record and any(k in record for k in ("answer", "text", "body")):
        question = str(record.get("question", "")).strip()
        answer = str(record.get("answer", record.get("text", record.get("body", "")))).strip()
        body = str(record.get("body", "")).strip()
        content = f"Question: {question}\nAnswer: {answer}" if question and answer else (body or answer or question)
        content = clean_text(content)
        if not content:
            return None
        title = str(record.get("title") or (f"FAQ: {question}" if question else record_id)).strip()
        category = str(record.get("category") or "FAQ").strip()
        metadata = {
            k: v for k, v in record.items() if k not in {"question", "answer", "body", "text", "title"}
        }
        metadata.update({
            "kind": "faq",
            "category": category,
            "intent": _infer_intent(category, content),
        })
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 2. Academic Calendar
    if stem == "academic_calendar" or ("event" in record and "date" in record and "subject" not in record):
        event = str(record.get("event", "")).strip()
        date = str(record.get("date", "")).strip()
        content = clean_text(f"Academic Calendar Event: {event}\nDate: {date}")
        if not content:
            return None
        title = f"Academic Calendar: {event}" if event else f"Academic Calendar: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"event", "date", "title"}}
        metadata.update({"kind": "academic_calendar", "category": "schedule", "intent": "schedule"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 3. Exam Schedule
    if stem == "exam_schedule" or ("subject" in record and ("date" in record or "time" in record)):
        subject = str(record.get("subject", "")).strip()
        date = str(record.get("date", "")).strip()
        time = str(record.get("time", "")).strip()
        lines = [f"Exam Schedule: {subject}"]
        if date:
            lines.append(f"Exam Date: {date}")
        if time:
            lines.append(f"Exam Time: {time}")
        content = clean_text("\n".join(lines))
        if not content:
            return None
        title = f"Exam Schedule: {subject}" if subject else f"Exam Schedule: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"subject", "date", "time", "title"}}
        metadata.update({"kind": "exam_schedule", "category": "exams", "intent": "exams"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 4. Courses
    if stem == "courses" or ("course" in record and any(k in record for k in ("semester", "credits", "faculty"))):
        course = str(record.get("course", "")).strip()
        sem = record.get("semester", "")
        credits = record.get("credits", "")
        fac = str(record.get("faculty", "")).strip()
        lines = [f"Course: {course}"]
        if sem != "":
            lines.append(f"Semester: {sem}")
        if credits != "":
            lines.append(f"Credits: {credits}")
        if fac:
            lines.append(f"Faculty Instructor: {fac}")
        content = clean_text("\n".join(lines))
        if not content:
            return None
        title = f"Course: {course}" if course else f"Course: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"course", "semester", "credits", "faculty", "title"}}
        metadata.update({"kind": "course", "category": "academics", "intent": "admissions"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 5. Faculty
    if stem == "faculty" or ("name" in record and any(k in record for k in ("department", "designation", "subjects", "email"))):
        name = str(record.get("name", "")).strip()
        dept = str(record.get("department", "")).strip()
        desig = str(record.get("designation", "")).strip()
        subjects = record.get("subjects", [])
        subjects_str = ", ".join(subjects) if isinstance(subjects, list) else str(subjects).strip()
        email = str(record.get("email", "")).strip()
        lines = [f"Faculty Member: {name}"]
        if dept:
            lines.append(f"Department: {dept}")
        if desig:
            lines.append(f"Designation: {desig}")
        if subjects_str:
            lines.append(f"Subjects Taught: {subjects_str}")
        if email:
            lines.append(f"Email: {email}")
        content = clean_text("\n".join(lines))
        if not content:
            return None
        title = f"Faculty: {name}" if name else f"Faculty: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"name", "department", "designation", "subjects", "email", "title"}}
        metadata.update({"kind": "faculty", "category": "academics", "intent": "admissions"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 6. Campus Services
    if stem == "campus_services" or ("service" in record and "timing" in record):
        service = str(record.get("service", "")).strip()
        timing = str(record.get("timing", "")).strip()
        content = clean_text(f"Campus Service: {service}\nOperating Hours: {timing}")
        if not content:
            return None
        title = f"Campus Service: {service}" if service else f"Campus Service: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"service", "timing", "title"}}
        metadata.update({
            "kind": "campus_service",
            "category": "campus_services",
            "intent": _infer_intent("campus_services", service),
        })
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 7. Attendance Policy
    if stem == "attendance_policy" or ("policy" in record and "attendance" in stem):
        policy = str(record.get("policy", "")).strip()
        content = clean_text(f"Attendance Policy: {policy}")
        if not content:
            return None
        title = f"Attendance Policy: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"policy", "title"}}
        metadata.update({"kind": "attendance_policy", "category": "academics", "intent": "exams"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 8. Hostel Rules
    if stem == "hostel" or ("rule" in record and "hostel" in stem):
        rule = str(record.get("rule", "")).strip()
        content = clean_text(f"Hostel Rule: {rule}")
        if not content:
            return None
        title = f"Hostel Rule: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"rule", "title"}}
        metadata.update({"kind": "hostel_rule", "category": "hostel", "intent": "hostel"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 9. Placement Policy
    if stem == "placement_policy" or ("rule" in record and "placement" in stem):
        rule = str(record.get("rule", "")).strip()
        content = clean_text(f"Placement Policy: {rule}")
        if not content:
            return None
        title = f"Placement Policy: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"rule", "title"}}
        metadata.update({"kind": "placement_policy", "category": "placement", "intent": "admissions"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 10. Holidays
    if stem == "holidays" or "holiday" in record:
        holiday = str(record.get("holiday", "")).strip()
        content = clean_text(f"University Holiday: {holiday}")
        if not content:
            return None
        title = f"University Holiday: {holiday}" if holiday else f"Holiday: {record_id}"
        metadata = {k: v for k, v in record.items() if k not in {"holiday", "title"}}
        metadata.update({"kind": "holiday", "category": "schedule", "intent": "schedule"})
        return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)

    # 11. Generic structured record fallback
    lines = []
    for k, v in record.items():
        if k in {"id", "document_id", "title"}:
            continue
        v_str = ", ".join(v) if isinstance(v, list) else str(v).strip()
        if v_str:
            lines.append(f"{k.replace('_', ' ').title()}: {v_str}")
    content = clean_text("\n".join(lines))
    if not content:
        return None
    title = str(record.get("title") or f"{path.stem.replace('_', ' ').title()}: {record_id}").strip()
    category = path.stem.replace("_", " ")
    metadata = {k: v for k, v in record.items() if k not in {"title"}}
    metadata.update({
        "kind": path.stem,
        "category": category,
        "intent": _infer_intent(category, content),
    })
    return SourceDocument(document_id=record_id, title=title, text=content, source=source, metadata=metadata)


def _parse_json_documents(path: Path, data_root: Path) -> list[SourceDocument]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload.get("faqs", []) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError(f"FAQ or knowledge base file must contain a list of records: {path}")

    documents: list[SourceDocument] = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            continue
        doc = _serialize_structured_record(record, path, data_root, index)
        if doc is not None:
            documents.append(doc)
    return documents


_faq_documents = _parse_json_documents


def _pdf_documents(path: Path, data_root: Path) -> list[SourceDocument]:
    reader = PdfReader(str(path))
    pdf_metadata = reader.metadata
    title = clean_text(str(getattr(pdf_metadata, "title", "") or "")) or path.stem
    source = path.relative_to(data_root).as_posix()
    documents: list[SourceDocument] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = clean_text(page.extract_text() or "")
        if not text:
            continue
        documents.append(
            SourceDocument(
                document_id=f"{path.stem}-page-{page_number}",
                title=title,
                text=text,
                source=source,
                metadata={"kind": "pdf", "page": page_number},
                page=page_number,
            )
        )
    return documents


def load_documents(data_dir: Path) -> list[SourceDocument]:
    """Load top-level FAQ JSON files, nested raw knowledge base JSON files, and PDFs beneath data_dir."""
    data_dir = data_dir.resolve()
    documents: list[SourceDocument] = []
    seen_paths: set[Path] = set()

    # 1. Top-level JSON files (e.g., sample_faq.json)
    for path in sorted(data_dir.glob("*.json")):
        if path.is_file() and path not in seen_paths:
            seen_paths.add(path)
            try:
                documents.extend(_parse_json_documents(path, data_dir))
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                logger.warning("Could not load FAQ/JSON source %s: %s", path, exc)

    # 2. Raw and nested knowledge base directories (e.g., raw/academic_ai_assistant/knowledge_base)
    for sub in ("raw", "knowledge_base"):
        sub_dir = data_dir / sub
        if sub_dir.exists():
            for path in sorted(sub_dir.rglob("*.json")):
                if path.is_file() and path not in seen_paths:
                    seen_paths.add(path)
                    try:
                        documents.extend(_parse_json_documents(path, data_dir))
                    except (OSError, json.JSONDecodeError, ValueError) as exc:
                        logger.warning("Could not load knowledge-base source %s: %s", path, exc)

    # 3. PDF files beneath data_dir/documents
    pdf_dir = data_dir / "documents"
    if pdf_dir.exists():
        for path in sorted(pdf_dir.rglob("*.pdf")):
            try:
                documents.extend(_pdf_documents(path, data_dir))
            except Exception as exc:  # A corrupt or unsupported PDF should not block other sources.
                logger.warning("Could not extract PDF %s: %s", path, exc)

    return documents


def chunk_documents(
    documents: list[SourceDocument], max_words: int = 180, overlap_words: int = 30
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for document in documents:
        for index, text in enumerate(chunk_text(document.text, max_words, overlap_words), start=1):
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{document.document_id}-chunk-{index}",
                    document_id=document.document_id,
                    title=document.title,
                    text=text,
                    source=document.source,
                    metadata=dict(document.metadata),
                    page=document.page,
                )
            )
    return chunks
