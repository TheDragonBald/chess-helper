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
    if not path.exists():
        raise FileNotFoundError(f"нет {path}")
    engine = chess.engine.SimpleEngine.popen_uci(str(path), **popen_args())
    try:
        info = engine.analyse(chess.Board(), chess.engine.Limit(depth=ENGINE_DEPTH, time=ENGINE_TIME))
    finally:
        # Ошибка quit() у зависшего движка не должна подменять причину сбоя, а close() не оставит
        # недемонный поток python-chess, из-за которого exe не смог бы завершиться
        try:
            engine.quit()
        except (chess.engine.EngineError, TimeoutError):
            engine.close()
    score = info.get("score")
    if score is None:
        raise RuntimeError("движок не выдал оценку")
    return f"Stockfish: глубина {info.get('depth')}, оценка {score.white()}"


def check_dotnet(root: Path) -> str:
    # Грузит pythonnet, WinForms и обе DLL WebView2 независимо от реестра; окно не создаётся
    import webview.platforms.edgechromium  # noqa: F401

    return ".NET-часть окна загружается"


def check_renderer(root: Path) -> Info:
    # Справка — только выбор движка окна: например, на раннере без WebView2 pywebview выбрал бы
    # Internet Explorer, и это не ошибка. Сбой импорта — ошибка: приложение при старте импортирует
    # именно webview.platforms.winforms, а check_dotnet грузит только edgechromium
    from backend.startup_check import load_winforms_renderer

    return Info(f"pywebview выбрал бы движок окна: {load_winforms_renderer()}")


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
