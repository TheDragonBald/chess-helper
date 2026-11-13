"""Функции скрипта сборки: версия и тег, обход зависимостей, лицензии, метка интернета, ошибки сборки."""
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build_exe


def test_read_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "1.2.3"\ndependencies = []\n', encoding="utf-8")
    assert build_exe.read_version(pyproject) == "1.2.3"


def test_check_tag_accepts_matching_tag():
    assert build_exe.check_tag("v0.1.0", "0.1.0") is None  # совпадает — без SystemExit


def test_check_tag_rejects_other_tag():
    with pytest.raises(SystemExit, match="v0.1.0"):
        build_exe.check_tag("v0.2.0", "0.1.0")


def test_runtime_distributions_follow_real_dependencies():
    names = {build_exe.canonical(d.metadata["Name"]) for d in build_exe.runtime_distributions()}
    assert {
        "chess", "pywebview", "bottle", "proxy-tools", "pythonnet",
        "clr-loader", "cffi", "pycparser", "typing-extensions",
    } <= names
    assert "pytest" not in names
    assert "pyinstaller" not in names


class FakeFile:
    """Подмена PackagePath: части пути внутри site-packages и настоящий файл на диске."""

    def __init__(self, relative: str, real: Path):
        self.parts = tuple(relative.split("/"))
        self._real = real

    def locate(self):
        return self._real


class FakeDist:
    def __init__(self, name, files):
        self.metadata = {"Name": name}
        self.files = files


def test_collect_licenses_copies_dist_info_license(tmp_path):
    license_file = tmp_path / "LICENSE"
    license_file.write_text("MIT текст", encoding="utf-8")
    dist = FakeDist(
        "Some_Pkg",
        [
            FakeFile("some_pkg-1.0.dist-info/licenses/LICENSE", license_file),
            FakeFile("some_pkg/__init__.py", tmp_path / "unused.py"),
        ],
    )
    target = tmp_path / "out"
    build_exe.collect_licenses(target, [dist], overrides=tmp_path / "overrides")
    assert (target / "some-pkg-LICENSE.txt").read_text(encoding="utf-8") == "MIT текст"
    assert len(list(target.iterdir())) == 1


def test_collect_licenses_uses_override_when_package_has_no_license(tmp_path):
    overrides = tmp_path / "overrides"
    overrides.mkdir()
    (overrides / "proxy-tools.txt").write_text("MIT override", encoding="utf-8")
    target = tmp_path / "out"
    build_exe.collect_licenses(target, [FakeDist("proxy_tools", [])], overrides=overrides)
    assert (target / "proxy-tools.txt").read_text(encoding="utf-8") == "MIT override"


def test_collect_licenses_fails_without_any_license(tmp_path):
    with pytest.raises(SystemExit, match="proxy-tools"):
        build_exe.collect_licenses(tmp_path / "out", [FakeDist("proxy_tools", [])], overrides=tmp_path / "none")


def test_assemble_without_python_license_stops_with_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(build_exe, "APP_DIR", tmp_path / "app")
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "python"))  # Python без LICENSE.txt
    stockfish = tmp_path / "stockfish.exe"
    stockfish.write_bytes(b"")
    with pytest.raises(SystemExit, match="LICENSE.txt"):
        build_exe.assemble(stockfish, "0.1.0")


class HangingProcess:
    """Подмена Popen: exe успел записать отчёт, но не завершился."""

    pid = 4242

    def __init__(self, args):
        self.args = args
        Path(args[2]).write_text("OK files: файлы на месте\n", encoding="utf-8")

    def wait(self, timeout=None):
        if timeout is not None:
            raise subprocess.TimeoutExpired(self.args, timeout)
        return 1


def test_self_check_timeout_prints_written_report(tmp_path, monkeypatch, capsys):
    killed = []
    monkeypatch.setattr(subprocess, "Popen", HangingProcess)
    # Настоящий taskkill по выдуманному PID мог бы убить чужой процесс
    monkeypatch.setattr(subprocess, "run", lambda args, check: killed.append(args))
    with pytest.raises(SystemExit, match="не уложилась"):
        build_exe.self_check_exe(tmp_path, tmp_path / "report.txt")
    assert killed[0][0] == "taskkill"
    assert "OK files: файлы на месте" in capsys.readouterr().out


@pytest.mark.skipif(sys.platform != "win32", reason="потоки NTFS есть только на Windows")
def test_mark_from_internet_writes_zone_identifier(tmp_path):
    (tmp_path / "sub").mkdir()
    dll = tmp_path / "sub" / "a.dll"
    dll.write_bytes(b"x")
    assert build_exe.mark_from_internet(tmp_path) == 1
    with open(f"{dll}:Zone.Identifier", "rb") as stream:
        assert stream.read() == b"[ZoneTransfer]\r\nZoneId=3\r\n"
