"""Самопроверка: отчёт, коды возврата, вложенный движок вместо STOCKFISH_PATH."""
import re
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
    def __init__(self, analyse_error=None, quit_error=None):
        self.analyse_error = analyse_error
        self.quit_error = quit_error
        self.quit_called = False
        self.close_called = False

    def analyse(self, board, limit):
        if self.analyse_error is not None:
            raise self.analyse_error
        return {"depth": 10, "score": chess.engine.PovScore(chess.engine.Cp(20), chess.WHITE)}

    def quit(self):
        self.quit_called = True
        if self.quit_error is not None:
            raise self.quit_error

    def close(self):
        self.close_called = True


def use_engine(monkeypatch, root: Path, engine: FakeEngine) -> list:
    """Кладёт файл движка в сборку и подменяет запуск Stockfish; возвращает список команд запуска."""
    (root / "engine").mkdir()
    (root / "engine" / "stockfish.exe").write_bytes(b"")
    commands = []

    def popen_uci(command, **kwargs):
        commands.append(command)
        return engine

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", staticmethod(popen_uci))
    return commands


def test_check_engine_uses_bundled_engine_not_env(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKFISH_PATH", str(tmp_path / "other.exe"))
    engine = FakeEngine()
    commands = use_engine(monkeypatch, tmp_path, engine)
    assert "глубина 10" in selfcheck.check_engine(tmp_path)
    assert commands == [str(tmp_path / "engine" / "stockfish.exe")]
    assert engine.quit_called


def test_check_engine_names_missing_engine(tmp_path, monkeypatch):
    def popen_uci(command, **kwargs):
        pytest.fail("движка нет — запускать нечего")

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", staticmethod(popen_uci))
    with pytest.raises(FileNotFoundError, match=re.escape(str(tmp_path / "engine" / "stockfish.exe"))):
        selfcheck.check_engine(tmp_path)


def test_check_engine_closes_engine_when_quit_fails(tmp_path, monkeypatch):
    engine = FakeEngine(quit_error=chess.engine.EngineTerminatedError("движок уже завершился"))
    use_engine(monkeypatch, tmp_path, engine)
    assert "глубина 10" in selfcheck.check_engine(tmp_path)
    assert engine.close_called


def test_check_engine_keeps_analysis_error_when_quit_fails(tmp_path, monkeypatch):
    # Зависший движок не должен подменять причину сбоя своей ошибкой из quit()
    engine = FakeEngine(analyse_error=TimeoutError("анализ завис"), quit_error=TimeoutError("quit завис"))
    use_engine(monkeypatch, tmp_path, engine)
    with pytest.raises(TimeoutError, match="анализ завис"):
        selfcheck.check_engine(tmp_path)
    assert engine.close_called


def test_check_renderer_import_failure_is_fail(tmp_path, monkeypatch):
    # Приложение при старте импортирует именно winforms: сбой импорта — ошибка сборки, а не справка
    def broken():
        raise RuntimeError("нет .NET")

    monkeypatch.setattr("backend.startup_check.load_winforms_renderer", broken)
    with pytest.raises(RuntimeError, match="нет .NET"):
        selfcheck.check_renderer(tmp_path)
    report = tmp_path / "report.txt"
    assert run_self_check(report, checks=(("renderer", selfcheck.check_renderer),), root=tmp_path) == 1
    assert report.read_text(encoding="utf-8").splitlines() == ["FAIL renderer: RuntimeError: нет .NET"]
