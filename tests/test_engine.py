import time
from pathlib import Path

import chess
import pytest

from backend.engine import EngineAnalyzer, resolve_engine_path

needs_engine = pytest.mark.skipif(
    not resolve_engine_path().exists(), reason="нет engine/stockfish.exe"
)

MATE_IN_ONE = "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"
WHITE_WITHOUT_QUEEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR b KQkq - 0 1"


@pytest.fixture
def analyzer():
    a = EngineAnalyzer()
    yield a
    a.close()


def run_to_end(analyzer, fen, pov):
    updates = []
    analyzer.analyze(fen, pov, updates.append)
    analyzer.wait(timeout=15)
    assert updates, "анализ не прислал ни одного результата"
    return updates


def test_missing_engine_sets_error_and_does_not_crash():
    a = EngineAnalyzer(Path("нет/такого/stockfish.exe"))
    assert a.error is not None
    updates = []
    a.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)
    a.wait(timeout=1)
    assert updates == []
    a.close()


@needs_engine
def test_mate_in_one_is_first_line(analyzer):
    final = run_to_end(analyzer, MATE_IN_ONE, chess.WHITE)[-1]
    first = final["lines"][0]
    assert first["uci"] == "a1a8"
    assert first["san"] == "Ra8#"
    assert first["score"] == {"cp": None, "mate": 1}
    assert final["fen"] == MATE_IN_ONE


@needs_engine
def test_start_position_returns_three_lines(analyzer):
    final = run_to_end(analyzer, chess.STARTING_FEN, chess.WHITE)[-1]
    assert len(final["lines"]) == 3
    assert final["depth"] >= 8
    assert len({line["uci"] for line in final["lines"]}) == 3


@needs_engine
def test_score_is_from_users_point_of_view(analyzer):
    # У белых нет ферзя: для чёрных оценка должна быть сильно в плюс
    final = run_to_end(analyzer, WHITE_WITHOUT_QUEEN, chess.BLACK)[-1]
    assert final["lines"][0]["score"]["cp"] > 300


@needs_engine
def test_stop_prevents_further_updates(analyzer):
    updates = []
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, updates.append)
    time.sleep(0.3)
    analyzer.stop()
    count = len(updates)
    time.sleep(1.0)
    assert len(updates) == count


@needs_engine
def test_new_analysis_replaces_old_one(analyzer):
    first, second = [], []
    analyzer.analyze(chess.STARTING_FEN, chess.WHITE, first.append)
    analyzer.analyze(MATE_IN_ONE, chess.WHITE, second.append)
    analyzer.wait(timeout=15)
    assert second and second[-1]["fen"] == MATE_IN_ONE
    assert all(r["fen"] == chess.STARTING_FEN for r in first)
