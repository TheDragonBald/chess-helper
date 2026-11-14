# Помогатор от спеки до первого релиза v0.1.0

Сессия: 12–14.11.2026. Статус: завершено.

## Итог

Помогатор сделан с нуля: окно с доской, правила партии и топ-3 подсказки Stockfish в фоне, затем исправления по ревью, документация и план развития в issues.
Добавлена сборка в zip под Windows с черновиком релиза по тегу в GitHub Actions.
Опубликован первый релиз [v0.1.0](https://github.com/TheDragonBald/chess-helper/releases/tag/v0.1.0), вся работа смержена в `main`.

## Состояние и что дальше

- Смержено и выпущено: PR [#1](https://github.com/TheDragonBald/chess-helper/pull/1), [#5](https://github.com/TheDragonBald/chess-helper/pull/5), [#6](https://github.com/TheDragonBald/chess-helper/pull/6), [#8](https://github.com/TheDragonBald/chess-helper/pull/8), [#22](https://github.com/TheDragonBald/chess-helper/pull/22), [#27](https://github.com/TheDragonBald/chess-helper/pull/27); тег и релиз [v0.1.0](https://github.com/TheDragonBald/chess-helper/releases/tag/v0.1.0) (Latest, zip 92,8 МБ).
- Открыто: ничего — открытых PR нет, на GitHub одна ветка `main`.
- Тесты: 122 passed на `main` (8c85df2) со Stockfish sf_19; в CI на теге `v0.1.0` — тоже 122.
- Дальше (справка, а не поручение):
  - [#26](https://github.com/TheDragonBald/chess-helper/issues/26) — доработки по ревью сборки, в том числе 16-разрядное окно Windows на испорченном движке;
  - [#10](https://github.com/TheDragonBald/chess-helper/issues/10) — тесты в GitHub Actions на каждый PR;
  - [#4](https://github.com/TheDragonBald/chess-helper/issues/4) — мелочи и тесты по ревью исправлений;
  - остальное — раздел «Планы» в [ABOUT_PROJECT.md](../ABOUT_PROJECT.md), всего открыто 19 issues.

## Что сделано

1. **Первая версия.** [Спека](../superpowers/specs/2026-11-12-chess-helper-design.md) и 4 задачи по [плану](../superpowers/plans/2026-11-12-chess-helper.md): окно pywebview с доской chessground, партия на python-chess, Stockfish в фоне, топ-3 подсказки.
   Следом три исправления прямо в `main` (ошибки вызовов бэкенда, ложная ничья при повторении, Ctrl+Z и премувы) и лицензия GPL-3.0, как у chessground.
2. **[PR #1](https://github.com/TheDragonBald/chess-helper/pull/1).** uv вместо requirements.txt, английский раздел README, галочка «Поверх всех окон».
3. **[PR #5](https://github.com/TheDragonBald/chess-helper/pull/5).** Находки полного ревью кода, 4 задачи по [плану](../superpowers/plans/2026-11-12-review-fixes.md): курьер доставки подсказок, история ходов для движка, правила ничьей, номер версии позиции.
   Остаток — в [#4](https://github.com/TheDragonBald/chess-helper/issues/4).
4. **[PR #6](https://github.com/TheDragonBald/chess-helper/pull/6).** Окно зависало на «Поверх всех окон»: pywebview 6.2.1 меняет TopMost не из UI-потока. Флаг теперь ставится в UI-потоке окна.
5. **Документы и планы.** [PR #8](https://github.com/TheDragonBald/chess-helper/pull/8) добавил [ARCHITECTURE.md](../ARCHITECTURE.md) и [ABOUT_PROJECT.md](../ABOUT_PROJECT.md).
   Идеи стали issues #2, #3, #7 и #9–#21; [PR #22](https://github.com/TheDragonBald/chess-helper/pull/22) разложил «Планы» по темам и связал известные ограничения с issues.
6. **Сборка под Windows ([#7](https://github.com/TheDragonBald/chess-helper/issues/7), [#9](https://github.com/TheDragonBald/chess-helper/issues/9)).** [Спека](../superpowers/specs/2026-11-13-windows-build-design.md) до плана прошла ревью субагентом; 9 задач по [плану](../superpowers/plans/2026-11-13-windows-build.md), каждую делал субагент, после каждой — ревью другим субагентом.
   Отклонения от плана: проверка задачи 5 переписана до старта, чтобы не открывать окно (команда повисла бы без человека); в задачу 6 добавлено ожидание Edge; в задаче 7 setuptools и `_decimal` исключены из сборки, чтобы не везти компоненты без собранных лицензий.
7. **Финальное ревью ветки.** Критичного нет, важных три: самопроверка глотала сбой .NET, тесты `app.py` могли открыть настоящее окно, версия Python в CI не закреплена.
   Исправлено волной из 7 коммитов, повторное ревью — готово к мержу; [PR #27](https://github.com/TheDragonBald/chess-helper/pull/27) закрыл #7 и #9.
8. **Релиз.** Пробный прогон workflow `release` на `main`, затем тег `v0.1.0`: CI прогнал тесты, собрал zip и создал черновик; после ручной проверки черновик опубликован.
   Попутно заведены [#23](https://github.com/TheDragonBald/chess-helper/issues/23), [#24](https://github.com/TheDragonBald/chess-helper/issues/24), [#25](https://github.com/TheDragonBald/chess-helper/issues/25) (идеи автора) и [#26](https://github.com/TheDragonBald/chess-helper/issues/26).

## Решения и почему

- Уведомления о сторонних компонентах внутри `python313.dll` (их нет в LICENSE.txt Python) — ссылкой на страницу лицензий CPython, файл [python-third-party.txt](../../packaging/licenses/python-third-party.txt), — решил автор.
- Предупреждение о ложных срабатываниях антивирусов в README и README.txt: exe без цифровой подписи — решил автор.
- Actions закреплены по хешу коммита сразу; разделение workflow на сборку и публикацию (токен записи отдельно от стороннего кода) меняет спеку и вынесено в [#26](https://github.com/TheDragonBald/chess-helper/issues/26) — решил автор.
- Релиз опубликован как есть, с автоматическими заметками — решил автор.

## Проверено

- Автоматически: 122 passed на `main`; в CI (пробный прогон и тег `v0.1.0`) — 122 passed, сборка и обе самопроверки, обычная и на копии с меткой «скачано из интернета»; ревью каждой задачи, финальное и повторное ревью ветки.
- Вручную, автор: нашёл зависание на «Поверх всех окон» и после PR #6 подтвердил, что галочка работает.
  Локальный zip: окно, иконка, подсказки, путь с кириллицей, испорченный движок — все этапы пройдены (про 16-разрядное окно — в «Граблях»).
  Zip из черновика релиза: при запуске из WinRAR Windows предупредила о неизвестном издателе, то есть метка «из интернета» дошла до exe; помогатор работает.
- Не проверено: распаковка скачанного zip Проводником (метку на всех файлах проверяет самопроверка в CI); окна с подсказкой при отсутствии WebView2 или .NET — только модульными тестами.

## Грабли

- .NET не грузит DLL с меткой «скачано из интернета»: без `chess-helper.exe.config` окно из скачанного zip не открылось бы. Нашло ревью спеки; сборка проверяет это на помеченной копии.
- У `astral-sh/setup-uv` нет плавающих тегов вида `v10`: версию пишут полностью, теперь — хешем коммита.
- Headless Edge при рендере иконки перезапускает сам себя и выходит раньше времени: [make_icon.py](../../scripts/make_icon.py) ждёт PNG и освобождения профиля.
- Если вместо `stockfish.exe` лежит файл без PE-заголовка, Windows сначала показывает своё окно «Неподдерживаемое 16-разрядное приложение», а уже потом помогатор пишет понятную ошибку; идея исправления — в [#26](https://github.com/TheDragonBald/chess-helper/issues/26).
- CI-сборка отличается от локальной: 179 файлов против 136, Python 3.13.18 против 3.13.15; обе самопроверки и ручной запуск — в порядке.
