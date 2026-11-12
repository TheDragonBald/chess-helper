"""Состояние шахматной партии — единственный источник правды для фронта."""
from __future__ import annotations

import chess

COLORS = {"white": chess.WHITE, "black": chess.BLACK}


def color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


class GameSession:
    def __init__(self) -> None:
        self.board = chess.Board()
        self.my_color: chess.Color = chess.WHITE
        self.error: str | None = None

    def new_game(self, my_color: str) -> None:
        # Начальная позиция, запоминаем цвет пользователя
        if my_color not in COLORS:
            raise ValueError(f"Неизвестный цвет: {my_color}")
        self.board = chess.Board()
        self.my_color = COLORS[my_color]
        self.error = None

    def move(self, from_sq: str, to_sq: str) -> bool:
        self.error = None
        try:
            from_idx = chess.parse_square(from_sq)
            to_idx = chess.parse_square(to_sq)
        except ValueError:
            self.error = f"Неверная клетка: {from_sq}-{to_sq}"
            return False
        move = chess.Move(from_idx, to_idx)
        piece = self.board.piece_at(from_idx)
        # Пешка на последней горизонтали всегда превращается в ферзя
        if piece and piece.piece_type == chess.PAWN and chess.square_rank(to_idx) in (0, 7):
            move.promotion = chess.QUEEN
        if move not in self.board.legal_moves:
            self.error = f"Незаконный ход: {from_sq}-{to_sq}"
            return False
        self.board.push(move)
        return True

    def undo(self) -> bool:
        self.error = None
        if not self.board.move_stack:
            return False
        self.board.pop()
        return True

    def load_fen(self, fen: str) -> bool:
        # Цвет пользователя не меняем, история начинается заново
        self.error = None
        try:
            board = chess.Board(fen)
        except ValueError:
            self.error = "Невалидный FEN"
            return False
        if not board.is_valid():
            self.error = "Невалидный FEN"
            return False
        self.board = board
        return True

    def status(self) -> str:
        if self.board.is_checkmate():
            return "checkmate"
        if self.board.is_stalemate():
            return "stalemate"
        # Без claim_draw: возможность заявить повтор — ещё не ничья
        if self.board.is_game_over() or self.board.is_repetition(3) or self.board.is_fifty_moves():
            return "draw"
        if self.board.is_check():
            return "check"
        return "playing"

    def is_my_turn(self) -> bool:
        return self.board.turn == self.my_color and self.status() in ("playing", "check")

    def dests(self) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for move in self.board.legal_moves:
            targets = result.setdefault(chess.square_name(move.from_square), [])
            to = chess.square_name(move.to_square)
            if to not in targets:  # четыре варианта превращения ведут на одну клетку
                targets.append(to)
        return result

    def history(self) -> list[str]:
        replay = self.board.root()
        sans = []
        for move in self.board.move_stack:
            sans.append(replay.san(move))
            replay.push(move)
        return sans

    def state(self) -> dict:
        last = self.board.move_stack[-1] if self.board.move_stack else None
        return {
            "fen": self.board.fen(),
            "turn": color_name(self.board.turn),
            "my_color": color_name(self.my_color),
            "dests": self.dests(),
            "last_move": (
                [chess.square_name(last.from_square), chess.square_name(last.to_square)]
                if last
                else None
            ),
            "status": self.status(),
            "history": self.history(),
            "error": self.error,
        }
