from __future__ import annotations

import json
from pathlib import Path

from csv_data_profiler.cli import main
from csv_data_profiler.report import ProfileReport
from csv_data_profiler.table import parse_table

DATA = Path(__file__).resolve().parent.parent / "data" / "orders.csv"


def test_profile_text(capsys) -> None:
    assert main(["profile", str(DATA)]) == 0
    out = capsys.readouterr().out
    assert "24 row(s) x 9 column(s)" in out
    assert "quality score" in out
    assert "COLUMN" in out


def test_profile_json(capsys) -> None:
    main(["profile", str(DATA), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == 24
    assert payload["duplicate_rows"] == 1
    assert payload["score"] < 100
    names = [profile["name"] for profile in payload["profiles"]]
    assert names[0] == "order_id"
    assert any(issue["code"] == "constant-column" for issue in payload["issues"])


def test_profile_markdown(capsys) -> None:
    main(["profile", str(DATA), "--markdown"])
    out = capsys.readouterr().out
    assert out.startswith("### orders.csv")
    assert "| Column | Kind |" in out


def test_columns_command(capsys) -> None:
    assert main(["columns", str(DATA)]) == 0
    out = capsys.readouterr().out
    assert "order_id" in out
    assert "missing=" in out


def test_correlations_command(capsys) -> None:
    assert main(["correlations", str(DATA), "--min-r", "0.8"]) == 0
    assert "units" in capsys.readouterr().out


def test_correlations_none(capsys) -> None:
    assert main(["correlations", str(DATA), "--min-r", "1.1"]) == 0
    assert "no numeric pair" in capsys.readouterr().out


def test_missing_file(tmp_path, capsys) -> None:
    assert main(["profile", str(tmp_path / "nope.csv")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_empty_file(tmp_path, capsys) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("  \n", encoding="utf-8")
    assert main(["profile", str(path)]) == 2
    assert "empty" in capsys.readouterr().err


def test_report_render_includes_correlations() -> None:
    table = parse_table(DATA.read_text(encoding="utf-8"))
    report = ProfileReport(table=table, source="orders.csv", minimum_correlation=0.8)
    text = report.render()
    assert "Correlations" in text
    assert "units <-> revenue" in text
    assert "Most common values" in text


def test_report_without_issues_says_so() -> None:
    table = parse_table("a,b\n1,2\n3,4\n5,6\n")
    report = ProfileReport(table=table, source="tiny.csv")
    assert "No data quality issues found." in report.render()
    assert "**Issues**" not in report.render_markdown()
