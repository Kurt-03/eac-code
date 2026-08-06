"""Tests for the `eaccode run` headless command + default registry."""
import json

from click.testing import CliRunner

from eaccode.cli import main
from eaccode.llm.client import CompletionResponse, TokenUsage
from eaccode.llm.models import ToolCall
from eaccode.tools.factory import build_default_registry


def test_default_registry_contains_core_tools():
    reg = build_default_registry()
    names = {t.name for t in reg.list()}
    assert {"read", "write", "edit", "bash", "glob", "todo_write"} <= names


def test_default_registry_allowed_tools_filter():
    reg = build_default_registry(allowed_tools=["read", "bash"])
    names = {t.name for t in reg.list()}
    assert names == {"read", "bash"}


class _MockClient:
    """Scripted LLMClient: first a write tool call, then the final answer."""

    def __init__(self, *args, **kwargs):
        self.calls = 0
        self._responses = [
            CompletionResponse(
                text="",
                tool_calls=[ToolCall(
                    id="t1", name="write",
                    arguments={"path": "out.txt", "content": "eaccode lebt"},
                )],
                stop_reason="tool_use",
                usage=TokenUsage(input_tokens=10, output_tokens=5),
                model="minimax/MiniMax-M3",
            ),
            CompletionResponse(
                text="Fertig! Die Datei wurde erstellt.",
                tool_calls=[],
                stop_reason="stop",
                usage=TokenUsage(input_tokens=20, output_tokens=10),
                model="minimax/MiniMax-M3",
            ),
        ]

    def complete(self, req):
        resp = self._responses[self.calls]
        self.calls += 1
        return resp


def _setup_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.chdir(tmp_path)  # agent workdir = Path.cwd()
    # Real BYOK config so the full providers → client path is exercised
    from eaccode.config.paths import EaccodePaths
    from eaccode.config.providers import ProviderConfig, save_providers

    save_providers(
        [ProviderConfig(name="minimax", api_key="mk-test", model="MiniMax-M3")],
        EaccodePaths().providers_file,
    )
    # Fake the LLM client so no network is needed
    monkeypatch.setattr("eaccode.llm.client.LLMClient", _MockClient)


def test_run_headless_writes_file_and_returns_json(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "Erstelle out.txt",
        "--print", "--output-format", "json",
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "Fertig" in data["result"]
    assert data["turns"] == 2
    assert data["cost_usd"] == 0.0
    # the tool actually executed against the workdir
    assert (tmp_path / "out.txt").read_text() == "eaccode lebt"


def test_run_text_output(tmp_path, monkeypatch):
    _setup_env(tmp_path, monkeypatch)

    runner = CliRunner()
    result = runner.invoke(main, [
        "run", "Erstelle out.txt",
        "--print", "--output-format", "text",
    ])
    assert result.exit_code == 0, result.output
    assert "Fertig" in result.output
