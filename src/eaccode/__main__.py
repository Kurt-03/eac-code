from eaccode._subprocess_compat import suppress_platform_ver_console

# Windows: stub platform._syscmd_ver BEFORE any heavyweight import — many
# dependencies touch platform.uname() at import time, which otherwise
# shells out `cmd /c ver` and flashes a visible console window in the
# REPL (Phase A.5).
suppress_platform_ver_console()

from eaccode.cli import main  # noqa: E402  (after the guard, by design)

main()
