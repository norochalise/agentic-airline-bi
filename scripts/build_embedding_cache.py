from agentic_bi.config import DOCUMENTS_DIR, RAG_CACHE_DIR
from agentic_bi.rag.embeddings import embed_texts, load_embedding_model
from agentic_bi.rag.ingestion import SUPPORTED_DOCUMENT_TYPES, ingest_document
from agentic_bi.rag.storage import save_embedding_cache

OUTPUT_DIR = RAG_CACHE_DIR


def main() -> None:
    chunks = []

    for file_path in sorted(DOCUMENTS_DIR.iterdir()):
        if file_path.suffix.lower() not in SUPPORTED_DOCUMENT_TYPES:
            continue

        chunks.extend(ingest_document(file_path))

    print("Total chunks:", len(chunks))

    model = load_embedding_model()

    texts = [chunk["text"] for chunk in chunks]

    embeddings = embed_texts(model=model, texts=texts)

    save_embedding_cache(embeddings=embeddings, chunks=chunks, output_dir=OUTPUT_DIR)

    print("Embedding shape:", embeddings.shape)
    print("Saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()
