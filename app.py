"""Запуск помогатора: окно pywebview + бэк на Python."""
import json
import logging

import webview

from backend.api import Api
from backend.engine import EngineAnalyzer
from backend.game import GameSession


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


def main() -> None:
    # Предупреждения и ошибки — в консоль: по ним видно, почему не пришли подсказки
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
        webview.start(http_server=True)
    finally:
        # Фоновый поток python-chess не демон: без этого процесс завис бы при сбое start()
        engine.close()


if __name__ == "__main__":
    main()
