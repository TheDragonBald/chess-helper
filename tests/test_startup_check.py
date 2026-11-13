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


def test_no_webview2_message_asks_to_restart_after_install():
    box = Box(7)
    show_startup_problem(NO_WEBVIEW2, None, message_box=box, open_url=lambda url: None)
    assert box.calls[0][0].endswith("Открыть страницу загрузки Microsoft? После установки запусти помогатор снова.")


def test_dotnet_message_mentions_log_and_unblock(tmp_path):
    box, opened = Box(1), []
    log_file = tmp_path / "helper.log"
    show_startup_problem(DOTNET, log_file, message_box=box, open_url=opened.append)
    text, title, flags = box.calls[0]
    assert str(log_file) in text
    assert "Разблокировать" in text
    assert flags == startup_check.MB_OK | startup_check.MB_ICONERROR
    assert opened == []


def test_dotnet_message_without_log_file_says_log_failed():
    # setup_logging() возвращает None, если папку лога не открыть
    box = Box(1)
    show_startup_problem(DOTNET, None, message_box=box, open_url=lambda url: None)
    text = box.calls[0][0]
    assert text.endswith("распакуй заново.\n\nЛог записать не удалось.")
    assert "в логе" not in text
