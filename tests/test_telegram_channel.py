from picoagent.channels.telegram import TelegramChannel, _split_message


def test_extract_inbound_filters_and_advances_offset() -> None:
    updates = [
        {
            "update_id": 10,
            "message": {
                "message_id": 1,
                "chat": {"id": 111},
                "from": {"is_bot": True},
                "text": "skip bot",
            },
        },
        {
            "update_id": 11,
            "message": {
                "message_id": 2,
                "chat": {"id": 222},
                "from": {"is_bot": False},
                "text": "hello",
            },
        },
        {
            "update_id": 12,
            "message": {
                "message_id": 3,
                "chat": {"id": 333},
                "from": {"is_bot": False},
                "caption": "from caption",
            },
        },
    ]

    inbound, offset = TelegramChannel._extract_inbound(updates, current_offset=9)

    assert offset == 13
    assert [msg.chat_id for msg in inbound] == ["222", "333"]
    assert [msg.text for msg in inbound] == ["hello", "from caption"]


def test_split_message_prefers_line_breaks() -> None:
    text = "line-1\nline-2\nline-3"
    chunks = _split_message(text, max_len=8)
    assert chunks == ["line-1", "line-2", "line-3"]
