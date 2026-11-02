from __future__ import annotations

import json
from pathlib import Path

import pytest

from simulacrum import __version__
from simulacrum.cli.main import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as e:
        main(["--version"])
    assert e.value.code == 0 and __version__ in capsys.readouterr().out


def test_usage_error_exits_2() -> None:
    with pytest.raises(SystemExit) as e:
        main([])
    assert e.value.code == 2


def test_run_prints_frames_and_writes_a_replayable_log(
    eco_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "run.json"
    assert (
        main(
            [
                "run",
                str(eco_dir / "forest.json"),
                "--ticks",
                "30",
                "--every",
                "15",
                "--seed",
                "7",
                "--log-out",
                str(log),
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "tick 15" in out and "tick 30" in out and "state hash" in out
    assert json.loads(log.read_text())["ticks"] == 30
    assert main(["verify", str(log), "--ecosystems", str(eco_dir)]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["ok"] is True


def test_verify_fails_with_exit_1_on_a_tampered_log(
    eco_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = tmp_path / "run.json"
    main(["run", str(eco_dir / "forest.json"), "--ticks", "10", "--log-out", str(log)])
    data = json.loads(log.read_text())
    data["final_hash"] = "0" * 16
    log.write_text(json.dumps(data))
    capsys.readouterr()
    assert main(["verify", str(log), "--ecosystems", str(eco_dir)]) == 1


def test_validate_reports_every_file_and_fails_if_any_is_bad(
    eco_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = [str(eco_dir / "forest.json"), str(eco_dir / "junction.json")]
    assert main(["validate", *good]) == 0
    assert capsys.readouterr().out.count("ok  ") == 2
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "name": "x",
                "environment": {"terrains": {"a": {}}},
                "agent_types": [{"name": "t", "brain": "no_such_brain"}],
            }
        )
    )
    assert main(["validate", good[0], str(bad)]) == 1
    captured = capsys.readouterr()
    assert "ok  " in captured.out and "FAIL" in captured.err and "no_such_brain" in captured.err


def test_missing_file_is_a_clean_error_not_a_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "/nonexistent/spec.json"]) == 1
    assert "error:" in capsys.readouterr().err
