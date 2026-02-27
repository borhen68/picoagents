from pathlib import Path

from picoagent.session import SessionManager, SessionState


def test_session_last_consolidated_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "sessions.json"
    manager = SessionManager(path)

    session = manager.get_or_create("cli")
    for i in range(10):
        session.add_message("user", f"msg{i}")
    session.last_consolidated = 6
    manager.save_session(session)

    loaded = SessionManager(path).get_or_create("cli")
    assert loaded.last_consolidated == 6
    assert len(loaded.messages) == 10


def test_session_last_consolidated_clamped_on_load(tmp_path: Path) -> None:
    path = tmp_path / "sessions.json"
    path.write_text(
        '{"sessions":[{"key":"x","last_consolidated":50,"messages":[{"role":"user","content":"hi","timestamp":0.0}]}]}',
        encoding="utf-8",
    )

    manager = SessionManager(path)
    session = manager.get_or_create("x")
    assert session.last_consolidated == 1


def test_get_history_returns_most_recent() -> None:
    session = SessionState(key="s")
    for i in range(8):
        session.add_message("user", f"msg{i}")

    history = session.get_history(3)
    assert [m["content"] for m in history] == ["msg5", "msg6", "msg7"]
