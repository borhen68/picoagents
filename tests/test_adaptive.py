from pathlib import Path

from picoagent.core.adaptive import AdaptiveThreshold


def test_adaptive_threshold_updates_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "threshold.json"
    tuner = AdaptiveThreshold(path=path, initial_threshold=1.5, min_threshold=0.5, max_threshold=2.0, step=0.1)

    start = tuner.current()
    lower = tuner.observe(success=True, top_confidence=0.9)
    assert lower < start

    higher = tuner.observe(success=False, top_confidence=0.8)
    assert higher > lower

    reloaded = AdaptiveThreshold(path=path, initial_threshold=1.0, min_threshold=0.5, max_threshold=2.0, step=0.1)
    assert reloaded.current() == higher
