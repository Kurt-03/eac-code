"""Shared pytest setup.

Note: no event-loop-policy overrides here. The Windows Selector loop does
NOT support subprocesses (NotImplementedError); the default Proactor loop
is correct, and subprocess-based tools run through asyncio.to_thread,
which works on both.
"""
