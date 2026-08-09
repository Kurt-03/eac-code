"""Tests for the cross-platform clipboard (Phase G.4)."""

import sys

from eaccode.ui.clipboard import clipboard_available, write_clipboard_text


def test_write_empty_returns_false():
    assert write_clipboard_text("") is False


def test_write_clipboard_windows_uses_clip(monkeypatch):
    monkeypatch.setattr("eaccode.ui.clipboard.sys.platform", "win32")
    calls = []

    def fake_run(argv, data):
        calls.append((argv, data))
        return True

    monkeypatch.setattr("eaccode.ui.clipboard._run", fake_run)
    assert write_clipboard_text("hello") is True
    assert calls[0][0] == ["clip"]
    assert calls[0][1].startswith(b"\xff\xfe")  # UTF-16LE BOM


def test_write_clipboard_macos_uses_pbcopy(monkeypatch):
    monkeypatch.setattr("eaccode.ui.clipboard.sys.platform", "darwin")
    calls = []

    def fake_run(argv, data):
        calls.append(argv)
        return True

    monkeypatch.setattr("eaccode.ui.clipboard._run", fake_run)
    assert write_clipboard_text("hi") is True
    assert calls[0] == ["pbcopy"]


def test_write_clipboard_linux_prefers_wl_copy(monkeypatch):
    monkeypatch.setattr("eaccode.ui.clipboard.sys.platform", "linux")
    monkeypatch.setattr("eaccode.ui.clipboard.shutil.which",
                        lambda name: "/usr/bin/wl-copy" if name == "wl-copy" else None)
    calls = []

    def fake_run(argv, data):
        calls.append(argv)
        return True

    monkeypatch.setattr("eaccode.ui.clipboard._run", fake_run)
    assert write_clipboard_text("x") is True
    assert calls[0] == ["wl-copy"]


def test_write_clipboard_linux_falls_back_to_xclip(monkeypatch):
    monkeypatch.setattr("eaccode.ui.clipboard.sys.platform", "linux")
    monkeypatch.setattr(
        "eaccode.ui.clipboard.shutil.which",
        lambda name: "/usr/bin/xclip" if name == "xclip" else None,
    )
    calls = []

    def fake_run(argv, data):
        calls.append(argv)
        return True

    monkeypatch.setattr("eaccode.ui.clipboard._run", fake_run)
    assert write_clipboard_text("x") is True
    assert calls[0][0] == "xclip"


def test_write_clipboard_no_backend_false(monkeypatch):
    monkeypatch.setattr("eaccode.ui.clipboard.sys.platform", "linux")
    monkeypatch.setattr("eaccode.ui.clipboard.shutil.which", lambda name: None)
    assert write_clipboard_text("x") is False


def test_clipboard_available_windows():
    if sys.platform == "win32":
        assert clipboard_available() is True
