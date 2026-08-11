"""Tests for BYOK provider configuration (Task 1.2)."""
from eaccode.config.providers import ProviderConfig, load_providers, save_providers


def test_provider_config_to_env():
    p = ProviderConfig(name="anthropic", api_key="sk-test", model="claude-sonnet-4-6")
    env = p.to_env()
    assert env["ANTHROPIC_API_KEY"] == "sk-test"


def test_provider_config_to_env_with_base_url():
    p = ProviderConfig(
        name="opencode-go",
        api_key="oc-test",
        model="deepseek-v4-flash",
        base_url="https://api.example/v1",
    )
    env = p.to_env()
    assert env["OPENCODE_GO_API_KEY"] == "oc-test"
    assert env["OPENCODE_GO_API_BASE"] == "https://api.example/v1"


def test_save_and_load_roundtrip(tmp_path):
    providers = [
        ProviderConfig(name="anthropic", api_key="sk-1", model="claude-sonnet-4-6"),
        ProviderConfig(name="minimax", api_key="mk-2", model="MiniMax-M2"),
    ]
    file = tmp_path / "providers.yaml"
    save_providers(providers, file)
    loaded = load_providers(file)
    assert len(loaded) == 2
    assert loaded[0].api_key.get_secret_value() == "sk-1"
    assert loaded[1].name == "minimax"
    assert loaded[1].model == "MiniMax-M2"


def test_load_missing_file_returns_empty(tmp_path):
    assert load_providers(tmp_path / "nope.yaml") == []


def test_save_restricts_permissions(tmp_path):
    """P0.6 Bug 4: save_providers must chmod 600 the secrets file itself,
    regardless of which code path saved it."""
    import os

    providers = [
        ProviderConfig(name="anthropic", api_key="sk-secret", model="claude-sonnet-4-6"),
    ]
    file = tmp_path / "providers.yaml"
    save_providers(providers, file)
    if os.name != "nt":
        assert (file.stat().st_mode & 0o777) == 0o600
    else:
        # Windows: chmod is a no-op; the file must at least exist with content.
        assert "sk-secret" in file.read_text(encoding="utf-8")
