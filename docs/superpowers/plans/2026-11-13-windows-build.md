# Сборка помогатора в exe для Windows — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** zip для GitHub Releases: распаковал, запустил `chess-helper.exe` двойным кликом — помогатор работает без Python, uv и консоли, Stockfish sf_19 внутри.

**Architecture:** PyInstaller собирает папку `dist/chess-helper/` (exe без консоли + `_internal/`), скрипт `scripts/build_exe.py` докладывает Stockfish, лицензии и `chess-helper.exe.config`, прогоняет самопроверку exe (`--self-check`) — обычную и на копии с меткой «из интернета» — и пакует zip. В коде: пути через `backend/paths.py`, лог в файл с перехватом исключений (`backend/logs.py`), проверка WebView2/.NET до окна (`backend/startup_check.py`), Stockfish без окна консоли. GitHub Actions по тегу `v*` собирает и создаёт черновик релиза.

**Tech Stack:** Python 3.13, uv, pywebview 6.2.1 (WinForms + WebView2, pythonnet 3.2.1), python-chess 1.11.2, PyInstaller ≥ 6.22, Pillow ≥ 11, pytest, GitHub Actions (`windows-latest`).

**Спека:** [docs/superpowers/specs/2026-11-13-windows-build-design.md](../specs/2026-11-13-windows-build-design.md) — источник требований; при расхождении с планом права спека.

## Global Constraints

- Ветка `feature/windows-build`. Не пушить, PR не создавать — это делает контроллер.
- Python 3.13; `pywebview==6.2.1` и `chess==1.11.2` не менять. Новых зависимостей приложения нет; PyInstaller и Pillow — только в группе `build`.
- Только Windows: тесты гоняются на Windows (`uv run pytest -q` из корня репозитория; `pytest.ini` уже содержит `pythonpath = .`).
- Комментарии и docstring'и в коде — на русском. Тексты для пользователя — на русском и на «ты», как в интерфейсе. Сообщения в лог — на русском.
- Коммиты — на английском, одно предложение, префикс в стиле истории (`feat:`, `build:`, `ci:`, `docs:`), в конце строка `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (отдельным абзацем, через `-m`).
- Перед каждым коммитом — `uv run pytest -q`, все тесты зелёные.
- Папку `engine/` разработчика не трогать. Метки «скачано из интернета» программно не снимать.
- Скачивать только то, на что пользователь дал разрешение (список — у контроллера): пакеты группы `build` и PyYAML с PyPI, архив Stockfish sf_19 с GitHub, тексты лицензий proxy-tools (GitHub) и WebView2 SDK (nuget.org).
- Точные значения (копировать как есть):
  - лог: `%LOCALAPPDATA%\chess-helper\logs\helper.log`, `RotatingFileHandler(maxBytes=1_000_000, backupCount=2, encoding="utf-8")`, уровень WARNING, формат `%(asctime)s %(levelname)s %(name)s: %(message)s`;
  - страница WebView2: `https://developer.microsoft.com/microsoft-edge/webview2/`;
  - Stockfish: `https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip`, SHA-256 `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7`, кэш `build/cache/stockfish-sf_19/stockfish.exe`;
  - самопроверка: анализ `Limit(depth=10, time=30)`; таймаут запуска самопроверки в скрипте — 120 с;
  - иконка: рендер 512×512, размеры .ico 16, 24, 32, 48, 64, 128, 256;
  - zip: `dist/chess-helper-v<версия>-windows-x64.zip`, внутри папка `chess-helper/`;
  - GitHub Actions: `actions/checkout@v7`, `astral-sh/setup-uv@v10.3.3`.

## Карта файлов

| Файл | Задача | Ответственность |
|---|---|---|
| `backend/paths.py` (новый) | 1 | `app_root()`, `log_dir()` |
| `backend/engine.py` | 1 | `DEFAULT_PATH` через `app_root()`, `popen_args()` с `CREATE_NO_WINDOW` |
| `backend/logs.py` (новый) | 2 | `setup_logging()`: файл, консоль, перехват исключений |
| `backend/startup_check.py` (новый) | 3 | `check_startup()`, `show_startup_problem()` |
| `backend/selfcheck.py` (новый) | 4 | `run_self_check()` и проверки |
| `app.py` | 5 | точка входа: лог → самопроверка или проверка при старте → окно |
| `assets/icon.svg`, `assets/icon.ico`, `scripts/make_icon.py` (новые) | 6 | иконка |
| `pyproject.toml`, `uv.lock`, `.gitignore` | 6 | группа `build`; `/build/`, `/dist/` |
| `chess-helper.spec`, `scripts/__init__.py`, `scripts/build_exe.py`, `packaging/README.txt`, `packaging/licenses/*.txt` (новые) | 7 | сборка zip |
| `.github/workflows/release.yml` (новый) | 8 | CI-сборка и черновик релиза |
| `README.md`, `docs/ARCHITECTURE.md`, `docs/ABOUT_PROJECT.md` | 9 | документация, sf_19 |
| `tests/test_paths.py`, `tests/test_logs.py`, `tests/test_startup_check.py`, `tests/test_selfcheck.py`, `tests/test_app.py`, `tests/test_build_exe.py` (новые), `tests/test_engine_unit.py` | 1–7 | тесты |

Число тестов: сейчас 70. После задач: 1 → 76, 2 → 85, 3 → 92, 4 → 99, 5 → 103, 7 → 111. Тесты `tests/test_engine.py` (9 штук) идут только при наличии движка (`engine/stockfish.exe` или `STOCKFISH_PATH`).

---

### Task 1: Пути и запуск Stockfish без окна консоли

**Files:**
- Create: `backend/paths.py`
- Modify: `backend/engine.py` (импорты, строка 14 `DEFAULT_PATH`, после `resolve_engine_path()` — новая функция, строка 86 `popen_uci`)
- Test: `tests/test_paths.py` (новый), `tests/test_engine_unit.py` (дописать)

**Interfaces:**
- Produces: `backend.paths.app_root() -> Path`, `backend.paths.log_dir() -> Path`, `backend.engine.popen_args() -> dict` — их используют задачи 2, 4, 5.

- [ ] **Step 1: Написать падающие тесты путей**

`tests/test_paths.py`:

```python
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
```

- [ ] **Step 2: Дописать падающие тесты движка**

В `tests/test_engine_unit.py` в блок импортов (после `import threading`) добавить:

```python
import subprocess
import sys
```

и после `from backend.engine import EngineAnalyzer, build_result`:

```python
from backend.paths import app_root
```

В конец файла:

```python
def test_default_engine_path_is_inside_app_root():
    assert engine_module.DEFAULT_PATH == app_root() / "engine" / "stockfish.exe"


@pytest.mark.skipif(sys.platform != "win32", reason="флаг CREATE_NO_WINDOW есть только на Windows")
def test_engine_starts_without_console_window(monkeypatch, tmp_path):
    # Без флага у exe без консоли Windows открыла бы для Stockfish отдельное чёрное окно
    calls = []

    def popen_uci(command, **kwargs):
        calls.append(kwargs)
        return FakeEngine()

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", staticmethod(popen_uci))
    path = tmp_path / "fake-stockfish.exe"
    path.write_bytes(b"")
    analyzer = EngineAnalyzer(path=path)
    try:
        assert calls == [{"creationflags": subprocess.CREATE_NO_WINDOW}]
    finally:
        analyzer.close()
```

- [ ] **Step 3: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_paths.py tests/test_engine_unit.py -q`
Expected: ошибка сбора `ModuleNotFoundError: No module named 'backend.paths'`.

- [ ] **Step 4: Создать `backend/paths.py`**

```python
"""Где лежат файлы помогатора: в исходниках и в собранном exe."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "chess-helper"


def app_root() -> Path:
    """Корень приложения: папка _internal в собранном exe, корень репозитория в исходниках."""
    # PyInstaller кладёт всё в папку _internal и сообщает её путь через sys._MEIPASS
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def log_dir() -> Path:
    """Папка логов в профиле пользователя: рядом с exe писать может быть нельзя."""
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / "AppData" / "Local"
    return root / APP_DIR_NAME / "logs"
```

- [ ] **Step 5: Изменить `backend/engine.py`**

Импорты (строки 4–12) привести к виду:

```python
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

import chess
import chess.engine

from backend.paths import app_root
```

Строку 14 заменить на:

```python
DEFAULT_PATH = app_root() / "engine" / "stockfish.exe"
```

Сразу после функции `resolve_engine_path()` добавить:

```python
def popen_args() -> dict:
    # Без CREATE_NO_WINDOW у exe без консоли Windows открывает для Stockfish отдельное
    # чёрное окно, а если его закрыть, движок завершается
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
```

В `_open()` строку `engine = chess.engine.SimpleEngine.popen_uci(str(self.path))` заменить на:

```python
            engine = chess.engine.SimpleEngine.popen_uci(str(self.path), **popen_args())
```

- [ ] **Step 6: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `76 passed`.

- [ ] **Step 7: Коммит**

```bash
git add backend/paths.py backend/engine.py tests/test_paths.py tests/test_engine_unit.py
git commit -m "feat: add app paths and start Stockfish without a console window" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Лог в файл и перехват необработанных исключений

**Files:**
- Create: `backend/logs.py`
- Test: `tests/test_logs.py` (новый)

**Interfaces:**
- Consumes: `backend.paths.log_dir()` (задача 1).
- Produces: `backend.logs.setup_logging(directory: Path | None = None) -> Path | None` — вызывает `app.py` (задача 5); `backend.logs.OWN_MARK` — метка наших обработчиков (для тестов).

- [ ] **Step 1: Написать падающие тесты**

`tests/test_logs.py`:

```python
"""Лог в файл: обработчики, ротация, работа без консоли, перехват исключений."""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

import pytest

from backend import logs


@pytest.fixture(autouse=True)
def clean_logging():
    # setup_logging меняет глобальное состояние: корневой логгер и хуки исключений
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    saved_hook, saved_thread_hook = sys.excepthook, threading.excepthook
    yield
    for handler in root.handlers[:]:
        if handler not in saved_handlers:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(saved_level)
    sys.excepthook, threading.excepthook = saved_hook, saved_thread_hook


def own_handlers():
    return [h for h in logging.getLogger().handlers if getattr(h, logs.OWN_MARK, False)]


def flush():
    for handler in own_handlers():
        handler.flush()


def test_warning_goes_to_log_file(tmp_path):
    log_file = logs.setup_logging(tmp_path)
    assert log_file == tmp_path / "helper.log"
    logging.getLogger("test").warning("проверка записи")
    flush()
    assert "проверка записи" in log_file.read_text(encoding="utf-8")


def test_info_is_not_written(tmp_path):
    log_file = logs.setup_logging(tmp_path)
    logging.getLogger("test").info("лишнее")
    flush()
    assert "лишнее" not in log_file.read_text(encoding="utf-8")


def test_rotation_settings(tmp_path):
    logs.setup_logging(tmp_path)
    [file_handler] = [h for h in own_handlers() if isinstance(h, RotatingFileHandler)]
    assert file_handler.maxBytes == 1_000_000
    assert file_handler.backupCount == 2


def test_no_console_handler_without_stderr(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    logs.setup_logging(tmp_path)
    assert all(isinstance(h, RotatingFileHandler) for h in own_handlers())
    logging.getLogger("test").warning("без консоли")  # не должно упасть


def test_console_handler_with_stderr(tmp_path):
    logs.setup_logging(tmp_path)
    assert any(type(h) is logging.StreamHandler for h in own_handlers())


def test_repeated_setup_does_not_duplicate_handlers(tmp_path):
    logs.setup_logging(tmp_path)
    first = len(own_handlers())
    logs.setup_logging(tmp_path)
    assert len(own_handlers()) == first


def test_unwritable_directory_keeps_console_only(tmp_path):
    blocker = tmp_path / "file-instead-of-dir"
    blocker.write_text("x", encoding="utf-8")
    assert logs.setup_logging(blocker / "logs") is None
    assert not any(isinstance(h, RotatingFileHandler) for h in own_handlers())


def test_unhandled_exception_is_logged_and_passed_on(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(sys, "excepthook", lambda exc_type, exc, tb: seen.append(exc_type))
    log_file = logs.setup_logging(tmp_path)
    try:
        raise ValueError("сломалось")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    flush()
    text = log_file.read_text(encoding="utf-8")
    assert "Необработанное исключение" in text
    assert "ValueError: сломалось" in text
    assert seen == [ValueError]


def test_unhandled_thread_exception_is_logged(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(threading, "excepthook", lambda args: seen.append(args.exc_type))
    log_file = logs.setup_logging(tmp_path)

    def boom():
        raise RuntimeError("в потоке")

    thread = threading.Thread(target=boom, name="test-thread")
    thread.start()
    thread.join()
    flush()
    text = log_file.read_text(encoding="utf-8")
    assert "test-thread" in text
    assert "RuntimeError: в потоке" in text
    assert seen == [RuntimeError]
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_logs.py -q`
Expected: ошибка сбора `ImportError: cannot import name 'logs' from 'backend'`.

- [ ] **Step 3: Создать `backend/logs.py`**

```python
"""Лог помогатора: файл в профиле пользователя и перехват необработанных исключений."""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.paths import log_dir

LOG_FILE_NAME = "helper.log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 2  # вместе с текущим файлом — не больше трёх

# Метка наших обработчиков и хуков: повторный вызов setup_logging их не дублирует
OWN_MARK = "_chess_helper_own"

log = logging.getLogger("chess_helper")


def setup_logging(directory: Path | None = None) -> Path | None:
    """Пишет WARNING и выше в файл и в консоль, если она есть. Возвращает путь к файлу или None."""
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    for handler in [h for h in root.handlers if getattr(h, OWN_MARK, False)]:
        root.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter(LOG_FORMAT)
    target = directory if directory is not None else log_dir()
    log_file: Path | None = target / LOG_FILE_NAME
    try:
        target.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
        )
    except OSError:
        log_file = None  # писать некуда — остаётся консоль, помогатор работает дальше
    else:
        _add_handler(root, file_handler, formatter)
    # У exe без консоли sys.stderr — None: обработчик консоли ему не нужен
    if sys.stderr is not None:
        _add_handler(root, logging.StreamHandler(sys.stderr), formatter)
    if log_file is None:
        log.warning("Не удалось открыть файл лога в %s — пишу только в консоль", target)
    _install_exception_hooks()
    return log_file


def _add_handler(root: logging.Logger, handler: logging.Handler, formatter: logging.Formatter) -> None:
    handler.setFormatter(formatter)
    setattr(handler, OWN_MARK, True)
    root.addHandler(handler)


def _install_exception_hooks() -> None:
    # Необработанное исключение пишем в лог и отдаём прежнему обработчику:
    # в exe это окно ошибки PyInstaller, в консоли — обычная трассировка
    if getattr(sys.excepthook, OWN_MARK, False):
        return
    previous_hook = sys.excepthook
    previous_thread_hook = threading.excepthook

    def excepthook(exc_type, exc, tb):
        log.critical("Необработанное исключение", exc_info=(exc_type, exc, tb))
        previous_hook(exc_type, exc, tb)

    def thread_excepthook(args):
        if args.exc_type is not SystemExit:
            name = args.thread.name if args.thread is not None else "?"
            log.critical(
                "Необработанное исключение в потоке %s",
                name,
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
        previous_thread_hook(args)

    setattr(excepthook, OWN_MARK, True)
    setattr(thread_excepthook, OWN_MARK, True)
    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
```

- [ ] **Step 4: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `85 passed`.

- [ ] **Step 5: Коммит**

```bash
git add backend/logs.py tests/test_logs.py
git commit -m "feat: write logs to a file and log unhandled exceptions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Проверка WebView2 и .NET при старте

**Files:**
- Create: `backend/startup_check.py`
- Test: `tests/test_startup_check.py` (новый)

**Interfaces:**
- Produces: `check_startup(load_platform=load_winforms_renderer) -> str | None` (коды `NO_WEBVIEW2 = "no_webview2"`, `DOTNET = "dotnet"`), `show_startup_problem(problem, log_file, message_box=..., open_url=...) -> None`, `load_winforms_renderer() -> str` — используют задачи 4 и 5.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_startup_check.py`:

```python
"""Проверка при старте: решение pywebview о движке окна и сообщения пользователю."""
import logging
import sys

import pytest

from backend import startup_check
from backend.startup_check import DOTNET, NO_WEBVIEW2, check_startup, show_startup_problem


def test_edge_chromium_is_ok():
    assert check_startup(lambda: "edgechromium") is None


def test_mshtml_means_no_webview2():
    assert check_startup(lambda: "mshtml") == NO_WEBVIEW2


def test_import_failure_means_dotnet_problem(caplog):
    def broken():
        raise RuntimeError("Failed to resolve Python.Runtime.Loader.Initialize")

    with caplog.at_level(logging.ERROR):
        assert check_startup(broken) == DOTNET
    assert "Python.Runtime" in caplog.text


def test_not_windows_skips_check(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert check_startup(lambda: pytest.fail("на не-Windows платформу не грузим")) is None


class Box:
    """Подмена MessageBoxW: запоминает вызовы и отвечает заданной кнопкой."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def __call__(self, text, title, flags):
        self.calls.append((text, title, flags))
        return self.answer


def test_no_webview2_yes_opens_download_page():
    box, opened = Box(startup_check.IDYES), []
    show_startup_problem(NO_WEBVIEW2, None, message_box=box, open_url=opened.append)
    assert opened == [startup_check.WEBVIEW2_URL]
    assert box.calls[0][2] == startup_check.MB_YESNO | startup_check.MB_ICONWARNING


def test_no_webview2_no_does_not_open_page():
    opened = []
    show_startup_problem(NO_WEBVIEW2, None, message_box=Box(7), open_url=opened.append)  # 7 — «Нет»
    assert opened == []


def test_dotnet_message_mentions_log_and_unblock(tmp_path):
    box, opened = Box(1), []
    log_file = tmp_path / "helper.log"
    show_startup_problem(DOTNET, log_file, message_box=box, open_url=opened.append)
    text, title, flags = box.calls[0]
    assert str(log_file) in text
    assert "Разблокировать" in text
    assert flags == startup_check.MB_OK | startup_check.MB_ICONERROR
    assert opened == []
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_startup_check.py -q`
Expected: ошибка сбора `ImportError: cannot import name 'startup_check' from 'backend'`.

- [ ] **Step 3: Создать `backend/startup_check.py`**

```python
"""Проверка при старте: есть ли WebView2 и загружается ли .NET-часть окна pywebview."""
from __future__ import annotations

import ctypes
import logging
import sys
import webbrowser
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)

NO_WEBVIEW2 = "no_webview2"
DOTNET = "dotnet"
WEBVIEW2_URL = "https://developer.microsoft.com/microsoft-edge/webview2/"
TITLE = "Шахматный помогатор"

# Флаги и ответ MessageBoxW; подписи кнопок Windows ставит на языке системы
MB_OK = 0x00000000
MB_YESNO = 0x00000004
MB_ICONERROR = 0x00000010
MB_ICONWARNING = 0x00000030
IDYES = 6

NO_WEBVIEW2_TEXT = (
    "Для работы помогатора нужен Microsoft Edge WebView2 Runtime. "
    "Открыть страницу загрузки Microsoft?"
)
DOTNET_TEXT = (
    "Не удалось загрузить компоненты помогатора. Если архив скачан из интернета, "
    "Windows мог заблокировать файлы: удали распакованную папку, открой «Свойства» "
    "zip-архива, отметь «Разблокировать» и распакуй заново.\n\n"
    "Подробности — в логе: {log_file}"
)


def load_winforms_renderer() -> str:
    """Импортирует платформенный модуль pywebview и возвращает выбранный им движок окна."""
    # Тот же модуль потом возьмёт из sys.modules webview.start(). Он грузит .NET (pythonnet,
    # WinForms) и выбирает движок: 'edgechromium' с WebView2, 'mshtml' (Internet Explorer) без него.
    # Без WebView2 импорт попутно пишет в HKCU режим IE для нашего exe — как сделал бы и start()
    from webview.platforms import winforms

    return winforms.renderer


def check_startup(load_platform: Callable[[], str] = load_winforms_renderer) -> str | None:
    """None — можно открывать окно; иначе код проблемы: NO_WEBVIEW2 или DOTNET."""
    if sys.platform != "win32":
        return None  # WinForms и WebView2 бывают только на Windows
    try:
        renderer = load_platform()
    except Exception:
        log.exception("Не удалось загрузить .NET-часть окна pywebview")
        return DOTNET
    if renderer != "edgechromium":
        log.warning("pywebview выбрал движок окна %r: WebView2 не найден", renderer)
        return NO_WEBVIEW2
    return None


def _message_box(text: str, title: str, flags: int) -> int:
    return ctypes.windll.user32.MessageBoxW(None, text, title, flags)


def show_startup_problem(
    problem: str,
    log_file: Path | None,
    message_box: Callable[[str, str, int], int] = _message_box,
    open_url: Callable[[str], object] = webbrowser.open,
) -> None:
    """Показывает системное окно с объяснением проблемы при старте."""
    if problem == NO_WEBVIEW2:
        if message_box(NO_WEBVIEW2_TEXT, TITLE, MB_YESNO | MB_ICONWARNING) == IDYES:
            open_url(WEBVIEW2_URL)
        return
    where = str(log_file) if log_file is not None else "лог записать не удалось"
    message_box(DOTNET_TEXT.format(log_file=where), TITLE, MB_OK | MB_ICONERROR)
```

- [ ] **Step 4: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `92 passed`.

- [ ] **Step 5: Коммит**

```bash
git add backend/startup_check.py tests/test_startup_check.py
git commit -m "feat: check WebView2 and the .NET runtime before opening the window" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Самопроверка собранного exe

**Files:**
- Create: `backend/selfcheck.py`
- Test: `tests/test_selfcheck.py` (новый)

**Interfaces:**
- Consumes: `backend.paths.app_root()`, `backend.engine.popen_args()` (задача 1), `backend.startup_check.load_winforms_renderer()` (задача 3).
- Produces: `backend.selfcheck.run_self_check(report: Path, checks=DEFAULT_CHECKS, root: Path | None = None) -> int` — вызывает `app.py` (задача 5) по флагу `--self-check`; класс `Info(str)` — результат-справка.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_selfcheck.py`:

```python
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
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_selfcheck.py -q`
Expected: ошибка сбора `ImportError: cannot import name 'selfcheck' from 'backend'`.

- [ ] **Step 3: Создать `backend/selfcheck.py`**

```python
"""Самопроверка собранного exe без окна: файлы, вложенный Stockfish, .NET-часть окна.

Запускается только при проверке сборки (scripts/build_exe.py и CI) флагом --self-check.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Sequence

from backend.paths import app_root

log = logging.getLogger(__name__)

REQUIRED_FILES = ("frontend/index.html", "frontend/vendor/chessground", "assets/icon.ico")
ENGINE_DEPTH = 10
ENGINE_TIME = 30.0


class Info(str):
    """Результат-справка: попадает в отчёт строкой INFO и не считается ошибкой."""


def check_files(root: Path) -> str:
    missing = [name for name in REQUIRED_FILES if not (root / name).exists()]
    if missing:
        raise FileNotFoundError("нет " + ", ".join(missing))
    return "файлы на месте"


def check_engine(root: Path) -> str:
    # Всегда вложенный движок: проверяем сборку, поэтому STOCKFISH_PATH здесь не учитывается
    import chess
    import chess.engine

    from backend.engine import popen_args

    path = root / "engine" / "stockfish.exe"
    engine = chess.engine.SimpleEngine.popen_uci(str(path), **popen_args())
    try:
        info = engine.analyse(chess.Board(), chess.engine.Limit(depth=ENGINE_DEPTH, time=ENGINE_TIME))
    finally:
        engine.quit()
    score = info.get("score")
    if score is None:
        raise RuntimeError("движок не выдал оценку")
    return f"Stockfish: глубина {info.get('depth')}, оценка {score.white()}"


def check_dotnet(root: Path) -> str:
    # Грузит pythonnet, WinForms и обе DLL WebView2 независимо от реестра; окно не создаётся
    import webview.platforms.edgechromium  # noqa: F401

    return ".NET-часть окна загружается"


def check_renderer(root: Path) -> Info:
    # Справка: без WebView2 на раннере GitHub pywebview выбрал бы Internet Explorer — это не ошибка
    from backend.startup_check import load_winforms_renderer

    try:
        renderer = load_winforms_renderer()
    except Exception as exc:
        return Info(f"не удалось узнать движок окна: {type(exc).__name__}: {exc}")
    return Info(f"pywebview выбрал бы движок окна: {renderer}")


Check = Callable[[Path], str]
DEFAULT_CHECKS: Sequence[tuple[str, Check]] = (
    ("files", check_files),
    ("engine", check_engine),
    ("dotnet", check_dotnet),
    ("renderer", check_renderer),
)


def run_self_check(report: Path, checks: Sequence[tuple[str, Check]] = DEFAULT_CHECKS, root: Path | None = None) -> int:
    """Пишет отчёт строками OK/FAIL/INFO; 0 — ни одного FAIL, иначе 1."""
    root = root if root is not None else app_root()
    lines: list[str] = []
    failed = False
    for name, check in checks:
        try:
            result = check(root)
        except Exception as exc:
            log.exception("Самопроверка %s не прошла", name)
            lines.append(f"FAIL {name}: {type(exc).__name__}: {exc}")
            failed = True
        else:
            level = "INFO" if isinstance(result, Info) else "OK"
            lines.append(f"{level} {name}: {result}")
    try:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        log.exception("Не удалось записать отчёт самопроверки в %s", report)
        return 1
    return 1 if failed else 0
```

- [ ] **Step 4: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `99 passed`.

- [ ] **Step 5: Коммит**

```bash
git add backend/selfcheck.py tests/test_selfcheck.py
git commit -m "feat: add a self-check mode for the built executable" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Точка входа `app.py`

**Files:**
- Modify: `app.py` (весь файл, кроме функции `apply_on_top`)
- Test: `tests/test_app.py` (новый)

**Interfaces:**
- Consumes: `setup_logging` (задача 2), `check_startup`, `show_startup_problem` (задача 3), `run_self_check` (задача 4), `app_root` (задача 1).
- Produces: `app.main(argv: list[str] | None = None) -> None`, `app.run_app() -> None`.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_app.py`:

```python
"""Точка входа: самопроверка, проблема при старте, обычный запуск."""
import pytest

import app


@pytest.fixture
def log_file(monkeypatch, tmp_path):
    # Настоящий setup_logging трогает папку логов и глобальные хуки — в тестах не нужен
    path = tmp_path / "helper.log"
    monkeypatch.setattr(app, "setup_logging", lambda: path)
    return path


def test_self_check_runs_and_exits_with_its_code(monkeypatch, log_file, tmp_path):
    calls = []

    def fake_run(report):
        calls.append(report)
        return 1

    monkeypatch.setattr("backend.selfcheck.run_self_check", fake_run)
    with pytest.raises(SystemExit) as exit_info:
        app.main(["--self-check", str(tmp_path / "report.txt")])
    assert exit_info.value.code == 1
    assert calls == [tmp_path / "report.txt"]


def test_self_check_without_report_path_exits_with_2(log_file):
    with pytest.raises(SystemExit) as exit_info:
        app.main(["--self-check"])
    assert exit_info.value.code == 2


def test_startup_problem_shows_message_and_skips_window(monkeypatch, log_file):
    shown, started = [], []
    monkeypatch.setattr("backend.startup_check.check_startup", lambda: "no_webview2")
    monkeypatch.setattr(
        "backend.startup_check.show_startup_problem",
        lambda problem, path: shown.append((problem, path)),
    )
    monkeypatch.setattr(app, "run_app", lambda: started.append(True))
    app.main([])
    assert shown == [("no_webview2", log_file)]
    assert started == []


def test_no_problem_starts_window(monkeypatch, log_file):
    started = []
    monkeypatch.setattr("backend.startup_check.check_startup", lambda: None)
    monkeypatch.setattr(app, "run_app", lambda: started.append(True))
    app.main([])
    assert started == [True]
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_app.py -q`
Expected: `FAILED` — у текущего `app` нет `setup_logging` и `run_app` (`AttributeError`), а `main()` не принимает `argv`.

- [ ] **Step 3: Переписать `app.py`**

Файл целиком (функция `apply_on_top` — без изменений, слово в слово как сейчас):

```python
"""Запуск помогатора: окно pywebview + бэк на Python."""
import json
import sys
from pathlib import Path

from backend.logs import setup_logging
from backend.paths import app_root


def apply_on_top(window, flag: bool) -> None:
    # «Поверх всех окон». pywebview 6.2.1 на Windows меняет TopMost прямо из потока вызова
    # (у нас это поток js_api): тот держит GIL и ждёт UI-поток окна, а UI-потоку для ответа
    # нужен тот же GIL — окно намертво зависает. В основной ветке pywebview это исправлено
    # через Invoke; пока не вышла версия новее 6.2.1, делаем так же сами.
    try:
        from System import Func, Type
        from webview.platforms.winforms import BrowserView
    except ImportError:
        window.on_top = flag  # не Windows: штатный путь pywebview
        return
    form = BrowserView.instances.get(window.uid)
    if form is None:
        window.on_top = flag
        return

    def _apply() -> None:
        form.TopMost = flag

    form.Invoke(Func[Type](_apply))


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    # Лог и перехват исключений — первым делом: у exe нет консоли, и всё, что сломается
    # дальше (даже импорт), должно попасть в файл
    log_file = setup_logging()
    if argv[:1] == ["--self-check"]:
        if len(argv) != 2:
            sys.exit(2)  # нужен путь к файлу отчёта
        from backend.selfcheck import run_self_check

        sys.exit(run_self_check(Path(argv[1])))
    from backend.startup_check import check_startup, show_startup_problem

    problem = check_startup()
    if problem is not None:
        show_startup_problem(problem, log_file)
        return
    run_app()


def run_app() -> None:
    # Тяжёлые модули — только здесь, после проверки при старте
    import webview

    from backend.api import Api
    from backend.engine import EngineAnalyzer
    from backend.game import GameSession

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
        apply_on_top(holder["window"], flag)

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
        # Иконка окна: в exe pywebview берёт её из файла exe, при запуске из исходников — отсюда
        webview.start(http_server=True, icon=str(app_root() / "assets" / "icon.ico"))
    finally:
        # Фоновый поток python-chess не демон: без этого процесс завис бы при сбое start()
        engine.close()


if __name__ == "__main__":
    main()
```

Строки `import logging`, `import webview`, `from backend.api import Api`, `from backend.engine import EngineAnalyzer`, `from backend.game import GameSession` на верхнем уровне и `logging.basicConfig(...)` в `main` больше не нужны — их не должно остаться.

- [ ] **Step 4: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `103 passed`.

- [ ] **Step 5: Проверить запуск из исходников**

Run: `uv run app.py` (окно открывается; закрыть крестиком).
Expected: окно помогатора с доской, как раньше; в `%LOCALAPPDATA%\chess-helper\logs\` появился `helper.log` (может быть пустым — пишутся только WARNING и выше). Иконки окна пока нет — она появится в задаче 6; предупреждений в консоли о ней быть не должно (pywebview просто не ставит иконку, если файла нет).

- [ ] **Step 6: Коммит**

```bash
git add app.py tests/test_app.py
git commit -m "feat: wire logging, the startup check and the self-check into app.py" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Иконка

**Files:**
- Modify: `pyproject.toml` (группа `build`), `uv.lock` (через `uv lock`), `.gitignore`
- Create: `assets/icon.svg`, `scripts/make_icon.py`, `assets/icon.ico` (генерируется)

**Interfaces:**
- Produces: `assets/icon.ico` — нужен `app.py` (окно), `chess-helper.spec` и самопроверке (задачи 4, 7).

- [ ] **Step 1: Добавить группу `build`**

В `pyproject.toml` блок `[dependency-groups]` привести к виду:

```toml
[dependency-groups]
dev = [
    "pytest>=8",
]
build = [
    "pyinstaller>=6.22",
    "pillow>=11",
]
```

Run: `uv lock` — затем `uv sync --group build`
Expected: в `uv.lock` появились `pyinstaller`, `pyinstaller-hooks-contrib`, `pillow` и их зависимости; `uv sync` ставит их без ошибок.

- [ ] **Step 2: Дописать `.gitignore`**

В конец `.gitignore`:

```
/build/
/dist/
```

С ведущим слэшем — чтобы не задеть отслеживаемую `frontend/vendor/chessground/dist/`. Проверка: `git check-ignore -v frontend/vendor/chessground/dist/chessground.js` ничего не выводит (код 1).

- [ ] **Step 3: Создать `assets/icon.svg`**

Точно утверждённый в спеке рисунок:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <defs>
    <clipPath id="tl"><polygon points="0,0 100,0 0,100"/></clipPath>
    <clipPath id="br"><polygon points="100,0 100,100 0,100"/></clipPath>
    <g id="queen">
      <path d="M20 90 Q20 82 28 81 L72 81 Q80 82 80 90 Z"/>
      <path d="M33 76 C38 67 40 60 40 53 L60 53 C60 60 62 67 67 76 Z"/>
      <path d="M37 50 C34 43 28 36 22 28 L33 34 L36 22 L44 32 L50 18 L56 32 L64 22 L67 34 L78 28 C72 36 66 43 63 50 Z"/>
      <circle cx="22" cy="26" r="3.6"/>
      <circle cx="36" cy="20" r="3.6"/>
      <circle cx="50" cy="15" r="4.2"/>
      <circle cx="64" cy="20" r="3.6"/>
    </g>
    <g id="accent">
      <rect x="27" y="74" width="46" height="8" rx="3"/>
      <rect x="34" y="47.5" width="32" height="6.5" rx="3.2"/>
    </g>
  </defs>
  <g clip-path="url(#tl)">
    <rect width="100" height="100" rx="10" fill="#b58863"/>
    <use href="#queen" fill="#f2ecdf"/>
    <use href="#accent" fill="#ddd3bf"/>
  </g>
  <g clip-path="url(#br)">
    <rect width="100" height="100" rx="10" fill="#f0d9b5"/>
    <use href="#queen" fill="#222222"/>
    <use href="#accent" fill="#3a3a3a"/>
  </g>
  <!-- Пятый шарик короны целиком чёрный: диагональ задевает его край, и без этого остаётся белый серп -->
  <circle cx="78" cy="26" r="3.6" fill="#222222"/>
</svg>
```

- [ ] **Step 4: Создать `scripts/make_icon.py`**

```python
"""Делает assets/icon.ico из assets/icon.svg: headless Edge рендерит PNG, Pillow собирает .ico.

Запуск: uv run --group build python scripts/make_icon.py
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icon.svg"
ICO = ROOT / "assets" / "icon.ico"
PREVIEW = ROOT / "build" / "icon-preview.png"
RENDER_SIZE = 512
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
# В PATH Edge обычно нет — ищем в стандартных папках установки
EDGE_CANDIDATES = (
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
)


def find_edge() -> Path:
    for path in EDGE_CANDIDATES:
        if path.exists():
            return path
    raise SystemExit("Не найден Microsoft Edge (msedge.exe): он нужен, чтобы отрисовать SVG")


def render_png(edge: Path, svg: Path, png: Path, size: int, profile: Path) -> None:
    # Отдельный профиль — чтобы не зацепить уже открытый Edge пользователя
    subprocess.run(
        [
            str(edge),
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={size},{size}",
            "--default-background-color=00000000",
            f"--screenshot={png}",
            svg.as_uri(),
        ],
        check=True,
        timeout=60,
    )


def main() -> None:
    edge = find_edge()
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "icon.png"
        render_png(edge, SVG, png, RENDER_SIZE, Path(tmp) / "profile")
        # with — чтобы файл закрылся до удаления временной папки: Windows не удаляет открытые файлы
        with Image.open(png) as source:
            image = source.convert("RGBA")
    if image.size != (RENDER_SIZE, RENDER_SIZE):
        raise SystemExit(f"Edge отрисовал {image.size}, а нужно {RENDER_SIZE}×{RENDER_SIZE}")
    if image.getpixel((0, 0))[3] != 0:
        raise SystemExit("Фон не прозрачный: левый верхний угол картинки непрозрачный")
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    image.save(PREVIEW)
    image.save(ICO, sizes=ICON_SIZES)
    print(f"Готово: {ICO} (превью — {PREVIEW})")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Сгенерировать `.ico` и проверить**

Run: `uv run --group build python scripts/make_icon.py`
Expected: `Готово: …\assets\icon.ico (превью — …\build\icon-preview.png)`.

Если скрипт остановился на проверке размера или прозрачности — не подгонять флаги вслепую: статус BLOCKED с выводом скрипта (спека: «если нет — другой способ рендера, тот же SVG»).

Run: `uv run --group build python -c "from PIL import Image; print(sorted(Image.open('assets/icon.ico').info['sizes']))"`
Expected: `[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]`

Контроллер показывает пользователю `build/icon-preview.png`.

- [ ] **Step 6: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `103 passed`.

- [ ] **Step 7: Коммит**

```bash
git add pyproject.toml uv.lock .gitignore assets/icon.svg assets/icon.ico scripts/make_icon.py
git commit -m "feat: add the split-queen app icon" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Скрипт сборки и настройки PyInstaller

**Files:**
- Create: `scripts/__init__.py`, `scripts/build_exe.py`, `chess-helper.spec`, `packaging/README.txt`, `packaging/licenses/proxy-tools.txt`, `packaging/licenses/webview2-sdk.txt`
- Test: `tests/test_build_exe.py` (новый)

**Interfaces:**
- Consumes: `assets/icon.ico` (задача 6), `--self-check` в `app.py` (задача 5).
- Produces: команда `uv run --group build python scripts/build_exe.py [--stockfish-only] [--expect-tag <тег>]`, кэш `build/cache/stockfish-sf_19/stockfish.exe`, `dist/chess-helper/`, `dist/chess-helper-v<версия>-windows-x64.zip` — используют задачи 8 и 9.

Перед шагом 8 нужны разрешённые пользователем скачивания: тексты лицензий proxy-tools (GitHub) и WebView2 SDK (nuget.org); перед шагом 9 — архив Stockfish sf_19 (≈81 МБ, GitHub).

- [ ] **Step 1: Написать падающие тесты**

`tests/test_build_exe.py`:

```python
"""Чистые функции скрипта сборки: версия и тег, обход зависимостей, лицензии, метка интернета."""
import sys
from pathlib import Path

import pytest

from scripts import build_exe


def test_read_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "1.2.3"\ndependencies = []\n', encoding="utf-8")
    assert build_exe.read_version(pyproject) == "1.2.3"


def test_check_tag_accepts_matching_tag():
    build_exe.check_tag("v0.1.0", "0.1.0")


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


@pytest.mark.skipif(sys.platform != "win32", reason="потоки NTFS есть только на Windows")
def test_mark_from_internet_writes_zone_identifier(tmp_path):
    (tmp_path / "sub").mkdir()
    dll = tmp_path / "sub" / "a.dll"
    dll.write_bytes(b"x")
    assert build_exe.mark_from_internet(tmp_path) == 1
    with open(f"{dll}:Zone.Identifier", "rb") as stream:
        assert stream.read() == b"[ZoneTransfer]\r\nZoneId=3\r\n"
```

- [ ] **Step 2: Убедиться, что тесты падают**

Run: `uv run pytest tests/test_build_exe.py -q`
Expected: ошибка сбора `ImportError: cannot import name 'build_exe' from 'scripts'` (или `ModuleNotFoundError`).

- [ ] **Step 3: Создать `scripts/__init__.py`**

```python
"""Скрипты сборки помогатора."""
```

- [ ] **Step 4: Создать `scripts/build_exe.py`**

```python
"""Сборка помогатора в zip для Windows: Stockfish, PyInstaller, лицензии, самопроверки.

Запуск: uv run --group build python scripts/build_exe.py [--stockfish-only] [--expect-tag vX.Y.Z]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
APP_NAME = "chess-helper"
APP_DIR = DIST / APP_NAME
LICENSE_OVERRIDES = ROOT / "packaging" / "licenses"

STOCKFISH_TAG = "sf_19"
STOCKFISH_URL = (
    "https://github.com/official-stockfish/Stockfish/releases/download/"
    f"{STOCKFISH_TAG}/stockfish-windows-x86-64-universal.zip"
)
STOCKFISH_SHA256 = "3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7"
STOCKFISH_CACHE = BUILD / "cache" / f"stockfish-{STOCKFISH_TAG}"
# Файл в архиве → имя в кэше
STOCKFISH_MEMBERS = {
    "stockfish/stockfish-windows-x86-64-universal.exe": "stockfish.exe",
    "stockfish/Copying.txt": "Copying.txt",
    "stockfish/AUTHORS": "AUTHORS",
}

SELF_CHECK_TIMEOUT = 120
ZONE_IDENTIFIER = b"[ZoneTransfer]\r\nZoneId=3\r\n"
LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|notice)", re.IGNORECASE)
EXE_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <runtime>
    <!-- .NET Framework не грузит DLL с меткой «скачано из интернета» без этой настройки -->
    <loadFromRemoteSources enabled="true"/>
  </runtime>
</configuration>
"""


def read_version(pyproject: Path = PYPROJECT) -> str:
    return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]


def check_tag(tag: str, version: str) -> None:
    if tag != f"v{version}":
        raise SystemExit(f"Тег {tag} не совпадает с версией {version} из pyproject.toml: ожидался v{version}")


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_distributions(pyproject: Path = PYPROJECT) -> list[metadata.Distribution]:
    """Установленные пакеты приложения: обход зависимостей от [project].dependencies с маркерами."""
    project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
    pending = [Requirement(spec) for spec in project["dependencies"]]
    found: dict[str, metadata.Distribution] = {}
    while pending:
        requirement = pending.pop()
        if requirement.marker is not None and not requirement.marker.evaluate({"extra": ""}):
            continue
        key = canonical(requirement.name)
        if key in found:
            continue
        dist = metadata.distribution(requirement.name)
        found[key] = dist
        pending.extend(Requirement(spec) for spec in dist.requires or [])
    return [found[key] for key in sorted(found)]


def license_files(dist) -> list[Path]:
    """Файлы лицензий из .dist-info пакета: папка licenses/ или LICENSE, COPYING, NOTICE."""
    files = []
    for file in dist.files or []:
        parts = file.parts
        if not parts or not parts[0].endswith(".dist-info"):
            continue
        if "licenses" in parts[1:-1] or LICENSE_NAME.match(parts[-1]):
            files.append(Path(file.locate()))
    return files


def collect_licenses(target: Path, dists, overrides: Path = LICENSE_OVERRIDES) -> None:
    """Копирует лицензии пакетов в target; если нет ни файла, ни запасного текста — ошибка."""
    target.mkdir(parents=True, exist_ok=True)
    missing = []
    for dist in dists:
        name = canonical(dist.metadata["Name"])
        files = license_files(dist)
        override = overrides / f"{name}.txt"
        if files:
            for file in files:
                dest = f"{name}-{file.name}"
                if not Path(dest).suffix:
                    dest += ".txt"
                shutil.copyfile(file, target / dest)
        elif override.exists():
            shutil.copyfile(override, target / f"{name}.txt")
        else:
            missing.append(name)
    if missing:
        raise SystemExit(
            "Нет текста лицензии для: " + ", ".join(missing)
            + f". Положи его в {overrides / '<пакет>.txt'}"
        )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_stockfish(cache: Path = STOCKFISH_CACHE) -> Path:
    """Скачивает архив sf_19 (если его нет в кэше), сверяет SHA-256, достаёт движок и лицензию."""
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "stockfish-windows-x86-64-universal.zip"
    if not archive.exists():
        print(f"Скачиваю {STOCKFISH_URL}")
        partial = archive.with_suffix(".part")
        urllib.request.urlretrieve(STOCKFISH_URL, partial)
        partial.replace(archive)
    actual = sha256(archive)
    if actual != STOCKFISH_SHA256:
        archive.unlink()
        raise SystemExit(f"SHA-256 архива Stockfish {actual} не совпал с ожидаемым; архив удалён — запусти сборку ещё раз")
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        absent = [member for member in STOCKFISH_MEMBERS if member not in names]
        if absent:
            listing = "\n".join(sorted(n for n in names if "/src/" not in n))
            raise SystemExit(f"В архиве Stockfish нет {absent}. Что в нём есть (без src/):\n{listing}")
        for member, name in STOCKFISH_MEMBERS.items():
            with zf.open(member) as src, open(cache / name, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return cache / "stockfish.exe"


def run_pyinstaller() -> None:
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", str(ROOT / "chess-helper.spec"),
            "--noconfirm", "--clean",
            "--distpath", str(DIST),
            "--workpath", str(BUILD / "pyinstaller"),
        ],
        cwd=ROOT,
        check=True,
    )


def assemble(stockfish: Path, version: str) -> None:
    """Докладывает в сборку движок, настройку .NET, README, LICENSE и лицензии компонентов."""
    engine_dir = APP_DIR / "_internal" / "engine"
    engine_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(stockfish, engine_dir / "stockfish.exe")
    (APP_DIR / f"{APP_NAME}.exe.config").write_text(EXE_CONFIG, encoding="utf-8")
    shutil.copyfile(ROOT / "LICENSE", APP_DIR / "LICENSE")
    readme = (ROOT / "packaging" / "README.txt").read_text(encoding="utf-8")
    # utf-8-sig и CRLF — чтобы README.txt правильно открывался в Блокноте
    (APP_DIR / "README.txt").write_text(readme.replace("{version}", version), encoding="utf-8-sig", newline="\r\n")
    licenses = APP_DIR / "licenses"
    collect_licenses(licenses, runtime_distributions())
    extras = {
        Path(sys.base_prefix) / "LICENSE.txt": "python-LICENSE.txt",
        stockfish.parent / "Copying.txt": "stockfish-Copying.txt",
        stockfish.parent / "AUTHORS": "stockfish-AUTHORS.txt",
        LICENSE_OVERRIDES / "webview2-sdk.txt": "webview2-sdk.txt",
        ROOT / "frontend" / "vendor" / "chessground" / "LICENSE": "chessground-LICENSE.txt",
    }
    for source, name in extras.items():
        shutil.copyfile(source, licenses / name)


def self_check_exe(app_dir: Path, report: Path) -> None:
    """Запускает chess-helper.exe --self-check и печатает отчёт; при ошибке останавливает сборку."""
    exe = app_dir / f"{APP_NAME}.exe"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.unlink(missing_ok=True)
    process = subprocess.Popen([str(exe), "--self-check", str(report)])
    try:
        code = process.wait(timeout=SELF_CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        # Убиваем всё дерево процессов: иначе оставшийся Stockfish держит файлы сборки
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False)
        process.wait()
        raise SystemExit(f"Самопроверка {app_dir} не уложилась в {SELF_CHECK_TIMEOUT} с")
    text = report.read_text(encoding="utf-8") if report.exists() else "(отчёта нет — подробности в логе)\n"
    print(f"Самопроверка {app_dir}:\n{text}", end="")
    if code != 0:
        raise SystemExit(f"Самопроверка {app_dir} не прошла: код {code}")


def mark_from_internet(folder: Path) -> int:
    """Пишет каждому файлу поток Zone.Identifier с ZoneId=3 — как Проводник при распаковке скачанного zip."""
    count = 0
    for path in folder.rglob("*"):
        if path.is_file():
            with open(f"{path}:Zone.Identifier", "wb") as stream:
                stream.write(ZONE_IDENTIFIER)
            count += 1
    return count


def motw_self_check() -> None:
    """Самопроверка на копии сборки, помеченной «скачано из интернета»."""
    workdir = BUILD / "motw-check"
    shutil.rmtree(workdir, ignore_errors=True)
    copy = workdir / APP_NAME
    shutil.copytree(APP_DIR, copy)
    print(f"Помечено «из интернета» файлов: {mark_from_internet(copy)}")
    try:
        self_check_exe(copy, BUILD / "selfcheck-motw-report.txt")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def make_zip(version: str) -> Path:
    archive = DIST / f"{APP_NAME}-v{version}-windows-x64.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(APP_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, (Path(APP_NAME) / path.relative_to(APP_DIR)).as_posix())
    return archive


def main(argv: list[str] | None = None) -> None:
    # В CI вывод идёт в канал в кодировке системы — без этого кириллица в выводе роняет скрипт
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Сборка помогатора в zip для Windows")
    parser.add_argument("--stockfish-only", action="store_true", help="только подготовить Stockfish в кэше")
    parser.add_argument("--expect-tag", help="тег релиза; должен быть равен v<версия из pyproject.toml>")
    args = parser.parse_args(argv)
    version = read_version()
    if args.expect_tag:
        check_tag(args.expect_tag, version)
    stockfish = prepare_stockfish()
    if args.stockfish_only:
        print(stockfish)
        return
    run_pyinstaller()
    assemble(stockfish, version)
    self_check_exe(APP_DIR, BUILD / "selfcheck-report.txt")
    motw_self_check()
    print(f"Готово: {make_zip(version)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Прогнать тесты**

Run: `uv run pytest -q`
Expected: `111 passed`.

- [ ] **Step 6: Создать `chess-helper.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
# Сборка помогатора PyInstaller'ом: папка dist/chess-helper с exe без консоли.
# Запускается из scripts/build_exe.py, который потом докладывает Stockfish, лицензии и настройку .NET.
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "app.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "assets" / "icon.ico"), "assets"),
    ],
    # Импортируются внутри функций (проверка при старте и самопроверка) — перечисляем явно
    hiddenimports=["webview.platforms.winforms", "webview.platforms.edgechromium"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="chess-helper",
    console=False,
    icon=str(ROOT / "assets" / "icon.ico"),
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="chess-helper", upx=False)
```

- [ ] **Step 7: Создать `packaging/README.txt`**

`{version}` скрипт заменяет на версию.

```
Chess Helper {version} — Windows
https://github.com/TheDragonBald/chess-helper

Run chess-helper.exe (double-click).

- Windows may show "Windows protected your PC" (SmartScreen): the program is
  not digitally signed. Click "More info" → "Run anyway".
- The Microsoft Edge WebView2 Runtime is required (preinstalled on Windows 11).
  If it is missing, the helper offers to open the download page.
- If the helper says it could not load its components, Windows has blocked the
  files downloaded from the internet: delete the unpacked folder, open the zip
  file's Properties, tick "Unblock" and unpack it again.
- Errors are written to %LOCALAPPDATA%\chess-helper\logs\helper.log

License: GPL-3.0 (LICENSE). Licenses of the bundled components are in the
"licenses" folder.
Source code of this version: https://github.com/TheDragonBald/chess-helper/tree/v{version}
Stockfish source code (GPL-3.0): https://github.com/official-stockfish/Stockfish/tree/sf_19

------------------------------------------------------------------------------

Шахматный помогатор {version} — Windows
https://github.com/TheDragonBald/chess-helper

Запуск — двойной клик по chess-helper.exe.

- Windows может показать «Система Windows защитила ваш компьютер» (SmartScreen):
  у программы нет цифровой подписи. Нажми «Подробнее» → «Выполнить в любом
  случае».
- Нужен Microsoft Edge WebView2 Runtime (на Windows 11 уже есть). Если его нет,
  помогатор предложит открыть страницу загрузки.
- Если помогатор пишет, что не удалось загрузить компоненты, Windows
  заблокировал скачанные из интернета файлы: удали распакованную папку, открой
  «Свойства» zip-архива, отметь «Разблокировать» и распакуй заново.
- Ошибки пишутся в %LOCALAPPDATA%\chess-helper\logs\helper.log

Лицензия: GPL-3.0 (файл LICENSE). Лицензии компонентов — в папке licenses.
Исходники этой версии: https://github.com/TheDragonBald/chess-helper/tree/v{version}
Исходники Stockfish (GPL-3.0): https://github.com/official-stockfish/Stockfish/tree/sf_19
```

- [ ] **Step 8: Тексты лицензий без файла в метаданных**

`packaging/licenses/proxy-tools.txt`. Найти файл лицензии в репозитории пакета:

Run: `gh api repos/jtushman/proxy_tools/contents -q '.[].name'`

Если среди файлов есть `LICENSE*` — взять его текст (`gh api repos/jtushman/proxy_tools/contents/<имя> -q .content | base64 -d`) и положить в файл после двух строк заголовка, как ниже. Если файла лицензии нет — записать стандартный текст MIT (лицензия указана в метаданных пакета: `License: MIT`, автор Jonathan Tushman):

```
proxy-tools 0.1.0 — MIT License
https://github.com/jtushman/proxy_tools

Copyright (c) Jonathan Tushman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

`packaging/licenses/webview2-sdk.txt` — лицензия NuGet-пакета `Microsoft.Web.WebView2` версии 1.0.3856.49 (это версия `Microsoft.Web.WebView2.Core.dll` в pywebview 6.2.1):

Run:
```bash
mkdir -p build
curl -sL "https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49/License" -o build/webview2-license.html
uv run python -c "import html, re; t = open('build/webview2-license.html', encoding='utf-8').read(); m = re.search(r'<pre[^>]*>(.*?)</pre>', t, re.S); print(html.unescape(m.group(1)).strip() if m else 'НЕТ <pre>')"
```

Записать файл: первая строка `Microsoft.Web.WebView2 1.0.3856.49 — DLL WebView2 из webview/lib пакета pywebview 6.2.1`, вторая — `https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49/License`, пустая строка, затем выведенный текст лицензии без изменений. Если вывелось `НЕТ <pre>` или текст пустой — статус BLOCKED.

- [ ] **Step 9: Полная сборка**

Run: `uv run --group build python scripts/build_exe.py`
Expected (порядок и суть):
- `Скачиваю https://github.com/official-stockfish/...` (только в первый раз);
- вывод PyInstaller, в конце `Build complete!`;
- `Самопроверка …\dist\chess-helper:` и строки `OK files: файлы на месте`, `OK engine: Stockfish: глубина 10, оценка …`, `OK dotnet: .NET-часть окна загружается`, `INFO renderer: pywebview выбрал бы движок окна: edgechromium`;
- `Помечено «из интернета» файлов: …` и такой же отчёт для `…\build\motw-check\chess-helper`;
- `Готово: …\dist\chess-helper-v0.1.0-windows-x64.zip`.

Если самопроверка падает с `ModuleNotFoundError` — дописать модуль в `hiddenimports` в `chess-helper.spec`, пересобрать и указать это в отчёте. Если обычная самопроверка проходит, а самопроверка на помеченной копии падает на `dotnet` — статус BLOCKED с обоими отчётами: по спеке это решается с пользователем. Если архив Stockfish устроен не так, как в `STOCKFISH_MEMBERS`, скрипт сам выведет содержимое архива — статус BLOCKED с этим выводом.

- [ ] **Step 10: Проверить состав zip**

Run:
```bash
uv run python -c "import zipfile; z = zipfile.ZipFile('dist/chess-helper-v0.1.0-windows-x64.zip'); n = z.namelist(); print(sorted({x.split('/')[1] for x in n})); print(sorted(x.split('/')[2] for x in n if x.startswith('chess-helper/licenses/')))"
```

Expected: первая строка — `['LICENSE', 'README.txt', '_internal', 'chess-helper.exe', 'chess-helper.exe.config', 'licenses']`; во второй — файлы лицензий `bottle`, `cffi`, `chess`, `chessground`, `clr-loader`, `proxy-tools`, `pycparser`, `python`, `pythonnet`, `pywebview`, `stockfish-AUTHORS`, `stockfish-Copying`, `typing-extensions`, `webview2-sdk`.

- [ ] **Step 11: Коммит**

```bash
git add scripts/__init__.py scripts/build_exe.py chess-helper.spec packaging/README.txt packaging/licenses/proxy-tools.txt packaging/licenses/webview2-sdk.txt tests/test_build_exe.py
git commit -m "build: add the PyInstaller spec and the release build script" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: GitHub Actions: сборка по тегу и черновик релиза

**Files:**
- Create: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `scripts/build_exe.py` с `--stockfish-only` и `--expect-tag` (задача 7).

- [ ] **Step 1: Создать `.github/workflows/release.yml`**

```yaml
# Сборка помогатора для Windows. Тег v* — черновик релиза с zip; ручной запуск — пробный прогон без релиза.
name: release

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    runs-on: windows-latest
    env:
      PYTHONUTF8: "1"  # кириллица в выводе скриптов и тестов
    steps:
      - uses: actions/checkout@v7

      # У setup-uv с v8 нет плавающих тегов вида v10 — только полные версии
      - uses: astral-sh/setup-uv@v10.3.3
        with:
          enable-cache: true

      - name: Install dependencies
        run: uv sync --group build

      - name: Prepare Stockfish
        run: uv run --group build python scripts/build_exe.py --stockfish-only

      # Тесты до сборки — так падение дешевле; с настоящим движком из кэша
      - name: Tests
        env:
          STOCKFISH_PATH: build/cache/stockfish-sf_19/stockfish.exe
        run: uv run pytest -q

      - name: Build
        shell: bash
        run: |
          if [ "${{ github.event_name }}" = "push" ]; then
            uv run --group build python scripts/build_exe.py --expect-tag "${{ github.ref_name }}"
          else
            uv run --group build python scripts/build_exe.py
          fi

      - name: Draft release
        if: github.event_name == 'push'
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
          TAG: ${{ github.ref_name }}
        run: |
          ZIP="dist/chess-helper-${TAG}-windows-x64.zip"
          if gh release view "$TAG" > /dev/null 2>&1; then
            gh release upload "$TAG" "$ZIP" --clobber
          else
            gh release create "$TAG" "$ZIP" --draft --generate-notes --title "Chess Helper $TAG"
          fi
```

- [ ] **Step 2: Проверить синтаксис YAML**

Run: `uv run --with pyyaml python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml', encoding='utf-8')); print('YAML ok')"`
Expected: `YAML ok`. Настоящая проверка — пробный прогон `workflow_dispatch` после мержа (см. «Финальная проверка»).

- [ ] **Step 3: Коммит**

```bash
git add .github/workflows/release.yml
git commit -m "ci: build the Windows zip and draft a release on version tags" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Stockfish sf_19 и документация

**Files:**
- Modify: `README.md`, `docs/ARCHITECTURE.md`, `docs/ABOUT_PROJECT.md`

**Interfaces:**
- Consumes: кэш `build/cache/stockfish-sf_19/stockfish.exe` (задача 7).

- [ ] **Step 1: Все тесты с sf_19**

Run (Git Bash): `STOCKFISH_PATH=build/cache/stockfish-sf_19/stockfish.exe uv run pytest -q`
(PowerShell: `$env:STOCKFISH_PATH = "build/cache/stockfish-sf_19/stockfish.exe"; uv run pytest -q`)
Expected: `111 passed` — из них 9 тестов `tests/test_engine.py` идут с sf_19. Если какой-то тест движка падает только с sf_19 — статус BLOCKED с выводом.

- [ ] **Step 2: `README.md`, английская часть**

Найти:

```
More (in Russian): [about the project](docs/ABOUT_PROJECT.md) and
[architecture](docs/ARCHITECTURE.md).

## Installation (Windows)
```

Заменить на:

```
More (in Russian): [about the project](docs/ABOUT_PROJECT.md) and
[architecture](docs/ARCHITECTURE.md).

## Download (Windows)

Download `chess-helper-v<version>-windows-x64.zip` from
[Releases](https://github.com/TheDragonBald/chess-helper/releases), unpack it
and run `chess-helper.exe`: Python and Stockfish are already inside.

- Windows may show "Windows protected your PC" (SmartScreen) because the
  program is not digitally signed: click "More info" → "Run anyway".
- The WebView2 Runtime is required (preinstalled on Windows 11). If it is
  missing, the helper offers to open the download page.
- If the helper says it could not load its components, Windows has blocked the
  downloaded files: delete the unpacked folder, open the zip file's
  Properties, tick "Unblock" and unpack it again.
- Errors are written to `%LOCALAPPDATA%\chess-helper\logs\helper.log`.

To run the helper from source instead, read on.

## Installation from source (Windows)
```

Найти:

```
Stockfish: download `stockfish-windows-x86-64-avx2.zip` (or
`stockfish-windows-x86-64.zip` if your CPU has no AVX2) from
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1. The
program is in the `stockfish` folder inside the archive (for example
`stockfish-windows-x86-64-avx2.exe`): copy it into the `engine` folder and
rename it to `stockfish.exe`, so the path is `engine/stockfish.exe`. You can
also keep it anywhere and put its full path into the `STOCKFISH_PATH`
environment variable.
```

Заменить на:

```
Stockfish: download `stockfish-windows-x86-64-universal.zip` from
https://github.com/official-stockfish/Stockfish/releases/tag/sf_19 (on Windows
on ARM — `stockfish-windows-arm64-universal.zip`). The program is
`stockfish/stockfish-windows-x86-64-universal.exe` inside the archive: copy it
into the `engine` folder and rename it to `stockfish.exe`, so the path is
`engine/stockfish.exe`. You can also keep it anywhere and put its full path
into the `STOCKFISH_PATH` environment variable.
```

Найти:

```
Errors (for example, why hints did not appear) are printed to the console the
helper was started from.
```

Заменить на:

```
Errors (for example, why hints did not appear) are written to
`%LOCALAPPDATA%\chess-helper\logs\helper.log` and printed to the console the
helper was started from.
```

Найти:

```
The board is [chessground](https://github.com/lichess-org/chessground)
(GPL-3.0); its files are in `frontend/vendor/chessground/`.
```

Заменить на:

```
The board is [chessground](https://github.com/lichess-org/chessground)
(GPL-3.0); its files are in `frontend/vendor/chessground/`.

The icon is our own drawing, also under GPL-3.0. Releases include Stockfish
(GPL-3.0); the licenses of all bundled components are in the `licenses` folder
of the zip.
```

- [ ] **Step 3: `README.md`, русская часть**

Найти:

```
Подробнее: [о проекте](docs/ABOUT_PROJECT.md) и [архитектура](docs/ARCHITECTURE.md).

## Установка (Windows)
```

Заменить на:

```
Подробнее: [о проекте](docs/ABOUT_PROJECT.md) и [архитектура](docs/ARCHITECTURE.md).

## Скачать (Windows)

Скачай `chess-helper-v<версия>-windows-x64.zip` из
[Releases](https://github.com/TheDragonBald/chess-helper/releases), распакуй и
запусти `chess-helper.exe`: Python и Stockfish уже внутри.

- Windows может показать «Система Windows защитила ваш компьютер» (SmartScreen):
  у программы нет цифровой подписи. Нажми «Подробнее» → «Выполнить в любом
  случае».
- Нужен WebView2 Runtime (на Windows 11 уже есть). Если его нет, помогатор
  предложит открыть страницу загрузки.
- Если помогатор пишет, что не удалось загрузить компоненты, Windows
  заблокировал скачанные файлы: удали распакованную папку, открой «Свойства»
  zip-архива, отметь «Разблокировать» и распакуй заново.
- Ошибки пишутся в `%LOCALAPPDATA%\chess-helper\logs\helper.log`.

Запуск из исходников — ниже.

## Установка из исходников (Windows)
```

Найти:

```
Stockfish: на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1 скачай
`stockfish-windows-x86-64-avx2.zip` (или `stockfish-windows-x86-64.zip`, если у
процессора нет AVX2). Программа лежит в архиве в папке `stockfish` (например,
`stockfish-windows-x86-64-avx2.exe`): скопируй её в папку `engine` и переименуй
в `stockfish.exe`, чтобы получилось `engine/stockfish.exe`. Можно положить её
куда угодно и указать полный путь в переменной окружения `STOCKFISH_PATH`.
```

Заменить на:

```
Stockfish: на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_19 скачай
`stockfish-windows-x86-64-universal.zip` (для Windows на ARM —
`stockfish-windows-arm64-universal.zip`). Программа лежит в архиве в папке
`stockfish` — `stockfish-windows-x86-64-universal.exe`: скопируй её в папку
`engine` и переименуй в `stockfish.exe`, чтобы получилось
`engine/stockfish.exe`. Можно положить её куда угодно и указать полный путь в
переменной окружения `STOCKFISH_PATH`.
```

Найти:

```
Ошибки (например, почему не появились подсказки) печатаются в консоль, из
которой запущен помогатор.
```

Заменить на:

```
Ошибки (например, почему не появились подсказки) пишутся в
`%LOCALAPPDATA%\chess-helper\logs\helper.log` и в консоль, из которой запущен
помогатор.
```

Найти:

```
Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.
```

Заменить на:

```
Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.

Иконка — наш собственный рисунок, тоже под GPL-3.0. В релизах лежит Stockfish
(GPL-3.0); лицензии всех компонентов сборки — в папке `licenses` внутри zip.
```

Пункт автора в «Good to know» / «Полезно знать» не трогать.

- [ ] **Step 4: `docs/ARCHITECTURE.md`**

1. Таблица библиотек, строку Stockfish заменить на:

```
| [Stockfish](https://stockfishchess.org/) | sf_19, сборка Windows x64 universal | Шахматный движок, отдельный процесс `engine/stockfish.exe`; в git не хранится, в zip-сборке лежит в `_internal/engine/` |
```

2. После строки `| pytest | ≥ 8 (группа `dev`) | Тесты |` добавить:

```
| [PyInstaller](https://pyinstaller.org/) | ≥ 6.22 (группа `build`) | Сборка exe папкой для релизов |
| [Pillow](https://python-pillow.org/) | ≥ 11 (группа `build`) | Сборка `assets/icon.ico` из PNG |
```

3. Блок дерева в «Структура файлов» (между ``` после заголовка) заменить целиком на:

```
app.py                       запуск: лог, самопроверка, проверка при старте, окно, связка Api ↔ окно, обход «поверх всех окон»
chess-helper.spec            настройки PyInstaller: сборка папкой, exe без консоли, иконка
backend/
  paths.py                   где лежат файлы в исходниках и в собранном exe, папка логов
  logs.py                    лог в файл и перехват необработанных исключений
  startup_check.py           проверка при старте: WebView2 и .NET-часть окна
  selfcheck.py               самопроверка собранного exe (--self-check)
  game.py                    GameSession — партия: ходы, отмена, FEN, статусы, история
  engine.py                  EngineAnalyzer — Stockfish в фоне: анализ, курьер доставки, падения, закрытие
  api.py                     Api — методы для JS; номер версии позиции rev; решает, анализировать ли
frontend/
  index.html                 разметка панели + import map для chessground
  main.js                    доска, панель, обработка ответов и подсказок, клавиши
  style.css                  тёмная тема, доска 560×560, панель 280 px
  vendor/chessground/        готовые файлы chessground (GPL-3.0)
assets/
  icon.svg                   иконка: исходник
  icon.ico                   иконка для exe и окна (16–256 px)
engine/
  .gitkeep                   папка есть в git; сюда кладётся stockfish.exe (игнорируется git)
scripts/
  build_exe.py               сборка zip: Stockfish, PyInstaller, лицензии, самопроверки
  make_icon.py               icon.svg → icon.ico (headless Edge + Pillow)
packaging/
  README.txt                 шаблон README для zip
  licenses/                  тексты лицензий, которых нет в метаданных пакетов
.github/workflows/
  release.yml                сборка по тегу v* → черновик релиза; вручную — пробный прогон
tests/
  test_game.py               правила партии (31 тест)
  test_api.py                Api с фейковым движком (16)
  test_engine_unit.py        EngineAnalyzer с фейковым процессом, без Stockfish (16)
  test_engine.py             EngineAnalyzer с настоящим Stockfish; пропускаются без exe (9)
  test_paths.py              пути в исходниках и в exe, папка логов (4)
  test_logs.py               лог в файл, ротация, без консоли, перехват исключений (9)
  test_startup_check.py      проверка при старте и сообщения (7)
  test_selfcheck.py          самопроверка и её отчёт (7)
  test_app.py                точка входа (4)
  test_build_exe.py          чистые функции скрипта сборки (8)
docs/
  ABOUT_PROJECT.md           о проекте
  ARCHITECTURE.md            этот документ
  superpowers/specs/…        спецификации (исходная и сборки exe)
  superpowers/plans/…        планы реализации — история, по шагам
pyproject.toml, uv.lock, .python-version, pytest.ini, .gitignore, LICENSE (GPL-3.0), README.md
```

4. В «`app.py` — сборка приложения» строку `- Настраивает логирование: `WARNING` и выше в консоль, из которой запущен помогатор.` заменить на:

```
- Первым делом `setup_logging()`: `WARNING` и выше — в `%LOCALAPPDATA%\chess-helper\logs\helper.log` (до трёх файлов по 1 МБ) и в консоль, если она есть; необработанные исключения, в том числе в потоках, тоже пишутся в лог.
- С аргументами `--self-check <отчёт>` запускает самопроверку собранного exe и выходит с её кодом.
- Иначе `check_startup()`: без WebView2 или если .NET-часть окна не загрузилась — системное окно с объяснением, и помогатор закрывается. Тяжёлые модули (pywebview, бэкенд) импортируются только после этого, в `run_app()`.
```

В той же секции фразу `` `webview.start(http_server=True)` раздаёт `frontend/` встроенным сервером.`` заменить на `` `webview.start(http_server=True, icon=…/assets/icon.ico)` раздаёт `frontend/` встроенным сервером; `icon` нужен для иконки окна при запуске из исходников (в exe pywebview берёт её из файла exe).``

5. В таблицу «Обработка ошибок» после строки `| Исключение при вызове бэка из JS | … |` добавить:

```
| Нет WebView2 | До окна — системное сообщение со ссылкой на страницу загрузки Microsoft |
| .NET-часть окна не загрузилась (например, файлы заблокированы как скачанные из интернета) | Системное сообщение с инструкцией «Свойства → Разблокировать», трассировка в лог |
| Необработанное исключение | Пишется в лог с трассировкой |
```

6. В «Тесты»: к пункту `test_engine_unit.py` в конце (перед точкой) дописать `, запуск без окна консоли`; после пункта `test_engine.py` добавить:

```
- `test_paths.py`, `test_logs.py` — пути в исходниках и в exe, папка логов; лог в файл, ротация, работа без консоли, перехват необработанных исключений.
- `test_startup_check.py`, `test_selfcheck.py`, `test_app.py` — проверка при старте и сообщения, самопроверка и её отчёт, точка входа.
- `test_build_exe.py` — чистые функции скрипта сборки: версия и тег, обход зависимостей, сбор лицензий, метка «из интернета».
```

7. Перед заголовком `## Решения и почему` вставить раздел:

```
## Сборка exe

Релиз — zip с папкой `chess-helper/`: `chess-helper.exe` без консоли, `chess-helper.exe.config`, служебная папка `_internal/` (Python, библиотеки, `frontend/`, `assets/icon.ico`, `engine/stockfish.exe`), `LICENSE`, `README.txt` и `licenses/`.

- **Скрипт** `uv run --group build python scripts/build_exe.py`: версия из `pyproject.toml` (с `--expect-tag` — сверка с тегом); Stockfish sf_19 в кэш `build/cache/stockfish-sf_19/` со сверкой SHA-256; PyInstaller по `chess-helper.spec`; движок, `chess-helper.exe.config`, `LICENSE`, `README.txt` из `packaging/` и лицензии всех пакетов сборки (обход зависимостей по метаданным; если файла нет — текст из `packaging/licenses/`, иначе ошибка); самопроверка; самопроверка на копии с меткой «из интернета»; zip `dist/chess-helper-v<версия>-windows-x64.zip`. С `--stockfish-only` только готовит движок.
- **Пути в exe.** `backend/paths.app_root()` — `sys._MEIPASS` (папка `_internal`) в сборке и корень репозитория в исходниках; фронтенд pywebview находит сам.
- **Без чёрного окна.** Stockfish запускается с `CREATE_NO_WINDOW`: иначе у exe без консоли Windows открыла бы для движка отдельное окно консоли.
- **Лог.** `backend/logs.py` — файл в `%LOCALAPPDATA%\chess-helper\logs\`, перехват `sys.excepthook` и `threading.excepthook`.
- **Проверка при старте.** `backend/startup_check.py` импортирует `webview.platforms.winforms` и читает его `renderer`: решение принимает сам pywebview, поэтому проверка с ним не расходится. Без WebView2 pywebview выбрал бы Internet Explorer, в котором доска не работает.
- **Метка «из интернета».** Проводник помечает файлы из скачанного zip, а .NET Framework не грузит такие DLL через `Assembly.LoadFrom` без `loadFromRemoteSources` — её включает `chess-helper.exe.config`. Скрипт сборки проверяет это самопроверкой на помеченной копии.
- **Самопроверка.** `chess-helper.exe --self-check <отчёт>`: файлы сборки, вложенный Stockfish (без учёта `STOCKFISH_PATH`) считает начальную позицию, грузится .NET-часть окна (`webview.platforms.edgechromium`); строки `OK`/`FAIL`/`INFO`, код 0 или 1.
- **Иконка.** `assets/icon.svg` — исходник; `scripts/make_icon.py` рендерит его headless Edge в PNG 512×512 и собирает `assets/icon.ico` Pillow'ом. В exe иконку окна pywebview берёт из файла exe.
- **GitHub Actions** (`.github/workflows/release.yml`): по тегу `v*` на `windows-latest` — Stockfish, тесты с настоящим движком, сборка, черновик релиза; ручной запуск — то же без релиза.
```

8. В «Решения и почему» в конец списка добавить:

```
- **Сборка папкой, а не одним exe.** Один exe при каждом запуске распаковывается во временную папку вместе с движком на десятки мегабайт, стартует медленнее и чаще смущает антивирусы.
- **Проверка WebView2 через сам pywebview.** Своя копия его логики могла бы с ним разойтись; спрашивать `renderer` у pywebview надёжнее.
```

9. В «Известные ограничения» строку `- Логи только в консоли, без файла ([#12](https://github.com/TheDragonBald/chess-helper/issues/12)).` заменить на:

```
- Нет сторожа зависаний и дампа потоков ([#12](https://github.com/TheDragonBald/chess-helper/issues/12)).
- Exe без цифровой подписи: при первом запуске SmartScreen предупреждает.
```

- [ ] **Step 5: `docs/ABOUT_PROJECT.md`**

1. В таблицу «Где лежит» после строки GitHub добавить:

```
| Готовая сборка (zip для Windows) | https://github.com/TheDragonBald/chess-helper/releases |
```

2. В абзац под таблицей в конец дописать: ` Готовый zip собирает `scripts/build_exe.py`, а по тегу `v*` — GitHub Actions (черновик релиза).`

3. В «Удобства» после строки про «Поверх всех окон» добавить:

```
- Готовая сборка для Windows: zip с exe, внутри Python и Stockfish; ошибки пишутся в лог-файл.
```

4. В «Как начать» найти:

````
Подробно — в [README](../README.md). Коротко:

```bash
uv sync
```

Скачать `stockfish-windows-x86-64-avx2.zip` из релиза [sf_17.1](https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1), положить exe из архива в `engine/` и переименовать в `stockfish.exe`. Затем:
````

Заменить на:

````
Проще всего — скачать zip из [Releases](https://github.com/TheDragonBald/chess-helper/releases), распаковать и запустить `chess-helper.exe`; подробности, в том числе про SmartScreen и разблокировку файлов, — в [README](../README.md).

Из исходников:

```bash
uv sync
```

Скачать `stockfish-windows-x86-64-universal.zip` из релиза [sf_19](https://github.com/official-stockfish/Stockfish/releases/tag/sf_19), положить `stockfish/stockfish-windows-x86-64-universal.exe` из архива в `engine/` и переименовать в `stockfish.exe`. Затем:
````

5. В «Ограничения» после `- Только Windows.` добавить:

```
- Exe без цифровой подписи: при первом запуске SmartScreen предупреждает.
```

6. В «История» после строки `| Документация | … |` добавить:

```
| Сборка exe | Zip с exe для Windows (PyInstaller) и черновик релиза по тегу через GitHub Actions; Stockfish sf_19; лог в файл; проверка WebView2 при старте; самопроверка сборки; своя иконка |
```

7. В «Планы»:
   - строки `#7` и `#9` в «Запуск и сборка» удалить, у строки `#3` в конце поставить точку вместо `;`;
   - строку `#17` в «Удобство» закончить `;` и после неё добавить `- [#23](https://github.com/TheDragonBald/chess-helper/issues/23) — несколько стилей фигур на выбор.`;
   - строку `#12` заменить на `- [#12](https://github.com/TheDragonBald/chess-helper/issues/12) — сторож зависаний и дамп потоков.`

- [ ] **Step 6: Проверить документацию**

Run: `grep -n "17\.1\|avx2" README.md docs/ABOUT_PROJECT.md docs/ARCHITECTURE.md`
Expected: пусто (код 1).

Run: `uv run pytest --collect-only -q | tail -1`
Expected: `111 tests collected` — числа в дереве `docs/ARCHITECTURE.md` должны с этим сходиться (31 + 16 + 16 + 9 + 4 + 9 + 7 + 7 + 4 + 8 = 111).

- [ ] **Step 7: Коммит**

```bash
git add README.md docs/ARCHITECTURE.md docs/ABOUT_PROJECT.md
git commit -m "docs: document the Windows build and switch to Stockfish sf_19" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Финальная проверка (контроллер)

1. Финальное ревью всей ветки (subagent-driven-development).
2. `uv run pytest -q` — `111 passed`; то же с `STOCKFISH_PATH` на sf_19.
3. `uv run --group build python scripts/build_exe.py` — zip собран, обе самопроверки проходят.
4. Ручная проверка пользователем на локальном zip:
   - распаковать, запустить двойным кликом: окно с доской и иконкой, подсказки появляются, чёрного окна нет;
   - распаковать в папку с кириллицей и пробелами (например, `D:\Тест папка\`) и запустить;
   - подложить вместо `_internal\engine\stockfish.exe` неработающий файл: в панели сообщение об ошибке, в `helper.log` запись.
5. PR по gitworking: тело на русском, `closes #7`, `closes #9`.
6. После мержа: пробный прогон `workflow_dispatch`; затем тег `v0.1.0` → черновик релиза; скачать zip браузером, распаковать Проводником, запустить — настоящая проверка метки «из интернета»; опубликовать релиз; отметить в #12, что лог в файл сделан.
