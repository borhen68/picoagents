"""Tests for provider get_default_model method."""
from picoagent.providers.registry import LocalHeuristicClient, SplitProviderClient


def test_local_heuristic_get_default_model() -> None:
    client = LocalHeuristicClient()
    assert client.get_default_model() == "local-heuristic"


def test_split_provider_delegates_get_default_model() -> None:
    chat = LocalHeuristicClient()
    embed = LocalHeuristicClient()
    split = SplitProviderClient(chat_client=chat, embedding_client=embed)
    assert split.get_default_model() == "local-heuristic"
