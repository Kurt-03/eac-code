"""`eaccode computer` subcommand — cua-driver status/install/doctor."""

from __future__ import annotations

import click

from eaccode.cli._output import print_info
from eaccode.tools import cua_install


@click.group(name="computer")
def computer() -> None:
    """Desktop automation (cua-driver): status, install, doctor."""


@computer.command(name="status")
def computer_status() -> None:
    """Show whether cua-driver is installed."""
    status = cua_install.driver_status()
    if status["installed"]:
        version = f" (v{status['version']})" if status["version"] else ""
        print_info(f"cua-driver: {status['path']}{version}")
    else:
        print_info("cua-driver: not installed — run `eaccode computer install`")


@computer.command(name="install")
def computer_install() -> None:
    """Install cua-driver via the platform package manager."""
    print_info(cua_install.install_cua_driver())
    if cua_install.driver_status()["installed"]:
        print_info("Installation verified.")
    else:
        print_info("Installation not verified yet — set EACCODE_CUA_DRIVER if needed.")


@computer.command(name="doctor")
def computer_doctor() -> None:
    """Run diagnostics and repair the Windows autostart service."""
    findings = cua_install.doctor()
    if not findings:
        print_info("All checks passed.")
        return
    for line in findings:
        print_info(line)
