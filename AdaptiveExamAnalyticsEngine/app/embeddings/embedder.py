import numpy as np

from app.config import settings


class EmbeddingUnavailable(Exception):
    pass


SentenceTransformer = None


def _get_sentence_transformer():
    cls = globals().get("SentenceTransformer")
    if cls is not None:
        return cls
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingUnavailable(
            "sentence-transformers not installed; install requirements-embeddings.txt"
        ) from exc
    globals()["SentenceTransformer"] = SentenceTransformer
    return SentenceTransformer


class Embedder:
    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or settings.embedding_model
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        cls = _get_sentence_transformer()
        try:
            self._model = cls(self._model_name)
        except Exception as exc:
            raise EmbeddingUnavailable(f"failed to load embedding model: {exc}") from exc

    def is_available(self) -> bool:
        if self._model is None and not settings.embedding_available:
            return False
        try:
            self._load()
            return True
        except EmbeddingUnavailable:
            return False

    def embed(self, text: str) -> np.ndarray:
        self._load()
        return self._model.encode([text])[0]

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        self._load()
        return self._model.encode(texts)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        a = np.asarray(a, dtype=float).flatten()
        b = np.asarray(b, dtype=float).flatten()
        denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
        return float(np.dot(a, b) / denom)