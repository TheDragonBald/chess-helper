"""Stockfish в фоновом потоке: три лучших хода для позиции."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

import chess
import chess.engine

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "engine" / "stockfish.exe"
ENGINE_OPTIONS = {"Threads": 2, "Hash": 128}
MULTIPV = 3
MAX_DEPTH = 20
MAX_TIME = 4.0
MIN_DEPTH_TO_SEND = 8
SEND_INTERVAL = 0.25
STOP_TIMEOUT = 2.0  # сколько stop() ждёт воркер и доставку; дольше — значит что-то зависло
CLOSE_TIMEOUT = 5.0  # сколько close() ждёт замок API, прежде чем закрыть движок без него

OnUpdate = Callable[[dict], None]
OnError = Callable[[str], None]

log = logging.getLogger(__name__)


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
    def __init__(self, path: Path | None = None, on_error: OnError | None = None) -> None:
        self.path = path or resolve_engine_path()
        self.error: str | None = None
        self._on_error = on_error  # сообщить о падении движка сразу, не дожидаясь действия
        self._engine: chess.engine.SimpleEngine | None = None
        self._crashed = False  # движок упал и ещё не перезапускался
        self._can_restart = True  # один перезапуск до следующего успешного анализа
        self._thread: threading.Thread | None = None
        self._analysis = None  # текущий SimpleAnalysisResult
        self._token = 0  # номер актуального анализа; старые потоки сравнивают с ним
        self._lock = threading.Lock()  # состояние анализа; воркер берёт только его
        self._api_lock = threading.RLock()  # сериализует analyze/stop/close; воркер его не берёт
        self._closed = False
        # Результаты в окно доставляет отдельный поток-курьер: воркер движка никогда
        # не ждёт evaluate_js, поэтому stop() и close() не зависнут вместе с окном
        self._mail = threading.Condition()
        self._outbox: tuple[int | None, Callable[[], None]] | None = None
        self._delivering = False
        threading.Thread(target=self._courier_loop, daemon=True, name="engine-courier").start()
        self._open()

    def _open(self) -> bool:
        if not self.path.exists():
            self.error = f"Не найден Stockfish: положи stockfish.exe в {self.path}"
            return False
        engine = None
        try:
            engine = chess.engine.SimpleEngine.popen_uci(str(self.path))
            engine.configure(ENGINE_OPTIONS)
        except (chess.engine.EngineError, OSError) as exc:
            # Процесс мог успеть запуститься: без close() он и поток python-chess
            # не дадут приложению завершиться
            if engine is not None:
                try:
                    engine.close()
                except Exception:
                    log.exception("Не удалось закрыть движок после ошибки запуска")
            self.error = f"Не удалось запустить Stockfish: {exc}"
            log.warning(self.error)
            return False
        self._engine = engine
        self.error = None
        return True

    def analyze(self, fen: str, pov: chess.Color, on_update: OnUpdate) -> None:
        # Весь метод под _api_lock: вызовы приходят из разных потоков pywebview
        with self._api_lock:
            self.stop()
            if self._closed:
                return
            with self._lock:
                restart = self._engine is None and self._crashed and self._can_restart
                if restart:
                    self._crashed = False
                    self._can_restart = False
            if restart:
                self._open()  # движок упал — единственный перезапуск
                if self._closed:
                    # close() не дождался замка и отработал, пока шёл перезапуск: новый движок закрываем сами
                    self._shutdown_engine()
                    return
            engine = self._engine
            if engine is None:
                return
            with self._lock:
                self._token += 1
                token = self._token
            board = chess.Board(fen)
            thread = threading.Thread(
                target=self._run, args=(engine, board, pov, on_update, token), daemon=True
            )
            self._thread = thread
            thread.start()

    def stop(self) -> None:
        with self._api_lock:
            with self._lock:
                self._token += 1
                analysis = self._analysis
            self._stop_analysis(analysis)
            # Воркер не ждёт окно, поэтому завершается быстро; зависшую доставку не ждём дольше таймаута
            self.wait(timeout=STOP_TIMEOUT)

    def wait(self, timeout: float | None = None) -> bool:
        # Ждёт конца анализа и доставки его последнего результата; True — если дождались
        deadline = None if timeout is None else time.monotonic() + timeout
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)
            if thread.is_alive():
                return False
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        with self._mail:
            return self._mail.wait_for(
                lambda: self._outbox is None and not self._delivering, remaining
            )

    def close(self) -> None:
        # Замок берём с таймаутом: если analyze/stop завис, движок всё равно надо закрыть
        locked = self._api_lock.acquire(timeout=CLOSE_TIMEOUT)
        try:
            if self._closed and self._engine is None:
                return  # уже закрыт: повторный вызов из finally в app.py ничего не ждёт
            self._closed = True
            with self._lock:
                self._token += 1
                analysis = self._analysis
            self._stop_analysis(analysis)
            self.wait(timeout=STOP_TIMEOUT)
            self._shutdown_engine()
        finally:
            with self._mail:
                self._mail.notify_all()  # курьер увидит _closed и выйдет
            if locked:
                self._api_lock.release()

    @staticmethod
    def _stop_analysis(analysis) -> None:
        if analysis is None:
            return
        try:
            analysis.stop()
        except chess.engine.EngineError:
            pass  # движок уже упал или выключен — останавливать нечего

    def _shutdown_engine(self) -> None:
        engine, self._engine = self._engine, None
        if engine is None:
            return
        try:
            engine.quit()
        except (chess.engine.EngineError, TimeoutError):
            try:
                engine.close()
            except Exception:
                log.exception("Не удалось закрыть Stockfish")

    def _notify_error(self, message: str) -> None:
        # Сообщение об ошибке идёт тем же курьером, что и результаты; после close() не шлём
        on_error = self._on_error
        if on_error is not None and not self._closed:
            self._post(None, lambda: on_error(message))

    def _post(self, token: int | None, send: Callable[[], None]) -> None:
        # Кладёт доставку в «почтовый ящик»; новое сообщение вытесняет недоставленное старое
        with self._mail:
            self._outbox = (token, send)
            self._mail.notify_all()

    def _courier_loop(self) -> None:
        while True:
            with self._mail:
                self._mail.wait_for(lambda: self._outbox is not None or self._closed)
                if self._outbox is None:
                    return  # анализатор закрыт, доставлять нечего
                token, send = self._outbox
                self._outbox = None
                # Чтение int атомарно; token None — сообщение об ошибке, оно не устаревает
                if token is not None and token != self._token:
                    self._mail.notify_all()
                    continue  # позиция уже сменилась
                self._delivering = True
            try:
                send()
            except Exception:
                # Например, окно уже закрыто или onAnalysis бросил исключение в JS
                log.exception("Не удалось доставить сообщение движка в окно")
            finally:
                with self._mail:
                    self._delivering = False
                    self._mail.notify_all()

    def _run(self, engine, board: chess.Board, pov: chess.Color, on_update: OnUpdate, token: int) -> None:
        try:
            delivered = self._run_once(engine, board, pov, on_update, token)
        except (chess.engine.EngineError, TimeoutError) as exc:  # EngineError включает EngineTerminatedError
            self._handle_crash(engine, exc)
        except Exception as exc:
            # Ошибка в нашем коде, а не в Stockfish: движок исправен, его не трогаем
            log.exception("Ошибка при разборе анализа")
            self._notify_error(f"Ошибка анализа: {exc}")
        else:
            if delivered:
                with self._lock:
                    self._can_restart = True  # успешный анализ снова разрешает один перезапуск

    def _handle_crash(self, engine, exc: Exception) -> None:
        log.error("Stockfish упал во время анализа", exc_info=exc)
        with self._lock:
            restart = self._can_restart
            self._crashed = True
            if self._engine is engine:
                self._engine = None
        try:
            engine.close()
        except Exception:
            log.exception("Не удалось закрыть упавший Stockfish")
        if restart:
            self.error = f"Stockfish упал: {exc}. Перезапущу его на следующем ходе"
        else:
            self.error = f"Stockfish снова упал: {exc}. Подсказки отключены — перезапусти помогатор"
        self._notify_error(self.error)

    def _run_once(self, engine, board: chess.Board, pov: chess.Color, on_update: OnUpdate, token: int) -> bool:
        # Возвращает True, если в окно ушёл хотя бы один результат
        limit = chess.engine.Limit(depth=MAX_DEPTH, time=MAX_TIME)
        expected = min(MULTIPV, board.legal_moves.count())
        last_depth = 0
        last_sent_at = 0.0
        delivered = False
        with engine.analysis(board, limit, multipv=MULTIPV) as analysis:
            with self._lock:
                if token != self._token:
                    return False
                self._analysis = analysis
            try:
                for info in analysis:
                    if token != self._token:
                        return delivered
                    if "pv" not in info or info.get("multipv", 1) < expected:
                        continue  # ждём, пока придут все линии текущей глубины
                    depth = info.get("depth", 0)
                    now = time.monotonic()
                    if depth >= MIN_DEPTH_TO_SEND and depth > last_depth and now - last_sent_at >= SEND_INTERVAL:
                        result = build_result(board, pov, analysis.multipv)
                        if result["lines"]:
                            self._post(token, lambda r=result: on_update(r))
                            delivered = True
                            last_depth = depth
                            last_sent_at = now
                if token == self._token:
                    result = build_result(board, pov, analysis.multipv)
                    if result["lines"]:
                        self._post(token, lambda r=result: on_update(r))
                        delivered = True
                return delivered
            finally:
                with self._lock:
                    # Осиротевший воркер (stop() не дождался его) не должен сбросить чужой анализ
                    if self._analysis is analysis:
                        self._analysis = None
