import time

import numpy as np

from picoagent.core.memory import VectorMemory


def test_recall_prefers_closest_vector() -> None:
    mem = VectorMemory(decay_lambda=0.0)
    mem.store("alpha", np.array([1.0, 0.0], dtype=np.float32))
    mem.store("beta", np.array([0.0, 1.0], dtype=np.float32))

    results = mem.recall(np.array([0.9, 0.1], dtype=np.float32), k=1)
    assert results == ["alpha"]


def test_decay_penalizes_old_entries() -> None:
    mem = VectorMemory(decay_lambda=3.0)
    now = time.time()
    mem.store("old", np.array([1.0, 0.0], dtype=np.float32), created_at=now - 7 * 86400)
    mem.store("new", np.array([0.9, 0.1], dtype=np.float32), created_at=now)

    results = mem.recall(np.array([1.0, 0.0], dtype=np.float32), k=2)
    assert results[0] == "new"


def test_save_and_load_roundtrip(tmp_path) -> None:
    path = tmp_path / "memory.npz"
    mem = VectorMemory(decay_lambda=0.0, persistence_path=path)
    mem.store("hello", np.array([0.1, 0.2, 0.3], dtype=np.float32), metadata={"kind": "note"})
    mem.save()

    loaded = VectorMemory(decay_lambda=0.0, persistence_path=path)
    count = loaded.load()

    assert count == 1
    assert loaded.recall(np.array([0.1, 0.2, 0.3], dtype=np.float32), k=1) == ["hello"]
