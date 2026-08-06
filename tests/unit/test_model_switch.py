"""Tests für Modell-Aliase + Fallback-Kette (Task 2.5)."""
import pytest

from eaccode.llm.model_switch import AliasConfig, FallbackChain, ModelResolver


def test_user_alias_resolution():
    r = ModelResolver(aliases={
        "fast": AliasConfig(provider="minimax", model="MiniMax-M2"),
        "work": AliasConfig(provider="opencode-go", model="deepseek-v4-flash",
                            base_url="https://api.example/v1"),
    })
    assert r.resolve("fast").provider == "minimax"
    assert r.resolve("fast").model == "MiniMax-M2"
    assert r.resolve("work").base_url == "https://api.example/v1"


def test_alias_shadows_builtin():
    r = ModelResolver(aliases={"sonnet": AliasConfig(provider="minimax", model="MiniMax-M2")})
    assert r.resolve("sonnet").provider == "minimax"  # User-Alias schlägt Built-in


def test_full_model_string_passthrough():
    r = ModelResolver(aliases={})
    resolved = r.resolve("anthropic/claude-sonnet-4-6")
    assert resolved.provider == "anthropic"
    assert resolved.model == "claude-sonnet-4-6"


def test_builtin_alias():
    r = ModelResolver(aliases={})
    assert r.resolve("minimax").model == "MiniMax-M2"


def test_unknown_alias_raises():
    r = ModelResolver(aliases={})
    with pytest.raises(ValueError):
        r.resolve("gibt-es-nicht")


def test_litellm_id_native_and_custom():
    assert ModelResolver().resolve("minimax").litellm_id == "minimax/MiniMax-M2"
    r = ModelResolver(aliases={
        "oc": AliasConfig(provider="opencode-go", model="deepseek-v4-flash"),
    })
    assert r.resolve("oc").litellm_id == "openai/deepseek-v4-flash"


def test_fallback_chain():
    chain = FallbackChain([("minimax", "MiniMax-M2"), ("opencode-go", "deepseek-v4-flash")])
    assert chain.next_after(0) == ("opencode-go", "deepseek-v4-flash")
    assert chain.next_after(1) is None  # Ende der Kette
    assert FallbackChain().next_after(0) is None  # leere Kette
