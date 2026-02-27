from picoagent.core.scheduler import EntropyScheduler


def test_select_low_entropy_returns_best_tool() -> None:
    scheduler = EntropyScheduler(threshold_bits=1.0)
    selected = scheduler.select({"shell": 4.0, "search": 1.0, "file": 0.5})
    assert selected == "shell"


def test_select_high_entropy_requests_clarification() -> None:
    scheduler = EntropyScheduler(threshold_bits=1.0)
    selected = scheduler.select({"shell": 1.0, "search": 1.0, "file": 1.0})
    assert selected is None


def test_empty_scores_clarifies() -> None:
    scheduler = EntropyScheduler()
    decision = scheduler.decide({})
    assert decision.should_clarify is True
    assert decision.tool_name is None
