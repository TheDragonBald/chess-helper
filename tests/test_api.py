import sys
import threading

import chess
import pytest

from backend.api import Api
from backend.game import GameSession


class FakeEngine:
    def __init__(self):
        self.calls = []
        self.boards = []
        self.error = None
        self.on_update = None

    def analyze(self, position, pov, on_update):
        self.calls.append(("analyze", position.fen(), pov))
        self.boards.append(position)
        self.on_update = on_update

    def stop(self):
        self.calls.append(("stop",))


@pytest.fixture
def setup():
    engine = FakeEngine()
    pushed, on_top = [], []
    api = Api(GameSession(), engine, pushed.append, on_top.append)
    return api, engine, pushed, on_top


def test_new_game_as_white_starts_analysis(setup):
    api, engine, _, _ = setup
    state = api.new_game("white")
    assert state["fen"] == chess.STARTING_FEN
    assert engine.calls[-1] == ("analyze", chess.STARTING_FEN, chess.WHITE)


def test_new_game_as_black_stops_analysis(setup):
    api, engine, _, _ = setup
    state = api.new_game("black")
    assert state["my_color"] == "black"
    assert engine.calls[-1] == ("stop",)


def test_opponent_turn_stops_analysis(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    api.move("e2", "e4")
    assert engine.calls[-1] == ("stop",)


def test_my_turn_as_black_starts_analysis(setup):
    api, engine, _, _ = setup
    api.new_game("black")
    state = api.move("e2", "e4")
    assert engine.calls[-1] == ("analyze", state["fen"], chess.BLACK)


def test_engine_gets_the_move_history(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    api.move("e2", "e4")
    api.move("e7", "e5")
    board = engine.boards[-1]
    assert [m.uci() for m in board.move_stack] == ["e2e4", "e7e5"]
    assert board.root().fen() == chess.STARTING_FEN


def test_illegal_move_does_not_touch_engine(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    calls_before = len(engine.calls)
    state = api.move("e2", "e5")
    assert state["error"] == "Незаконный ход: e2-e5"
    assert len(engine.calls) == calls_before


def test_undo_back_to_my_turn_restarts_analysis(setup):
    api, engine, _, _ = setup
    api.new_game("white")
    api.move("e2", "e4")
    state = api.undo()
    assert engine.calls[-1] == ("analyze", state["fen"], chess.WHITE)


def test_load_fen_reanalyzes(setup):
    api, engine, _, _ = setup
    api.new_game("black")
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    api.load_fen(fen)
    assert engine.calls[-1] == ("analyze", fen, chess.BLACK)


def test_state_contains_engine_error(setup):
    api, engine, _, _ = setup
    engine.error = "Не найден Stockfish"
    assert api.get_state()["engine_error"] == "Не найден Stockfish"


def test_analysis_results_carry_position_rev(setup):
    api, engine, pushed, _ = setup
    state = api.new_game("white")
    engine.on_update({"fen": state["fen"], "depth": 10, "lines": []})
    assert pushed == [{"fen": state["fen"], "depth": 10, "lines": [], "rev": state["rev"]}]


def test_rev_changes_only_when_position_changes(setup):
    api, _, _, _ = setup
    first = api.new_game("white")
    moved = api.move("e2", "e4")
    assert moved["rev"] == first["rev"] + 1
    assert api.move("e7", "e4")["rev"] == moved["rev"]  # незаконный ход позицию не меняет
    assert api.get_state()["rev"] == moved["rev"]
    assert api.undo()["rev"] == moved["rev"] + 1


def test_late_analysis_keeps_its_own_rev(setup):
    api, engine, pushed, _ = setup
    api.new_game("white")
    old_update = engine.on_update
    api.move("e2", "e4")
    state = api.move("e7", "e5")
    old_update({"fen": "old", "depth": 9, "lines": []})
    engine.on_update({"fen": state["fen"], "depth": 9, "lines": []})
    assert [p["rev"] for p in pushed] == [state["rev"] - 2, state["rev"]]


def test_error_belongs_to_the_action_only(setup):
    api, _, _, _ = setup
    api.new_game("white")
    assert api.move("e2", "e5")["error"] == "Незаконный ход: e2-e5"
    assert api.get_state()["error"] is None
    assert api.set_on_top(True)["error"] is None


def test_set_on_top_passes_flag(setup):
    api, _, _, on_top = setup
    api.set_on_top(True)
    api.set_on_top(False)
    assert on_top == [True, False]


def test_only_api_methods_are_public(setup):
    api, _, _, _ = setup
    public = {name for name in dir(api) if not name.startswith("_")}
    assert public == {"get_state", "new_game", "move", "undo", "load_fen", "set_on_top"}


def test_concurrent_calls_do_not_corrupt_board(setup):
    api, _, _, _ = setup
    api.new_game("white")
    errors = []
    old_hook = threading.excepthook
    old_interval = sys.getswitchinterval()
    threading.excepthook = lambda args: errors.append(args.exc_value)

    def hammer(moves):
        for i in range(300):
            api.undo()
            api.move(*moves[i % 2])
            api.get_state()

    pairs = [
        [("g1", "f3"), ("f3", "g1")],
        [("g8", "f6"), ("f6", "g8")],
        [("g1", "f3"), ("f3", "g1")],
        [("g8", "f6"), ("f6", "g8")],
        [("g1", "f3"), ("f3", "g1")],
    ]
    try:
        sys.setswitchinterval(1e-6)
        threads = [threading.Thread(target=hammer, args=(m,)) for m in pairs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old_interval)
        threading.excepthook = old_hook

    assert errors == []
    board = api._game.board
    replay = board.root()
    for move in board.move_stack:
        # push() не проверяет законность, поэтому проверяем каждый ход явно
        assert replay.is_legal(move)
        replay.push(move)
    assert replay.fen() == board.fen()
