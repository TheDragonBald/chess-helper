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
    dists = runtime_distributions()
    # PyInstaller кладёт setuptools в сборку через runtime-хуки, поэтому прикладываем и его лицензию
    if (APP_DIR / "_internal" / "setuptools").exists():
        dists.append(metadata.distribution("setuptools"))
    collect_licenses(licenses, dists)
    extras = {
        Path(sys.base_prefix) / "LICENSE.txt": "python-LICENSE.txt",
        stockfish.parent / "Copying.txt": "stockfish-Copying.txt",
        stockfish.parent / "AUTHORS": "stockfish-AUTHORS.txt",
        LICENSE_OVERRIDES / "webview2-sdk.txt": "webview2-sdk.txt",
        LICENSE_OVERRIDES / "openssl.txt": "openssl.txt",
        LICENSE_OVERRIDES / "libffi.txt": "libffi.txt",
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
    # line_buffering — чтобы наши строки шли по порядку с выводом PyInstaller, а не в конце
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
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
