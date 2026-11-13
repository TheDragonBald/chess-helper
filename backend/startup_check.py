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
    "Открыть страницу загрузки Microsoft? После установки запусти помогатор снова."
)
DOTNET_TEXT = (
    "Не удалось загрузить компоненты помогатора. Если архив скачан из интернета, "
    "Windows мог заблокировать файлы: удали распакованную папку, открой «Свойства» "
    "zip-архива, отметь «Разблокировать» и распакуй заново.\n\n"
    "{details}"
)
# Последний абзац DOTNET_TEXT: где лог или что записать его не удалось (setup_logging вернул None)
DOTNET_LOG_DETAILS = "Подробности — в логе: {log_file}"
DOTNET_NO_LOG_DETAILS = "Лог записать не удалось."


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
    if log_file is not None:
        details = DOTNET_LOG_DETAILS.format(log_file=log_file)
    else:
        details = DOTNET_NO_LOG_DETAILS
    message_box(DOTNET_TEXT.format(details=details), TITLE, MB_OK | MB_ICONERROR)
