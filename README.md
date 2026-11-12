# Шахматный помогатор

Окно с доской: повторяешь в нём ходы партии (свои и соперника), а на своём ходу
видишь три лучших хода от Stockfish — зелёная стрелка лучший, синяя и жёлтая —
второй и третий.

## Установка (Windows)

Команды ниже — для Git Bash или PowerShell (не для cmd.exe). Нужен WebView2 Runtime
(на Windows 11 установлен по умолчанию).

```bash
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
```

Stockfish: сначала создай папку `engine` (в свежем клоне её нет), затем на странице
https://github.com/official-stockfish/Stockfish/releases/tag/sf_17.1 скачай
`stockfish-windows-x86-64-avx2.zip` (или `stockfish-windows-x86-64.zip`, если у
процессора нет AVX2) и положи exe из архива как `engine/stockfish.exe` (или
укажи путь в переменной `STOCKFISH_PATH`).

## Запуск

```bash
.venv/Scripts/python app.py
```

## Управление

- Перетаскивай фигуры за обе стороны; незаконный ход не пройдёт.
- «Новая за белых» / «Новая за чёрных» — новая партия и разворот доски.
- «Отменить» или Ctrl+Z — отменить последний полуход.
- «Поверх окон» — окно висит над Discord.
- Поле FEN — поставить позицию, если партия уже идёт.

## Тесты

```bash
.venv/Scripts/python -m pytest -v
```

## Лицензии

Проект распространяется под GPL-3.0, текст — в файле [LICENSE](LICENSE).

Доска — [chessground](https://github.com/lichess-org/chessground) (GPL-3.0),
файлы лежат в `frontend/vendor/chessground/`.
