from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AdaptiveThresholdState:
    threshold_bits: float
    updates: int = 0
    successes: int = 0
    failures: int = 0


class AdaptiveThreshold:
    """Simple online tuner for entropy threshold."""

    def __init__(
        self,
        *,
        path: str | Path,
        initial_threshold: float,
        min_threshold: float = 0.5,
        max_threshold: float = 2.5,
        step: float = 0.05,
    ) -> None:
        self.path = Path(path).expanduser()
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.step = step
        self.state = AdaptiveThresholdState(threshold_bits=initial_threshold)
        self.load()

    def current(self) -> float:
        return float(self.state.threshold_bits)

    def observe(self, *, success: bool, top_confidence: float) -> float:
        self.state.updates += 1
        if success:
            self.state.successes += 1
        else:
            self.state.failures += 1

        if success and top_confidence >= 0.8:
            self.state.threshold_bits -= self.step * 0.5
        elif not success:
            self.state.threshold_bits += self.step
        elif top_confidence < 0.55:
            self.state.threshold_bits += self.step * 0.5

        self.state.threshold_bits = max(self.min_threshold, min(self.max_threshold, self.state.threshold_bits))
        self.save()
        return self.state.threshold_bits

    def load(self) -> AdaptiveThresholdState:
        if not self.path.exists():
            return self.state

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        self.state = AdaptiveThresholdState(
            threshold_bits=float(raw.get("threshold_bits", self.state.threshold_bits)),
            updates=int(raw.get("updates", 0)),
            successes=int(raw.get("successes", 0)),
            failures=int(raw.get("failures", 0)),
        )
        self.state.threshold_bits = max(self.min_threshold, min(self.max_threshold, self.state.threshold_bits))
        return self.state

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "threshold_bits": self.state.threshold_bits,
            "updates": self.state.updates,
            "successes": self.state.successes,
            "failures": self.state.failures,
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return self.path
