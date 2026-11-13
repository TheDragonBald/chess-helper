"""Делает assets/icon.ico из assets/icon.svg: headless Edge рендерит PNG, Pillow собирает .ico.

Запуск: uv run --group build python scripts/make_icon.py
"""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "assets" / "icon.svg"
ICO = ROOT / "assets" / "icon.ico"
PREVIEW = ROOT / "build" / "icon-preview.png"
RENDER_SIZE = 512
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
EDGE_TIMEOUT = 60  # секунд на отрисовку
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
        timeout=EDGE_TIMEOUT,
    )
    # msedge.exe может перезапустить себя дочерним процессом и сразу выйти с кодом 0 —
    # тогда картинки ещё нет. Ждём, пока она появится и Edge отпустит профиль (исчезнет lockfile)
    lock = profile / "lockfile"
    deadline = time.monotonic() + EDGE_TIMEOUT
    while not png.exists() or lock.exists():
        if time.monotonic() > deadline:
            raise SystemExit(f"Edge не отрисовал {png.name} за {EDGE_TIMEOUT} с")
        time.sleep(0.2)


def main() -> None:
    edge = find_edge()
    # ignore_cleanup_errors — на случай, если вспомогательный процесс Edge ещё держит файл профиля
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
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
