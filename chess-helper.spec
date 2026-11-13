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
