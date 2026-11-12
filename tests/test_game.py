import chess
import pytest

from backend.game import GameSession

START_FEN = chess.STARTING_FEN
PROMO_FEN = "8/P7/8/8/8/8/8/k6K w - - 0 1"


@pytest.fixture
def game():
    g = GameSession()
    g.new_game("white")
    return g


def play(g, *moves):
    # Удобный помощник: ходы в формате "e2e4"
    for m in moves:
        assert g.move(m[:2], m[2:4]), f"ход {m} не прошёл"


def test_new_game_starts_from_initial_position(game):
    state = game.state()
    assert state["fen"] == START_FEN
    assert state["turn"] == "white"
    assert state["my_color"] == "white"
    assert state["last_move"] is None
    assert state["history"] == []
    assert state["status"] == "playing"
    assert state["error"] is None
    assert state["draw_reason"] is None
    assert state["claimable_draw"] is None
    assert state["history_start"] == {"number": 1, "turn": "white"}


def test_new_game_rejects_unknown_color():
    with pytest.raises(ValueError):
        GameSession().new_game("green")


def test_legal_move_changes_position(game):
    assert game.move("e2", "e4") is True
    state = game.state()
    assert state["turn"] == "black"
    assert state["last_move"] == ["e2", "e4"]
    assert state["history"] == ["e4"]
    assert state["error"] is None


def test_illegal_move_keeps_position(game):
    assert game.move("e2", "e5") is False
    state = game.state()
    assert state["fen"] == START_FEN
    assert state["error"] == "Незаконный ход: e2-e5"


def test_bad_square_is_rejected(game):
    assert game.move("z9", "e4") is False
    assert game.state()["fen"] == START_FEN
    assert game.state()["error"] == "Неверная клетка: z9-e4"


def test_pawn_auto_promotes_to_queen(game):
    assert game.load_fen(PROMO_FEN)
    assert game.move("a7", "a8") is True
    assert game.board.piece_at(chess.A8) == chess.Piece(chess.QUEEN, chess.WHITE)


def test_undo_reverts_half_move(game):
    play(game, "e2e4")
    assert game.undo() is True
    assert game.state()["fen"] == START_FEN


def test_undo_on_empty_history_returns_false(game):
    assert game.undo() is False


def test_dests_format(game):
    dests = game.state()["dests"]
    assert sorted(dests["e2"]) == ["e3", "e4"]
    assert sorted(dests["g1"]) == ["f3", "h3"]
    assert "e7" not in dests  # сейчас ход белых


def test_promotion_dests_are_not_duplicated(game):
    game.load_fen(PROMO_FEN)
    assert game.state()["dests"]["a7"] == ["a8"]


def test_check_status(game):
    game.load_fen("4k3/8/8/8/8/8/4Q3/4K3 b - - 0 1")
    assert game.state()["status"] == "check"


def test_checkmate_status(game):
    # Детский мат
    play(game, "e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    assert game.state()["status"] == "checkmate"


def test_stalemate_status(game):
    game.load_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert game.state()["status"] == "stalemate"


def test_is_my_turn_for_white(game):
    assert game.is_my_turn() is True
    play(game, "e2e4")
    assert game.is_my_turn() is False


def test_is_my_turn_for_black():
    g = GameSession()
    g.new_game("black")
    assert g.is_my_turn() is False
    play(g, "e2e4")
    assert g.is_my_turn() is True


def test_no_turn_after_checkmate():
    g = GameSession()
    g.new_game("black")
    play(g, "e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7")
    assert g.board.turn == chess.BLACK
    assert g.is_my_turn() is False


def test_load_valid_fen(game):
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    play(game, "d2d4")
    assert game.load_fen(fen) is True
    state = game.state()
    assert state["fen"] == fen
    assert state["history"] == []


def test_load_invalid_fen_keeps_position(game):
    assert game.load_fen("not a fen") is False
    assert game.state()["fen"] == START_FEN
    assert game.state()["error"] == "Невалидный FEN: не удалось разобрать строку"


def test_load_fen_keeps_my_color():
    g = GameSession()
    g.new_game("black")
    assert g.load_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    assert g.state()["my_color"] == "black"


def test_possible_repetition_is_still_playing():
    # Повтор лишь возможен (можно заявить), но не произошёл — партия продолжается
    g = GameSession()
    g.new_game("black")
    play(g, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1")
    assert g.status() == "playing"
    assert g.is_my_turn() is True
    assert g.state()["claimable_draw"] is None


def test_threefold_repetition_only_allows_claiming_a_draw(game):
    play(game, "g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8")
    state = game.state()
    assert state["status"] == "playing"
    assert state["claimable_draw"] == "threefold_repetition"
    assert game.is_my_turn() is True
    assert state["dests"]  # ходы по-прежнему принимаются


def test_insufficient_material_ends_the_game(game):
    assert game.load_fen("8/8/8/8/8/8/8/k1K5 w - - 0 1") is True
    state = game.state()
    assert state["status"] == "draw"
    assert state["draw_reason"] == "insufficient_material"
    assert state["dests"] == {}
    assert game.move("c1", "c2") is False
    assert game.state()["error"] == "Партия окончена — начни новую или отмени ход"


def test_fen_without_kings_is_rejected(game):
    assert game.load_fen("8/8/8/8/8/8/8/8 w - - 0 1") is False
    assert game.state()["fen"] == START_FEN
    assert "нет белого короля" in game.state()["error"]


def test_fifty_moves_only_allow_claiming_a_draw(game):
    assert game.load_fen("7k/8/8/8/8/8/R7/K7 w - - 100 80") is True
    state = game.state()
    assert state["status"] == "playing"
    assert state["claimable_draw"] == "fifty_moves"
    assert game.is_my_turn() is True


def test_seventyfive_moves_end_the_game(game):
    assert game.load_fen("7k/8/8/8/8/8/R7/K7 w - - 150 100") is True
    state = game.state()
    assert state["status"] == "draw"
    assert state["draw_reason"] == "seventyfive_moves"
    assert state["claimable_draw"] is None
    assert state["dests"] == {}
    assert game.is_my_turn() is False


def test_castling(game):
    play(game, "e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6", "e1g1")
    assert game.board.piece_at(chess.G1) == chess.Piece(chess.KING, chess.WHITE)
    assert game.board.piece_at(chess.F1) == chess.Piece(chess.ROOK, chess.WHITE)
    assert game.state()["history"][-1] == "O-O"


def test_en_passant(game):
    play(game, "e2e4", "a7a6", "e4e5", "d7d5", "e5d6")
    assert game.board.piece_at(chess.D5) is None
    assert game.state()["history"][-1] == "exd6"


def test_black_promotion_with_capture():
    g = GameSession()
    g.new_game("black")
    assert g.load_fen("k7/8/8/8/8/8/1p6/R6K b - - 0 1") is True
    assert g.move("b2", "a1") is True
    assert g.board.piece_at(chess.A1) == chess.Piece(chess.QUEEN, chess.BLACK)
    assert g.state()["history"] == ["bxa1=Q+"]


def test_history_start_after_fen_with_black_to_move(game):
    assert game.load_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1")
    play(game, "e7e5", "g1f3")
    state = game.state()
    assert state["history"] == ["e5", "Nf3"]
    assert state["history_start"] == {"number": 1, "turn": "black"}


def test_short_fen_is_rejected(game):
    assert game.load_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR") is False
    assert game.state()["error"].startswith("Неполный FEN")
    assert game.state()["fen"] == START_FEN


def test_bad_castling_rights_are_explained(game):
    assert game.load_fen("4k3/8/8/8/8/8/8/4K2R w KQkq - 0 1") is False
    assert game.state()["error"] == (
        "Невалидный FEN: права на рокировку не сходятся с положением королей и ладей"
    )
