"""Tests for the Slack channel."""
from picoagent.channels.slack import SlackChannel


def test_slack_channel_init() -> None:
    ch = SlackChannel(token="xoxb-test", channel_id="C123")
    assert ch.token == "xoxb-test"
    assert ch.channel_id == "C123"
    assert ch.reply_in_thread is True


def test_ts_gt_compares_correctly() -> None:
    assert SlackChannel._ts_gt("1234567890.123457", "1234567890.123456") is True
    assert SlackChannel._ts_gt("1234567890.123456", "1234567890.123457") is False
    assert SlackChannel._ts_gt("1234567890.123456", "1234567890.123456") is False


def test_ts_gt_handles_invalid_values() -> None:
    assert SlackChannel._ts_gt("abc", "aab") is True
    assert SlackChannel._ts_gt("aab", "abc") is False
