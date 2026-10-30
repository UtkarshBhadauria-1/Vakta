from dataclasses import dataclass
from typing import Protocol

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.documents import DocumentChunk


class SentenceTransformerEmbedder:
    """CPU-backed sentence embeddings, normalized for cosine similarity."""

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name, device="cpu")

    def encode_texts(self, texts: list[str]) -> np.ndarray:
        return np.asarray(
            self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True),
            dtype=np.float32,
        )


class TextEmbedder(Protocol):
    def encode_texts(self, texts: list[str]) -> np.ndarray: ...


@dataclass(frozen=True)
class SearchResult:
    chunk: DocumentChunk
    score: float


class Retriever(Protocol):
    chunks: list[DocumentChunk]

    def search(self, query: str, top_k: int = 4) -> list[SearchResult]: ...


class FaissRetriever:
    """An IndexFlatIP FAISS index over L2-normalized document embeddings."""

    def __init__(self, chunks: list[DocumentChunk], embedder: TextEmbedder):
        if not chunks:
            raise ValueError("Cannot build a retrieval index without document chunks")
        self.chunks = chunks
        self.embedder = embedder

        vectors = self._normalize(self.embedder.encode_texts([chunk.text for chunk in chunks]))
        if vectors.ndim != 2 or vectors.shape[0] != len(chunks) or vectors.shape[1] == 0:
            raise ValueError("Embedder returned an invalid document embedding matrix")
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        matrix = np.ascontiguousarray(vectors, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        faiss.normalize_L2(matrix)
        return matrix

    def search(self, query: str, top_k: int = 4) -> list[SearchResult]:
        query = query.strip()
        if not query:
            return []
        vector = self._normalize(self.embedder.encode_texts([query]))
        if vector.shape[1] != self.index.d:
            raise ValueError("Query embedding dimension does not match the FAISS index")
        scores, indices = self.index.search(vector, min(max(1, top_k), len(self.chunks)))
        results: list[SearchResult] = []
        for score, index in zip(scores[0], indices[0], strict=True):
            if index >= 0:
                results.append(SearchResult(chunk=self.chunks[int(index)], score=float(score)))
        return results
