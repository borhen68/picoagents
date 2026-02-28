from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(slots=True)
class MemoryRecord:
    text: str
    embedding: np.ndarray
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorMemory:
    """Cosine-ranked memory with exponential time decay."""

    def __init__(self, decay_lambda: float = 0.05, persistence_path: str | Path | None = None, max_memories: int = 10000) -> None:
        if decay_lambda < 0:
            raise ValueError("decay_lambda must be >= 0")
        if max_memories <= 0:
            raise ValueError("max_memories must be > 0")
        self.decay_lambda = float(decay_lambda)
        self.persistence_path = Path(persistence_path).expanduser() if persistence_path else None
        self.max_memories = int(max_memories)
        self._records: list[MemoryRecord] = []
        self._dimension: int | None = None

    def __len__(self) -> int:
        return len(self._records)

    def store(
        self,
        text: str,
        embedding: np.ndarray,
        *,
        created_at: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        vector = np.asarray(embedding, dtype=np.float32).reshape(-1)
        if vector.size == 0:
            raise ValueError("embedding cannot be empty")
        if self._dimension is None:
            self._dimension = int(vector.shape[0])
        elif vector.shape[0] != self._dimension:
            raise ValueError(f"embedding dimension mismatch: expected {self._dimension}, got {vector.shape[0]}")

        self._records.append(
            MemoryRecord(
                text=text,
                embedding=vector,
                created_at=float(created_at if created_at is not None else time.time()),
                metadata=dict(metadata or {}),
            )
        )
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        """Evict oldest 10% of records when max_memories is exceeded."""
        if len(self._records) <= self.max_memories:
            return
        evict_count = max(1, self.max_memories // 10)
        # Sort by created_at ascending (oldest first), evict the oldest evict_count
        sorted_indices = sorted(range(len(self._records)), key=lambda i: self._records[i].created_at)
        indices_to_remove = set(sorted_indices[:evict_count])
        self._records = [r for i, r in enumerate(self._records) if i not in indices_to_remove]

    def recall(self, query_embedding: np.ndarray, k: int = 5) -> list[str]:
        ranked = self.recall_with_scores(query_embedding, k=k)
        return [item[0] for item in ranked]

    def recall_with_scores(self, query_embedding: np.ndarray, k: int = 5) -> list[tuple[str, float]]:
        if k <= 0 or not self._records:
            return []

        query = np.asarray(query_embedding, dtype=np.float32).reshape(-1)
        if self._dimension is None:
            return []
        if query.shape[0] != self._dimension:
            raise ValueError(f"query embedding dimension mismatch: expected {self._dimension}, got {query.shape[0]}")

        embeddings = np.vstack([r.embedding for r in self._records])
        query_norm = np.linalg.norm(query)
        mem_norms = np.linalg.norm(embeddings, axis=1)

        denom = np.maximum(query_norm * mem_norms, 1e-12)
        cosine = (embeddings @ query) / denom

        now = time.time()
        ages_in_days = np.array([(now - r.created_at) / 86400.0 for r in self._records], dtype=np.float32)
        decay = np.exp(-self.decay_lambda * np.maximum(ages_in_days, 0.0))
        final_scores = cosine * decay

        top_n = min(k, len(self._records))
        indices = np.argsort(final_scores)[-top_n:][::-1]
        return [(self._records[i].text, float(final_scores[i])) for i in indices]

    def save(self, path: str | Path | None = None) -> Path:
        out_path = self._resolve_path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._records:
            np.savez_compressed(
                out_path,
                embeddings=np.empty((0, 0), dtype=np.float32),
                texts=np.array([], dtype=object),
                created_at=np.array([], dtype=np.float64),
                metadata=np.array([], dtype=object),
            )
            return out_path

        embeddings = np.vstack([r.embedding for r in self._records])
        texts = np.array([r.text for r in self._records], dtype=object)
        created_at = np.array([r.created_at for r in self._records], dtype=np.float64)
        metadata = np.array([json.dumps(r.metadata, ensure_ascii=True) for r in self._records], dtype=object)

        np.savez_compressed(
            out_path,
            embeddings=embeddings,
            texts=texts,
            created_at=created_at,
            metadata=metadata,
        )
        return out_path

    def load(self, path: str | Path | None = None) -> int:
        in_path = self._resolve_path(path)
        if not in_path.exists():
            return 0

        with np.load(in_path, allow_pickle=True) as data:
            embeddings = np.asarray(data["embeddings"], dtype=np.float32)
            texts = data["texts"].tolist()
            created_at = np.asarray(data["created_at"], dtype=np.float64).tolist()
            metadata_raw = data["metadata"].tolist()

        self._records.clear()
        self._dimension = None

        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        if embeddings.size == 0:
            return 0

        for i, text in enumerate(texts):
            record = MemoryRecord(
                text=str(text),
                embedding=np.asarray(embeddings[i], dtype=np.float32).reshape(-1),
                created_at=float(created_at[i]),
                metadata=json.loads(str(metadata_raw[i])) if metadata_raw else {},
            )
            self._records.append(record)

        self._dimension = int(self._records[0].embedding.shape[0]) if self._records else None
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()
        self._dimension = None

    def _resolve_path(self, path: str | Path | None) -> Path:
        candidate = Path(path).expanduser() if path is not None else self.persistence_path
        if candidate is None:
            raise ValueError("no persistence path provided")
        return candidate


def cosine_similarity(query: np.ndarray, candidate: np.ndarray) -> float:
    query_v = np.asarray(query, dtype=np.float32).reshape(-1)
    cand_v = np.asarray(candidate, dtype=np.float32).reshape(-1)
    if query_v.shape != cand_v.shape:
        raise ValueError("shape mismatch for cosine similarity")

    denom = max(np.linalg.norm(query_v) * np.linalg.norm(cand_v), 1e-12)
    return float(np.dot(query_v, cand_v) / denom)


def decay_weight(age_days: float, decay_lambda: float) -> float:
    if age_days < 0:
        age_days = 0
    return float(math.exp(-decay_lambda * age_days))
