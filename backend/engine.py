"""Stockfish в фоновом потоке: три лучших хода для позиции."""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable

import chess
import chess.engine

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "engine" / "stockfish.exe"
MULTIPV = 3
MAX_DEPTH = 20
MAX_TIME = 4.0
MIN_DEPTH_TO_SEND = 8
SEND_INTERVAL = 0.25

OnUpdate = Callable[[dict], None]


def resolve_engine_path() -> Path:
    # Путь можно переопределить переменной окружения STOCKFISH_PATH
    env = os.environ.get("STOCKFISH_PATH")
    return Path(env) if env else DEFAULT_PATH


def build_result(board: chess.Board, pov: chess.Color, infos: list[dict]) -> dict:
    # Превращает ответы движка в формат для фронта; оценка — с точки зрения pov
    lines = []
    depth = 0
    for info in infos:
        pv = info.get("pv")
        score = info.get("score")
        if not pv or score is None:
            continue
        move = pv[0]
        pov_score = score.pov(pov)
        lines.append(
            {
                "uci": move.uci(),
                "san": board.san(move),
                "score": {"cp": pov_score.score(), "mate": pov_score.mate()},
            }
        )
        depth = max(depth, info.get("depth", 0))
    return {"fen": board.fen(), "depth": depth, "lines": lines}


class EngineAnalyzer:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or resolve_engine_path()
        self.error: str | None = None
        self._engine: chess.engine.SimpleEngine | None = None
        self._crashed = False
        self._thread: threading.Thread | None = None
        self._analysis = None  # текущий SimpleAnalysisResult
        self._token = 0  # номер актуального анализа; старые потоки сравнивают с ним
        self._lock = threading.Lock()  # состояние анализа; единственный замок воркера
        self._api_lock = threading.RLock()  # сериализует analyze/stop/close; воркер его не берёт
        self._closed = False
        self._open()

    def _open(self) -> bool:
        if not self.path.exists():
            self.error = f"Не найден Stockfish: положи stockfish.exe в {self.path}"
            return False
        try:
            self._engine = chess.engine.SimpleEngine.popen_uci(str(self.path))
            self._engine.configure({"Threads": 2, "Hash": 128})
        except (chess.engine.EngineError, OSError) as exc:
            self._engine = None
            self.error = f"Не удалось запустить Stockfish: {exc}"
            return False
        self.error = None
        return True

    def analyze(self, fen: str, pov: chess.Color, on_update: OnUpdate) -> None:
        # Весь метод под _api_lock: вызовы приходят из разных потоков pywebview
        with self._api_lock:
            self.stop()
            if self._closed:
                return
            if self._engine is None and self._crashed:
                # Движок упал в прошлый раз — один перезапуск
                self._crashed = False
                self._open()
            if self._engine is None:
                return
            with self._lock:
                self._token += 1
                token = self._token
            board = chess.Board(fen)
            thread = threading.Thread(
                target=self._run, args=(board, pov, on_update, token), daemon=True
            )
            self._thread = thread
            thread.start()

    def stop(self) -> None:
        with self._api_lock:
            with self._lock:
                self._token += 1
                analysis = self._analysis
            if analysis is not None:
                analysis.stop()
            self.wait()

    def wait(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

    def close(self) -> None:
        with self._api_lock:
            self._closed = True
            with self._lock:
                self._token += 1
                analysis = self._analysis
            if analysis is not None:
                analysis.stop()
            # Таймаут нужен: если close() вызван из GUI-потока, а воркер ждёт evaluate_js,
            # бесконечный join дал бы взаимную блокировку
            self.wait(timeout=5)
            engine, self._engine = self._engine, None
            if engine is not None:
                try:
                    engine.quit()
                except (chess.engine.EngineError, TimeoutError):
                    try:
                        engine.close()
                    except Exception:
                        pass

    def _run(self, board: chess.Board, pov: chess.Color, on_update: OnUpdate, token: int) -> None:
        try:
            self._run_once(board, pov, on_update, token)
        except (chess.engine.EngineError, TimeoutError) as exc:  # EngineError включает EngineTerminatedError
            self._crashed = True
            self.error = f"Stockfish упал: {exc}"
            engine, self._engine = self._engine, None
            if engine is not None:
                try:
                    engine.close()
                except Exception:
                    pass
        finally:
            with self._lock:
                self._analysis = None

    def _deliver(self, on_update: OnUpdate, result: dict) -> bool:
        # Ошибка колбэка (например, окно уже закрыто) не означает падение движка
        try:
            on_update(result)
        except Exception:
            return False
        return True

    def _run_once(self, board: chess.Board, pov: chess.Color, on_update: OnUpdate, token: int) -> None:
        limit = chess.engine.Limit(depth=MAX_DEPTH, time=MAX_TIME)
        expected = min(MULTIPV, board.legal_moves.count())
        last_depth = 0
        last_sent_at = 0.0
        with self._engine.analysis(board, limit, multipv=MULTIPV) as analysis:
            with self._lock:
                if token != self._token:
                    return
                self._analysis = analysis
            for info in analysis:
                if token != self._token:
                    return
                if "pv" not in info or info.get("multipv", 1) < expected:
                    continue  # ждём, пока придут все линии текущей глубины
                depth = info.get("depth", 0)
                now = time.monotonic()
                if depth >= MIN_DEPTH_TO_SEND and depth > last_depth and now - last_sent_at >= SEND_INTERVAL:
                    result = build_result(board, pov, analysis.multipv)
                    if result["lines"]:
                        if not self._deliver(on_update, result):
                            return  # колбэк сломан — прекращаем отправку по этому анализу
                        last_depth = depth
                        last_sent_at = now
            if token == self._token:
                result = build_result(board, pov, analysis.multipv)
                if result["lines"]:
                    self._deliver(on_update, result)
