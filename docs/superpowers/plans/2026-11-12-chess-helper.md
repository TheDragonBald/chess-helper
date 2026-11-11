# Шахматный помогатор — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Десктоп-окно с шахматной доской, где пользователь вручную повторяет ходы партии из Discord, а на его ходу видит три лучших хода от Stockfish (стрелки + список с оценкой).

**Architecture:** `pywebview` открывает нативное окно и показывает фронт на чистом JS (доска `chessground`). Фронт вызывает Python-методы через `pywebview.api`. Бэк держит партию (`python-chess`) и гоняет `stockfish.exe` в фоновом потоке, отправляя результаты во фронт через `window.evaluate_js`.

**Tech Stack:** Python 3.13, pywebview 6.2.1, chess (python-chess) 1.11.2, pytest, Stockfish 17.x (Windows x64), chessground 9.2.1 (ES-модули, без сборщика).

Спека: `docs/superpowers/specs/2026-11-12-chess-helper-design.md`.

## Global Constraints

- Python строго 3.13 (`py -3.13`), виртуальное окружение `.venv` в корне проекта.
- Движок: `engine/stockfish.exe`, путь переопределяется переменной окружения `STOCKFISH_PATH`.
- Настройки движка: `MultiPV = 3` (через параметр `multipv` анализа), `Threads = 2`, `Hash = 128`.
- Анализ заканчивается при глубине 20 или через 4 секунды — что раньше.
- Обновления анализа во фронт: при росте глубины, начиная с глубины 8, не чаще раза в 250 мс; финальный результат отправляется всегда.
- Оценка всегда с точки зрения пользователя: плюс — хорошо для пользователя.
- Подсказки только на ходу пользователя; на ходу соперника стрелки и список пустые.
- Превращение пешки — всегда в ферзя.
- Стрелки: 1-й ход кисть `green`, 2-й `blue`, 3-й `yellow`.
- Комментарии в коде — на русском; сообщения коммитов — на английском, с трейлером `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `frontend/vendor/chessground/` коммитится; `engine/stockfish.exe`, `.venv/`, `node_modules/` — нет.
- Все команды выполняются из корня проекта в Git Bash.

## Структура файлов

| Файл | Ответственность |
|---|---|
| `requirements.txt` | зависимости Python |
| `pytest.ini` | корень импорта для тестов |
| `.gitignore` | что не коммитим |
| `backend/__init__.py` | пакет бэка |
| `backend/game.py` | `GameSession` — состояние партии, без движка и окна |
| `backend/engine.py` | `EngineAnalyzer` — Stockfish в фоне, MultiPV 3 |
| `backend/api.py` | `Api` — методы для JS, решает, когда запускать анализ |
| `app.py` | запуск окна, связка фронта и бэка |
| `frontend/index.html` | разметка, import map |
| `frontend/main.js` | доска, панель, события |
| `frontend/style.css` | стили |
| `frontend/vendor/chessground/` | файлы chessground (dist + assets + LICENSE) |
| `tests/test_game.py` | тесты партии |
| `tests/test_engine.py` | тесты движка (с настоящим Stockfish) |
| `tests/test_api.py` | тесты `Api` с фейковым движком |
| `README.md` | установка и запуск |

---

### Task 1: Окружение и состояние партии (`GameSession`)

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `backend/__init__.py`, `backend/game.py`
- Test: `tests/test_game.py`

**Interfaces:**
- Consumes: ничего.
- Produces:
  - `backend.game.GameSession()` — атрибуты `board: chess.Board`, `my_color: chess.Color`, `error: str | None`.
  - `new_game(my_color: str) -> None` (`"white"`/`"black"`, иначе `ValueError`)
  - `move(from_sq: str, to_sq: str) -> bool`
  - `undo() -> bool`
  - `load_fen(fen: str) -> bool`
  - `status() -> str` (`"playing" | "check" | "checkmate" | "stalemate" | "draw"`)
  - `is_my_turn() -> bool`
  - `dests() -> dict[str, list[str]]`
  - `history() -> list[str]` (SAN)
  - `state() -> dict` с ключами `fen, turn, my_color, dests, last_move, status, history, error` (ключ `engine_error` добавляет `Api`).

- [ ] **Step 1: Создать окружение и служебные файлы**

`requirements.txt`:
```
pywebview==6.2.1
chess==1.11.2
pytest>=8
```

`pytest.ini`:
```ini
[pytest]
pythonpath = .
testpaths = tests
```

`.gitignore`:
```
.venv/
node_modules/
__pycache__/
.pytest_cache/
engine/stockfish.exe
.vendor-tmp/
.sf-tmp/
```

`backend/__init__.py` — пустой файл.

Run:
```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```
Expected: `Successfully installed ... chess-1.11.2 ... pywebview-6.2.1 ...` (плюс зависимости вроде `pythonnet`, `bottle`, `proxy_tools`).

- [ ] **Step 2: Написать падающие тесты**

`tests/test_game.py`:
```python
import chess
import pytest

from backend.game import GameSession

START_FEN = chess.STARTING_FEN
PROMO_FEN = "8/P7/8/8/8/8/8/k6K w - - 0 1"


@pytest.fixture
def game():
    g = GameSession()
    g.new_game("white")
    return g


def play(g, *moves):
    # Удобный помощник: ходы в формате "e2e4"
    for m in moves:
        assert g.move(m[:2], m[2:4]), f"ход {m} не прошёл"


def test_new_game_starts_from_initial_position(game):
    state = game.state()
    assert state["fen"] == START_FEN
    assert state["turn"] == "white"
    assert state["my_color"] == "white"
    assert state["last_move"] is None
    assert state["history"] == []
    assert state["status"] == "playing"
    assert state["error"] is None


def test_new_game_rejects_unknown_color():
    with pytest.raises(ValueError):
        GameSession().new_game("green")


def test_legal_move_changes_position(game):
    assert game.move("e2", "e4") is True
    state = game.state()
    assert state["turn"] == "black"
    assert state["last_move"] == ["e2", "e4"]
    assert state["history"] == ["e4"]
    assert state["error"] is None


def test_illegal_move_keeps_position(game):
    assert game.move("e2", "e5") is False
    state = game.state()
    assert state["fen"] == START_FEN
    assert state["error"] == "Незаконный ход: e2-e5"


def test_bad_square_is_rejected(game):
    assert game.move("z9", "e4") is False
    assert game.state()["fen"] == START_FEN
    assert game.state()["error"] == "Неверная клетка: z9-e4"


def test_pawn_auto_promotes_to_queen(game):
    assert game.load_fen(PROMO_FEN)
    assert game.move("a7", "a8") is True
    assert game.board.piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)


def test_undo_reverts_half_move(game):
    play(game, "e2e4")
    assert game.undo() is True
    assert game.state()["fen"] == START_FEN


def test_undo_on_empty_history_returns_false(game):
    assert game.undo() is False


def test_dests_format(game):
    dests = game.state()["dests"]
    assert sorted(dests["e2"]) == ["e3", "e4"]
    assert sorted(dests["g1"]) == ["f3", "h3"]
    assert "e7" not in dests  # сейчас ход белых


def test_promotion_dests_are_not_duplicated(game):
    game.load_fen(PROMO_FEN)
    assert game.state()["dests"]["a7"] == ["a8"]


def test_check_status(game):
    game.load_fen("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1")
    assert game.state()["status"] == "check"


def test_checkmate_status(game):
    # Детский мат
    play(game, "e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    assert game.state()["status"] == "checkmate"


def test_stalemate_status(game):
    game.load_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert game.state()["status"] == "stalemate"


def test_is_my_turn_for_white(game):
    assert game.is_my_turn() is True
    play(game, "e2e4")
    assert game.is_my_turn() is False


def test_is_my_turn_for_black():
    g = GameSession()
    g.new_game("black")
    assert g.is_my_turn() is False
    play(g, "e2e4")
    assert g.is_my_turn() is True


def test_no_turn_after_checkmate():
    g = GameSession()
    g.new_game("black")
    play(g, "e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    assert g.board.turn == chess.BLACK
    assert g.is_my_turn() is False


def test_load_valid_fen(game):
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    play(game, "d2d4")
    assert game.load_fen(fen) is True
    state = game.state()
    assert state["fen"] == fen
    assert state["history"] == []


def test_load_invalid_fen_keeps_position(game):
    assert game.load_fen("not a fen") is False
    assert game.state()["fen"] == START_FEN
    assert game.state()["error"] == "Невалидный FEN"


def test_load_fen_keeps_my_color():
    g = GameSession()
    g.new_game("black")
    assert g.load_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    assert g.state()["my_color"] == "black"
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `.venv/Scripts/python -m pytest tests/test_game.py -v`
Expected: ошибка сбора `ModuleNotFoundError: No module named 'backend.game'`.

- [ ] **Step 4: Реализовать `GameSession`**

`backend/game.py`:
```python
"""Состояние шахматной партии — единственный источник правды для фронта."""
from __future__ import annotations

import chess

COLORS = {"white": chess.WHITE, "black": chess.BLACK}


def color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


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
        try:
            board = chess.Board(fen)
        except ValueError:
            self.error = "Невалидный FEN"
            return False
        if not board.is_valid():
            self.error = "Невалидный FEN"
            return False
        self.board = board
        return True

    def status(self) -> str:
        if self.board.is_checkmate():
            return "checkmate"
        if self.board.is_stalemate():
            return "stalemate"
        if self.board.is_game_over(claim_draw=True):
            return "draw"
        if self.board.is_check():
            return "check"
        return "playing"

    def is_my_turn(self) -> bool:
        return self.board.turn == self.my_color and self.status() in ("playing", "check")

    def dests(self) -> dict[str, list[str]]:
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
            "status": self.status(),
            "history": self.history(),
            "error": self.error,
        }
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `.venv/Scripts/python -m pytest tests/test_game.py -v`
Expected: `19 passed`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt pytest.ini .gitignore backend/__init__.py backend/game.py tests/test_game.py
git commit -m "feat: add game session with legal move handling" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Stockfish и анализатор (`EngineAnalyzer`)

**Files:**
- Create: `engine/stockfish.exe` (скачивается, в git не попадает), `backend/engine.py`
- Test: `tests/test_engine.py`

**Interfaces:**
- Consumes: ничего из Task 1 (работает с FEN-строками и `chess.Color`).
- Produces:
  - `backend.engine.resolve_engine_path() -> pathlib.Path`
  - `backend.engine.build_result(board: chess.Board, pov: chess.Color, infos: list[dict]) -> dict`
  - `backend.engine.EngineAnalyzer(path: Path | None = None)` — атрибут `error: str | None`
  - `analyze(fen: str, pov: chess.Color, on_update: Callable[[dict], None]) -> None`
  - `stop() -> None`, `wait(timeout: float | None = None) -> None`, `close() -> None`
  - Формат результата: `{"fen": str, "depth": int, "lines": [{"uci": str, "san": str, "score": {"cp": int | None, "mate": int | None}}]}`

- [ ] **Step 1: Скачать Stockfish**

> Это загрузка файла из интернета (~50 МБ, официальный релиз `official-stockfish/Stockfish` на GitHub). Перед выполнением спросить разрешения у пользователя.

Run:
```bash
mkdir -p .sf-tmp engine
curl -L -o .sf-tmp/sf.zip https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-windows-x86-64-avx2.zip
py -3.13 -I -m zipfile -e .sf-tmp/sf.zip .sf-tmp/
cp .sf-tmp/stockfish/stockfish-windows-x86-64-avx2.exe engine/stockfish.exe
rm -rf .sf-tmp
printf "uci\nquit\n" | engine/stockfish.exe | grep -m1 "id name"
```
Expected: строка вида `id name Stockfish 17.1`.
Если вывода нет или процесс падает (процессор без AVX2) — повторить с архивом `stockfish-windows-x86-64.zip` и файлом `stockfish/stockfish-windows-x86-64.exe`.

- [ ] **Step 2: Написать падающие тесты**

`tests/test_engine.py`:
```python
import time
from pathlib import Path

import chess
import pytest

from backend.engine import EngineAnalyzer, resolve_engine_path

needs_engine = pytest.mark.skipif(
    not resolve_engine_path().exists(), reason="нет engine/stockfish.exe"
)

MATE_IN_ONE = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
WHITE_WITHOUT_QUEEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"


@pytest.fixture
def analyzer():
    a = EngineAnalyzer()
    yield a
    a.close()


def run_to_end(analyzer, fen, pov):
    updates = []
    analyzer.analyze(fen, pov, updates.append)
    analyzer.wait(timeout=15)
    assert updates, "анализ не прислал ни одного результата"
    return updates


def test_missing_engine_sets_error_and_does_not_crash():
    a = EngineAnalyzer(Path("нет/такого/stockfish.exe"))
    assert a.error is not None
    updates = []
    a.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)
    a.wait(timeout=1)
    assert updates == []
    a.close()


@needs_engine
def test_mate_in_one_is_first_line(analyzer):
    final = run_to_end(analyzer, MATE_IN_ONE, chess.WHITE)[-1]
    first = final["lines"][0]
    assert first["uci"] == "a1a8"
    assert first["san"] == "Ra8#"
    assert first["score"] == {"cp": None, "mate": 1}
    assert final["fen"] == MATE_IN_ONE


@needs_engine
def test_start_position_returns_three_lines(analyzer):
    final = run_to_end(analyzer, chess.STARTING_FEN, chess.WHITE)[-1]
    assert len(final["lines"]) == 3
    assert final["depth"] >= 8
    assert len({line["uci"] for line in final["lines"]}) == 3


@needs_engine
def test_score_is_from_users_point_of_view(analyzer):
    # У белых нет ферзя: для чёрных оценка должна быть сильно в плюс
    final = run_to_end(analyzer, WHITE_WITHOUT_QUEEN, chess.BLACK)[-1]
    assert final["lines"][0]["score"]["cp"] > 300


@needs_engine
def test_stop_prevents_further_updates(analyzer):
    updates = []
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)
    time.sleep(0.3)
    analyzer.stop()
    count = len(updates)
    time.sleep(1.0)
    assert len(updates) == count


@needs_engine
def test_new_analysis_replaces_old_one(analyzer):
    first, second = [], []
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, first.append)
    analyzer.analyze(MATE_IN_ONE, chess.WHITE, second.append)
    analyzer.wait(timeout=15)
    assert second and second[-1]["fen"] == MATE_IN_ONE
    assert all(r["fen"] == chess.STARTING_FEN for r in first)
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `.venv/Scripts/python -m pytest tests/test_engine.py -v`
Expected: ошибка сбора `ModuleNotFoundError: No module named 'backend.engine'`.

- [ ] **Step 4: Реализовать `EngineAnalyzer`**

`backend/engine.py`:
```python
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
        self._lock = threading.Lock()
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
        self.stop()
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
        self._thread = threading.Thread(
            target=self._run, args=(board, pov, on_update, token), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
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
        self.stop()
        if self._engine is not None:
            try:
                self._engine.quit()
            except chess.engine.EngineError:
                pass
            self._engine = None

    def _run(self, board: chess.Board, pov: chess.Color, on_update: OnUpdate, token: int) -> None:
        try:
            self._run_once(board, pov, on_update, token)
        except chess.engine.EngineError as exc:  # включает EngineTerminatedError
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
                        on_update(result)
                        last_depth = depth
                        last_sent_at = now
            if token == self._token:
                result = build_result(board, pov, analysis.multipv)
                if result["lines"]:
                    on_update(result)
```

- [ ] **Step 5: Убедиться, что тесты проходят**

Run: `.venv/Scripts/python -m pytest tests/test_engine.py -v`
Expected: `6 passed` (тесты с движком занимают ~15 секунд).

- [ ] **Step 6: Прогнать все тесты**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `25 passed`.

- [ ] **Step 7: Commit**

```bash
git add backend/engine.py tests/test_engine.py
git commit -m "feat: add background Stockfish analyzer with top-3 lines" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: API для фронта (`Api`)

**Files:**
- Create: `backend/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `GameSession` (Task 1): `new_game`, `move`, `undo`, `load_fen`, `is_my_turn`, `state`, `board`, `my_color`. `EngineAnalyzer` (Task 2): `analyze(fen, pov, on_update)`, `stop()`, атрибут `error`.
- Produces: `backend.api.Api(game, engine, push_analysis: Callable[[dict], None], set_on_top: Callable[[bool], None])` с публичными методами (все возвращают `state` с ключом `engine_error`):
  `get_state()`, `new_game(my_color: str)`, `move(from_sq: str, to_sq: str)`, `undo()`, `load_fen(fen: str)`, `set_on_top(flag: bool)`.
  Все остальные атрибуты начинаются с `_`, чтобы pywebview не пробрасывал их в JS.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_api.py`:
```python
import chess
import pytest

from backend.api import Api
from backend.game import GameSession


class FakeEngine:
    def __init__(self):
        self.calls = []
        self.error = None
        self.on_update = None

    def analyze(self, fen, pov, on_update):
        self.calls.append(("analyze", fen, pov))
        self.on_update = on_update

    def stop(self):
        self.calls.append(("stop",))


@pytest.fixture
def setup():
    engine = FakeEngine()
    pushed, on_top = [], []
    api = Api(GameSession(), engine, pushed.append, on_top.append)
    return api, engine, pushed, on_top


def test_new_game_as_white_starts_analysis(setup):
    api, engine, _, _ = setup
    state = api.new_game("white")
    assert state["fen"] == chess.STARTING_FEN
    assert engine.calls[-1] == ("analyze", chess.STARTING_FEN, chess.WHITE)


def test_new_game_as_black_stops_analysis(setup):
    api, engine, _, _ = setup
    state = api.new_game("black")
    assert state["my_color"] == "black"
    assert engine.calls[-1] == ("stop",)


def test_opponent_turn_stops_analysis(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    api.move("e2", "e4")
    assert engine.calls[-1] == ("stop",)


def test_my_turn_as_black_starts_analysis(setup):
    api, engine, _, _ = setup
    api.new_game("black")
    state = api.move("e2", "e4")
    assert engine.calls[-1] == ("analyze", state["fen"], chess.BLACK)


def test_illegal_move_does_not_touch_engine(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    calls_before = len(engine.calls)
    state = api.move("e2", "e5")
    assert state["error"] == "Незаконный ход: e2-e5"
    assert len(engine.calls) == calls_before


def test_undo_back_to_my_turn_restarts_analysis(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    api.move("e2", "e4")
    state = api.undo()
    assert engine.calls[-1] == ("analyze", state["fen"], chess.WHITE)


def test_load_fen_reanalyzes(setup):
    api, engine, _, _ = setup
    api.new_game("black")
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    api.load_fen(fen)
    assert engine.calls[-1] == ("analyze", fen, chess.BLACK)


def test_state_contains_engine_error(setup):
    api, engine, _, _ = setup
    engine.error = "Не найден Stockfish"
    assert api.get_state()["engine_error"] == "Не найден Stockfish"


def test_analysis_results_are_pushed(setup):
    api, engine, pushed, _ = setup
    api.new_game("white")
    engine.on_update({"fen": "x", "depth": 10, "lines": []})
    assert pushed == [{"fen": "x", "depth": 10, "lines": []}]


def test_set_on_top_passes_flag(setup):
    api, _, _, on_top = setup
    api.set_on_top(True)
    api.set_on_top(False)
    assert on_top == [True, False]


def test_only_api_methods_are_public(setup):
    api, _, _, _ = setup
    public = {name for name in dir(api) if not name.startswith("_")}
    assert public == {"get_state", "new_game", "move", "undo", "load_fen", "set_on_top"}
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `.venv/Scripts/python -m pytest tests/test_api.py -v`
Expected: ошибка сбора `ModuleNotFoundError: No module named 'backend.api'`.

- [ ] **Step 3: Реализовать `Api`**

`backend/api.py`:
```python
"""Методы, которые фронт вызывает через window.pywebview.api."""
from __future__ import annotations

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

    def get_state(self) -> dict:
        return self._state()

    def new_game(self, my_color: str) -> dict:
        self._game.new_game(my_color)
        self._refresh_analysis()
        return self._state()

    def move(self, from_sq: str, to_sq: str) -> dict:
        if self._game.move(from_sq, to_sq):
            self._refresh_analysis()
        return self._state()

    def undo(self) -> dict:
        if self._game.undo():
            self._refresh_analysis()
        return self._state()

    def load_fen(self, fen: str) -> dict:
        if self._game.load_fen(fen):
            self._refresh_analysis()
        return self._state()

    def set_on_top(self, flag: bool) -> dict:
        self._set_on_top(bool(flag))
        return self._state()

    def _refresh_analysis(self) -> None:
        # Подсказки нужны только на ходу пользователя
        if self._game.is_my_turn():
            self._engine.analyze(self._game.board.fen(), self._game.my_color, self._push_analysis)
        else:
            self._engine.stop()

    def _state(self) -> dict:
        state = self._game.state()
        state["engine_error"] = self._engine.error
        return state
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `36 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/api.py tests/test_api.py
git commit -m "feat: add pywebview API wiring game state to engine" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Окно, фронт и README

**Files:**
- Create: `frontend/vendor/chessground/` (копия из npm), `frontend/index.html`, `frontend/main.js`, `frontend/style.css`, `app.py`, `README.md`

**Interfaces:**
- Consumes: `Api` (Task 3) через `window.pywebview.api.*` (каждый метод возвращает Promise с `state`); `GameSession`, `EngineAnalyzer` (Tasks 1–2) для сборки в `app.py`. Бэк вызывает во фронте `window.onAnalysis(result)` с форматом из Task 2.
- Produces: запускаемое приложение `python app.py`.

- [ ] **Step 1: Скопировать chessground в vendor**

Run:
```bash
mkdir -p .vendor-tmp frontend/vendor/chessground
(cd .vendor-tmp && npm pack chessground@9.2.1 && tar -xzf chessground-9.2.1.tgz)
cp -r .vendor-tmp/package/dist frontend/vendor/chessground/dist
cp -r .vendor-tmp/package/assets frontend/vendor/chessground/assets
cp .vendor-tmp/package/LICENSE* frontend/vendor/chessground/
rm -rf .vendor-tmp
ls frontend/vendor/chessground/dist/chessground.js frontend/vendor/chessground/assets/chessground.cburnett.css
```
Expected: оба пути выводятся без ошибки.

- [ ] **Step 2: Разметка**

`frontend/index.html`:
```html
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Шахматный помогатор</title>
  <link rel="stylesheet" href="vendor/chessground/assets/chessground.base.css">
  <link rel="stylesheet" href="vendor/chessground/assets/chessground.brown.css">
  <link rel="stylesheet" href="vendor/chessground/assets/chessground.cburnett.css">
  <link rel="stylesheet" href="style.css">
  <script type="importmap">
    { "imports": { "chessground": "./vendor/chessground/dist/chessground.js" } }
  </script>
</head>
<body>
  <main class="layout">
    <div id="board" class="board"></div>
    <aside class="panel">
      <div id="status" class="status">Загрузка…</div>
      <ol id="lines" class="lines"></ol>
      <div id="depth" class="depth"></div>
      <div id="engine-error" class="error" hidden></div>
      <div class="buttons">
        <button id="new-white">Новая за белых</button>
        <button id="new-black">Новая за чёрных</button>
        <button id="undo">Отменить (Ctrl+Z)</button>
        <label class="toggle"><input type="checkbox" id="on-top"> Поверх окон</label>
      </div>
      <div class="fen">
        <input id="fen-input" placeholder="Вставь FEN позиции">
        <button id="load-fen">Загрузить</button>
      </div>
      <div id="action-error" class="error" hidden></div>
      <div id="history" class="history"></div>
    </aside>
  </main>
  <script type="module" src="main.js"></script>
</body>
</html>
```

- [ ] **Step 3: Стили**

`frontend/style.css`:
```css
/* Тёмная тема, доска слева, панель справа */
body { margin: 0; background: #1e1e1e; color: #ddd; font-family: "Segoe UI", sans-serif; }
.layout { display: flex; gap: 16px; padding: 16px; }
.board { width: 560px; height: 560px; flex: none; }
.panel { width: 280px; display: flex; flex-direction: column; gap: 10px; }
.status { font-size: 18px; font-weight: 600; min-height: 24px; }
.lines { margin: 0; padding-left: 22px; font-size: 20px; font-family: Consolas, monospace; min-height: 84px; }
.line-green { color: #4caf50; }
.line-blue { color: #4a90e2; }
.line-yellow { color: #e6c229; }
.depth { color: #888; font-size: 12px; min-height: 16px; }
.error { color: #ff6b6b; font-size: 13px; }
.buttons { display: flex; flex-wrap: wrap; gap: 6px; }
button { background: #333; color: #ddd; border: 1px solid #555; border-radius: 4px; padding: 6px 10px; cursor: pointer; }
button:hover { background: #444; }
.toggle { display: flex; align-items: center; gap: 6px; font-size: 14px; }
.fen { display: flex; gap: 6px; }
.fen input { flex: 1; min-width: 0; background: #2a2a2a; color: #ddd; border: 1px solid #555; border-radius: 4px; padding: 6px; }
.history { font-size: 12px; color: #aaa; max-height: 140px; overflow: auto; line-height: 1.5; }
```

- [ ] **Step 4: Логика фронта**

`frontend/main.js`:
```js
// Фронт помогатора: доска chessground + панель с подсказками.
import { Chessground } from 'chessground';

const BRUSHES = ['green', 'blue', 'yellow'];
const STATUS_TEXT = { check: 'Шах!', checkmate: 'Мат', stalemate: 'Пат', draw: 'Ничья' };
const GAME_OVER = ['checkmate', 'stalemate', 'draw'];

const el = (id) => document.getElementById(id);
const api = () => window.pywebview.api;
let state = null;

const cg = Chessground(el('board'), {
  movable: { free: false, showDests: true, events: { after: onUserMove } },
  highlight: { lastMove: true, check: true },
  animation: { enabled: true, duration: 150 },
});

async function onUserMove(orig, dest) {
  render(await api().move(orig, dest));
}

function render(next) {
  state = next;
  cg.set({
    fen: state.fen,
    orientation: state.my_color,
    turnColor: state.turn,
    lastMove: state.last_move ?? undefined,
    check: state.status === 'check' || state.status === 'checkmate',
    movable: { color: state.turn, dests: new Map(Object.entries(state.dests)) },
  });
  clearHints(); // свежие подсказки придут в onAnalysis
  renderStatus();
}

function clearHints() {
  cg.setAutoShapes([]);
  el('lines').innerHTML = '';
  el('depth').textContent = '';
}

function renderStatus() {
  const turn = state.turn === state.my_color ? 'Твой ход' : 'Ход соперника — повтори его';
  const extra = STATUS_TEXT[state.status];
  if (GAME_OVER.includes(state.status)) {
    el('status').textContent = `Игра окончена: ${extra}`;
  } else {
    el('status').textContent = extra ? `${turn} · ${extra}` : turn;
  }
  showError(el('engine-error'), state.engine_error);
  showError(el('action-error'), state.error);
  el('history').textContent = formatHistory(state.history);
}

function showError(node, text) {
  node.hidden = !text;
  node.textContent = text ?? '';
}

function formatHistory(sans) {
  const parts = [];
  for (let i = 0; i < sans.length; i += 2) {
    parts.push(`${i / 2 + 1}. ${sans[i]}${sans[i + 1] ? ' ' + sans[i + 1] : ''}`);
  }
  return parts.join('  ');
}

function formatScore({ cp, mate }) {
  if (mate !== null) return mate > 0 ? `мат в ${mate}` : `тебе мат в ${-mate}`;
  const pawns = cp / 100;
  return `${pawns > 0 ? '+' : ''}${pawns.toFixed(1)}`;
}

// Бэк вызывает эту функцию через evaluate_js по мере расчёта
window.onAnalysis = (result) => {
  if (!state || result.fen !== state.fen || state.turn !== state.my_color) return; // устаревший анализ
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
};

el('new-white').addEventListener('click', async () => render(await api().new_game('white')));
el('new-black').addEventListener('click', async () => render(await api().new_game('black')));
el('undo').addEventListener('click', async () => render(await api().undo()));
el('on-top').addEventListener('change', async (e) => render(await api().set_on_top(e.target.checked)));
el('load-fen').addEventListener('click', async () => render(await api().load_fen(el('fen-input').value.trim())));

document.addEventListener('keydown', async (e) => {
  // KeyZ не зависит от раскладки (работает и на русской)
  if (e.ctrlKey && e.code === 'KeyZ') {
    e.preventDefault();
    render(await api().undo());
  }
});

async function start() {
  render(await api().new_game('white'));
}

if (window.pywebview?.api) start();
else window.addEventListener('pywebviewready', start, { once: true });
```

- [ ] **Step 5: Точка входа**

`app.py`:
```python
"""Запуск помогатора: окно pywebview + бэк на Python."""
import json

import webview

from backend.api import Api
from backend.engine import EngineAnalyzer
from backend.game import GameSession


def main() -> None:
    game = GameSession()
    engine = EngineAnalyzer()
    holder: dict = {}  # окно создаётся после Api, поэтому храним ссылку здесь

    def push_analysis(result: dict) -> None:
        window = holder.get("window")
        if window is not None:
            window.evaluate_js(f"window.onAnalysis({json.dumps(result)})")

    def set_on_top(flag: bool) -> None:
        holder["window"].on_top = flag

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
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Проверить запуском**

Run: `.venv/Scripts/python app.py`

Проверить по списку (всё должно выполняться):
1. Открывается окно «Шахматный помогатор», доска белыми снизу, статус «Твой ход».
2. В течение ~1 секунды появляются три стрелки (зелёная, синяя, жёлтая) и список из трёх ходов с оценкой, глубина растёт до 20.
3. Ход e2–e4 мышкой: стрелки и список исчезают, статус «Ход соперника — повтори его».
4. Ход e7–e5: стрелки снова появляются.
5. Ctrl+Z (на русской раскладке тоже) отменяет e7–e5, стрелки пропадают.
6. «Новая за чёрных»: доска разворачивается, подсказок нет; после хода белых — появляются.
7. «Поверх окон»: окно остаётся над Discord; снятие галочки возвращает обычное поведение.
8. Вставить FEN `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1` при игре за чёрных → «Загрузить» → позиция ставится, подсказки появляются. Вставить `мусор` → под полем «Невалидный FEN».
9. Пешка доходит до последней горизонтали → становится ферзём.
10. Переименовать `engine/stockfish.exe` → перезапустить → доска работает, в панели «Не найден Stockfish: …». Вернуть имя.
11. Закрыть окно — в диспетчере задач не остаётся процесса `stockfish.exe`.

Если `chessground` не загрузился (пустое место вместо доски) — открыть DevTools: `webview.start(http_server=True, debug=True)` и посмотреть ошибку в консоли.

- [ ] **Step 7: README**

`README.md`:
````markdown
# Шахматный помогатор

Окно с доской: повторяешь в нём ходы партии (свои и соперника), а на своём ходу
видишь три лучших хода от Stockfish — зелёная стрелка лучший, синяя и жёлтая —
второй и третий.

## Установка (Windows)

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

Stockfish: скачай `stockfish-windows-x86-64-avx2.zip` с
https://github.com/official-stockfish/Stockfish/releases/latest и положи exe
как `engine/stockfish.exe` (или укажи путь в переменной `STOCKFISH_PATH`).

## Запуск

```bash
.venv/Scripts/python app.py
```

## Управление

- Перетаскивай фигуры за обе стороны; незаконный ход не пройдёт.
- «Новая за белых» / «Новая за чёрных» — новая партия и разворот доски.
- «Отменить» или Ctrl+Z — отменить последний полуход.
- «Поверх окон» — окно висит над Discord.
- Поле FEN — поставить позицию, если партия уже идёт.

## Тесты

```bash
.venv/Scripts/python -m pytest -v
```

## Лицензии

Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.
````

- [ ] **Step 8: Прогнать все тесты ещё раз**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `36 passed`.

- [ ] **Step 9: Commit**

```bash
git add frontend app.py README.md
git commit -m "feat: add desktop window with chessground board and hint panel" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
