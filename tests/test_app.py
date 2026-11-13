"""Точка входа: самопроверка, проблема при старте, обычный запуск."""
import pytest

import app


@pytest.fixture
def log_file(monkeypatch, tmp_path):
    # Настоящий setup_logging трогает папку логов и глобальные хуки — в тестах не нужен
    path = tmp_path / "helper.log"
    monkeypatch.setattr(app, "setup_logging", lambda: path)
    return path


def test_self_check_runs_and_exits_with_its_code(monkeypatch, log_file, tmp_path):
    calls = []

    def fake_run(report):
        calls.append(report)
        return 1

    monkeypatch.setattr("backend.selfcheck.run_self_check", fake_run)
    with pytest.raises(SystemExit) as exit_info:
        app.main(["--self-check", str(tmp_path / "report.txt")])
    assert exit_info.value.code == 1
    assert calls == [tmp_path / "report.txt"]


def test_self_check_without_report_path_exits_with_2(log_file):
    with pytest.raises(SystemExit) as exit_info:
        app.main(["--self-check"])
    assert exit_info.value.code == 2


def test_startup_problem_shows_message_and_skips_window(monkeypatch, log_file):
    shown, started = [], []
    monkeypatch.setattr("backend.startup_check.check_startup", lambda: "no_webview2")
    monkeypatch.setattr(
        "backend.startup_check.show_startup_problem",
        lambda problem, path: shown.append((problem, path)),
    )
    monkeypatch.setattr(app, "run_app", lambda: started.append(True))
    app.main([])
    assert shown == [("no_webview2", log_file)]
    assert started == []


def test_no_problem_starts_window(monkeypatch, log_file):
    started = []
    monkeypatch.setattr("backend.startup_check.check_startup", lambda: None)
    monkeypatch.setattr(app, "run_app", lambda: started.append(True))
    app.main([])
    assert started == [True]
