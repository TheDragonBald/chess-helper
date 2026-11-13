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
