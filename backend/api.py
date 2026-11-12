"""Методы, которые фронт вызывает через window.pywebview.api."""
from __future__ import annotations

import threading
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
        # pywebview вызывает каждый метод в отдельном потоке, а GameSession не потокобезопасна
        self._lock = threading.Lock()
        # Номер версии позиции: по нему фронт отличает свежие ответы и анализ от запоздавших
        self._rev = 0

    def get_state(self) -> dict:
        with self._lock:
            return self._state(with_error=False)

    def new_game(self, my_color: str) -> dict:
        with self._lock:
            self._game.new_game(my_color)
            self._position_changed()
            return self._state()

    def move(self, from_sq: str, to_sq: str) -> dict:
        with self._lock:
            if self._game.move(from_sq, to_sq):
                self._position_changed()
            return self._state()

    def undo(self) -> dict:
        with self._lock:
            if self._game.undo():
                self._position_changed()
            return self._state()

    def load_fen(self, fen: str) -> dict:
        with self._lock:
            if self._game.load_fen(fen):
                self._position_changed()
            return self._state()

    def set_on_top(self, flag: bool) -> dict:
        with self._lock:
            self._set_on_top(bool(flag))
            return self._state(with_error=False)

    def _position_changed(self) -> None:
        # Новая версия позиции; подсказки нужны только на ходу пользователя
        self._rev += 1
        if self._game.is_my_turn():
            rev = self._rev
            push = self._push_analysis
            self._engine.analyze(
                self._game.board.copy(),  # с историей ходов, а не только FEN
                self._game.my_color,
                lambda result: push({**result, "rev": rev}),
            )
        else:
            self._engine.stop()

    def _state(self, with_error: bool = True) -> dict:
        state = self._game.state()
        state["rev"] = self._rev
        state["engine_error"] = self._engine.error
        if not with_error:
            state["error"] = None  # ошибка относится только к действию, которое её вызвало
        return state
