from pathlib import Path

from agentic_bi.rag.chunker import chunk_document
from agentic_bi.rag.loader import load_pdf_pages, load_text_document

SUPPORTED_DOCUMENT_TYPES = {".txt", ".pdf"}


def ingest_document(
    file_path: Path, chunk_size: int = 180, overlap: int = 30
) -> list[dict]:
    """
    Load and chunk a supported document while preserving retrieval metadata.
    """

    suffix = file_path.suffix.lower()

    if suffix not in SUPPORTED_DOCUMENT_TYPES:
        raise ValueError(f"Unsupported document type: {suffix}")

    chunks = []

    # Text documents are treated as a single source unit.
    if suffix == ".txt":
        document = load_text_document(file_path)

        text_chunks = chunk_document(
            text=document["text"],
            source=document["source"],
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for index, chunk in enumerate(text_chunks):
            chunks.append(
                {
                    "chunk_id": f"{file_path.stem}:c{index}",
                    "source": document["source"],
                    "path": document["path"],
                    "page_number": None,
                    "text": chunk["text"],
                    "word_count": chunk["word_count"],
                }
            )

        return chunks

    # PDF content is chunked page by page so page-level citations are retained.
    pages = load_pdf_pages(file_path)

    for page in pages:
        page_chunks = chunk_document(
            text=page["text"],
            source=page["source"],
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for index, chunk in enumerate(page_chunks):
            chunks.append(
                {
                    "chunk_id": (f"{file_path.stem}:p{page['page_number']}:c{index}"),
                    "source": page["source"],
                    "path": page["path"],
                    "page_number": page["page_number"],
                    "text": chunk["text"],
                    "word_count": chunk["word_count"],
                }
            )

    return chunks
