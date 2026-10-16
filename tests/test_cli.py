import json
import os
import subprocess
import sys
from pathlib import Path

from lora_link_budget.cli import main


def test_range_json(capsys):
    main(["range", "--sf", "7", "12", "--model", "free-space", "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert [r["SF"] for r in rows] == [7, 12]
    assert float(rows[1]["range m"]) > float(rows[0]["range m"])


def test_example_runs_end_to_end(capsys):
    main(["example"])
    out = capsys.readouterr().out
    assert "Worked example" in out and "life years" in out and "1482.8" in out


def test_module_entry_point():
    r = subprocess.run(
        [sys.executable, "-m", "lora_link_budget", "airtime", "--payload", "10", "--sf", "7"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert "61.7" in r.stdout
