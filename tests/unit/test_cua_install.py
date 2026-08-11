"""Tests for the cua-driver installer/doctor (Phase I.5)."""

from eaccode.tools import cua_install


class TestDriverStatus:
    def test_missing_driver(self, monkeypatch):
        monkeypatch.setattr("eaccode.tools.cua_install.find_driver", lambda: None)
        status = cua_install.driver_status()
        assert status == {"installed": False, "path": None, "version": None}

    def test_installed_driver_reads_version(self, monkeypatch, tmp_path):
        binary = tmp_path / "cua-driver.exe"
        binary.write_text("fake", encoding="utf-8")
        monkeypatch.setattr("eaccode.tools.cua_install.find_driver",
                            lambda: binary)

        def fake_run(cmd, capture_output=True, text=True, encoding="utf-8",
                     errors="replace", timeout=10):
            class _P:
                stdout = "cua-driver 1.2.3\n"
                stderr = ""
            return _P()

        monkeypatch.setattr("eaccode.tools.cua_install.subprocess.run", fake_run)
        status = cua_install.driver_status()
        assert status["installed"] is True
        assert status["version"] == "cua-driver 1.2.3"


class TestDoctor:
    def test_doctor_missing_driver(self, monkeypatch):
        monkeypatch.setattr("eaccode.tools.cua_install.driver_status",
                            lambda: {"installed": False, "path": None,
                                     "version": None})
        findings = cua_install.doctor()
        assert len(findings) == 1
        assert "not found" in findings[0]

    def test_doctor_healthy(self, monkeypatch):
        monkeypatch.setattr("eaccode.tools.cua_install.driver_status",
                            lambda: {"installed": True, "path": "/x/cua-driver",
                                     "version": "1.0"})
        monkeypatch.setattr("eaccode.tools.cua_install._repair_windows_autostart",
                            lambda: None)
        findings = cua_install.doctor()
        assert any("cua-driver:" in f for f in findings)

    def test_doctor_reports_autostart_repair(self, monkeypatch):
        monkeypatch.setattr("eaccode.tools.cua_install.driver_status",
                            lambda: {"installed": True, "path": "/x/cua-driver",
                                     "version": None})
        monkeypatch.setattr("eaccode.tools.cua_install._repair_windows_autostart",
                            lambda: "service was stopped")
        findings = cua_install.doctor()
        assert any("service" in f for f in findings)


class TestInstall:
    def test_install_missing_winget_returns_instructions(self, monkeypatch):
        monkeypatch.setattr("eaccode.tools.cua_install.sys.platform", "win32")
        monkeypatch.setattr("eaccode.tools.cua_install.shutil.which",
                            lambda name: None if name == "winget" else "/bin/x")
        out = cua_install.install_cua_driver()
        assert "winget not found" in out

    def test_install_non_windows_returns_manual(self, monkeypatch):
        monkeypatch.setattr("eaccode.tools.cua_install.sys.platform", "linux")
        out = cua_install.install_cua_driver()
        assert "Manual install" in out
