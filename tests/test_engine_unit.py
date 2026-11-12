"""Тесты EngineAnalyzer без настоящего Stockfish: процесс движка подменён фейком."""
import threading
import time

import chess
import chess.engine
import pytest

import backend.engine as engine_module
from backend.engine import EngineAnalyzer, build_result


def info(move="e2e4", cp=None, mate=None, depth=10, multipv=1, pov=chess.WHITE):
    score = chess.engine.Cp(cp) if mate is None else chess.engine.Mate(mate)
    return {
        "pv": [chess.Move.from_uci(move)],
        "score": chess.engine.PovScore(score, pov),
        "depth": depth,
        "multipv": multipv,
    }


class FakeAnalysis:
    """Подмена SimpleAnalysisResult: отдаёт заданные info, может «думать» до stop() и «падать»."""

    def __init__(self, infos=(), crash=None, block=False, stop_error=None):
        self.multipv = list(infos)
        self._infos = list(infos)
        self._crash = crash
        self._block = block
        self._stop_error = stop_error
        self._released = threading.Event()
        self.started = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        self.started.set()
        yield from self._infos
        if self._block:
            self._released.wait(timeout=5)  # «думает», пока анализ не остановят
        if self._crash is not None:
            raise self._crash

    def stop(self):
        self._released.set()
        if self._stop_error is not None:
            raise self._stop_error


class FakeEngine:
    """Подмена SimpleEngine: по анализу на каждый вызов analysis()."""

    def __init__(self, analyses=(), fail_configure=False, configure_delay=0.0):
        self._analyses = list(analyses)
        self._fail_configure = fail_configure
        self._configure_delay = configure_delay
        self.closed = False

    def configure(self, options):
        time.sleep(self._configure_delay)
        if self._fail_configure:
            raise chess.engine.EngineError("engine does not support option Threads")

    def analysis(self, board, limit=None, multipv=None):
        return self._analyses.pop(0)

    def quit(self):
        self.closed = True

    def close(self):
        self.closed = True


def crash():
    return FakeAnalysis(crash=chess.engine.EngineTerminatedError("engine process died unexpectedly"))


def ok():
    return FakeAnalysis([info(cp=30)])


@pytest.fixture
def fake_engines(monkeypatch, tmp_path):
    # Каждый popen_uci отдаёт следующий фейковый движок из очереди
    queue, started = [], []

    def popen_uci(command, **kwargs):
        engine = queue.pop(0)
        started.append(engine)
        return engine

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", staticmethod(popen_uci))
    path = tmp_path / "fake-stockfish.exe"
    path.write_bytes(b"")
    return path, queue, started


def test_build_result_scores_from_users_point_of_view():
    result = build_result(chess.Board(), chess.BLACK, [info(mate=2, pov=chess.WHITE)])
    assert result["lines"][0]["score"] == {"cp": None, "mate": -2}


def test_build_result_skips_infos_without_pv_or_score():
    infos = [
        info("e2e4", cp=20, depth=12),
        {"depth": 12, "multipv": 2},
        {"pv": [chess.Move.from_uci("d2d4")], "depth": 12, "multipv": 3},
    ]
    result = build_result(chess.Board(), chess.WHITE, infos)
    assert [line["san"] for line in result["lines"]] == ["e4"]
    assert result["depth"] == 12


def test_build_result_with_fewer_lines_than_multipv():
    board = chess.Board()
    result = build_result(board, chess.WHITE, [info("e2e4", cp=20), info("d2d4", cp=10, multipv=2)])
    assert [line["uci"] for line in result["lines"]] == ["e2e4", "d2d4"]
    assert result["fen"] == board.fen()


def test_configure_failure_closes_started_engine(fake_engines):
    path, queue, started = fake_engines
    queue.append(FakeEngine(fail_configure=True))
    analyzer = EngineAnalyzer(path)
    assert analyzer.error.startswith("Не удалось запустить Stockfish")
    assert started[0].closed is True
    analyzer.close()


def test_crash_is_reported_and_engine_restarts_only_once(fake_engines):
    path, queue, started = fake_engines
    queue.extend([FakeEngine([crash()]), FakeEngine([crash()]), FakeEngine([ok()])])
    errors, updates = [], []
    analyzer = EngineAnalyzer(path, on_error=errors.append)

    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)
    assert analyzer.wait(timeout=5)
    assert errors[-1].startswith("Stockfish упал")
    assert analyzer.error == errors[-1]
    assert started[0].closed is True

    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)  # единственный перезапуск
    assert analyzer.wait(timeout=5)
    assert len(started) == 2
    assert errors[-1].startswith("Stockfish снова упал")

    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)  # больше не поднимаем
    assert analyzer.wait(timeout=5)
    assert len(started) == 2
    assert updates == []
    analyzer.close()


def test_successful_analysis_allows_next_restart(fake_engines):
    path, queue, started = fake_engines
    queue.extend([FakeEngine([crash()]), FakeEngine([ok(), crash()]), FakeEngine([ok()])])
    errors, updates = [], []
    analyzer = EngineAnalyzer(path, on_error=errors.append)
    # падение → перезапуск и успех → падение → снова перезапуск и успех
    for _ in range(4):
        analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)
        assert analyzer.wait(timeout=5)
    assert len(started) == 3
    assert [e.split(":")[0] for e in errors] == ["Stockfish упал", "Stockfish упал"]
    assert len(updates) == 2
    assert analyzer.error is None
    analyzer.close()


def test_second_close_does_not_wait_again(fake_engines, monkeypatch):
    # Первый close() ждёт зависшую доставку; второй (из finally в app.py) ждать не должен
    monkeypatch.setattr(engine_module, "STOP_TIMEOUT", 0.2)
    path, queue, started = fake_engines
    queue.append(FakeEngine([ok()]))
    analyzer = EngineAnalyzer(path)
    entered, release = threading.Event(), threading.Event()

    def stuck(_result):
        entered.set()
        release.wait()

    try:
        analyzer.analyze(chess.STARTING_FEN, chess.WHITE, stuck)
        assert entered.wait(timeout=5)
        analyzer.close()
        assert started[0].closed is True
        began = time.monotonic()
        analyzer.close()
        assert time.monotonic() - began < 0.1
    finally:
        release.set()


def test_stop_and_close_do_not_hang_on_stuck_delivery(fake_engines, monkeypatch):
    # Имитация зависшего evaluate_js: колбэк не возвращается, пока его не отпустят
    monkeypatch.setattr(engine_module, "STOP_TIMEOUT", 0.2)
    path, queue, _ = fake_engines
    queue.append(FakeEngine([ok()]))
    analyzer = EngineAnalyzer(path)
    entered, release = threading.Event(), threading.Event()

    def stuck(_result):
        entered.set()
        release.wait()

    try:
        analyzer.analyze(chess.STARTING_FEN, chess.WHITE, stuck)
        assert entered.wait(timeout=5)
        began = time.monotonic()
        analyzer.stop()
        analyzer.close()
        assert time.monotonic() - began < 2.0
    finally:
        release.set()


def test_close_during_slow_restart_still_closes_new_engine(fake_engines, monkeypatch):
    # close() не дождался замка, пока перезапуск висит в configure: новый движок всё равно закрыт
    monkeypatch.setattr(engine_module, "CLOSE_TIMEOUT", 0.2)
    path, queue, started = fake_engines
    queue.extend([FakeEngine([crash()]), FakeEngine([ok()], configure_delay=0.6)])
    analyzer = EngineAnalyzer(path)
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)
    assert analyzer.wait(timeout=5)
    restarter = threading.Thread(
        target=analyzer.analyze, args=(chess.STARTING_FEN, chess.WHITE, lambda _r: None)
    )
    restarter.start()
    time.sleep(0.1)  # перезапуск уже внутри configure и держит замок
    analyzer.close()
    restarter.join(timeout=5)
    assert not restarter.is_alive()
    assert started[1].closed is True


def test_stopping_a_crashed_analysis_does_not_raise(fake_engines):
    path, queue, _ = fake_engines
    dead = chess.engine.EngineTerminatedError("engine process died unexpectedly")
    blocking = FakeAnalysis(block=True, stop_error=dead)
    queue.append(FakeEngine([blocking]))
    analyzer = EngineAnalyzer(path)
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)
    assert blocking.started.wait(timeout=5)
    analyzer.stop()  # не должно бросить EngineTerminatedError
    assert analyzer.wait(timeout=5)
    analyzer.close()


def test_interrupted_analysis_does_not_restore_restart(fake_engines):
    path, queue, started = fake_engines
    blocking = FakeAnalysis(block=True)
    queue.extend([FakeEngine([crash()]), FakeEngine([blocking, crash()]), FakeEngine([ok()])])
    errors = []
    analyzer = EngineAnalyzer(path, on_error=errors.append)
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)  # падение
    assert analyzer.wait(timeout=5)
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)  # перезапуск, анализ «думает»
    assert blocking.started.wait(timeout=5)
    # ход до первого результата прерывает анализ, следующий анализ падает
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)
    assert analyzer.wait(timeout=5)
    assert errors[-1].startswith("Stockfish снова упал")
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)
    assert analyzer.wait(timeout=5)
    assert len(started) == 2
    analyzer.close()


def test_internal_error_is_not_reported_as_engine_crash(fake_engines, monkeypatch):
    def broken(*args):
        raise ValueError("сломанный разбор")

    monkeypatch.setattr(engine_module, "build_result", broken)
    path, queue, started = fake_engines
    queue.append(FakeEngine([ok()]))
    errors = []
    analyzer = EngineAnalyzer(path, on_error=errors.append)
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, lambda _r: None)
    assert analyzer.wait(timeout=5)
    assert errors == ["Ошибка анализа: сломанный разбор"]
    assert analyzer.error is None
    assert started[0].closed is False
    analyzer.close()
