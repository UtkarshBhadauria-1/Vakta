import numpy as np
import pytest

from app.documents import SourceDocument, chunk_documents, chunk_text, clean_text
from app.retriever import FaissRetriever


class FixedEmbedder:
    """Predictable two-axis test vectors; production uses Sentence Transformers."""

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        vectors = []
        for text in texts:
            lowered = text.lower()
            axis = 0 if any(word in lowered for word in ("scholarship", "financial aid")) else 1
            vector = [0.0, 0.0]
            vector[axis] = 1.0
            vectors.append(vector)
        return np.asarray(vectors, dtype=np.float32)


def test_clean_and_overlapping_chunks() -> None:
    assert clean_text("  hello\r\n\tworld  ") == "hello\nworld"
    text = " ".join(f"word{i}" for i in range(12))
    chunks = chunk_text(text, max_words=5, overlap_words=2)
    assert len(chunks) == 4
    assert chunks[0].split()[-2:] == chunks[1].split()[:2]
    with pytest.raises(ValueError):
        chunk_text(text, max_words=3, overlap_words=3)


def test_document_chunking_keeps_title_source_and_metadata() -> None:
    document = SourceDocument(
        document_id="aid-faq",
        title="Scholarship applications",
        text="Scholarship applications use the student portal.",
        source="sample_faq.json",
        metadata={"category": "Finances"},
    )
    [chunk] = chunk_documents([document])
    assert chunk.title == "Scholarship applications"
    assert chunk.source == "sample_faq.json"
    assert chunk.metadata["category"] == "Finances"


def test_faiss_returns_most_similar_chunk_first() -> None:
    chunks = [
        SourceDocument("aid", "Scholarships", "Scholarship financial aid awards.", "faq.json"),
        SourceDocument("library", "Library", "Library opening hours and study spaces.", "faq.json"),
    ]
    chunk_records = chunk_documents(chunks)
    retriever = FaissRetriever(chunk_records, FixedEmbedder())
    result = retriever.search("What are scholarship application deadlines?", top_k=2)
    assert result[0].chunk.document_id == "aid"
    assert result[0].score == pytest.approx(1.0)
    assert result[1].chunk.document_id == "library"


def test_empty_or_invalid_retrieval_inputs() -> None:
    with pytest.raises(ValueError):
        FaissRetriever([], FixedEmbedder())
    retriever = FaissRetriever(
        chunk_documents([SourceDocument("x", "Title", "a short document", "source.json")]),
        FixedEmbedder(),
    )
    assert retriever.search("  ") == []


def test_pdf_ingestion_preserves_title_source_and_page(tmp_path, monkeypatch) -> None:
    from app import documents as document_module

    data_dir = tmp_path / "data"
    pdf_dir = data_dir / "documents"
    pdf_dir.mkdir(parents=True)
    pdf_path = pdf_dir / "student-handbook.pdf"
    pdf_path.write_bytes(b"test fixture")

    class FakePage:
        def extract_text(self) -> str:
            return "  Campus   handbook information.  "

    class FakeMetadata:
        title = "Campus Handbook"

    class FakeReader:
        metadata = FakeMetadata()
        pages = [FakePage()]

    monkeypatch.setattr(document_module, "PdfReader", lambda _path: FakeReader())
    [document] = document_module.load_documents(data_dir)
    assert document.title == "Campus Handbook"
    assert document.source == "documents/student-handbook.pdf"
    assert document.page == 1
    assert document.text == "Campus handbook information."
    [chunk] = document_module.chunk_documents([document])
    assert chunk.metadata["kind"] == "pdf"
    assert chunk.metadata["page"] == 1


def test_load_documents_ingests_all_structured_and_faq_records() -> None:
    from pathlib import Path
    from app.documents import load_documents, chunk_documents

    data_dir = Path(__file__).resolve().parents[1] / "data"
    documents = load_documents(data_dir)
    assert len(documents) == 198

    # Verify key document IDs from both sample FAQ and raw knowledge base
    doc_ids = {doc.document_id for doc in documents}
    assert "faq-registration" in doc_ids
    assert "AC001" in doc_ids
    assert "C001" in doc_ids
    assert "F001" in doc_ids
    assert "E001" in doc_ids
    assert "Q001" in doc_ids
    assert "S001" in doc_ids
    assert "HS001" in doc_ids
    assert "H001" in doc_ids
    assert "A001" in doc_ids
    assert "P001" in doc_ids

    # Verify all seven observed intents are represented
    intents = {doc.metadata.get("intent") for doc in documents}
    assert intents == {"admissions", "schedule", "fees", "exams", "grievance", "hostel", "library"}

    # Verify chunking preserves document count and creates valid chunks
    chunks = chunk_documents(documents)
    assert len(chunks) >= 198
    for chunk in chunks:
        assert chunk.chunk_id
        assert chunk.document_id
        assert chunk.title
        assert chunk.text
        assert chunk.source


def test_structured_record_serialization_and_metadata(tmp_path) -> None:
    import json
    from app.documents import load_documents

    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw" / "test_kb"
    raw_dir.mkdir(parents=True)

    test_calendar = [{"document_id": "AC099", "event": "Final Hackathon", "date": "15 Dec"}]
    (raw_dir / "academic_calendar.json").write_text(json.dumps(test_calendar), encoding="utf-8")

    test_faculty = [{
        "document_id": "F099",
        "name": "Dr. Turing",
        "department": "Computer Science",
        "designation": "Professor",
        "subjects": ["Theory of Computation"],
        "email": "turing@college.edu",
    }]
    (raw_dir / "faculty.json").write_text(json.dumps(test_faculty), encoding="utf-8")

    test_hostel = [{"document_id": "HS099", "rule": "Quiet hours begin at 10 PM"}]
    (raw_dir / "hostel.json").write_text(json.dumps(test_hostel), encoding="utf-8")

    docs = load_documents(data_dir)
    assert len(docs) == 3

    by_id = {doc.document_id: doc for doc in docs}

    cal_doc = by_id["AC099"]
    assert "Final Hackathon" in cal_doc.text
    assert "15 Dec" in cal_doc.text
    assert cal_doc.metadata["kind"] == "academic_calendar"
    assert cal_doc.metadata["intent"] == "schedule"
    assert cal_doc.metadata["category"] == "schedule"

    fac_doc = by_id["F099"]
    assert "Dr. Turing" in fac_doc.text
    assert "Theory of Computation" in fac_doc.text
    assert "turing@college.edu" in fac_doc.text
    assert fac_doc.metadata["kind"] == "faculty"
    assert fac_doc.metadata["intent"] == "admissions"

    hostel_doc = by_id["HS099"]
    assert "Quiet hours begin at 10 PM" in hostel_doc.text
    assert hostel_doc.metadata["kind"] == "hostel_rule"
    assert hostel_doc.metadata["intent"] == "hostel"


def test_empty_malformed_and_non_dict_records_handled_safely(tmp_path) -> None:
    import json
    from app.documents import load_documents

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    # Empty list
    (data_dir / "empty.json").write_text("[]", encoding="utf-8")

    # Non-dict and blank records
    mixed_content = [
        "not a dict",
        123,
        {},
        {"document_id": "blank", "text": "   "},
        {"document_id": "valid-1", "question": "Where is the lab?", "answer": "Room 101"},
    ]
    (data_dir / "mixed.json").write_text(json.dumps(mixed_content), encoding="utf-8")

    # Corrupt JSON file
    (data_dir / "corrupt.json").write_text("{invalid json", encoding="utf-8")

    docs = load_documents(data_dir)
    # Only the 1 valid record should be loaded
    assert len(docs) == 1
    assert docs[0].document_id == "valid-1"
    assert "Where is the lab?" in docs[0].text


def test_retrieval_compatibility_with_structured_records() -> None:
    from app.documents import SourceDocument, chunk_documents

    docs = [
        SourceDocument("C001", "Course: AI", "Course: Artificial Intelligence\nFaculty: Dr. Faculty 1", "courses.json", {"intent": "admissions"}),
        SourceDocument("HS001", "Hostel Rule", "Hostel Rule: Gate closes at 10 PM", "hostel.json", {"intent": "hostel"}),
    ]
    chunks = chunk_documents(docs)

    class DomainEmbedder:
        def encode_texts(self, texts: list[str]) -> np.ndarray:
            vectors = []
            for t in texts:
                low = t.lower()
                if "course" in low or "ai" in low or "artificial" in low:
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return np.asarray(vectors, dtype=np.float32)

    retriever = FaissRetriever(chunks, DomainEmbedder())
    results = retriever.search("Tell me about the Artificial Intelligence course", top_k=2)
    assert len(results) == 2
    assert results[0].chunk.document_id == "C001"
    assert results[0].score == pytest.approx(1.0)
