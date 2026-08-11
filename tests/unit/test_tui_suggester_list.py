"""Tests for the v0.4.0 list-style suggester (TUI redesign Phase C.2)."""



def test_slash_empty_returns_all_sorted():
    from eaccode.tui.suggester_list import list_slash_completions

    completions = list_slash_completions("")
    assert completions  # non-empty
    names = [c[0] for c in completions]
    assert names == sorted(names, key=lambda n: (len(n), n))


def test_slash_filters_by_prefix():
    from eaccode.tui.suggester_list import list_slash_completions

    completions = list_slash_completions("/mo")
    names = [c[0] for c in completions]
    assert all(n.startswith("mo") for n in names)
    assert "mode" in names
    assert "model" in names


def test_slash_no_match_returns_empty():
    from eaccode.tui.suggester_list import list_slash_completions

    completions = list_slash_completions("/zzzznomatch")
    assert completions == []


def test_slash_returns_label_and_desc():
    from eaccode.tui.suggester_list import list_slash_completions

    completions = list_slash_completions("/help")
    assert len(completions) == 1
    name, desc = completions[0]
    assert name == "help"
    assert desc  # non-empty description


def test_at_context_returns_all():
    from eaccode.tui.suggester_list import list_at_completions

    completions = list_at_completions("@")
    labels = [c[0] for c in completions]
    assert "@file:" in labels
    assert "@folder:" in labels
    assert "@diff" in labels


def test_at_filters_by_prefix():
    from eaccode.tui.suggester_list import list_at_completions

    completions = list_at_completions("@fi")
    names = [c[0] for c in completions]
    assert all(n.lower().startswith("@fi") for n in names)
    assert "@file:" in names
