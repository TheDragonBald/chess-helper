"""Запуск помогатора: окно pywebview + бэк на Python."""
import json

import webview

from backend.api import Api
from backend.engine import EngineAnalyzer
from backend.game import GameSession


def main() -> None:
    game = GameSession()
    engine = EngineAnalyzer()
    holder: dict = {}  # окно создаётся после Api, поэтому храним ссылку здесь

    def push_analysis(result: dict) -> None:
        window = holder.get("window")
        if window is not None:
            window.evaluate_js(f"window.onAnalysis({json.dumps(result)})")

    def set_on_top(flag: bool) -> None:
        holder["window"].on_top = flag

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
    webview.start(http_server=True)


if __name__ == "__main__":
    main()
