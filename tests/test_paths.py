"""Пути помогатора: в исходниках, в собранном exe и папка логов."""
import sys
from pathlib import Path

from backend.paths import app_root, log_dir

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_app_root_in_sources_is_repository_root():
    assert app_root() == REPO_ROOT
    assert (app_root() / "app.py").exists()


def test_app_root_in_frozen_exe_is_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert app_root() == tmp_path


def test_log_dir_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert log_dir() == tmp_path / "chess-helper" / "logs"


def test_log_dir_without_localappdata_falls_back_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert log_dir() == tmp_path / "AppData" / "Local" / "chess-helper" / "logs"
