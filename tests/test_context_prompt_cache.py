from __future__ import annotations

from picoagent.agent.context import ContextBuilder


def test_system_prompt_stays_stable_when_runtime_changes() -> None:
    builder = ContextBuilder()
    memories = ["alpha", "beta"]

    prompt1 = builder.build_system_prompt(memories)
    _ = builder.build_runtime_context(channel="cli", chat_id="direct")
    prompt2 = builder.build_system_prompt(memories)

    assert prompt1 == prompt2


def test_runtime_context_is_separate_untrusted_user_message() -> None:
    builder = ContextBuilder()
    messages = builder.build_messages(
        user_message="Return exactly: OK",
        memories=[],
        history=[],
        channel="cli",
        chat_id="direct",
    )

    assert messages[0]["role"] == "system"
    assert "Current Time:" not in messages[0]["content"]

    assert messages[-2]["role"] == "user"
    assert ContextBuilder.runtime_tag in messages[-2]["content"]
    assert "Channel: cli" in messages[-2]["content"]
    assert "Chat ID: direct" in messages[-2]["content"]

    assert messages[-1] == {"role": "user", "content": "Return exactly: OK"}
