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
    # Уровень и у обработчика: логгер со своим уровнем INFO/DEBUG (например, pywebview)
    # иначе писал бы в файл в обход уровня корня
    handler.setLevel(logging.WARNING)
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
