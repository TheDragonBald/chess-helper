# Сборка помогатора в exe для Windows — дизайн

Дата: 2026-11-13. Закрывает [#7](https://github.com/TheDragonBald/chess-helper/issues/7) (сборка exe) и [#9](https://github.com/TheDragonBald/chess-helper/issues/9) (Stockfish sf_19), частично [#12](https://github.com/TheDragonBald/chess-helper/issues/12) (лог в файл).

## Цель

Скачал zip из GitHub Releases, распаковал Проводником, запустил `chess-helper.exe` двойным кликом — и помогатор работает. Без Python, uv и консоли; Stockfish уже внутри.

## Решения

| Вопрос | Решение |
|---|---|
| Формат | Папка в zip (PyInstaller onedir), а не один exe: запуск мгновенный, антивирусы ругаются реже |
| Инструмент | PyInstaller: pywebview его официально поддерживает, в pyinstaller-hooks-contrib есть `hook-webview`, `hook-clr`, `hook-clr_loader` |
| Где собирается | Скрипт `scripts/build_exe.py` на компьютере разработчика и GitHub Actions по тегу `v*`, который создаёт черновик релиза |
| Stockfish | sf_19, архив `stockfish-windows-x86-64-universal.zip`: сборка сама выбирает инструкции процессора, поэтому работает на любом x86-64. README и ABOUT переходят на sf_19 (#9) |
| Консоль | Нет. Ошибки, включая необработанные исключения, пишутся в лог-файл |
| Иконка | Свой рисунок ферзя, вариант «кремовый и чёрный» (SVG ниже) |
| Версия первого релиза | `v0.1.0`, из `pyproject.toml` |

## Не входит

- Цифровая подпись exe, установщик, автообновление.
- Сторож зависаний и дамп потоков — остаются в #12.
- CI на каждый PR — #10.
- Заставка «окно или браузер» — #2; стили фигур — #23.
- Программное снятие меток «скачано из интернета» с файлов (см. раздел про метку).

## Что получает пользователь

Архив `chess-helper-v0.1.0-windows-x64.zip`:

```
chess-helper/
├── chess-helper.exe
├── chess-helper.exe.config   # разрешает .NET грузить DLL с меткой «из интернета»
├── _internal/                # Python, библиотеки, frontend/, assets/icon.ico, engine/stockfish.exe
├── LICENSE                   # GPL-3.0
├── README.txt                # запуск, WebView2, SmartScreen, разблокировка, где лог, исходники
└── licenses/                 # лицензии компонентов сборки
```

`licenses/` собирает скрипт сборки:
- Python-пакеты сборки — обход зависимостей начиная с `[project].dependencies` по метаданным установленных пакетов, с вычислением маркеров (библиотека `packaging` ставится вместе с PyInstaller). Сейчас это chess, pywebview, bottle, proxy-tools, pythonnet, clr-loader, cffi, pycparser, typing-extensions. Берутся файлы лицензий из `.dist-info`; если их нет, берётся текст из `packaging/licenses/<пакет>.txt`. Если нет ни того, ни другого, сборка останавливается с ошибкой. Сейчас без файла лицензии только proxy-tools (MIT): его текст кладётся в `packaging/licenses/proxy-tools.txt`;
- Python — `LICENSE.txt` из `sys.base_prefix` той установки Python, которой собирается exe;
- Stockfish — `Copying.txt` и `AUTHORS` из архива sf_19;
- WebView2 SDK — уведомление Microsoft для `Microsoft.Web.WebView2.*.dll` из `webview/lib`, текст в `packaging/licenses/webview2-sdk.txt`;
- chessground — копия `frontend/vendor/chessground/LICENSE`.

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
- ставит `sys.excepthook` и `threading.excepthook`: необработанное исключение пишется в лог с трассировкой и передаётся прежнему обработчику, поэтому окно ошибки от PyInstaller остаётся;
- если папку создать нельзя — остаётся только консоль, функция возвращает `None`, помогатор не падает;
- повторный вызов не дублирует обработчики.

Возвращает путь к файлу лога. Если запущены два помогатора сразу, ротация лога может не сработать (Windows не даёт переименовать открытый файл); запись при этом продолжается, это допустимо.

### `backend/engine.py`

- Движок запускается так: `SimpleEngine.popen_uci(str(self.path), **popen_args())`. На Windows `popen_args()` возвращает `{"creationflags": subprocess.CREATE_NO_WINDOW}`, иначе `{}`. Без флага у exe без консоли Windows открывает для Stockfish отдельное чёрное окно, а если его закрыть, движок завершается.
- `DEFAULT_PATH = app_root() / "engine" / "stockfish.exe"`; переменная `STOCKFISH_PATH` по-прежнему главнее.

### `backend/startup_check.py` (новый)

Без WebView2 pywebview 6.2.1 молча переключается на движок Internet Explorer, который не понимает `<script type="module">` и import map: окно открывается, но доски нет и ничего не работает. Проверка спрашивает решение у самого pywebview, а не повторяет его логику, поэтому разойтись с ним не может.

- `check_startup(load_platform=...) -> str | None` до создания окна импортирует `webview.platforms.winforms` и читает его `renderer`. Модуль грузит .NET (pythonnet, WinForms) и выбирает движок окна; `webview.start()` потом берёт его из `sys.modules`. Результат:
  - `"edgechromium"` — всё в порядке, `None`;
  - любое другое значение — `"no_webview2"`;
  - исключение при импорте (.NET-часть не загрузилась) — `"dotnet"`, исключение пишется в лог с трассировкой.

  Без WebView2 импорт попутно записывает в `HKCU` режим Internet Explorer для нашего exe — то же самое сделал бы и `webview.start()`. Функция загрузки передаётся параметром, чтобы тесты подставляли фейк. При обновлении pywebview (#11) проверку нужно перепроверить: `renderer` — внутренняя переменная модуля.
- `show_startup_problem(problem, log_file, message_box=..., open_url=...)` — системное окно `MessageBoxW`; подписи кнопок Windows ставит на языке системы:
  - `"no_webview2"`: флаги `MB_YESNO | MB_ICONWARNING`, текст «Для работы помогатора нужен Microsoft Edge WebView2 Runtime. Открыть страницу загрузки Microsoft?»; «Да» открывает https://developer.microsoft.com/microsoft-edge/webview2/ в браузере;
  - `"dotnet"`: флаги `MB_OK | MB_ICONERROR`, текст «Не удалось загрузить компоненты помогатора. Если архив скачан из интернета, Windows мог заблокировать файлы: удали распакованную папку, открой «Свойства» zip-архива, отметь «Разблокировать» и распакуй заново. Подробности — в логе: <путь к логу>». Тексты для пользователя — на «ты», как в интерфейсе помогатора.

### `backend/selfcheck.py` (новый)

`run_self_check(report: Path) -> int` проверяет собранный exe без окна, чтобы сломанная сборка не попала в релиз. Запускается только при проверке сборки (скрипт и CI), при обычном старте её нет.

1. В `app_root()` лежат `frontend/index.html`, `frontend/vendor/chessground/` и `assets/icon.ico`.
2. Вложенный Stockfish — всегда `app_root()/engine/stockfish.exe`, переменная `STOCKFISH_PATH` игнорируется — запускается с тем же `popen_args()` и выдаёт оценку начальной позиции с `Limit(depth=10, time=30)`.
3. Загружается .NET-часть окна: `import webview.platforms.edgechromium` грузит pythonnet, WinForms и обе DLL WebView2 независимо от того, есть ли WebView2 в реестре. Окно при этом не создаётся.
4. Справочно — какой движок выбрал бы pywebview (`renderer` из `webview.platforms.winforms`): строка `INFO`, не ошибка, на раннере GitHub WebView2 может не быть.

Тяжёлые импорты выполняются внутри проверок. Каждая проверка ловит любое исключение и пишет в отчёт строку `OK …`, `FAIL …: причина` или `INFO …`; трассировка уходит в лог. Код возврата — 0, если ни одного `FAIL`, иначе 1. Если отчёт не записать — код 1, причина в логе. Зависимости проверок передаются параметрами, чтобы их можно было подменить в тестах.

### `app.py`

На верхнем уровне — только стандартная библиотека и `backend.logs` / `backend.paths`. Всё остальное импортируется внутри `main`, после того как поставлен перехват исключений, чтобы сбой импорта попал в лог, а самопроверка не повисла на окне ошибки:

```python
def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    log_file = setup_logging()  # файл лога и перехват необработанных исключений
    if argv[:1] == ["--self-check"]:
        if len(argv) != 2:
            sys.exit(2)  # нужен путь к файлу отчёта
        from backend.selfcheck import run_self_check
        sys.exit(run_self_check(Path(argv[1])))
    from backend.startup_check import check_startup, show_startup_problem
    problem = check_startup()
    if problem is not None:
        show_startup_problem(problem, log_file)
        return
    import webview
    ...  # как сейчас: Api, EngineAnalyzer, окно
    webview.start(http_server=True, icon=str(app_root() / "assets" / "icon.ico"))
```

Иконку окна pywebview ставит из файла `assets/icon.ico`, переданного в параметре `icon` (в exe он лежит в `_internal`): на WinForms параметр работает (`winforms.py:243-250`), хотя в описании pywebview сказано «только GTK/QT». Без `icon` pywebview взял бы иконку из исполняемого файла процесса — при запуске `uv run app.py` это `python.exe`.

## Метка «скачано из интернета»

Проводник ставит метку `Zone.Identifier` на все файлы, распакованные из скачанного zip. .NET Framework не загружает через `Assembly.LoadFrom` сборки с меткой зоны «Интернет», пока это не разрешено настройкой `loadFromRemoteSources`. Так грузятся `Python.Runtime.dll` (pythonnet) и DLL WebView2. Без мер помогатор из скачанного zip может не запуститься, хотя локальная сборка и самопроверка в CI проходят: метки там нет.

- **Основная мера.** Скрипт сборки кладёт рядом с exe `chess-helper.exe.config` — штатную настройку .NET Framework для процесса:
  ```xml
  <configuration>
    <runtime>
      <loadFromRemoteSources enabled="true"/>
    </runtime>
  </configuration>
  ```
- **Автоматическая проверка.** Скрипт сборки копирует готовую папку в `build/motw-check/`, записывает каждому файлу поток `:Zone.Identifier` с `ZoneId=3` и запускает самопроверку на копии. Она должна пройти так же, как без метки.
- **Если мера не сработает.** Помогатор не падает молча: проверка при старте показывает окно `"dotnet"` с инструкцией «Свойства → Разблокировать», та же инструкция есть в `README.txt` и README. Как быть дальше, решаем вместе с пользователем.
- Снимать метки программно (удалять потоки `Zone.Identifier`) не будем: это похоже на обход защиты Windows, а антивирусы такое не любят.

## Иконка

- `assets/icon.svg` — исходник, утверждённый в чате: свой ферзь без контура, разрезанный по диагонали; кремовая половина (`#f2ecdf`, детали `#ddd3bf`) — на тёмной клетке `#b58863`, чёрная (`#222222`, детали `#3a3a3a`) — на светлой `#f0d9b5`. Цвета клеток — как у доски помогатора (тема brown).
- Пятый, крайний правый шарик короны рисуется целиком чёрным поверх разреза: диагональ проходит в 2,8 единицы от его центра при радиусе 3,6 и иначе оставляет на нём белый серп.
- `assets/icon.ico` — размеры 16, 24, 32, 48, 64, 128, 256. Его делает `scripts/make_icon.py`: headless Edge рендерит SVG в PNG 512×512 с прозрачным фоном, Pillow уменьшает картинку и собирает .ico. Edge ищется по пути `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` (в `PATH` его обычно нет), флаги: `--headless --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=512,512 --default-background-color=00000000 --screenshot=<png> <svg>`. Файл .ico коммитится, поэтому для обычной сборки ни Edge, ни Pillow не нужны.
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
  <!-- Пятый шарик короны целиком чёрный: диагональ задевает его край, и без этого остаётся белый серп -->
  <circle cx="78" cy="26" r="3.6" fill="#222222"/>
</svg>
```

## Сборка

### Зависимости

В `pyproject.toml` — новая группа `build = ["pyinstaller>=6.22", "pillow>=11"]`. Обычный `uv sync` её не ставит. Скрипты сборки запускаются через `uv run --group build …`, тогда группа ставится сама и на чистом клоне.

### `chess-helper.spec`

Файл настроек PyInstaller в корне репозитория:
- точка входа `app.py`;
- данные: `frontend/` → `frontend/`, `assets/icon.ico` → `assets/`;
- `EXE(name="chess-helper", console=False, icon="assets/icon.ico", upx=False)` — UPX выключен, с ним антивирусы ругаются чаще;
- `COLLECT(name="chess-helper")` — сборка папкой, служебные файлы в `_internal/` (по умолчанию в PyInstaller 6).

### `scripts/build_exe.py`

Запуск: `uv run --group build python scripts/build_exe.py [--stockfish-only] [--expect-tag <тег>]`. Пути скрипт считает от своего расположения (корень репозитория — папка выше `scripts/`), поэтому работает из любой текущей папки.

1. Читает версию из `pyproject.toml` (`tomllib`). С `--expect-tag` сразу проверяет, что тег равен `v` + версия, иначе останавливается до сборки.
2. Готовит Stockfish в кэше `build/cache/stockfish-sf_19/`:
   - если кэша нет, скачивает `https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip`;
   - всегда сверяет SHA-256 с зашитым `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7` (из данных релиза на GitHub);
   - достаёт `stockfish/stockfish-windows-x86-64-universal.exe` как `build/cache/stockfish-sf_19/stockfish.exe`, рядом — `stockfish/Copying.txt` и `stockfish/AUTHORS`; если таких файлов в архиве нет — ошибка со списком содержимого архива.

   Папку `engine/` разработчика скрипт не трогает. С `--stockfish-only` на этом останавливается и печатает путь к движку.
3. Запускает PyInstaller: `python -m PyInstaller chess-helper.spec --noconfirm --clean --distpath dist --workpath build/pyinstaller`.
4. Кладёт движок в `dist/chess-helper/_internal/engine/stockfish.exe`.
5. Пишет `dist/chess-helper/chess-helper.exe.config` (см. раздел про метку), добавляет `LICENSE`, `README.txt` из шаблона и папку `licenses/`.
6. Запускает `chess-helper.exe --self-check build/selfcheck-report.txt` с таймаутом 120 секунд и печатает отчёт. При таймауте убивает всё дерево процессов (`taskkill /PID <pid> /T /F`), чтобы оставшийся Stockfish не держал файлы. При ненулевом коде — останавливается с ошибкой.
7. Повторяет самопроверку на копии с меткой «из интернета» в `build/motw-check/` и удаляет копию.
8. Упаковывает `dist/chess-helper/` в `dist/chess-helper-v<версия>-windows-x64.zip` (внутри — папка `chess-helper/`).

### `.gitignore`

Добавляются `/build/` и `/dist/` — с ведущим слэшем, чтобы не задеть отслеживаемую `frontend/vendor/chessground/dist/`.

### GitHub Actions: `.github/workflows/release.yml`

- Запуск: push тега `v*` и вручную (`workflow_dispatch`) — ручной запуск делает всё, кроме релиза, для пробного прогона.
- `runs-on: windows-latest`, `permissions: contents: write`.
- Шаги:
  1. `actions/checkout@v7`; `astral-sh/setup-uv@v10.3.3` с кэшем — у setup-uv с v8 нет плавающих тегов вида `v10`, только полные;
  2. `uv sync --group build`;
  3. `uv run --group build python scripts/build_exe.py --stockfish-only`;
  4. `uv run pytest` с `STOCKFISH_PATH=build/cache/stockfish-sf_19/stockfish.exe` — проходят и тесты с настоящим движком; тесты идут до сборки, так падение дешевле;
  5. `uv run --group build python scripts/build_exe.py`, а при push тега — с `--expect-tag ${{ github.ref_name }}`;
  6. только при `github.event_name == 'push'`, с `env: GH_TOKEN: ${{ github.token }}`: если релиза с этим тегом нет — `gh release create <тег> dist/chess-helper-<тег>-windows-x64.zip --draft --generate-notes`, если есть (повторный прогон) — `gh release upload <тег> <zip> --clobber`.

Релиз создаётся черновиком: его смотрят и публикуют вручную.

`workflow_dispatch` срабатывает, только когда workflow уже лежит в основной ветке, поэтому пробный прогон — после мержа и до первого тега.

## Stockfish sf_19 (#9)

- Все тесты, включая `tests/test_engine.py`, проходят с sf_19 локально и в CI.
- Устройство архива известно из `upload_binaries.yml` тега sf_19: внутри папка `stockfish/` с `stockfish-windows-x86-64-universal.exe`, `Copying.txt`, `AUTHORS`, исходниками `src/` и прочим.
- README (обе части) и `docs/ABOUT_PROJECT.md`: ссылка на релиз sf_19, архив `stockfish-windows-x86-64-universal.zip`, шаг «скопируй `stockfish/stockfish-windows-x86-64-universal.exe` в `engine/` и переименуй в `stockfish.exe`», упоминание сборки arm64 для Windows на ARM.

## Документация

- README, обе части:
  - новый первый раздел «Download (Windows)» / «Скачать (Windows)»: ссылка на Releases; распаковать, запустить `chess-helper.exe`; предупреждение SmartScreen проходят через «Подробнее → Выполнить в любом случае» (exe без подписи); нужен WebView2 Runtime; что делать, если Windows заблокировал файлы («Свойства» zip → «Разблокировать»); где лог. Установка из исходников — ниже, как сейчас;
  - «Запуск»: ошибки пишутся в `%LOCALAPPDATA%\chess-helper\logs\helper.log` и в консоль, если она есть;
  - «Лицензии»: иконка — свой рисунок под GPL-3.0; в релизе лежит Stockfish (GPL-3.0).
- `docs/ARCHITECTURE.md`:
  - новый раздел «Сборка exe»: spec, скрипты, CI, пути в exe, самопроверка, лог и перехват исключений, проверка при старте, метка «из интернета», `CREATE_NO_WINDOW`, иконка;
  - таблица библиотек: строка Stockfish (сейчас «17.1, сборка Windows x64 avx2», стр. 33) → sf_19 universal; добавить PyInstaller и Pillow (только для сборки);
  - описание `app.py` (стр. 72, «WARNING и выше в консоль») → файл лога и консоль;
  - дерево файлов: новые модули, `scripts/`, `packaging/`, `assets/`, `.github/`;
  - раздел «Тесты»: новые файлы тестов;
  - ограничения: вместо «Логи только в консоли» (стр. 272) — «нет сторожа зависаний (#12)».
- `docs/ABOUT_PROJECT.md`: в «Как начать» и «Где лежит» — готовая сборка; строка в «Истории»; в «Планах» убрать #7 и #9, добавить #23, у #12 оставить сторож зависаний и дамп потоков.

## Тесты

Модульные (pytest, по TDD):
- `tests/test_paths.py` — `app_root()` из исходников указывает на корень репозитория, в сборке (подменённые `sys.frozen`, `sys._MEIPASS`) — на `_MEIPASS`; `log_dir()` берёт `LOCALAPPDATA`, без неё — домашнюю папку.
- `tests/test_logs.py` — файл создаётся и в него пишется WARNING; без `sys.stderr` нет консольного обработчика и нет ошибки; повторный вызов не дублирует обработчики; недоступная папка — `None` без исключения; параметры ротации; `sys.excepthook` и `threading.excepthook` пишут исключение в лог и вызывают прежний обработчик.
- `tests/test_engine_unit.py` — `popen_uci` получает `creationflags=CREATE_NO_WINDOW` (только Windows).
- `tests/test_startup_check.py` — `renderer` равен `"edgechromium"` → `None`; `"mshtml"` → `"no_webview2"`; исключение при загрузке → `"dotnet"` и запись в лог. Окна сообщений: для `"no_webview2"` «Да» открывает страницу, «Нет» — нет; для `"dotnet"` текст содержит путь к логу.
- `tests/test_selfcheck.py` — всё в порядке → 0 и строки `OK`; нет фронтенда или иконки, движок не запускается, .NET-часть не грузится, проверка бросает исключение → `FAIL` и 1 без проброса исключения; заданный `STOCKFISH_PATH` не влияет на проверяемый путь; отчёт не записывается → 1.
- `tests/test_app.py` — проблема при старте → показано сообщение, окно не создаётся; `--self-check <путь>` вызывает самопроверку и возвращает её код; `--self-check` без пути — код 2.
- `tests/test_build_exe.py` — чистые функции скрипта сборки: чтение версии и проверка тега; обход зависимостей и сбор лицензий: файл из `.dist-info`, запасной текст из `packaging/licenses/`, ошибка, если нет ни того, ни другого; запись потока `Zone.Identifier`.

Проверка сборки:
- `scripts/build_exe.py` у разработчика: zip собирается, обе самопроверки (обычная и с меткой) проходят.
- Вручную:
  - скачать zip браузером из черновика релиза, распаковать Проводником, запустить двойным кликом — окно с доской и иконкой, подсказки появляются, чёрного окна нет;
  - распаковать в папку с кириллицей и пробелами в пути (например, `D:\Тест папка\`) и запустить;
  - подложить вместо движка неработающий файл — в панели сообщение об ошибке, в логе запись.
- В CI: пробный прогон `workflow_dispatch` после мержа, затем тег `v0.1.0` → черновик релиза.

## Что выяснить при реализации

- Устройство архива sf_19 — подтвердить на самом архиве (скачивание 81 МБ — с разрешения).
- Хватает ли `chess-helper.exe.config` для DLL с меткой: ответит самопроверка на копии с меткой. Если нет — остаются окно `"dotnet"` и инструкция в README, решаем с пользователем.
- Что headless Edge с указанными флагами рендерит SVG с прозрачным фоном нужного размера; если нет — другой способ рендера, тот же SVG.
- Работает ли clr-loader 0.3.1 из папки с кириллицей в пути — ручная проверка. Если нет — предупреждение в README и issue.
- Тексты лицензий proxy-tools (MIT, https://github.com/jtushman/proxy_tools) и WebView2 SDK для версии DLL из pywebview 6.2.1.
- Что pythonnet и pywebview работают в сборке папкой — это проверяет самопроверка.
- Ложные срабатывания антивирусов не лечим, только предупреждаем в README.

## Связанные issues

- PR закрывает #7 и #9.
- После мержа отметить в #12, что лог в файл сделан; остаются сторож зависаний и дамп потоков.
- В «Планы» документации добавить #23.
