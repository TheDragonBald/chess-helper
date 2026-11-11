"""Методы, которые фронт вызывает через window.pywebview.api."""
from __future__ import annotations

from typing import Callable


class Api:
    def __init__(
        self,
        game,
        engine,
        push_analysis: Callable[[dict], None],
        set_on_top: Callable[[bool], None],
    ) -> None:
        # Атрибуты с подчёркиванием pywebview не пробрасывает в JS
        self._game = game
        self._engine = engine
        self._push_analysis = push_analysis
        self._set_on_top = set_on_top

    def get_state(self) -> dict:
        return self._state()

    def new_game(self, my_color: str) -> dict:
        self._game.new_game(my_color)
        self._refresh_analysis()
        return self._state()

    def move(self, from_sq: str, to_sq: str) -> dict:
        if self._game.move(from_sq, to_sq):
            self._refresh_analysis()
        return self._state()

    def undo(self) -> dict:
        if self._game.undo():
            self._refresh_analysis()
        return self._state()

    def load_fen(self, fen: str) -> dict:
        if self._game.load_fen(fen):
            self._refresh_analysis()
        return self._state()

    def set_on_top(self, flag: bool) -> dict:
        self._set_on_top(bool(flag))
        return self._state()

    def _refresh_analysis(self) -> None:
        # Подсказки нужны только на ходу пользователя
        if self._game.is_my_turn():
            self._engine.analyze(self._game.board.fen(), self._game.my_color, self._push_analysis)
        else:
            self._engine.stop()

    def _state(self) -> dict:
        state = self._game.state()
        state["engine_error"] = self._engine.error
        return state
