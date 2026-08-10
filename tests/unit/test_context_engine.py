"""Tests for the context engine (Phase I.12) — plugin loading, tool wrapping,
and slash-command registration."""

import pydantic
import pytest

from eaccode.context.engine import ContextEngine, PluginTool, get_engine
from eaccode.tools.base import ToolContext


@pytest.fixture
def ctx(tmp_path):
    return ToolContext(workdir=tmp_path)


def _write_plugin(plugins_dir, name: str, body: str):
    plugins_dir.mkdir(parents=True, exist_ok=True)
    path = plugins_dir / f"{name}.py"
    path.write_text(body, encoding="utf-8")
    return path


class TestLoading:
    def test_empty_dir_loads_nothing(self, tmp_path):
        engine = ContextEngine(tmp_path / "no_plugins")
        assert engine.load() == []

    def test_plugin_registers_tool_and_slash(self, tmp_path):
        _write_plugin(
            tmp_path,
            "greeter",
            """
from eaccode.tools.base import ToolResult

def setup(api):
    def hello(args, ctx):
        return ToolResult(content=f"Hello, {args['name']}!")

    api.register_tool("greet", "Greet someone", hello,
                      parameters={"name": (str, "who to greet")})
    api.register_slash_command("hello", "Say hi", lambda arg: f"hi {arg}")
""",
        )
        engine = ContextEngine(tmp_path)
        engine.load()

        assert engine._loaded == ["greeter"]
        assert [t.name for t in engine.tool_specs()] == ["greet"]
        assert [s.name for s in engine.slash_specs()] == ["hello"]

    def test_plugin_without_setup_is_reported_not_fatal(self, tmp_path):
        _write_plugin(tmp_path, "empty", "x = 1\n")
        engine = ContextEngine(tmp_path)
        engine.load()
        assert engine._loaded == []
        assert len(engine.errors()) == 1
        assert "setup" in engine.errors()[0][1]

    def test_broken_plugin_does_not_break_others(self, tmp_path):
        _write_plugin(tmp_path, "broken", "raise RuntimeError('boom')\n")
        _write_plugin(
            tmp_path,
            "fine",
            "def setup(api):\n"
            "    api.register_tool('ok', 'd', lambda a, c: 'y')\n",
        )
        engine = ContextEngine(tmp_path)
        engine.load()
        assert engine._loaded == ["fine"]
        assert len(engine.errors()) == 1
        assert "RuntimeError" in engine.errors()[0][1]

    def test_get_engine_caches_per_directory(self, tmp_path):
        _write_plugin(
            tmp_path,
            "a",
            "def setup(api):\n"
            "    api.register_tool('t', 'd', lambda a, c: 'x')\n",
        )
        first = get_engine(tmp_path)
        second = get_engine(tmp_path)
        assert first is second
        assert len(first.tool_specs()) == 1  # setup ran exactly once


class TestPluginTool:
    @pytest.mark.asyncio
    async def test_sync_handler_returns_text(self, tmp_path, ctx):
        _write_plugin(
            tmp_path,
            "p",
            "def setup(api):\n"
            "    api.register_tool('t', 'd', lambda a, c: 'plain')\n",
        )
        tool = PluginTool(get_engine(tmp_path).tool_specs()[0])
        result = await tool.run(tool.input_model(), ctx)
        assert result.content == "plain"

    @pytest.mark.asyncio
    async def test_async_handler_returns_tool_result(self, tmp_path, ctx):
        _write_plugin(
            tmp_path,
            "p",
            """
import asyncio
from eaccode.tools.base import ToolResult

async def handle(args, ctx):
    await asyncio.sleep(0)
    return ToolResult(content="async done", is_error=True)

def setup(api):
    api.register_tool("atool", "async tool", handle)
""",
        )
        tool = PluginTool(get_engine(tmp_path).tool_specs()[0])
        result = await tool.run(tool.input_model(), ctx)
        assert result.content == "async done"
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_parameters_are_validated(self, tmp_path, ctx):
        _write_plugin(
            tmp_path,
            "p",
            """
def setup(api):
    api.register_tool("add", "add two ints", lambda a, c: str(a["x"] + a["y"]),
                      parameters={"x": (int, "first"), "y": (int, "second")})
""",
        )
        tool = PluginTool(get_engine(tmp_path).tool_specs()[0])
        assert tool.name == "add"
        schema = tool.to_schema()
        props = schema["input_schema"]["properties"]
        assert set(props) == {"x", "y"}
        with pytest.raises(pydantic.ValidationError):
            await tool.run(tool.input_model(x="not-int", y=2), ctx)

    @pytest.mark.asyncio
    async def test_args_dict_passed_to_handler(self, tmp_path, ctx):
        _write_plugin(
            tmp_path,
            "p",
            """
def setup(api):
    api.register_tool("echo", "echo args", lambda a, c: repr(a),
                      parameters={"n": (int, "number")})
""",
        )
        tool = PluginTool(get_engine(tmp_path).tool_specs()[0])
        result = await tool.run(tool.input_model(n=7), ctx)
        assert result.content == "{'n': 7}"


class TestSlashIntegration:
    def test_install_plugin_commands_wires_dispatch(self, tmp_path):
        from eaccode.context.engine import ContextEngine
        from eaccode.ui.command_def import COMMAND_REGISTRY, get_command
        from eaccode.ui.commands import DISPATCH_TABLE, handle_command, install_plugin_commands

        _write_plugin(
            tmp_path,
            "p",
            "def setup(api):\n"
            "    api.register_slash_command('ping', 'pong',\n"
            "                              lambda arg: 'pong ' + arg)\n",
        )
        engine = ContextEngine(tmp_path)
        engine.load()

        before = len(COMMAND_REGISTRY)
        install_plugin_commands(engine.slash_specs())
        assert "ping" in DISPATCH_TABLE
        assert get_command("ping") is not None
        assert len(COMMAND_REGISTRY) == before + 1

        class FakeApp:
            pass

        result = handle_command("/ping now", FakeApp())
        assert result.message == "pong now"

    def test_builtin_commands_win_over_plugins(self, tmp_path):
        from eaccode.ui.command_def import get_command
        from eaccode.ui.commands import install_plugin_commands

        _write_plugin(
            tmp_path,
            "p",
            "def setup(api):\n"
            "    api.register_slash_command('help', 'hijack',\n"
            "                              lambda arg: 'hijacked')\n",
        )
        engine = ContextEngine(tmp_path)
        engine.load()
        install_plugin_commands(engine.slash_specs())
        # /help still resolves to the built-in handler
        assert get_command("help").description != "hijack"

    def test_plugin_command_error_is_reported(self, tmp_path):
        from eaccode.ui.commands import handle_command, install_plugin_commands

        _write_plugin(
            tmp_path,
            "p",
            "def setup(api):\n"
            "    def boom(arg):\n"
            "        raise RuntimeError('x')\n"
            "    api.register_slash_command('boom', 'b', boom)\n",
        )
        engine = ContextEngine(tmp_path)
        engine.load()
        install_plugin_commands(engine.slash_specs())

        class FakeApp:
            pass

        result = handle_command("/boom", FakeApp())
        assert "RuntimeError" in result.message
