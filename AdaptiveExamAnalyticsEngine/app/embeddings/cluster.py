import numpy as np


def hierarchical_clusters(vectors: np.ndarray, distance_threshold: float) -> list[int]:
    vectors = np.asarray(vectors, dtype=float)
    if vectors.shape[0] <= 1:
        return [0] * vectors.shape[0]
    from sklearn.cluster import AgglomerativeClustering

    model = AgglomerativeClustering(
        n_clusters=None,
        metric="euclidean",
        linkage="ward",
        distance_threshold=distance_threshold,
    )
    labels = model.fit_predict(vectors)
    return [int(x) for x in labels]


def dominant_topics(labels: list[int], topics: list[str]) -> dict[int, str]:
    result: dict[int, str] = {}
    for label in set(labels):
        topic_counts: dict[str, int] = {}
        for t, l in zip(topics, labels):
            if l == label:
                topic_counts[t] = topic_counts.get(t, 0) + 1
        result[label] = max(topic_counts, key=topic_counts.get)
    return result
