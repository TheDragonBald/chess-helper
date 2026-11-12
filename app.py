"""Запуск помогатора: окно pywebview + бэк на Python."""
import json
import logging

import webview

from backend.api import Api
from backend.engine import EngineAnalyzer
from backend.game import GameSession


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
        holder["window"].on_top = flag

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
