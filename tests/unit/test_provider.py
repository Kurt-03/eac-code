"""Tests for the memory provider abstraction (A.10)."""

from eaccode.memory.provider import MarkdownMemoryProvider


def test_provider_roundtrip(tmp_path):
    provider = MarkdownMemoryProvider(tmp_path)
    provider.add_fact("memory", "use uv", "h1")
    assert "use uv" in provider.read("memory", "h1")
    assert provider.replace_fact("memory", "use uv", "use uv build", "h1") is True
    assert "use uv build" in provider.read("memory", "h1")
    assert provider.remove_line("memory", "uv build", "h1") is True
    assert "uv" not in provider.read("memory", "h1")


def test_provider_global_kinds(tmp_path):
    provider = MarkdownMemoryProvider(tmp_path)
    provider.add_fact("user", "John")
    assert "John" in provider.read("user")
    provider.add_fact("soul", "be direct")
    assert "be direct" in provider.read("soul")
