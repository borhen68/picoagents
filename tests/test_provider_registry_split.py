from picoagent.config import AgentConfig, AgentsConfig, ProvidersConfig
from picoagent.providers.registry import OpenAICompatibleClient, ProviderRegistry, SplitProviderClient


def test_create_client_supports_split_embedding_provider(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    cfg = AgentConfig(
        providers=ProvidersConfig.from_dict({
            "groq": {"apiKey": "groq-key"},
            "openai": {"apiKey": "openai-key"},
        }),
        agents=AgentsConfig(
            model="llama-3.3-70b-versatile",
            provider="groq",
            embedding_model="text-embedding-3-small",
            embedding_provider="openai",
        ),
    )

    client = ProviderRegistry().create_client(cfg)

    assert isinstance(client, SplitProviderClient)
    assert isinstance(client._chat, OpenAICompatibleClient)
    assert isinstance(client._embed, OpenAICompatibleClient)
    assert client._chat.base_url == "https://api.groq.com/openai/v1"
    assert client._embed.base_url == "https://api.openai.com/v1"
    assert client._chat.api_key == "groq-key"
    assert client._embed.api_key == "openai-key"


def test_create_client_uses_single_provider_when_embedding_provider_not_set(monkeypatch) -> None:
    monkeypatch.setenv("PICOAGENT_API_KEY", "key")
    cfg = AgentConfig(
        providers=ProvidersConfig.from_dict({"openrouter": {"apiKey": "key"}}),
        agents=AgentsConfig(model="openai/gpt-4o-mini", provider="openrouter"),
    )

    client = ProviderRegistry().create_client(cfg)

    assert isinstance(client, OpenAICompatibleClient)
    assert not isinstance(client, SplitProviderClient)
