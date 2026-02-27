from picoagent.channels.discord_ import DiscordChannel, _extract_retry_after, _split_message


def test_extract_inbound_skips_bot_and_orders() -> None:
    messages = [
        {"id": "1002", "content": "second", "author": {"id": "u2", "bot": False}},
        {"id": "1001", "content": "first", "author": {"id": "u1", "bot": False}},
        {"id": "1003", "content": "", "author": {"id": "u3", "bot": False}},
        {"id": "1004", "content": "bot", "author": {"id": "bot1", "bot": True}},
    ]

    inbound, last_id = DiscordChannel._extract_inbound(messages, after_id="1000", bot_user_id="bot1")

    assert [msg.message_id for msg in inbound] == ["1001", "1002"]
    assert [msg.content for msg in inbound] == ["first", "second"]
    assert last_id == "1004"


def test_extract_retry_after_from_rate_limit_payload() -> None:
    raw = '{"message":"You are being rate limited.","retry_after":1.75,"global":false}'
    assert _extract_retry_after(raw) == 1.75


def test_split_message_preserves_order() -> None:
    text = "alpha beta gamma delta"
    chunks = _split_message(text, max_len=10)
    assert chunks == ["alpha beta", "gamma", "delta"]
