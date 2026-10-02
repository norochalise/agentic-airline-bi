import pytest

from agentic_bi.rag.chunker import chunk_document
from agentic_bi.rag.ingestion import ingest_document


def words(count, start=0):
    return " ".join(f"w{i}" for i in range(start, start + count))


def test_chunks_overlap_by_the_requested_number_of_words():
    chunks = chunk_document(words(25), source="doc.txt", chunk_size=10, overlap=3)

    # Each chunk starts 7 words after the previous one.
    assert [c["text"].split()[0] for c in chunks] == ["w0", "w7", "w14", "w21"]
    assert chunks[0]["text"].split()[-3:] == chunks[1]["text"].split()[:3]
    assert [c["word_count"] for c in chunks] == [10, 10, 10, 4]
    assert all(c["source"] == "doc.txt" for c in chunks)


def test_empty_text_gives_no_chunks():
    assert chunk_document("   ", source="doc.txt") == []


@pytest.mark.parametrize(
    ("chunk_size", "overlap"), [(0, 0), (10, -1), (10, 10)], ids=str
)
def test_invalid_chunk_settings_are_rejected(chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_document(
            "some text", source="doc.txt", chunk_size=chunk_size, overlap=overlap
        )


def test_text_document_ingestion_keeps_citation_metadata(tmp_path):
    path = tmp_path / "service_plan.txt"
    path.write_text(words(25), encoding="utf-8")

    chunks = ingest_document(path, chunk_size=10, overlap=3)

    assert [c["chunk_id"] for c in chunks] == [
        "service_plan:c0",
        "service_plan:c1",
        "service_plan:c2",
        "service_plan:c3",
    ]
    assert chunks[0]["source"] == "service_plan.txt"
    assert chunks[0]["page_number"] is None


def test_pdf_ingestion_chunks_page_by_page(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")

    path = tmp_path / "contract.pdf"
    with pymupdf.open() as pdf:
        for text in ("Refunds are issued.", "", "Bags are covered."):
            page = pdf.new_page()
            if text:
                page.insert_text((72, 72), text)
        pdf.save(path)

    chunks = ingest_document(path)

    # The blank page is skipped; page numbers stay 1-based and real.
    assert [c["chunk_id"] for c in chunks] == ["contract:p1:c0", "contract:p3:c0"]
    assert [c["page_number"] for c in chunks] == [1, 3]
    assert "Refunds" in chunks[0]["text"]


def test_unsupported_document_type_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        ingest_document(tmp_path / "notes.docx")
