"""Запуск помогатора: окно pywebview + бэк на Python."""
import json
import sys
from pathlib import Path

from backend.logs import setup_logging
from backend.paths import app_root


def apply_on_top(window, flag: bool) -> None:
    # «Поверх всех окон». pywebview 6.2.1 на Windows меняет TopMost прямо из потока вызова
    # (у нас это поток js_api): тот держит GIL и ждёт UI-поток окна, а UI-потоку для ответа
    # нужен тот же GIL — окно намертво зависает. В основной ветке pywebview это исправлено
    # через Invoke; пока не вышла версия новее 6.2.1, делаем так же сами.
    try:
        from System import Func, Type
        from webview.platforms.winforms import BrowserView
    except ImportError:
        window.on_top = flag  # не Windows: штатный путь pywebview
        return
    form = BrowserView.instances.get(window.uid)
    if form is None:
        window.on_top = flag
        return

    def _apply() -> None:
        form.TopMost = flag

    form.Invoke(Func[Type](_apply))


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    # Лог и перехват исключений — первым делом: у exe нет консоли, и всё, что сломается
    # дальше (даже импорт), должно попасть в файл
    log_file = setup_logging()
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
    run_app()


def run_app() -> None:
    # Тяжёлые модули — только здесь, после проверки при старте
    import webview

    from backend.api import Api
    from backend.engine import EngineAnalyzer
    from backend.game import GameSession

    holder: dict = {}  # окно создаётся после Api, поэтому храним ссылку здесь

    def run_js(script: str) -> None:
        window = holder.get("window")
        if window is not None:
            window.evaluate_js(script)

    def push_analysis(result: dict) -> None:
        run_js(f"window.onAnalysis({json.dumps(result)})")

    def push_engine_error(message: str) -> None:
        run_js(f"window.onEngineError({json.dumps(message)})")

    def set_on_top(flag: bool) -> None:
        apply_on_top(holder["window"], flag)

    game = GameSession()
    engine = EngineAnalyzer(on_error=push_engine_error)
    api = Api(game, engine, push_analysis, set_on_top)
    window = webview.create_window(
        "Шахматный помогатор",
        "frontend/index.html",
        js_api=api,
        width=900,
        height=640,
        min_size=(760, 600),
    )
    holder["window"] = window
    window.events.closed += engine.close
    try:
        # Иконку окна pywebview ставит из файла assets/icon.ico; в exe он лежит в _internal (app_root())
        webview.start(http_server=True, icon=str(app_root() / "assets" / "icon.ico"))
    finally:
        # Фоновый поток python-chess не демон: без этого процесс завис бы при сбое start()
        engine.close()


if __name__ == "__main__":
    main()
