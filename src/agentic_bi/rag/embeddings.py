from sentence_transformers import SentenceTransformer

from agentic_bi.config import EMBEDDING_MODEL

DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODEL


def load_embedding_model(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> SentenceTransformer:
    """
    Load the local embedding model used for semantic retrieval.
    """

    return SentenceTransformer(model_name)


def embed_texts(model: SentenceTransformer, texts: list[str]):
    """
    Convert a collection of texts into dense vector representations.
    """

    return model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
