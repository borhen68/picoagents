import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from picoagent.core.dual_memory import DualMemoryStore
from picoagent.session import SessionState
from picoagent.providers.registry import ProviderClient


@pytest.fixture
def memory_store(tmp_path: Path):
    return DualMemoryStore(workspace=tmp_path, memory_dir_name="test_memory")


def test_dual_memory_basic_io(memory_store: DualMemoryStore):
    # Should start empty
    assert memory_store.read_long_term() == ""
    assert memory_store.get_memory_context() == ""

    # Write long term
    memory_store.write_long_term("User likes pizza.")
    assert memory_store.read_long_term() == "User likes pizza."
    assert "User likes pizza." in memory_store.get_memory_context()

    # Append history
    memory_store.append_history("Event 1")
    memory_store.append_history("Event 2")
    
    history_content = memory_store.history_file.read_text()
    assert "Event 1\n\nEvent 2\n\n" == history_content


@pytest.mark.asyncio
async def test_dual_memory_consolidate_success(memory_store: DualMemoryStore):
    # Setup mock session with 5 messages
    session = SessionState(key="test_session")
    for i in range(5):
        session.add_message("user", f"msg {i}")
        session.add_message("assistant", f"reply {i}")
        
    session.metadata = {"dual_memory_consolidated": 0}

    # Setup mock provider that returns a JSON string
    mock_provider = MagicMock(spec=ProviderClient)
    mock_provider.chat.return_value = json.dumps({
        "history_entry": "User sent 5 messages about tests.",
        "memory_update": "# Facts\n- User writes tests",
    })

    # Consolidate with a window that forces processing 
    success = await memory_store.consolidate(
        session=session,
        provider=mock_provider,
        model="test-model",
        memory_window=4  # keep_count = 2. It will process messages 0, 1, 2
    )

    # Verify logic
    assert success is True
    assert memory_store.read_long_term() == "# Facts\n- User writes tests"
    assert "User sent 5 messages" in memory_store.history_file.read_text()
    
    # Verify metadata was updated (10 messages total minus keep_count of 2 = 8)
    assert session.metadata["dual_memory_consolidated"] == 8


@pytest.mark.asyncio
async def test_dual_memory_consolidate_no_tool_call(memory_store: DualMemoryStore):
    session = SessionState(key="test_session")
    for i in range(5):
        session.add_message("user", f"msg {i}")
        session.add_message("assistant", f"reply {i}")

    mock_provider = MagicMock(spec=ProviderClient)
    mock_provider.chat.return_value = "I forgot to return JSON"

    success = await memory_store.consolidate(
        session=session,
        provider=mock_provider,
        model="test-model",
        memory_window=2 
    )

    assert success is False
    assert memory_store.read_long_term() == ""  # Nothing written
