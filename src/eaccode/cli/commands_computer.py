"""`eaccode computer` subcommand — cua-driver status/install/doctor."""

from __future__ import annotations

import click

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
        click.echo(f"cua-driver: {status['path']}{version}")
    else:
        click.echo("cua-driver: not installed — run `eaccode computer install`")


@computer.command(name="install")
def computer_install() -> None:
    """Install cua-driver via the platform package manager."""
    click.echo(cua_install.install_cua_driver())
    if cua_install.driver_status()["installed"]:
        click.echo("Installation verified.")
    else:
        click.echo("Installation not verified yet — set EACCODE_CUA_DRIVER if needed.")


@computer.command(name="doctor")
def computer_doctor() -> None:
    """Run diagnostics and repair the Windows autostart service."""
    findings = cua_install.doctor()
    if not findings:
        click.echo("All checks passed.")
        return
    for line in findings:
        click.echo(line)
