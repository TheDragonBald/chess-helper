[Русская версия](#шахматный-помогатор)

# Chess Helper

A window with a chessboard: you mirror the moves of a game in it (both yours and
your opponent's), and on your turn it shows Stockfish's three best moves — the
green arrow is the best one, blue and yellow are the second and third.

The interface is in Russian; the controls below give the button names with
translations.

## Installation (Windows)

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) (for
example, `winget install --id=astral-sh.uv -e`) and the WebView2 Runtime
(preinstalled on Windows 11). The commands work in any shell: PowerShell, cmd
or Git Bash.

```bash
uv sync
```

uv creates `.venv` and installs the dependencies pinned in `uv.lock`; if
Python 3.13 is missing, uv downloads it.

Stockfish: first create the `engine` folder (a fresh clone doesn't have it),
then download `stockfish-windows-x86-64-avx2.zip` (or
`stockfish-windows-x86-64.zip` if your CPU has no AVX2) from
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1 and put
the exe from the archive at `engine/stockfish.exe` (or set its path in the
`STOCKFISH_PATH` environment variable).

## Running

```bash
uv run app.py
```

## Controls

- Drag the pieces for both sides; an illegal move won't go through.
- «Новая за белых» / «Новая за чёрных» (new game as White / Black) — start a new
  game and flip the board accordingly.
- «Отменить» (undo) or Ctrl+Z — take back the last half-move.
- «Поверх всех окон» (always on top) — keeps the window above all other
  windows, not just Discord.
- FEN field — set up a position if the game is already in progress.

## Tests

```bash
uv run pytest -v
```

## Licenses

The project is licensed under GPL-3.0; the text is in [LICENSE](LICENSE).

The board is [chessground](https://github.com/lichess-org/chessground)
(GPL-3.0); its files are in `frontend/vendor/chessground/`.

---

# Шахматный помогатор

[English version](#chess-helper)

Окно с доской: повторяешь в нём ходы партии (свои и соперника), а на своём ходу
видишь три лучших хода от Stockfish — зелёная стрелка лучший, синяя и жёлтая —
второй и третий.

## Установка (Windows)

Нужны [uv](https://docs.astral.sh/uv/getting-started/installation/) (например,
`winget install --id=astral-sh.uv -e`) и WebView2 Runtime (на Windows 11
установлен по умолчанию). Команды работают в любой консоли: PowerShell, cmd
или Git Bash.

```bash
uv sync
```

uv создаст `.venv` и поставит зависимости, зафиксированные в `uv.lock`; если
Python 3.13 нет, uv скачает его сам.

Stockfish: сначала создай папку `engine` (в свежем клоне её нет), затем на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1 скачай
`stockfish-windows-x86-64-avx2.zip` (или `stockfish-windows-x86-64.zip`, если у
процессора нет AVX2) и положи exe из архива как `engine/stockfish.exe` (или
укажи путь в переменной `STOCKFISH_PATH`).

## Запуск

```bash
uv run app.py
```

## Управление

- Перетаскивай фигуры за обе стороны; незаконный ход не пройдёт.
- «Новая за белых» / «Новая за чёрных» — новая партия и разворот доски.
- «Отменить» или Ctrl+Z — отменить последний полуход.
- «Поверх всех окон» — окно висит поверх всех остальных окон, а не только
  Discord.
- Поле FEN — поставить позицию, если партия уже идёт.

## Тесты

```bash
uv run pytest -v
```

## Лицензии

Проект распространяется под GPL-3.0, текст — в файле [LICENSE](LICENSE).

Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.
