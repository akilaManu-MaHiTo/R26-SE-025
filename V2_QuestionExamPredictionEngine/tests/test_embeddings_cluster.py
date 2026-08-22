import numpy as np
import pytest

from app.embeddings.cluster import dominant_topics, hierarchical_clusters


def test_cluster_separates_well_spaced_vectors():
    vectors = np.array(
        [
            [0.0, 0.0],
            [0.1, 0.0],
            [5.0, 5.0],
            [5.1, 5.0],
        ]
    )
    labels = hierarchical_clusters(vectors, distance_threshold=1.0)
    assert len(set(labels)) == 2


def test_single_vector_gets_single_cluster():
    vectors = np.array([[0.0, 0.0]])
    assert hierarchical_clusters(vectors, distance_threshold=1.0) == [0]


def test_dominant_topics():
    labels = [0, 0, 1, 1]
    topics = ["SQL", "SQL", "JDBC", "JDBC"]
    assert dominant_topics(labels, topics) == {0: "SQL", 1: "JDBC"}


def test_embedding_unavailable_raises_without_model(monkeypatch):
    from app.embeddings.embedder import EmbeddingUnavailable, Embedder

    class NoModel:
        def __init__(self, *a, **k):
            raise ImportError("no torch")

    monkeypatch.setattr("app.embeddings.embedder.SentenceTransformer", NoModel)
    embedder = Embedder()
    assert embedder.is_available() is False
    with pytest.raises(EmbeddingUnavailable):
        embedder.embed("hello")