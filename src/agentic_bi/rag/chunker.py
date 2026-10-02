def chunk_document(
    text: str, source: str, chunk_size: int = 180, overlap: int = 30
) -> list[dict]:
    """
    Split document text into overlapping word-based chunks.

    Each chunk preserves source and position metadata for later
    retrieval, citation, and evaluation.
    """

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    words = text.split()

    chunks = []

    start = 0
    chunk_id = 0

    while start < len(words):
        end = start + chunk_size

        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        chunks.append(
            {
                "chunk_id": chunk_id,
                "source": source,
                "text": chunk_text,
                "word_count": len(chunk_words),
            }
        )

        chunk_id += 1

        start += chunk_size - overlap

    return chunks
