"""Tests for the v0.4.0 ASCII spinner (TUI redesign Phase A.2)."""



def test_spinner_cycles_through_frames():
    from eaccode.tui.spinner import Spinner

    sp = Spinner()
    seen = set()
    for _ in range(7):
        seen.add(sp.frame())
        sp.tick()
    # 6 of 7 unique — last frame equals first after wrap; allow >= 4
    assert len(seen) >= 4


def test_spinner_advances_only_on_tick():
    from eaccode.tui.spinner import Spinner

    sp = Spinner(interval=10_000)
    before = sp.frame()
    sp.tick()
    after = sp.frame()
    # After one tick, frame must differ (we have 6 unique frames).
    assert before != after


def test_spinner_frame_is_single_char():
    from eaccode.tui.spinner import Spinner

    sp = Spinner()
    assert len(sp.frame()) == 1


def test_spinner_animation_stop():
    from eaccode.tui.spinner import Spinner

    sp = Spinner()
    sp.stop()
    assert sp.is_running() is False
