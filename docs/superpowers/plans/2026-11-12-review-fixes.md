# Исправления по ревью — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Цель:** закрыть находки ревью Fable (Important I1–I4, Minor, пробелы в тестах, устаревшие README и спеку), не добавляя новых функций.

**Архитектура:** движок доставляет результаты в окно через отдельный поток-курьер, поэтому `stop()`/`close()` больше не зависают на `evaluate_js`. Каждое изменение позиции получает номер версии `rev`, который приходит и в ответах API, и в результатах анализа: по нему фронт отличает свежие данные от запоздавших. Статус партии строится по `board.outcome()` без `claim_draw`: троекратное повторение и 50 ходов дают лишь «можно потребовать ничью», а подсказки продолжают работать.

**Стек:** Python 3.13, pywebview 6.2.1, python-chess 1.11.2, Stockfish 17.1, chessground 9.2.1, uv, pytest.

## Global Constraints

- Ветка `fix/review-findings` (создана от ветки PR #1 `chore/readme-en-uv`). Не пушить, не трогать другие ветки.
- Тесты: `uv run pytest -q` из корня репозитория. Stockfish лежит в `engine/stockfish.exe`, поэтому движковые тесты не пропускаются. Новые тесты движка не должны требовать Stockfish: процесс подменяется фейком через `monkeypatch`.
- Комментарии в коде и тексты интерфейса — на русском. Сообщения коммитов — на английском, одно предложение, в стиле `feat:`/`fix:`/`docs:`/`test:`, и в конце строка `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (через пустую строку).
- Публичные методы `Api` — ровно `get_state`, `new_game`, `move`, `undo`, `load_fen`, `set_on_top` (их проверяет `test_only_api_methods_are_public`). Всё прочее — с подчёркиванием.
- `frontend/vendor/` не трогать.
- GUI в этой среде не запускается. Фронт проверяется командой `node --check frontend/main.js`.
- Формат `state` после всех задач (поля, которые добавляет `Api`, помечены):

```json
{
  "fen": "…",
  "turn": "white",
  "my_color": "white",
  "dests": {"e2": ["e3", "e4"]},
  "last_move": ["e7", "e5"],
  "status": "playing",
  "draw_reason": null,
  "claimable_draw": null,
  "history": ["e4", "e5"],
  "history_start": {"number": 1, "turn": "white"},
  "error": null,
  "rev": 7,
  "engine_error": null
}
```

  - `status`: `"playing" | "check" | "checkmate" | "stalemate" | "draw"`; `"draw"` — только ничья, наступающая сама: нехватка материала, пятикратное повторение, 75 ходов.
  - `draw_reason`: `null | "insufficient_material" | "fivefold_repetition" | "seventyfive_moves"`.
  - `claimable_draw`: `null | "threefold_repetition" | "fifty_moves"` — только пока партия не окончена.
  - `dests` пуст, когда партия окончена.
  - `rev` и `engine_error` добавляет `Api`. Результат анализа = `build_result(...)` плюс `"rev"`.

## Что сознательно не входит

Адаптивный размер доски (M6), запуск фронта через `get_state` вместо `new_game` (M8: перезагрузка страницы без debug-режима невозможна), настраиваемые параметры движка (M12), тесты фронта, все идеи вне скоупа.

---

### Task 1: Движок — курьер доставки, таймауты, падения, логи

**Files:**
- Modify: `backend/engine.py` (полная замена, код ниже)
- Create: `tests/test_engine_unit.py`
- Modify: `tests/test_engine.py:68-76` (тест `test_stop_prevents_further_updates`)

**Interfaces:**
- Consumes: ничего нового.
- Produces: `EngineAnalyzer(path: Path | None = None, on_error: Callable[[str], None] | None = None)`; `wait(timeout) -> bool`; константы `ENGINE_OPTIONS`, `STOP_TIMEOUT`, `CLOSE_TIMEOUT`. `analyze`, `stop`, `close`, `error`, `build_result`, `resolve_engine_path` — с прежними сигнатурами. Task 3 передаёт `on_error` из `app.py`.

Что закрывает: I1 (процесс не закрывался при ошибке `configure`), I2 (ожидание без таймаута под замками), M1 (падение не доходило до интерфейса, перезапуск был бесконечным), M5 (ошибки глотались без следа), M9 (повторный `close()` снова ждал), часть M10 (тесты `build_result`, падения, перезапуска, повторного `close`, тест `stop` на событии).

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_engine_unit.py`:

```python
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
    """Подмена SimpleAnalysisResult: отдаёт заданные info и, если нужно, «падает»."""

    def __init__(self, infos=(), crash=None):
        self.multipv = list(infos)
        self._infos = list(infos)
        self._crash = crash

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        yield from self._infos
        if self._crash is not None:
            raise self._crash

    def stop(self):
        pass


class FakeEngine:
    """Подмена SimpleEngine: по анализу на каждый вызов analysis()."""

    def __init__(self, analyses=(), fail_configure=False):
        self._analyses = list(analyses)
        self._fail_configure = fail_configure
        self.closed = False

    def configure(self, options):
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
    analyzer.wait(timeout=5)
    assert errors[-1].startswith("Stockfish упал")
    assert analyzer.error == errors[-1]
    assert started[0].closed is True

    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)  # единственный перезапуск
    analyzer.wait(timeout=5)
    assert len(started) == 2
    assert errors[-1].startswith("Stockfish снова упал")

    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)  # больше не поднимаем
    analyzer.wait(timeout=5)
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
        analyzer.wait(timeout=5)
    assert len(started) == 3
    assert [e.split(":")[0] for e in errors] == ["Stockfish упал", "Stockfish упал"]
    assert len(updates) == 2
    assert analyzer.error is None
    analyzer.close()


def test_close_twice_returns_immediately(fake_engines):
    path, queue, started = fake_engines
    queue.append(FakeEngine())
    analyzer = EngineAnalyzer(path)
    analyzer.close()
    assert started[0].closed is True
    began = time.monotonic()
    analyzer.close()
    assert time.monotonic() - began < 0.1


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
```

В `tests/test_engine.py` заменить тест `test_stop_prevents_further_updates` (строки 68-76) на версию с событием вместо `sleep` перед `stop()`:

```python
@needs_engine
def test_stop_prevents_further_updates(analyzer):
    updates = []
    first = threading.Event()

    def collect(result):
        updates.append(result)
        first.set()

    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, collect)
    assert first.wait(timeout=10), "анализ не прислал ни одного результата"
    analyzer.stop()
    count = len(updates)
    time.sleep(0.5)
    assert len(updates) == count
```

- [ ] **Step 2: Убедиться, что новые тесты падают**

Run: `uv run pytest tests/test_engine_unit.py -q`
Expected: тесты `build_result` и `test_close_twice_returns_immediately` проходят (это поведение не меняется), остальные падают: `TypeError: EngineAnalyzer.__init__() got an unexpected keyword argument 'on_error'` у тестов падения, `assert False is True` у `test_configure_failure_closes_started_engine`, `AttributeError` про `STOP_TIMEOUT` у `test_stop_and_close_do_not_hang_on_stuck_delivery` (в старом модуле этой константы нет, поэтому тест падает сразу, а не виснет).

- [ ] **Step 3: Заменить `backend/engine.py` целиком**

```python
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
            if analysis is not None:
                analysis.stop()
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
            if analysis is not None:
                analysis.stop()
            self.wait(timeout=STOP_TIMEOUT)
            engine, self._engine = self._engine, None
            if engine is not None:
                try:
                    engine.quit()
                except (chess.engine.EngineError, TimeoutError):
                    try:
                        engine.close()
                    except Exception:
                        log.exception("Не удалось закрыть Stockfish")
        finally:
            with self._mail:
                self._mail.notify_all()  # курьер увидит _closed и выйдет
            if locked:
                self._api_lock.release()

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
            self._run_once(engine, board, pov, on_update, token)
        except Exception as exc:  # EngineTerminatedError, TimeoutError и всё неожиданное
            self._handle_crash(engine, exc)
        else:
            with self._lock:
                self._can_restart = True  # анализ прошёл: следующему падению снова положен перезапуск
        finally:
            with self._lock:
                self._analysis = None

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
        on_error = self._on_error
        if on_error is not None and not self._closed:
            message = self.error
            self._post(None, lambda: on_error(message))

    def _run_once(self, engine, board: chess.Board, pov: chess.Color, on_update: OnUpdate, token: int) -> None:
        limit = chess.engine.Limit(depth=MAX_DEPTH, time=MAX_TIME)
        expected = min(MULTIPV, board.legal_moves.count())
        last_depth = 0
        last_sent_at = 0.0
        with engine.analysis(board, limit, multipv=MULTIPV) as analysis:
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
                        self._post(token, lambda r=result: on_update(r))
                        last_depth = depth
                        last_sent_at = now
            if token == self._token:
                result = build_result(board, pov, analysis.multipv)
                if result["lines"]:
                    self._post(token, lambda r=result: on_update(r))
```

- [ ] **Step 4: Прогнать тесты движка**

Run: `uv run pytest tests/test_engine_unit.py tests/test_engine.py -q`
Expected: `17 passed` (8 новых + 9 прежних).

- [ ] **Step 5: Прогнать весь набор**

Run: `uv run pytest -q`
Expected: `52 passed`.

- [ ] **Step 6: Коммит**

```bash
git add backend/engine.py tests/test_engine_unit.py tests/test_engine.py
git commit -m "fix: deliver engine results via a courier thread, close the engine on setup failure and report crashes with a single restart"
```

(с трейлером `Co-Authored-By` из Global Constraints через пустую строку)

---

### Task 2: Правила партии — ничья, конец партии, FEN, нумерация

**Files:**
- Modify: `backend/game.py` (полная замена, код ниже)
- Modify: `tests/test_game.py`

**Interfaces:**
- Consumes: ничего нового.
- Produces: в `GameSession.state()` новые поля `draw_reason`, `claimable_draw`, `history_start` (формат — в Global Constraints); `move()` отклоняет ход после конца партии с ошибкой `"Партия окончена — начни новую или отмени ход"`; `dests()` пуст после конца партии; `is_my_turn()` — `True` только на своём ходу, пока `board.outcome()` равен `None`. Сигнатуры методов не меняются.

Что закрывает: I4 (троекратное повторение и 50 ходов больше не обрывают подсказки), противоречие «игра окончена, но фигуры двигаются», M2 (данные для нумерации после FEN с ходом чёрных), M3 (короткий FEN), M4 (причина невалидного FEN), часть M10 (рокировка, взятие на проходе, превращение чёрных со взятием, 50 и 75 ходов).

- [ ] **Step 1: Написать падающие тесты**

В `tests/test_game.py`:

1. В `test_new_game_starts_from_initial_position` после `assert state["error"] is None` добавить:

```python
    assert state["draw_reason"] is None
    assert state["claimable_draw"] is None
    assert state["history_start"] == {"number": 1, "turn": "white"}
```

2. В `test_load_invalid_fen_keeps_position` заменить последнюю строку на:

```python
    assert game.state()["error"] == "Невалидный FEN: не удалось разобрать строку"
```

3. В `test_possible_repetition_is_still_playing` добавить в конец:

```python
    assert g.state()["claimable_draw"] is None
```

4. Тест `test_actual_threefold_repetition_is_draw` заменить на:

```python
def test_threefold_repetition_only_allows_claiming_a_draw(game):
    play(game, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8")
    state = game.state()
    assert state["status"] == "playing"
    assert state["claimable_draw"] == "threefold_repetition"
    assert game.is_my_turn() is True
    assert state["dests"]  # ходы по-прежнему принимаются
```

5. Тест `test_insufficient_material_is_draw` заменить на:

```python
def test_insufficient_material_ends_the_game(game):
    assert game.load_fen("8/8/8/8/8/8/8/k1K5 w - - 0 1") is True
    state = game.state()
    assert state["status"] == "draw"
    assert state["draw_reason"] == "insufficient_material"
    assert state["dests"] == {}
    assert game.move("c1", "c2") is False
    assert game.state()["error"] == "Партия окончена — начни новую или отмени ход"
```

6. В `test_fen_without_kings_is_rejected` добавить в конец:

```python
    assert "нет белого короля" in game.state()["error"]
```

7. Добавить в конец файла новые тесты:

```python
def test_fifty_moves_only_allow_claiming_a_draw(game):
    assert game.load_fen("7k/8/8/8/8/8/R7/K7 w - - 100 80") is True
    state = game.state()
    assert state["status"] == "playing"
    assert state["claimable_draw"] == "fifty_moves"
    assert game.is_my_turn() is True


def test_seventyfive_moves_end_the_game(game):
    assert game.load_fen("7k/8/8/8/8/8/R7/K7 w - - 150 100") is True
    state = game.state()
    assert state["status"] == "draw"
    assert state["draw_reason"] == "seventyfive_moves"
    assert state["claimable_draw"] is None
    assert state["dests"] == {}
    assert game.is_my_turn() is False


def test_castling(game):
    play(game, "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1")
    assert game.board.piece_at(chess.G1) == chess.Piece(chess.KING, chess.WHITE)
    assert game.board.piece_at(chess.F1) == chess.Piece(chess.ROOK, chess.WHITE)
    assert game.state()["history"][-1] == "O-O"


def test_en_passant(game):
    play(game, "e2e4", "a7a6", "e4e5", "d7d5", "e5d6")
    assert game.board.piece_at(chess.D5) is None
    assert game.state()["history"][-1] == "exd6"


def test_black_promotion_with_capture():
    g = GameSession()
    g.new_game("black")
    assert g.load_fen("k7/8/8/8/8/8/1p6/R6K b - - 0 1") is True
    assert g.move("b2", "a1") is True
    assert g.board.piece_at(chess.A1) == chess.Piece(chess.QUEEN, chess.BLACK)
    assert g.state()["history"] == ["bxa1=Q+"]


def test_history_start_after_fen_with_black_to_move(game):
    assert game.load_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    play(game, "e7e5", "g1f3")
    state = game.state()
    assert state["history"] == ["e5", "Nf3"]
    assert state["history_start"] == {"number": 1, "turn": "black"}


def test_short_fen_is_rejected(game):
    assert game.load_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR") is False
    assert game.state()["error"].startswith("Неполный FEN")
    assert game.state()["fen"] == START_FEN


def test_bad_castling_rights_are_explained(game):
    assert game.load_fen("4k3/8/8/8/8/8/8/4K2R w KQkq - 0 1") is False
    assert game.state()["error"] == (
        "Невалидный FEN: права на рокировку не сходятся с положением королей и ладей"
    )
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_game.py -q`
Expected: FAIL — `KeyError: 'draw_reason'`, `KeyError: 'claimable_draw'`, `KeyError: 'history_start'`, неверные тексты ошибок, `status == "draw"` вместо `"playing"` при троекратном повторении. Тесты рокировки и взятия на проходе могут пройти сразу — это нормально, они закрепляют поведение.

- [ ] **Step 3: Заменить `backend/game.py` целиком**

```python
"""Состояние шахматной партии — единственный источник правды для фронта."""
from __future__ import annotations

import chess

COLORS = {"white": chess.WHITE, "black": chess.BLACK}

# Ничьи, которые наступают сами по правилам, без заявления игрока
DRAW_REASONS = {
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
    chess.Termination.SEVENTYFIVE_MOVES: "seventyfive_moves",
}

# Флаги board.status() → понятная причина, почему позиция невозможна
FEN_PROBLEMS = (
    (chess.STATUS_EMPTY, "доска пустая"),
    (chess.STATUS_NO_WHITE_KING, "нет белого короля"),
    (chess.STATUS_NO_BLACK_KING, "нет чёрного короля"),
    (chess.STATUS_TOO_MANY_KINGS, "больше одного короля одного цвета"),
    (chess.STATUS_TOO_MANY_WHITE_PAWNS, "у белых больше 8 пешек"),
    (chess.STATUS_TOO_MANY_BLACK_PAWNS, "у чёрных больше 8 пешек"),
    (chess.STATUS_PAWNS_ON_BACKRANK, "пешка на первой или последней горизонтали"),
    (chess.STATUS_TOO_MANY_WHITE_PIECES, "у белых больше 16 фигур"),
    (chess.STATUS_TOO_MANY_BLACK_PIECES, "у чёрных больше 16 фигур"),
    (chess.STATUS_BAD_CASTLING_RIGHTS, "права на рокировку не сходятся с положением королей и ладей"),
    (chess.STATUS_INVALID_EP_SQUARE, "неверное поле для взятия на проходе"),
    (chess.STATUS_OPPOSITE_CHECK, "под шахом король стороны, которая сейчас не ходит"),
    (chess.STATUS_TOO_MANY_CHECKERS, "невозможный шах: слишком много шахующих фигур"),
    (chess.STATUS_IMPOSSIBLE_CHECK, "невозможный шах"),
)

GAME_OVER_ERROR = "Партия окончена — начни новую или отмени ход"
SHORT_FEN_ERROR = (
    "Неполный FEN: нужны расстановка, чей ход и права на рокировку, например «… w KQkq - 0 1»"
)
UNPARSABLE_FEN_ERROR = "Невалидный FEN: не удалось разобрать строку"


def color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


def describe_invalid(board: chess.Board) -> str:
    status = board.status()
    reasons = [text for flag, text in FEN_PROBLEMS if status & flag]
    return "Невалидный FEN: " + "; ".join(reasons or ["позиция невозможна"])


class GameSession:
    def __init__(self) -> None:
        self.board = chess.Board()
        self.my_color: chess.Color = chess.WHITE
        self.error: str | None = None

    def new_game(self, my_color: str) -> None:
        # Начальная позиция, запоминаем цвет пользователя
        if my_color not in COLORS:
            raise ValueError(f"Неизвестный цвет: {my_color}")
        self.board = chess.Board()
        self.my_color = COLORS[my_color]
        self.error = None

    def move(self, from_sq: str, to_sq: str) -> bool:
        self.error = None
        if self.board.outcome() is not None:
            self.error = GAME_OVER_ERROR
            return False
        try:
            from_idx = chess.parse_square(from_sq)
            to_idx = chess.parse_square(to_sq)
        except ValueError:
            self.error = f"Неверная клетка: {from_sq}-{to_sq}"
            return False
        move = chess.Move(from_idx, to_idx)
        piece = self.board.piece_at(from_idx)
        # Пешка на последней горизонтали всегда превращается в ферзя
        if piece and piece.piece_type == chess.PAWN and chess.square_rank(to_idx) in (0, 7):
            move.promotion = chess.QUEEN
        if move not in self.board.legal_moves:
            self.error = f"Незаконный ход: {from_sq}-{to_sq}"
            return False
        self.board.push(move)
        return True

    def undo(self) -> bool:
        self.error = None
        if not self.board.move_stack:
            return False
        self.board.pop()
        return True

    def load_fen(self, fen: str) -> bool:
        # Цвет пользователя не меняем, история начинается заново
        self.error = None
        if len(fen.split()) < 3:
            # python-chess молча подставил бы «ход белых, без рокировок»
            self.error = SHORT_FEN_ERROR
            return False
        try:
            board = chess.Board(fen)
        except ValueError:
            self.error = UNPARSABLE_FEN_ERROR
            return False
        if not board.is_valid():
            self.error = describe_invalid(board)
            return False
        self.board = board
        return True

    def status(self) -> str:
        return self._status(self.board.outcome())

    def is_my_turn(self) -> bool:
        # Подсказки нужны на своём ходу, пока партия не окончилась сама
        return self.board.turn == self.my_color and self.board.outcome() is None

    def dests(self) -> dict[str, list[str]]:
        if self.board.outcome() is not None:
            return {}  # партия окончена: ходы не принимаются
        result: dict[str, list[str]] = {}
        for move in self.board.legal_moves:
            targets = result.setdefault(chess.square_name(move.from_square), [])
            to = chess.square_name(move.to_square)
            if to not in targets:  # четыре варианта превращения ведут на одну клетку
                targets.append(to)
        return result

    def history(self) -> list[str]:
        replay = self.board.root()
        sans = []
        for move in self.board.move_stack:
            sans.append(replay.san(move))
            replay.push(move)
        return sans

    def state(self) -> dict:
        outcome = self.board.outcome()  # без claim_draw: только окончания, наступающие сами
        root = self.board.root()
        last = self.board.move_stack[-1] if self.board.move_stack else None
        return {
            "fen": self.board.fen(),
            "turn": color_name(self.board.turn),
            "my_color": color_name(self.my_color),
            "dests": self.dests(),
            "last_move": (
                [chess.square_name(last.from_square), chess.square_name(last.to_square)]
                if last
                else None
            ),
            "status": self._status(outcome),
            "draw_reason": DRAW_REASONS.get(outcome.termination) if outcome else None,
            "claimable_draw": None if outcome else self._claimable_draw(),
            "history": self.history(),
            # С какого хода начинается история: после FEN это может быть, например, «12...»
            "history_start": {"number": root.fullmove_number, "turn": color_name(root.turn)},
            "error": self.error,
        }

    def _status(self, outcome: chess.Outcome | None) -> str:
        if outcome is not None:
            if outcome.termination == chess.Termination.CHECKMATE:
                return "checkmate"
            if outcome.termination == chess.Termination.STALEMATE:
                return "stalemate"
            return "draw"
        if self.board.is_check():
            return "check"
        return "playing"

    def _claimable_draw(self) -> str | None:
        # Ничью можно потребовать, но по правилам партия продолжается — подсказки нужны
        if self.board.is_repetition(3):
            return "threefold_repetition"
        if self.board.is_fifty_moves():
            return "fifty_moves"
        return None
```

- [ ] **Step 4: Прогнать тесты партии**

Run: `uv run pytest tests/test_game.py -q`
Expected: `31 passed`.

- [ ] **Step 5: Прогнать весь набор**

Run: `uv run pytest -q`
Expected: `60 passed`.

- [ ] **Step 6: Коммит**

```bash
git add backend/game.py tests/test_game.py
git commit -m "fix: keep hints after a claimable draw, stop accepting moves once the game is over and explain invalid FENs"
```

(с трейлером `Co-Authored-By` через пустую строку)

---

### Task 3: Номер версии позиции, ошибка только в ответе действия, фронт

**Files:**
- Modify: `backend/api.py` (полная замена)
- Modify: `app.py` (полная замена)
- Modify: `frontend/main.js` (полная замена)
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: из Task 1 — `EngineAnalyzer(on_error=...)`; из Task 2 — поля `state`: `draw_reason`, `claimable_draw`, `history_start`.
- Produces: `state["rev"]`; результат анализа с полем `"rev"`; JS-функции `window.onAnalysis(result)` и `window.onEngineError(message)`.

Что закрывает: I3 (потеря подсказки «мат в 1», перестановка ответов), M1 (сообщение о падении движка на фронте), M2 (нумерация на фронте), M5 (логирование включено в приложении), M7 (Enter в поле FEN, подтверждение «Новая за…», «-0.0», Ctrl+Shift+Z и автоповтор, причина ничьей, залипающая ошибка), часть M10 (вместо тавтологичных проверок — проверка `rev` и законности ходов).

- [ ] **Step 1: Написать падающие тесты**

В `tests/test_api.py`:

1. Тест `test_analysis_results_are_pushed` заменить на:

```python
def test_analysis_results_carry_position_rev(setup):
    api, engine, pushed, _ = setup
    state = api.new_game("white")
    engine.on_update({"fen": state["fen"], "depth": 10, "lines": []})
    assert pushed == [{"fen": state["fen"], "depth": 10, "lines": [], "rev": state["rev"]}]
```

2. Добавить после него:

```python
def test_rev_changes_only_when_position_changes(setup):
    api, _, _, _ = setup
    first = api.new_game("white")
    moved = api.move("e2", "e4")
    assert moved["rev"] == first["rev"] + 1
    assert api.move("e7", "e4")["rev"] == moved["rev"]  # незаконный ход позицию не меняет
    assert api.get_state()["rev"] == moved["rev"]
    assert api.undo()["rev"] == moved["rev"] + 1


def test_late_analysis_keeps_its_own_rev(setup):
    api, engine, pushed, _ = setup
    api.new_game("white")
    old_update = engine.on_update
    api.move("e2", "e4")
    state = api.move("e7", "e5")
    old_update({"fen": "old", "depth": 9, "lines": []})
    engine.on_update({"fen": state["fen"], "depth": 9, "lines": []})
    assert [p["rev"] for p in pushed] == [state["rev"] - 2, state["rev"]]


def test_error_belongs_to_the_action_only(setup):
    api, _, _, _ = setup
    api.new_game("white")
    assert api.move("e2", "e5")["error"] == "Незаконный ход: e2-e5"
    assert api.get_state()["error"] is None
    assert api.set_on_top(True)["error"] is None
```

3. В `test_concurrent_calls_do_not_corrupt_board` заменить хвост после `assert errors == []` на:

```python
    board = api._game.board
    replay = board.root()
    for move in board.move_stack:
        # push() не проверяет законность, поэтому проверяем каждый ход явно
        assert replay.is_legal(move)
        replay.push(move)
    assert replay.fen() == board.fen()
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_api.py -q`
Expected: FAIL — `KeyError: 'rev'` и `assert 'Незаконный ход: e2-e5' is None` в `test_error_belongs_to_the_action_only`.

- [ ] **Step 3: Заменить `backend/api.py` целиком**

```python
"""Методы, которые фронт вызывает через window.pywebview.api."""
from __future__ import annotations

import threading
from typing import Callable


class Api:
    def __init__(
        self,
        game,
        engine,
        push_analysis: Callable[[dict], None],
        set_on_top: Callable[[bool], None],
    ) -> None:
        # Атрибуты с подчёркиванием pywebview не пробрасывает в JS
        self._game = game
        self._engine = engine
        self._push_analysis = push_analysis
        self._set_on_top = set_on_top
        # pywebview вызывает каждый метод в отдельном потоке, а GameSession не потокобезопасна
        self._lock = threading.Lock()
        # Номер версии позиции: по нему фронт отличает свежие ответы и анализ от запоздавших
        self._rev = 0

    def get_state(self) -> dict:
        with self._lock:
            return self._state(with_error=False)

    def new_game(self, my_color: str) -> dict:
        with self._lock:
            self._game.new_game(my_color)
            self._position_changed()
            return self._state()

    def move(self, from_sq: str, to_sq: str) -> dict:
        with self._lock:
            if self._game.move(from_sq, to_sq):
                self._position_changed()
            return self._state()

    def undo(self) -> dict:
        with self._lock:
            if self._game.undo():
                self._position_changed()
            return self._state()

    def load_fen(self, fen: str) -> dict:
        with self._lock:
            if self._game.load_fen(fen):
                self._position_changed()
            return self._state()

    def set_on_top(self, flag: bool) -> dict:
        with self._lock:
            self._set_on_top(bool(flag))
            return self._state(with_error=False)

    def _position_changed(self) -> None:
        # Новая версия позиции; подсказки нужны только на ходу пользователя
        self._rev += 1
        if self._game.is_my_turn():
            rev = self._rev
            push = self._push_analysis
            self._engine.analyze(
                self._game.board.fen(),
                self._game.my_color,
                lambda result: push({**result, "rev": rev}),
            )
        else:
            self._engine.stop()

    def _state(self, with_error: bool = True) -> dict:
        state = self._game.state()
        state["rev"] = self._rev
        state["engine_error"] = self._engine.error
        if not with_error:
            state["error"] = None  # ошибка относится только к действию, которое её вызвало
        return state
```

- [ ] **Step 4: Заменить `app.py` целиком**

```python
"""Запуск помогатора: окно pywebview + бэк на Python."""
import json
import logging

import webview

from backend.api import Api
from backend.engine import EngineAnalyzer
from backend.game import GameSession


def main() -> None:
    # Предупреждения и ошибки — в консоль: по ним видно, почему не пришли подсказки
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    holder: dict = {}  # окно создаётся после Api, поэтому храним ссылку здесь

    def run_js(script: str) -> None:
        window = holder.get("window")
        if window is not None:
            window.evaluate_js(script)

    def push_analysis(result: dict) -> None:
        run_js(f"window.onAnalysis({json.dumps(result)})")

    def push_engine_error(message: str) -> None:
        run_js(f"window.onEngineError({json.dumps(message)})")

    def set_on_top(flag: bool) -> None:
        holder["window"].on_top = flag

    game = GameSession()
    engine = EngineAnalyzer(on_error=push_engine_error)
    api = Api(game, engine, push_analysis, set_on_top)
    window = webview.create_window(
        "Шахматный помогатор",
        "frontend/index.html",
        js_api=api,
        width=900,
        height=640,
        min_size=(760, 600),
    )
    holder["window"] = window
    window.events.closed += engine.close
    try:
        webview.start(http_server=True)
    finally:
        # Фоновый поток python-chess не демон: без этого процесс завис бы при сбое start()
        engine.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Заменить `frontend/main.js` целиком**

```javascript
// Фронт помогатора: доска chessground + панель с подсказками.
import { Chessground } from 'chessground';

const BRUSHES = ['green', 'blue', 'yellow'];
const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';
const GAME_OVER_TEXT = { checkmate: 'Мат', stalemate: 'Пат', draw: 'Ничья' };
const DRAW_REASON_TEXT = {
  insufficient_material: 'мало фигур для мата',
  fivefold_repetition: 'пятикратное повторение',
  seventyfive_moves: '75 ходов без взятий и ходов пешек',
};
const CLAIM_TEXT = {
  threefold_repetition: 'троекратное повторение',
  fifty_moves: '50 ходов без взятий и ходов пешек',
};
const CONFIRM_MS = 3000; // столько ждём второго нажатия «Новая за…»

const el = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
let state = null;
let pendingAnalysis = null; // анализ позиции, чьё состояние ещё не дошло до фронта

const cg = Chessground(el('board'), {
  premovable: { enabled: false },
  movable: { free: false, showDests: true, events: { after: onUserMove } },
  highlight: { lastMove: true, check: true },
  animation: { enabled: true, duration: 150 },
});

// Общий вызов бэка: рендерит ответ; при ошибке показывает её и пересинхронизирует доску
async function call(fn) {
  try {
    render(await fn());
  } catch (err) {
    const message = String(err?.message ?? err);
    showError(el('action-error'), message);
    try {
      render(await api().get_state());
      showError(el('action-error'), message); // render мог стереть текст ошибки
    } catch {
      // состояние не получить — оставляем сообщение об ошибке
    }
  }
}

function onUserMove(orig, dest) {
  // старые стрелки сотрёт render, когда придёт новая позиция
  return call(() => api().move(orig, dest));
}

function render(next) {
  // Ответы бэка приходят из разных потоков и могут обогнать друг друга:
  // состояние со старым номером версии уже неактуально
  if (state && next.rev < state.rev) return;
  const changed = !state || next.rev !== state.rev;
  state = next;
  cg.set({
    fen: state.fen,
    orientation: state.my_color,
    turnColor: state.turn,
    lastMove: state.last_move ?? undefined,
    check: state.status === 'check' || state.status === 'checkmate',
    movable: { color: state.turn, dests: new Map(Object.entries(state.dests)) },
  });
  if (changed) clearHints(); // свежие подсказки придут в onAnalysis
  renderStatus();
  // Анализ этой позиции мог прийти раньше её состояния
  if (pendingAnalysis && pendingAnalysis.rev <= state.rev) {
    const result = pendingAnalysis;
    pendingAnalysis = null;
    if (result.rev === state.rev) showAnalysis(result);
  }
}

function clearHints() {
  cg.setAutoShapes([]);
  el('lines').innerHTML = '';
  el('depth').textContent = '';
}

function statusText() {
  const over = GAME_OVER_TEXT[state.status];
  if (over) {
    const reason = DRAW_REASON_TEXT[state.draw_reason];
    return `Игра окончена: ${over}${reason ? ` (${reason})` : ''}`;
  }
  const parts = [state.turn === state.my_color ? 'Твой ход' : 'Ход соперника — повтори его'];
  if (state.status === 'check') parts.push('Шах!');
  const claim = CLAIM_TEXT[state.claimable_draw];
  if (claim) parts.push(`можно потребовать ничью: ${claim}`);
  return parts.join(' · ');
}

function renderStatus() {
  el('status').textContent = statusText();
  showError(el('engine-error'), state.engine_error);
  showError(el('action-error'), state.error);
  el('history').textContent = formatHistory(state.history, state.history_start);
}

function showError(node, text) {
  node.hidden = !text;
  node.textContent = text ?? '';
}

function formatHistory(sans, start) {
  // После FEN с ходом чёрных первая запись выглядит как «12... e5»
  const parts = [];
  let number = start.number;
  let i = 0;
  if (start.turn === 'black' && sans.length > 0) {
    parts.push(`${number}... ${sans[0]}`);
    number += 1;
    i = 1;
  }
  for (; i < sans.length; i += 2, number += 1) {
    parts.push(`${number}. ${sans[i]}${sans[i + 1] ? ' ' + sans[i + 1] : ''}`);
  }
  return parts.join('  ');
}

function formatScore({ cp, mate }) {
  if (mate !== null) return mate > 0 ? `мат в ${mate}` : `тебе мат в ${-mate}`;
  const pawns = cp / 100;
  if (Math.abs(pawns) < 0.05) return '0.0'; // иначе −0.03 показалось бы как «-0.0»
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(1)}`;
}

function showAnalysis(result) {
  if (state.turn !== state.my_color) return; // на ходу соперника подсказки не нужны
  const shapes = result.lines.map((line, i) => ({
    orig: line.uci.slice(0, 2),
    dest: line.uci.slice(2, 4),
    brush: BRUSHES[i],
  }));
  cg.setAutoShapes(shapes.reverse()); // зелёная стрелка рисуется последней, поверх остальных
  el('lines').innerHTML = '';
  result.lines.forEach((line, i) => {
    const li = document.createElement('li');
    li.className = `line-${BRUSHES[i]}`;
    li.textContent = `${line.san}  ${formatScore(line.score)}`;
    el('lines').appendChild(li);
  });
  el('depth').textContent = `Глубина ${result.depth}`;
}

// Бэк вызывает эту функцию через evaluate_js по мере расчёта
window.onAnalysis = (result) => {
  if (state && result.rev < state.rev) return; // анализ старой позиции
  if (!state || result.rev > state.rev) {
    // ответ на действие ещё в пути — покажем анализ, когда придёт состояние
    if (!pendingAnalysis || result.rev >= pendingAnalysis.rev) pendingAnalysis = result;
    return;
  }
  showAnalysis(result);
};

// Бэк сообщает о падении движка сразу, не дожидаясь следующего действия
window.onEngineError = (message) => {
  clearHints();
  showError(el('engine-error'), message);
};

// «Новая за…» стирает партию: если терять есть что, просим нажать второй раз
function confirmNewGame(button, color) {
  const hasGame = state && (state.history.length > 0 || state.fen !== START_FEN);
  if (hasGame && !button.dataset.label) {
    button.dataset.label = button.textContent;
    button.textContent = 'Точно? Нажми ещё раз';
    setTimeout(() => resetConfirm(button), CONFIRM_MS);
    return;
  }
  resetConfirm(button);
  call(() => api().new_game(color));
}

function resetConfirm(button) {
  if (button.dataset.label) {
    button.textContent = button.dataset.label;
    delete button.dataset.label;
  }
}

const loadFen = () => call(() => api().load_fen(el('fen-input').value.trim()));

el('new-white').addEventListener('click', (e) => confirmNewGame(e.currentTarget, 'white'));
el('new-black').addEventListener('click', (e) => confirmNewGame(e.currentTarget, 'black'));
el('undo').addEventListener('click', () => call(() => api().undo()));
el('on-top').addEventListener('change', (e) => call(() => api().set_on_top(e.target.checked)));
el('load-fen').addEventListener('click', loadFen);
el('fen-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') loadFen();
});

document.addEventListener('keydown', (e) => {
  // в текстовом поле Ctrl+Z — это отмена ввода, а не отмена хода; чекбокс не в счёт
  if (e.target?.matches?.('textarea, input:not([type="checkbox"])')) return;
  // KeyZ не зависит от раскладки; Shift/Alt — другие сочетания; автоповтор не отменяет пачку ходов
  if (e.ctrlKey && !e.shiftKey && !e.altKey && !e.metaKey && e.code === 'KeyZ') {
    e.preventDefault();
    if (!e.repeat) call(() => api().undo());
  }
});

function start() {
  return call(() => api().new_game('white'));
}

if (window.pywebview?.api) start();
else window.addEventListener('pywebviewready', start, { once: true });
```

- [ ] **Step 6: Прогнать тесты и проверить синтаксис фронта**

Run: `uv run pytest tests/test_api.py -q`
Expected: `15 passed`.

Run: `node --check frontend/main.js`
Expected: пустой вывод, код возврата 0.

Run: `uv run python -c "import app"`
Expected: пустой вывод (импорт без ошибок; окно не открывается, потому что `main()` не вызывается).

- [ ] **Step 7: Прогнать весь набор**

Run: `uv run pytest -q`
Expected: `63 passed`.

- [ ] **Step 8: Коммит**

```bash
git add backend/api.py app.py frontend/main.js tests/test_api.py
git commit -m "fix: version positions so the UI drops stale responses and keeps early analysis, and show engine crashes and draw reasons"
```

(с трейлером `Co-Authored-By` через пустую строку)

---

### Task 4: README, спека, папка engine

**Files:**
- Modify: `README.md` (полная замена)
- Modify: `docs/superpowers/specs/2026-11-12-chess-helper-design.md` (замена разделов)
- Modify: `.gitignore`
- Create: `engine/.gitkeep` (пустой файл)

**Interfaces:**
- Consumes: поведение из Task 1–3.
- Produces: документация, совпадающая с кодом.

Что закрывает: M11 (`.gitignore` и папка `engine/`), несостыковки 1–10 из ревью.

- [ ] **Step 1: Папка engine**

В `.gitignore` заменить строку `engine/stockfish.exe` двумя строками:

```
engine/*
!engine/.gitkeep
```

Создать пустой файл `engine/.gitkeep`.

Run: `git check-ignore -v engine/stockfish.exe; git status --short engine`
Expected: первая команда печатает правило `engine/*` для `engine/stockfish.exe`; вторая показывает только `?? engine/.gitkeep`.

- [ ] **Step 2: Заменить `README.md` целиком**

````markdown
[Русская версия](#шахматный-помогатор)

# Chess Helper

A window with a chessboard: you mirror the moves of a game in it (both yours and
your opponent's), and on your turn it shows Stockfish's three best moves — the
green arrow is the best one, blue and yellow are the second and third.

The interface is in Russian; the controls below give the button names with
translations.

## Installation (Windows)

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (for
example, `winget install --id=astral-sh.uv -e`) and the WebView2 Runtime
(preinstalled on Windows 11). The commands work in any shell: PowerShell, cmd
or Git Bash.

```bash
uv sync
```

uv creates `.venv` and installs the dependencies pinned in `uv.lock`; if
Python 3.13 is missing, uv downloads it.

Stockfish: download `stockfish-windows-x86-64-avx2.zip` (or
`stockfish-windows-x86-64.zip` if your CPU has no AVX2) from
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1. The
program is in the `stockfish` folder inside the archive (for example
`stockfish-windows-x86-64-avx2.exe`): copy it into the `engine` folder and
rename it to `stockfish.exe`, so the path is `engine/stockfish.exe`. You can
also keep it anywhere and put its full path into the `STOCKFISH_PATH`
environment variable.

## Running

```bash
uv run app.py
```

Errors (for example, why hints did not appear) are printed to the console the
helper was started from.

## Controls

- Drag the pieces for both sides; an illegal move won't go through.
- «Новая за белых» / «Новая за чёрных» (new game as White / Black) — start a new
  game and flip the board accordingly. If the current game has moves or a
  loaded position, click the button a second time to confirm.
- «Отменить» (undo) or Ctrl+Z — take back the last half-move. Holding the keys
  down does not undo several moves.
- «Поверх всех окон» (always on top) — keeps the window above all other
  windows, not just Discord.
- FEN field and «Загрузить» (load) or Enter — set up a position if the game is
  already in progress. The FEN needs at least the piece placement, the side to
  move and the castling rights (for example `… w KQkq - 0 1`).

## Good to know

- To join a game in progress as Black, press «Новая за чёрных» first and only
  then load the FEN: loading a position keeps your colour.
- A pawn always promotes to a queen. If your opponent promotes to another
  piece, set up the resulting position with a FEN.
- After a threefold repetition or 50 moves without captures and pawn moves the
  status says a draw can be claimed, and the hints keep working. The game ends
  by itself only on checkmate, stalemate, insufficient material, fivefold
  repetition or 75 such moves; after that the board accepts no more moves.
- If Stockfish crashes, the panel says so right away and the helper restarts
  it on your next move. If it crashes again before a successful analysis, the
  hints stay off until you restart the helper.

## Tests

```bash
uv run pytest -v
```

## Licenses

The project is licensed under GPL-3.0; the text is in [LICENSE](LICENSE).

The board is [chessground](https://github.com/lichess-org/chessground)
(GPL-3.0); its files are in `frontend/vendor/chessground/`.

---

# Шахматный помогатор

[English version](#chess-helper)

Окно с доской: повторяешь в нём ходы партии (свои и соперника), а на своём ходу
видишь три лучших хода от Stockfish — зелёная стрелка лучший, синяя и жёлтая —
второй и третий.

## Установка (Windows)

Нужны [uv](https://docs.astral.sh/uv/getting-started/installation/) (например,
`winget install --id=astral-sh.uv -e`) и WebView2 Runtime (на Windows 11
установлен по умолчанию). Команды работают в любой консоли: PowerShell, cmd
или Git Bash.

```bash
uv sync
```

uv создаст `.venv` и поставит зависимости, зафиксированные в `uv.lock`; если
Python 3.13 нет, uv скачает его сам.

Stockfish: на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1 скачай
`stockfish-windows-x86-64-avx2.zip` (или `stockfish-windows-x86-64.zip`, если у
процессора нет AVX2). Программа лежит в архиве в папке `stockfish` (например,
`stockfish-windows-x86-64-avx2.exe`): скопируй её в папку `engine` и переименуй
в `stockfish.exe`, чтобы получилось `engine/stockfish.exe`. Можно положить её
куда угодно и указать полный путь в переменной окружения `STOCKFISH_PATH`.

## Запуск

```bash
uv run app.py
```

Ошибки (например, почему не появились подсказки) печатаются в консоль, из
которой запущен помогатор.

## Управление

- Перетаскивай фигуры за обе стороны; незаконный ход не пройдёт.
- «Новая за белых» / «Новая за чёрных» — новая партия и разворот доски. Если в
  текущей партии есть ходы или загруженная позиция, кнопку нужно нажать второй
  раз.
- «Отменить» или Ctrl+Z — отменить последний полуход. Зажатые клавиши не
  отменяют несколько ходов подряд.
- «Поверх всех окон» — окно висит поверх всех остальных окон, а не только
  Discord.
- Поле FEN и «Загрузить» или Enter — поставить позицию, если партия уже идёт. В
  FEN нужны хотя бы расстановка, чей ход и права на рокировку (например
  `… w KQkq - 0 1`).

## Полезно знать

- Чтобы подключиться к идущей партии за чёрных, сначала нажми «Новая за
  чёрных», потом загрузи FEN: загрузка позиции не меняет твой цвет.
- Пешка всегда превращается в ферзя. Если соперник превратил пешку в другую
  фигуру, поставь получившуюся позицию через FEN.
- После троекратного повторения или 50 ходов без взятий и ходов пешек статус
  подскажет, что можно потребовать ничью, а подсказки продолжат работать. Сама
  партия заканчивается только матом, патом, нехваткой фигур для мата,
  пятикратным повторением или 75 такими ходами — после этого доска не
  принимает ходы.
- Если Stockfish упадёт, панель сразу об этом скажет, а помогатор перезапустит
  его на твоём следующем ходу. Если движок упадёт снова до первого удачного
  анализа, подсказки отключатся до перезапуска помогатора.

## Тесты

```bash
uv run pytest -v
```

## Лицензии

Проект распространяется под GPL-3.0, текст — в файле [LICENSE](LICENSE).

Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.
````

- [ ] **Step 3: Обновить спеку**

В `docs/superpowers/specs/2026-11-12-chess-helper-design.md`:

1. Строку `Статус: согласован в обсуждении, ждёт ревью спеки` заменить на
   `Статус: реализован; обновлён 2026-11-12 по итогам ревью кода`.

2. В таблице «Стек» после строки «Тесты» добавить строку:
   `| Зависимости | uv: pyproject.toml + uv.lock, версия Python в .python-version |`

3. Блок кода в разделе «Структура файлов» заменить на:

```
app.py                     # запуск: окно + связка фронта с бэком, логирование
backend/
  __init__.py
  game.py                  # GameSession: состояние партии
  engine.py                # EngineAnalyzer: Stockfish в фоне, MultiPV 3, поток-курьер доставки
  api.py                   # Api: методы, которые вызывает JS; номер версии позиции
frontend/
  index.html               # разметка + import map
  main.js                  # доска, панель, обработка событий
  style.css
  vendor/chessground/      # скопированные файлы chessground
engine/
  .gitkeep                 # папка есть в git; stockfish.exe кладётся вручную и игнорируется
tests/
  test_game.py
  test_engine.py           # с настоящим Stockfish
  test_engine_unit.py      # без Stockfish: процесс движка подменён фейком
  test_api.py
pyproject.toml             # зависимости (uv)
uv.lock
.python-version            # 3.13
README.md                  # как поставить и запустить (английский и русский)
LICENSE                    # GPL-3.0
.gitignore                 # .venv/, node_modules/, engine/* кроме .gitkeep, __pycache__/
```

4. В разделе `backend/game.py` пункт про `move` дополнить предложением:
   `После конца партии (мат, пат, ничья, наступающая сама) ход отклоняется с ошибкой «Партия окончена — начни новую или отмени ход».`
   Пункт про `load_fen` заменить на:
   `- load_fen(fen: str) -> bool — ставит позицию из FEN (на случай, если партия уже идёт); цвет пользователя не меняется, история очищается. Нужны минимум три поля (расстановка, чей ход, рокировки), иначе ошибка «Неполный FEN…». Невалидная позиция → False, позиция не меняется, в ошибке названа причина (например, «нет белого короля»).`
   Пункт про `is_my_turn` заменить на:
   `- is_my_turn() -> bool — ход за пользователем и партия не окончилась сама (board.outcome() без claim_draw равен None).`

5. В разделе `backend/engine.py` после пункта про `close()` добавить пункты:

```
- Результаты в окно доставляет отдельный поток-курьер: воркер кладёт результат
  в «почтовый ящик» на одно место (новый вытесняет недоставленный старый), курьер
  вызывает on_update. Воркер движка никогда не ждёт окно.
- `stop()` ждёт завершения воркера и текущей доставки не дольше STOP_TIMEOUT (2 с);
  `close()` ждёт замок не дольше CLOSE_TIMEOUT (5 с) и закрывает движок в любом
  случае; повторный `close()` возвращается сразу.
- Ошибка `configure` после запуска процесса закрывает процесс.
- О падении движка сообщается сразу через колбэк `on_error` (в окне —
  `window.onEngineError`).
- Ошибки доставки и падения пишутся в лог (`logging`).
```

   Пункт `Если процесс движка упал во время анализа → …` заменить на:
   `- Если процесс движка упал во время анализа → сообщение в панели сразу; при следующем analyze() движок перезапускается один раз. Если он упадёт снова до первого успешного анализа — подсказки отключены до перезапуска приложения. Успешный анализ снова разрешает один перезапуск.`

6. В разделе `backend/api.py` после абзаца про `is_my_turn()` добавить:

```
Каждое изменение позиции (новая партия, ход, отмена, FEN) увеличивает номер версии
`rev`. Он есть в каждом `state` и в каждом результате анализа, поэтому фронт
отбрасывает запоздавшие ответы и не теряет анализ, пришедший раньше ответа на ход.
Ошибка действия (`state.error`) возвращается только в ответе этого действия:
`get_state()` и `set_on_top()` отдают `error: null`.
```

7. В разделе `frontend/main.js`:
   - в перечне панели **Поверх окон** заменить на **Поверх всех окон** (окно поверх всех окон, а не только Discord);
   - пункт `window.onAnalysis(result) игнорирует результат, если result.fen не совпадает с текущей позицией` заменить на:
     `- window.onAnalysis(result) сравнивает result.rev с текущим state.rev: старый отбрасывает, более новый откладывает до прихода его состояния, совпадающий рисует (только на ходу пользователя). Ответ API со старым rev тоже не рисуется.`
   - добавить пункты:

```
- window.onEngineError(message) показывает сообщение о падении движка и стирает подсказки.
- «Новая за белых/чёрных» при непустой партии требует второго нажатия в течение 3 с.
- Enter в поле FEN загружает позицию; Ctrl+Z без Shift/Alt, автоповтор зажатой клавиши игнорируется.
- Статус: «Игра окончена: Ничья (причина)» для ничьей, наступающей самой;
  «… · можно потребовать ничью: троекратное повторение / 50 ходов…» без остановки подсказок.
- История нумеруется от history_start: после FEN с ходом чёрных — «1... e5 2. Nf3».
```

8. В разделе «Форматы данных» JSON `state` заменить на JSON из Global Constraints этого плана (`docs/superpowers/plans/2026-11-12-review-fixes.md`), а список под ним — на:

```
- `status`: `"playing" | "check" | "checkmate" | "stalemate" | "draw"`; `"draw"` — только
  ничья, наступающая сама: нехватка материала, пятикратное повторение, 75 ходов.
- `draw_reason`: `null | "insufficient_material" | "fivefold_repetition" | "seventyfive_moves"`.
- `claimable_draw`: `null | "threefold_repetition" | "fifty_moves"` — партия продолжается,
  подсказки работают.
- `dests` пуст, когда партия окончена.
- `history_start`: номер хода и цвет первого полухода истории (корень — начальная позиция или FEN).
- `last_move`: `null` в начальной позиции.
- `error`: текст ошибки действия (незаконный ход, плохой FEN, партия окончена) или `null`.
- `rev`: номер версии позиции.
```

   В JSON результата анализа после `"depth": 18,` добавить строку `"rev": 7,`.

9. В таблице «Обработка ошибок» строку «Движок упал» заменить на
   `| Движок упал | сообщение в панели сразу; один перезапуск на следующем ходе; повторное падение до успешного анализа — подсказки отключены до перезапуска приложения |`,
   строку «Невалидный FEN» — на
   `| Невалидный или неполный FEN | позиция не меняется, под полем ввода причина |`
   и добавить строки:
   `| Партия окончена сама (мат, пат, нехватка материала, 5-кратное повторение, 75 ходов) | ходы не принимаются, статус с причиной |`
   `| Зависло окно (evaluate_js) | stop()/close() не ждут дольше таймаутов, движок закрывается |`

10. Раздел «Тестирование» дополнить:

```
`tests/test_engine_unit.py` (без Stockfish, процесс подменён фейком):
- `build_result`: знак оценки с точки зрения пользователя, пропуск info без pv/score, меньше трёх линий;
- ошибка `configure` закрывает процесс;
- падение → сообщение → один перезапуск; повторное падение — без перезапуска; успешный анализ снова разрешает перезапуск;
- повторный `close()` мгновенный; зависшая доставка не вешает `stop()`/`close()`.

`tests/test_api.py` (с фейковым движком):
- анализ на своём ходу и остановка на чужом, отмена, FEN;
- `rev` растёт только при смене позиции и приходит в результатах анализа;
- ошибка действия не повторяется в `get_state()`/`set_on_top()`;
- набор публичных методов и параллельные вызовы из нескольких потоков.
```

    В последнем абзаце раздела («Интерфейс проверяется запуском `app.py` вручную…») заменить «поверх окон» на «поверх всех окон».

    В списке `tests/test_game.py` добавить пункты:
    `- рокировка, взятие на проходе, превращение чёрных со взятием;`
    `- троекратное повторение и 50 ходов — «можно потребовать ничью», 75 ходов и нехватка материала — конец партии;`
    `- неполный FEN и причина невалидного FEN; history_start после FEN с ходом чёрных.`

11. Блок кода в разделе «Настройка» заменить на:

```
uv sync                   # .venv и зависимости из uv.lock
# stockfish.exe → engine/
uv run app.py
uv run pytest -q
```

   и убрать из него упоминание `npm install chessground`, добавив после блока абзац:
   `chessground уже скопирован в frontend/vendor/; npm нужен только для обновления его версии.`

- [ ] **Step 4: Проверить**

Run: `uv run pytest -q`
Expected: `63 passed` (документация тесты не меняет).

Run: `git grep -n -i -E "requirements\.txt|поверх окон" -- README.md docs/superpowers/specs`
Expected: пустой вывод («Поверх всех окон» под этот шаблон не попадает).

- [ ] **Step 5: Коммит**

```bash
git add README.md docs/superpowers/specs/2026-11-12-chess-helper-design.md .gitignore engine/.gitkeep
git commit -m "docs: document draw rules, engine crash handling and setup details, and keep the engine folder in git"
```

(с трейлером `Co-Authored-By` через пустую строку)
