## [Русская версия 🇷🇺](#шахматный-помогатор)

# Chess Helper

A window with a chessboard: you mirror the moves of a game in it (both yours and
your opponent's), and on your turn it shows Stockfish's three best moves — the
green arrow is the best one, blue and yellow are the second and third.

The interface is in Russian; the controls below give the button names with
translations.

More (in Russian): [about the project](docs/ABOUT_PROJECT.md) and
[architecture](docs/ARCHITECTURE.md).

## Download (Windows)

Download `chess-helper-v<version>-windows-x64.zip` from
[Releases](https://github.com/TheDragonBald/chess-helper/releases), unpack it
and run `chess-helper.exe`: Python and Stockfish are already inside.

- Windows may show "Windows protected your PC" (SmartScreen) because the
  program is not digitally signed: click "More info" → "Run anyway".
- Some antivirus programs falsely flag unsigned programs like this one as
  dangerous. The source code is open, and you can build the helper yourself:
  see [installation from source](#installation-from-source-windows) below.
- The WebView2 Runtime is required (preinstalled on Windows 11). If it is
  missing, the helper offers to open the download page.
- If the helper says it could not load its components, Windows has blocked the
  downloaded files: delete the unpacked folder, open the zip file's
  Properties, tick "Unblock" and unpack it again.
- Errors are written to `%LOCALAPPDATA%\chess-helper\logs\helper.log`.

To run the helper from source instead, read on.

## Installation from source (Windows)

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (for
example, `winget install --id=astral-sh.uv -e`) and the WebView2 Runtime
(preinstalled on Windows 11). The commands work in any shell: PowerShell, cmd
or Git Bash.

```bash
uv sync
```

uv creates `.venv` and installs the dependencies pinned in `uv.lock`; if
Python 3.13 is missing, uv downloads it.

Stockfish: download `stockfish-windows-x86-64-universal.zip` from
https://github.com/official-stockfish/Stockfish/releases/tag/sf_19 (on Windows
on ARM — `stockfish-windows-arm64-universal.zip`). The program is
`stockfish/stockfish-windows-x86-64-universal.exe` inside the archive: copy it
into the `engine` folder and rename it to `stockfish.exe`, so the path is
`engine/stockfish.exe`. You can also keep it anywhere and put its full path
into the `STOCKFISH_PATH` environment variable.

## Running

```bash
uv run app.py
```

Errors (for example, why hints did not appear) are written to
`%LOCALAPPDATA%\chess-helper\logs\helper.log` and printed to the console the
helper was started from.

## Controls

- Drag the pieces for both sides; an illegal move won't go through.
- «Новая за белых» / «Новая за чёрных» (new game as White / Black) — start a new
  game and flip the board accordingly. If the current game has moves or a
  loaded position, click the button a second time to confirm.
- «Отменить» (undo) or Ctrl+Z — take back the last half-move. Holding the keys
  down does not undo several moves.
- «Поверх всех окон» (always on top) — keeps the window above all other
  windows, not just Discord.
- FEN field and «Загрузить» (load) or Enter — set up a position if the game is
  already in progress. The FEN needs at least the piece placement, the side to
  move and the castling rights (for example `… w KQkq - 0 1`).

## Good to know

- To join a game in progress as Black, press «Новая за чёрных» first and only
  then load the FEN: loading a position keeps your colour.
- A pawn always promotes to a queen. If your opponent promotes to another
  piece, set up the resulting position with a FEN.
- After a threefold repetition or 50 moves without captures and pawn moves the
  status says a draw can be claimed, and the hints keep working. The game ends
  by itself only on checkmate, stalemate, insufficient material, fivefold
  repetition or 75 such moves; after that the board accepts no more moves.
- If Stockfish crashes, the panel says so right away and the helper restarts
  it the next time it is your turn. If it crashes again before a successful analysis, the
  hints stay off until you restart the helper.
- The author (I am) believes this application is borderline cheating, but in the future, this project will expand, allowing users not only to copy engine moves but also to learn, train, customize the interface, and evaluate both their own and others' moves.

## Tests

```bash
uv run pytest -v
```

## Licenses

The project is licensed under GPL-3.0; the text is in [LICENSE](LICENSE).

The board is [chessground](https://github.com/lichess-org/chessground)
(GPL-3.0); its files are in `frontend/vendor/chessground/`.

The icon is our own drawing, also under GPL-3.0. Releases include Stockfish
(GPL-3.0); the licenses of all bundled components are in the `licenses` folder
of the zip.

---

# Шахматный помогатор

## [English version 🇺🇸](#chess-helper)

Окно с доской: повторяешь в нём ходы партии (свои и соперника), а на своём ходу
видишь три лучших хода от Stockfish — зелёная стрелка лучший, синяя и жёлтая —
второй и третий.

Подробнее: [о проекте](docs/ABOUT_PROJECT.md) и [архитектура](docs/ARCHITECTURE.md).

## Скачать (Windows)

Скачай `chess-helper-v<версия>-windows-x64.zip` из
[Releases](https://github.com/TheDragonBald/chess-helper/releases), распакуй и
запусти `chess-helper.exe`: Python и Stockfish уже внутри.

- Windows может показать «Система Windows защитила ваш компьютер» (SmartScreen):
  у программы нет цифровой подписи. Нажми «Подробнее» → «Выполнить в любом
  случае».
- Некоторые антивирусы ложно считают опасными программы без подписи, как эта.
  Исходники открыты, и собрать помогатор можно самому — см.
  [установку из исходников](#установка-из-исходников-windows) ниже.
- Нужен WebView2 Runtime (на Windows 11 уже есть). Если его нет, помогатор
  предложит открыть страницу загрузки.
- Если помогатор пишет, что не удалось загрузить компоненты, Windows
  заблокировал скачанные файлы: удали распакованную папку, открой «Свойства»
  zip-архива, отметь «Разблокировать» и распакуй заново.
- Ошибки пишутся в `%LOCALAPPDATA%\chess-helper\logs\helper.log`.

Запуск из исходников — ниже.

## Установка из исходников (Windows)

Нужны [uv](https://docs.astral.sh/uv/getting-started/installation/) (например,
`winget install --id=astral-sh.uv -e`) и WebView2 Runtime (на Windows 11
установлен по умолчанию). Команды работают в любой консоли: PowerShell, cmd
или Git Bash.

```bash
uv sync
```

uv создаст `.venv` и поставит зависимости, зафиксированные в `uv.lock`; если
Python 3.13 нет, uv скачает его сам.

Stockfish: на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_19 скачай
`stockfish-windows-x86-64-universal.zip` (для Windows на ARM —
`stockfish-windows-arm64-universal.zip`). Программа лежит в архиве в папке
`stockfish` — `stockfish-windows-x86-64-universal.exe`: скопируй её в папку
`engine` и переименуй в `stockfish.exe`, чтобы получилось
`engine/stockfish.exe`. Можно положить её куда угодно и указать полный путь в
переменной окружения `STOCKFISH_PATH`.

## Запуск

```bash
uv run app.py
```

Ошибки (например, почему не появились подсказки) пишутся в
`%LOCALAPPDATA%\chess-helper\logs\helper.log` и в консоль, из которой запущен
помогатор.

## Управление

- Перетаскивай фигуры за обе стороны; незаконный ход не пройдёт.
- «Новая за белых» / «Новая за чёрных» — новая партия и разворот доски. Если в
  текущей партии есть ходы или загруженная позиция, кнопку нужно нажать второй
  раз.
- «Отменить» или Ctrl+Z — отменить последний полуход. Зажатые клавиши не
  отменяют несколько ходов подряд.
- «Поверх всех окон» — окно висит поверх всех остальных окон, а не только
  Discord.
- Поле FEN и «Загрузить» или Enter — поставить позицию, если партия уже идёт. В
  FEN нужны хотя бы расстановка, чей ход и права на рокировку (например
  `… w KQkq - 0 1`).

## Полезно знать

- Чтобы подключиться к идущей партии за чёрных, сначала нажми «Новая за
  чёрных», потом загрузи FEN: загрузка позиции не меняет твой цвет.
- Пешка всегда превращается в ферзя. Если соперник превратил пешку в другую
  фигуру, поставь получившуюся позицию через FEN.
- После троекратного повторения или 50 ходов без взятий и ходов пешек статус
  подскажет, что можно потребовать ничью, а подсказки продолжат работать. Сама
  партия заканчивается только матом, патом, нехваткой фигур для мата,
  пятикратным повторением или 75 такими ходами — после этого доска не
  принимает ходы.
- Если Stockfish упадёт, панель сразу об этом скажет, а помогатор перезапустит
  его, когда снова будет твой ход. Если движок упадёт снова до первого удачного
  анализа, подсказки отключатся до перезапуска помогатора.
- Автор (я) считает, что это приложение на грани с читами, но в дальнейшем этот проект будет расширятся, и можно будет не только копировать ходы движка, а учиться, тренироваться, менять интерфейс и оценивать как чужие, так и свои ходы.

## Тесты

```bash
uv run pytest -v
```

## Лицензии

Проект распространяется под GPL-3.0, текст — в файле [LICENSE](LICENSE).

Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.

Иконка — наш собственный рисунок, тоже под GPL-3.0. В релизах лежит Stockfish
(GPL-3.0); лицензии всех компонентов сборки — в папке `licenses` внутри zip.
