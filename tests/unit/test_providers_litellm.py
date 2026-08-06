"""Tests für das LiteLLM-Modell-Mapping (Task 1.5)."""
from eaccode.config.providers import ProviderConfig


def test_minimax_uses_native_prefix():
    p = ProviderConfig(name="minimax", api_key="mk", model="MiniMax-M2")
    assert p.litellm_model("MiniMax-M2") == "minimax/MiniMax-M2"


def test_anthropic_uses_native_prefix():
    p = ProviderConfig(name="anthropic", api_key="sk", model="claude-sonnet-4-6")
    assert p.litellm_model("claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"


def test_opencode_go_uses_openai_prefix_for_custom_endpoint():
    p = ProviderConfig(
        name="opencode-go",
        api_key="oc",
        model="deepseek-v4-flash",
        base_url="https://api.example/v1",
    )
    assert p.litellm_model("deepseek-v4-flash") == "openai/deepseek-v4-flash"


def test_already_prefixed_model_passes_through():
    p = ProviderConfig(name="minimax", api_key="mk", model="MiniMax-M2")
    assert p.litellm_model("openai/gpt-4o") == "openai/gpt-4o"
    assert p.litellm_model("minimax/MiniMax-M2") == "minimax/MiniMax-M2"
