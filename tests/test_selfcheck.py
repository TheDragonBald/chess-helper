"""Самопроверка: отчёт, коды возврата, вложенный движок вместо STOCKFISH_PATH."""
from pathlib import Path

import chess
import chess.engine
import pytest

from backend import selfcheck
from backend.selfcheck import Info, run_self_check


def ok_check(root):
    return "всё хорошо"


def info_check(root):
    return Info("справка")


def broken_check(root):
    raise RuntimeError("сломано")


def test_all_ok_returns_zero_and_writes_report(tmp_path):
    report = tmp_path / "report.txt"
    code = run_self_check(report, checks=(("a", ok_check), ("b", info_check)), root=tmp_path)
    assert code == 0
    assert report.read_text(encoding="utf-8").splitlines() == ["OK a: всё хорошо", "INFO b: справка"]


def test_failed_check_returns_one_and_does_not_raise(tmp_path):
    report = tmp_path / "report.txt"
    code = run_self_check(report, checks=(("a", broken_check), ("b", ok_check)), root=tmp_path)
    assert code == 1
    assert report.read_text(encoding="utf-8").splitlines() == [
        "FAIL a: RuntimeError: сломано",
        "OK b: всё хорошо",
    ]


def test_unwritable_report_returns_one(tmp_path):
    report = tmp_path / "missing-dir" / "report.txt"
    assert run_self_check(report, checks=(("a", ok_check),), root=tmp_path) == 1


def make_bundle(root: Path, with_icon: bool = True) -> None:
    (root / "frontend" / "vendor" / "chessground").mkdir(parents=True)
    (root / "frontend" / "index.html").write_text("<html></html>", encoding="utf-8")
    if with_icon:
        (root / "assets").mkdir()
        (root / "assets" / "icon.ico").write_bytes(b"ico")


def test_check_files_passes_for_complete_bundle(tmp_path):
    make_bundle(tmp_path)
    assert selfcheck.check_files(tmp_path)


def test_check_files_names_missing_icon(tmp_path):
    make_bundle(tmp_path, with_icon=False)
    with pytest.raises(FileNotFoundError, match="assets/icon.ico"):
        selfcheck.check_files(tmp_path)


class FakeEngine:
    def __init__(self):
        self.quit_called = False

    def analyse(self, board, limit):
        return {"depth": 10, "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE)}

    def quit(self):
        self.quit_called = True


def test_check_engine_uses_bundled_engine_not_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKFISH_PATH", str(tmp_path / "other.exe"))
    commands, engine = [], FakeEngine()

    def popen_uci(command, **kwargs):
        commands.append(command)
        return engine

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", staticmethod(popen_uci))
    assert "глубина 10" in selfcheck.check_engine(tmp_path)
    assert commands == [str(tmp_path / "engine" / "stockfish.exe")]
    assert engine.quit_called


def test_check_renderer_never_fails(monkeypatch):
    def broken():
        raise RuntimeError("нет .NET")

    monkeypatch.setattr("backend.startup_check.load_winforms_renderer", broken)
    result = selfcheck.check_renderer(Path("."))
    assert isinstance(result, Info)
    assert "нет .NET" in result
