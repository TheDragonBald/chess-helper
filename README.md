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

Stockfish: download `stockfish-windows-x86-64-avx2.zip` (or
`stockfish-windows-x86-64.zip` if your CPU has no AVX2) from
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1. The
program is in the `stockfish` folder inside the archive (for example
`stockfish-windows-x86-64-avx2.exe`): copy it into the `engine` folder and
rename it to `stockfish.exe`, so the path is `engine/stockfish.exe`. You can
also keep it anywhere and put its full path into the `STOCKFISH_PATH`
environment variable.

## Running

```bash
uv run app.py
```

Errors (for example, why hints did not appear) are printed to the console the
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

Stockfish: на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1 скачай
`stockfish-windows-x86-64-avx2.zip` (или `stockfish-windows-x86-64.zip`, если у
процессора нет AVX2). Программа лежит в архиве в папке `stockfish` (например,
`stockfish-windows-x86-64-avx2.exe`): скопируй её в папку `engine` и переименуй
в `stockfish.exe`, чтобы получилось `engine/stockfish.exe`. Можно положить её
куда угодно и указать полный путь в переменной окружения `STOCKFISH_PATH`.

## Запуск

```bash
uv run app.py
```

Ошибки (например, почему не появились подсказки) печатаются в консоль, из
которой запущен помогатор.

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

## Тесты

```bash
uv run pytest -v
```

## Лицензии

Проект распространяется под GPL-3.0, текст — в файле [LICENSE](LICENSE).

Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.
