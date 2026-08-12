"""P7 (v0.7.2): ReplContext + CtxProxy attribute routing."""

from eaccode.ui.context import ReplContext, _CtxProxy


def test_proxy_routes_dataclass_fields():
    ctx = ReplContext(workdir=__import__("pathlib").Path("/tmp"))
    proxy = _CtxProxy(ctx)
    assert proxy.workdir == __import__("pathlib").Path("/tmp")
    assert proxy._agent is None  # default


def test_proxy_routes_state_bag():
    ctx = ReplContext()
    ctx.state["messages"] = [{"role": "user", "content": "hi"}]
    proxy = _CtxProxy(ctx)
    assert proxy.messages == [{"role": "user", "content": "hi"}]


def test_proxy_writes_back_to_state():
    ctx = ReplContext()
    proxy = _CtxProxy(ctx)
    proxy.custom_attr = 42
    assert ctx.state["custom_attr"] == 42


def test_proxy_aliases_set_dataclass():
    ctx = ReplContext()
    proxy = _CtxProxy(ctx)
    proxy._agent = "fake-agent"
    assert ctx.agent == "fake-agent"
    assert proxy._agent == "fake-agent"


def test_proxy_unknown_attribute_returns_none():
    """Unknown attrs return None (matching the getattr(app, ...) pattern
    that the slash-commands already use internally)."""
    proxy = _CtxProxy(ReplContext())
    assert proxy.unknown is None
