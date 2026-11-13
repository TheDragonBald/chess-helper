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


def test_info_of_logger_with_own_level_is_not_written(tmp_path):
    # Как у pywebview: свой уровень INFO у логгера обходит уровень корня
    log_file = logs.setup_logging(tmp_path)
    chatty = logging.getLogger("test.own-level")
    chatty.setLevel(logging.INFO)
    try:
        chatty.info("болтовня")
        flush()
    finally:
        chatty.setLevel(logging.NOTSET)
    assert "болтовня" not in log_file.read_text(encoding="utf-8")


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
