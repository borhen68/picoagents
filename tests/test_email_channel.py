"""Tests for the email channel."""
from picoagent.channels.email import EmailChannel


def test_email_channel_init_with_allow_from() -> None:
    ch = EmailChannel(
        username="test@example.com",
        password="pass",
        imap_host="imap.example.com",
        smtp_host="smtp.example.com",
        allow_from={"allowed@example.com"},
    )
    assert ch.allow_from == {"allowed@example.com"}


def test_email_channel_init_without_allow_from() -> None:
    ch = EmailChannel(
        username="test@example.com",
        password="pass",
        imap_host="imap.example.com",
        smtp_host="smtp.example.com",
    )
    assert ch.allow_from is None


def test_reply_subject_adds_re_prefix() -> None:
    assert EmailChannel._reply_subject("Hello") == "Re: Hello"


def test_reply_subject_preserves_existing_re() -> None:
    assert EmailChannel._reply_subject("Re: Hello") == "Re: Hello"


def test_reply_subject_empty() -> None:
    assert EmailChannel._reply_subject("") == "Re: picoagent"
