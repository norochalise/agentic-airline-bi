from pathlib import Path

import pymupdf

from agentic_bi.config import project_relative


def load_text_document(file_path: Path) -> dict:
    """
    Load a text document and return its content with source metadata.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    if file_path.suffix.lower() != ".txt":
        raise ValueError(f"Unsupported document type: {file_path.suffix}")

    text = file_path.read_text(encoding="utf-8")

    return {"source": file_path.name, "path": project_relative(file_path), "text": text}


def load_pdf_pages(file_path: Path) -> list[dict]:
    """
    Extract text from a PDF while preserving page-level metadata.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(f"Unsupported document type: {file_path.suffix}")

    pages = []

    with pymupdf.open(file_path) as pdf:
        for page_index, page in enumerate(pdf):
            text = page.get_text("text").strip()

            if not text:
                continue

            pages.append(
                {
                    "source": file_path.name,
                    "path": project_relative(file_path),
                    "page_number": page_index + 1,
                    "text": text,
                }
            )

    return pages
