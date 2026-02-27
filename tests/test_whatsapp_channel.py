import json
from pathlib import Path

from picoagent.channels.whatsapp import WhatsAppChannel


def test_whatsapp_reads_jsonl_from_cursor(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text(
        "\n".join(
            [
                json.dumps({"from": "111", "text": "hello"}),
                json.dumps({"from": "222", "body": "need help"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    channel = WhatsAppChannel(access_token=None, phone_number_id=None, inbox_path=inbox)
    messages, cursor = channel._read_new_messages(0)

    assert cursor == 2
    assert [m.sender for m in messages] == ["111", "222"]
    assert [m.text for m in messages] == ["hello", "need help"]


def test_whatsapp_cursor_roundtrip(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox.jsonl"
    inbox.write_text("", encoding="utf-8")
    cursor_path = tmp_path / "cursor.txt"

    channel = WhatsAppChannel(access_token=None, phone_number_id=None, inbox_path=inbox, cursor_path=cursor_path)
    assert channel._load_cursor() == 0

    channel._save_cursor(8)
    assert channel._load_cursor() == 8
