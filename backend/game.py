"""Состояние шахматной партии — единственный источник правды для фронта."""
from __future__ import annotations

import chess

COLORS = {"white": chess.WHITE, "black": chess.BLACK}

# Ничьи, которые наступают сами по правилам, без заявления игрока
DRAW_REASONS = {
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
    chess.Termination.SEVENTYFIVE_MOVES: "seventyfive_moves",
}

# Флаги board.status() → понятная причина, почему позиция невозможна
FEN_PROBLEMS = (
    (chess.STATUS_EMPTY, "доска пустая"),
    (chess.STATUS_NO_WHITE_KING, "нет белого короля"),
    (chess.STATUS_NO_BLACK_KING, "нет чёрного короля"),
    (chess.STATUS_TOO_MANY_KINGS, "больше одного короля одного цвета"),
    (chess.STATUS_TOO_MANY_WHITE_PAWNS, "у белых больше 8 пешек"),
    (chess.STATUS_TOO_MANY_BLACK_PAWNS, "у чёрных больше 8 пешек"),
    (chess.STATUS_PAWNS_ON_BACKRANK, "пешка на первой или последней горизонтали"),
    (chess.STATUS_TOO_MANY_WHITE_PIECES, "у белых больше 16 фигур"),
    (chess.STATUS_TOO_MANY_BLACK_PIECES, "у чёрных больше 16 фигур"),
    (chess.STATUS_BAD_CASTLING_RIGHTS, "права на рокировку не сходятся с положением королей и ладей"),
    (chess.STATUS_INVALID_EP_SQUARE, "неверное поле для взятия на проходе"),
    (chess.STATUS_OPPOSITE_CHECK, "под шахом король стороны, которая сейчас не ходит"),
    (chess.STATUS_TOO_MANY_CHECKERS, "невозможный шах: слишком много шахующих фигур"),
    (chess.STATUS_IMPOSSIBLE_CHECK, "невозможный шах"),
)

GAME_OVER_ERROR = "Партия окончена — начни новую или отмени ход"
SHORT_FEN_ERROR = (
    "Неполный FEN: нужны расстановка, чей ход и права на рокировку, например «… w KQkq - 0 1»"
)
UNPARSABLE_FEN_ERROR = "Невалидный FEN: не удалось разобрать строку"


def color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


def describe_invalid(board: chess.Board) -> str:
    status = board.status()
    reasons = [text for flag, text in FEN_PROBLEMS if status & flag]
    return "Невалидный FEN: " + "; ".join(reasons or ["позиция невозможна"])


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
        if self.board.outcome() is not None:
            self.error = GAME_OVER_ERROR
            return False
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
        if len(fen.split()) < 3:
            # python-chess молча подставил бы «ход белых, без рокировок»
            self.error = SHORT_FEN_ERROR
            return False
        try:
            board = chess.Board(fen)
        except ValueError:
            self.error = UNPARSABLE_FEN_ERROR
            return False
        if not board.is_valid():
            self.error = describe_invalid(board)
            return False
        self.board = board
        return True

    def status(self) -> str:
        return self._status(self.board.outcome())

    def is_my_turn(self) -> bool:
        # Подсказки нужны на своём ходу, пока партия не окончилась сама
        return self.board.turn == self.my_color and self.board.outcome() is None

    def dests(self) -> dict[str, list[str]]:
        if self.board.outcome() is not None:
            return {}  # партия окончена: ходы не принимаются
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
        outcome = self.board.outcome()  # без claim_draw: только окончания, наступающие сами
        root = self.board.root()
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
            "status": self._status(outcome),
            "draw_reason": DRAW_REASONS.get(outcome.termination) if outcome else None,
            "claimable_draw": None if outcome else self._claimable_draw(),
            "history": self.history(),
            # С какого хода начинается история: после FEN это может быть, например, «12...»
            "history_start": {"number": root.fullmove_number, "turn": color_name(root.turn)},
            "error": self.error,
        }

    def _status(self, outcome: chess.Outcome | None) -> str:
        if outcome is not None:
            if outcome.termination == chess.Termination.CHECKMATE:
                return "checkmate"
            if outcome.termination == chess.Termination.STALEMATE:
                return "stalemate"
            return "draw"
        if self.board.is_check():
            return "check"
        return "playing"

    def _claimable_draw(self) -> str | None:
        # Ничью можно потребовать, но по правилам партия продолжается — подсказки нужны
        if self.board.is_repetition(3):
            return "threefold_repetition"
        if self.board.is_fifty_moves():
            return "fifty_moves"
        return None
