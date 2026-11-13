# Сборка помогатора в exe для Windows — дизайн

Дата: 2026-11-13. Закрывает [#7](https://github.com/TheDragonBald/chess-helper/issues/7) (сборка exe) и [#9](https://github.com/TheDragonBald/chess-helper/issues/9) (Stockfish sf_19), частично [#12](https://github.com/TheDragonBald/chess-helper/issues/12) (лог в файл).

## Цель

Скачал zip из GitHub Releases, распаковал, запустил `chess-helper.exe` двойным кликом — и помогатор работает. Без Python, uv и консоли; Stockfish уже внутри.

## Решения

| Вопрос | Решение |
|---|---|
| Формат | Папка в zip (PyInstaller onedir), а не один exe: запуск мгновенный, антивирусы ругаются реже |
| Инструмент | PyInstaller: pywebview его официально поддерживает, в pyinstaller-hooks-contrib есть `hook-webview`, `hook-clr`, `hook-clr_loader` |
| Где собирается | Скрипт `scripts/build_exe.py` на компьютере разработчика и GitHub Actions по тегу `v*`, который создаёт черновик релиза |
| Stockfish | sf_19, архив `stockfish-windows-x86-64-universal.zip`: сборка сама выбирает инструкции процессора, поэтому работает на любом x86-64. README и ABOUT переходят на sf_19 (#9) |
| Консоль | Нет. Ошибки пишутся в лог-файл |
| Иконка | Свой рисунок ферзя, вариант «кремовый и чёрный» (SVG ниже) |
| Версия первого релиза | `v0.1.0`, из `pyproject.toml` |

## Не входит

- Цифровая подпись exe, установщик, автообновление.
- Сторож зависаний и дамп потоков — остаются в #12.
- CI на каждый PR — #10.
- Заставка «окно или браузер» — #2; стили фигур — #23.

## Что получает пользователь

Архив `chess-helper-v0.1.0-windows-x64.zip`:

```
chess-helper/
├── chess-helper.exe
├── _internal/        # Python, библиотеки, frontend/, assets/icon.ico, engine/stockfish.exe
├── LICENSE           # GPL-3.0
├── README.txt        # запуск, WebView2, SmartScreen, где лог, ссылки на исходники
└── licenses/         # лицензии компонентов сборки
```

`licenses/` собирается автоматически:
- Stockfish — файлы лицензии из архива sf_19;
- Python — `LICENSE.txt` из установки Python, которой собирается exe;
- Python-пакеты сборки — файлы лицензий из метаданных установленных пакетов, обход зависимостей начиная с `[project].dependencies` (сейчас это chess, pywebview, pythonnet, clr-loader, bottle, proxy-tools, typing-extensions).

BSD и MIT требуют прикладывать уведомления к бинарной сборке, GPL — давать доступ к исходникам: ссылки на исходники помогатора (тег релиза) и Stockfish (тег sf_19) — в `README.txt`.

`README.txt` двуязычный (английский, затем русский), шаблон — `packaging/README.txt` с подстановкой версии.

## Изменения в коде

### `backend/paths.py` (новый)

- `app_root() -> Path` — в собранном exe `Path(sys._MEIPASS)` (папка `_internal`), иначе корень репозитория. Признак сборки — `getattr(sys, "frozen", False)`.
- `log_dir() -> Path` — `%LOCALAPPDATA%\chess-helper\logs`; если переменной нет — `~\AppData\Local\chess-helper\logs`.

Через `app_root()` считаются путь к движку по умолчанию (`engine/stockfish.exe`), к иконке (`assets/icon.ico`) и к фронтенду для самопроверки. Фронтенд для окна pywebview по-прежнему находит сам: его `get_app_root()` уже знает про `sys._MEIPASS`.

### `backend/logs.py` (новый)

`setup_logging(directory: Path | None = None) -> Path | None` заменяет `logging.basicConfig` в `app.py`:
- файл `helper.log` в `directory` (по умолчанию `log_dir()`), `RotatingFileHandler(maxBytes=1_000_000, backupCount=2, encoding="utf-8")` — не больше трёх файлов по 1 МБ;
- уровень WARNING, формат как сейчас: `%(asctime)s %(levelname)s %(name)s: %(message)s`;
- вывод в консоль — только если `sys.stderr` не `None` (у exe без консоли его нет);
- если папку создать нельзя — остаётся только консоль, функция возвращает `None`, помогатор не падает;
- повторный вызов не дублирует обработчики.

Возвращает путь к файлу лога.

### `backend/engine.py`

- Движок запускается так: `SimpleEngine.popen_uci(str(self.path), **popen_args())`. На Windows `popen_args()` возвращает `{"creationflags": subprocess.CREATE_NO_WINDOW}`, иначе `{}`. Без флага у exe без консоли Windows открывает для Stockfish отдельное чёрное окно, а если его закрыть, движок завершается.
- `DEFAULT_PATH = app_root() / "engine" / "stockfish.exe"`; переменная `STOCKFISH_PATH` по-прежнему главнее.

### `backend/webview2.py` (новый)

Без WebView2 pywebview 6.2.1 молча переключается на движок Internet Explorer, который не понимает `<script type="module">` и import map: окно открывается, но доски нет и ничего не работает.

- `webview2_installed(read_value=...) -> bool` повторяет проверку `_is_chromium()` из `webview/platforms/winforms.py` pywebview 6.2.1: .NET Framework не ниже 4.6.2 (`Release` ≥ 394802) и одна из сборок WebView2 (Runtime, Beta, Dev, Canary) версии не ниже 86.0.622.0 в `HKCU` или `HKLM` (на 64-битной Windows — ветка `WOW6432Node`). Функция чтения реестра передаётся параметром, чтобы тесты подставляли фейк. Модуль `webview.platforms.winforms` не импортируется: при отсутствии WebView2 его импорт сразу включает режим Internet Explorer.
- `show_webview2_missing(message_box=..., open_url=...)` — системное окно `MessageBoxW` с кнопками «Да» / «Нет» и текстом «Для работы помогатора нужен Microsoft Edge WebView2 Runtime. Открыть страницу загрузки Microsoft?». «Да» открывает https://developer.microsoft.com/microsoft-edge/webview2/ в браузере. В лог пишется предупреждение.

### `backend/selfcheck.py` (новый)

`run_self_check(report: Path) -> int` проверяет собранный exe без окна, чтобы сломанная сборка не попала в релиз. Запускается только при проверке сборки (скрипт и CI), при обычном старте её нет.
1. `frontend/index.html` и `frontend/vendor/chessground/` лежат в `app_root()`;
2. Stockfish запускается (с тем же `CREATE_NO_WINDOW`) и выдаёт оценку начальной позиции на глубине 10, таймаут 30 секунд;
3. загружается .NET-часть pywebview — `import webview.platforms.winforms` (pythonnet, WinForms, DLL WebView2), окно при этом не создаётся;
4. справочно — найден ли WebView2 (`INFO`, не ошибка: на раннере GitHub его может не быть).

Каждая проверка пишет в отчёт строку `OK …`, `FAIL …: причина` или `INFO …`. Код возврата — 0, если ни одного `FAIL`, иначе 1. Зависимости проверок передаются параметрами, чтобы их можно было подменить в тестах.

### `app.py`

```python
def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    setup_logging()
    if argv[:1] == ["--self-check"]:
        if len(argv) != 2:
            sys.exit(2)  # нужен путь к файлу отчёта
        sys.exit(run_self_check(Path(argv[1])))
    if not webview2_installed():
        show_webview2_missing()
        return
    ...  # как сейчас
    webview.start(http_server=True, icon=str(app_root() / "assets" / "icon.ico"))
```

Иконку окна pywebview в exe и сам берёт из файла exe, но параметр `icon` нужен, чтобы иконка была и при запуске `uv run app.py`.

## Иконка

- `assets/icon.svg` — исходник, утверждённый в чате: свой ферзь без контура, разрезанный по диагонали; кремовая половина (`#f2ecdf`, детали `#ddd3bf`) — на тёмной клетке `#b58863`, чёрная (`#222222`, детали `#3a3a3a`) — на светлой `#f0d9b5`. Цвета клеток — как у доски помогатора (тема brown).
- `assets/icon.ico` — размеры 16, 24, 32, 48, 64, 128, 256. Его делает `scripts/make_icon.py`: headless Edge (`msedge --headless`, есть в Windows 11) рендерит SVG в PNG 512×512 с прозрачным фоном, Pillow уменьшает и собирает .ico. Файл .ico коммитится, поэтому для обычной сборки ни Edge, ни Pillow не нужны.
- Рисунок свой, распространяется под GPL-3.0 вместе с проектом.

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
      <circle cx="78" cy="26" r="3.6"/>
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
</svg>
```

## Сборка

### Зависимости

В `pyproject.toml` — новая группа `build = ["pyinstaller>=6.22", "pillow>=11"]`. Обычный `uv sync` её не ставит; для сборки — `uv sync --group build`.

### `chess-helper.spec`

Файл настроек PyInstaller в корне репозитория:
- точка входа `app.py`;
- данные: `frontend/` → `frontend/`, `assets/icon.ico` → `assets/`;
- `EXE(name="chess-helper", console=False, icon="assets/icon.ico", upx=False)` — UPX выключен, с ним антивирусы ругаются чаще;
- `COLLECT(name="chess-helper")` — сборка папкой, служебные файлы в `_internal/` (по умолчанию в PyInstaller 6).

### `scripts/build_exe.py`

Одна команда `uv run python scripts/build_exe.py`:
1. Читает версию из `pyproject.toml` (`tomllib`).
2. Готовит Stockfish в кэше `build/cache/stockfish-sf_19/`: если кэша нет, скачивает `https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip`, всегда сверяет SHA-256 с зашитым `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7` (из данных релиза на GitHub), кладёт exe движка как `build/cache/stockfish-sf_19/stockfish.exe`, рядом — файлы лицензии из архива. Папку `engine/` разработчика не трогает.
3. Запускает PyInstaller: `python -m PyInstaller chess-helper.spec --noconfirm --clean --distpath dist --workpath build/pyinstaller`.
4. Кладёт движок в `dist/chess-helper/_internal/engine/stockfish.exe`.
5. Добавляет `LICENSE`, `README.txt` из шаблона и папку `licenses/`.
6. Запускает `chess-helper.exe --self-check <отчёт>` (таймаут 120 с), печатает отчёт; при ненулевом коде — останавливается с ошибкой.
7. Упаковывает `dist/chess-helper/` в `dist/chess-helper-v<версия>-windows-x64.zip` (внутри — папка `chess-helper/`).

В `.gitignore` добавляются `build/` и `dist/`.

### GitHub Actions: `.github/workflows/release.yml`

- Запуск: push тега `v*` и вручную (`workflow_dispatch`) — ручной запуск делает всё, кроме релиза, для пробного прогона.
- `runs-on: windows-latest`, `permissions: contents: write`.
- Шаги:
  1. `actions/checkout@v7`, `astral-sh/setup-uv@v10` с кэшем;
  2. `uv sync --group build`;
  3. для тега — проверка, что тег равен `v` + версия из `pyproject.toml`, иначе ошибка;
  4. `uv run python scripts/build_exe.py`;
  5. `uv run pytest` с `STOCKFISH_PATH=build/cache/stockfish-sf_19/stockfish.exe` — проходят и тесты с настоящим движком;
  6. для тега — `gh release create <тег> dist/chess-helper-<тег>-windows-x64.zip --draft --generate-notes`.

Релиз создаётся черновиком: его смотрят и публикуют вручную.

`workflow_dispatch` срабатывает, только когда workflow уже лежит в основной ветке, поэтому пробный прогон — после мержа и до первого тега.

## Stockfish sf_19 (#9)

- Все тесты, включая `tests/test_engine.py`, проходят с sf_19 локально и в CI.
- README (обе части) и `docs/ABOUT_PROJECT.md`: ссылка на релиз sf_19, архив `stockfish-windows-x86-64-universal.zip`, точное имя exe внутри архива, шаг «скопируй в `engine/` и переименуй в `stockfish.exe`», упоминание сборки arm64 для Windows на ARM.

## Документация

- README, обе части: новый первый раздел «Download (Windows)» / «Скачать (Windows)» — ссылка на Releases, распаковать, запустить `chess-helper.exe`; предупреждение SmartScreen проходят через «Подробнее → Выполнить в любом случае» (exe без подписи); нужен WebView2 Runtime; где лог. Установка из исходников — ниже, как сейчас.
- README, «Запуск»: ошибки пишутся в `%LOCALAPPDATA%\chess-helper\logs\helper.log` и в консоль, если она есть.
- README, «Лицензии»: иконка — свой рисунок под GPL-3.0; в релизе лежит Stockfish (GPL-3.0).
- `docs/ARCHITECTURE.md`: раздел «Сборка exe» (spec, скрипт, CI, пути в exe, самопроверка, лог, проверка WebView2, `CREATE_NO_WINDOW`, иконка), обновлённое дерево файлов; в ограничениях вместо «логи только в консоли» — «нет сторожа зависаний (#12)».
- `docs/ABOUT_PROJECT.md`: в «Как начать» и «Где лежит» — готовая сборка; строка в «Истории»; в «Планах» убрать #7 и #9, добавить #23, у #12 оставить сторож зависаний и дамп потоков.

## Тесты

Модульные (pytest, по TDD):
- `tests/test_paths.py` — `app_root()` из исходников указывает на корень репозитория, в сборке (подменённые `sys.frozen`, `sys._MEIPASS`) — на `_MEIPASS`; `log_dir()` берёт `LOCALAPPDATA`, без неё — домашнюю папку.
- `tests/test_logs.py` — файл создаётся и в него пишется WARNING; без `sys.stderr` нет консольного обработчика и нет ошибки; повторный вызов не дублирует обработчики; недоступная папка — `None` без исключения; параметры ротации.
- `tests/test_engine_unit.py` — `popen_uci` получает `creationflags=CREATE_NO_WINDOW` (только Windows).
- `tests/test_webview2.py` — фейковый реестр: Runtime есть; нет; версия ниже 86.0.622.0; `0.0.0.0`; только в `HKCU`; .NET ниже 4.6.2. Окно сообщения: «Да» открывает страницу, «Нет» — нет.
- `tests/test_selfcheck.py` — всё в порядке → 0 и строки `OK`; нет фронтенда, движок не запускается, .NET-часть не грузится → `FAIL` и 1.
- `tests/test_app.py` — без WebView2 показывается сообщение и окно не создаётся; `--self-check <путь>` вызывает самопроверку и возвращает её код; `--self-check` без пути — код 2.

Проверка сборки:
- `scripts/build_exe.py` у разработчика: zip собирается, самопроверка проходит.
- Вручную: распаковать zip, запустить двойным кликом — окно с доской и иконкой, подсказки появляются, чёрного окна нет; если подложить вместо движка неработающий файл — в панели сообщение об ошибке, в логе запись.
- В CI: пробный прогон `workflow_dispatch` после мержа, затем тег `v0.1.0` → черновик релиза.

## Что выяснить при реализации

- Имя exe и файлы лицензии в архиве sf_19 — по самому архиву (скачивание 81 МБ — с разрешения).
- Что страница загрузки WebView2 открывается по указанному адресу.
- Что headless Edge рендерит SVG с прозрачным фоном нужного размера; если нет — другой способ рендера, тот же SVG.
- Что pythonnet и pywebview работают в сборке папкой: это и проверяет самопроверка.
- Ложные срабатывания антивирусов не лечим, только предупреждаем в README.

## Связанные issues

- PR закрывает #7 и #9.
- После мержа отметить в #12, что лог в файл сделан; остаются сторож зависаний и дамп потоков.
- В «Планы» документации добавить #23.
