"""Tests for the shared split_message utility."""
from picoagent.channels.utils import split_message


def test_short_message_returns_single_chunk() -> None:
    assert split_message("hello", max_len=100) == ["hello"]


def test_empty_message() -> None:
    assert split_message("", max_len=100) == [""]


def test_splits_on_space_boundary() -> None:
    text = "alpha beta gamma delta"
    chunks = split_message(text, max_len=10)
    assert chunks == ["alpha beta", "gamma", "delta"]


def test_splits_on_newline_boundary() -> None:
    text = "line one\nline two\nline three"
    chunks = split_message(text, max_len=15)
    assert chunks[0] == "line one"
    assert "line two" in chunks[1]


def test_hard_cut_when_no_boundary() -> None:
    text = "abcdefghijklmnop"
    chunks = split_message(text, max_len=5)
    assert chunks[0] == "abcde"
    assert "".join(chunks) == text
