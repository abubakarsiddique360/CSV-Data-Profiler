from __future__ import annotations

from csv_data_profiler.columns import profile_table
from csv_data_profiler.quality import Issue, duplicate_rows, quality_issues, quality_score
from csv_data_profiler.table import parse_table

CLEAN = """name,score
a,10
b,20
c,30
"""


def codes(text: str) -> set[str]:
    table = parse_table(text)
    return {issue.code for issue in quality_issues(table, profile_table(table))}


def test_clean_table_scores_full() -> None:
    table = parse_table(CLEAN)
    issues = quality_issues(table, profile_table(table))
    assert issues == []
    assert quality_score(issues) == 100


def test_empty_column_lowers_the_score() -> None:
    text = "a,b\n1,\n2,\n3,\n"
    table = parse_table(text)
    issues = quality_issues(table, profile_table(table))
    assert "empty-column" in {issue.code for issue in issues}
    assert quality_score(issues) < 100


def test_high_missing_ratio_is_reported() -> None:
    assert "high-missing" in codes("a,b\n1,x\n2,\n3,\n4,\n")


def test_constant_column_is_reported() -> None:
    assert "constant-column" in codes("a,b\ny,1\ny,2\ny,3\n")


def test_duplicate_rows_are_reported() -> None:
    table = parse_table("a,b\n1,2\n1,2\n1,2\n3,4\n")
    assert duplicate_rows(table) == 2
    assert "duplicate-rows" in {issue.code for issue in quality_issues(table, profile_table(table))}


def test_single_duplicate_in_a_large_table_is_tolerated() -> None:
    rows = "\n".join(f"{index},{index * 2}" for index in range(1, 40))
    table = parse_table("a,b\n" + rows + "\n39,78\n")
    assert duplicate_rows(table) == 1
    assert "duplicate-rows" not in {issue.code for issue in quality_issues(table, profile_table(table))}


def test_tiny_table_is_reported() -> None:
    assert "tiny-table" in codes("a,b\n1,2\n")


def test_outlier_heavy_column_is_reported() -> None:
    values = "\n".join(str(value) for value in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 1000, 2000, 3000])
    assert "outlier-heavy" in codes("v\n" + values + "\n")


def test_points_are_capped() -> None:
    span = ",".join(f"c{index}" for index in range(6))
    blank = ",".join("" for _ in range(6))
    table = parse_table(span + "\n" + (blank + "\n") * 2)
    issues = [issue for issue in quality_issues(table, profile_table(table)) if issue.code == "empty-column"]
    assert len(issues) == 1
    assert issues[0].points == 30


def test_score_never_goes_negative() -> None:
    assert quality_score([Issue("x", 80, "a"), Issue("y", 80, "b")]) == 0
    assert quality_score([Issue("x", 1, "a")]) == 99


def test_issue_dict() -> None:
    assert Issue("duplicate-rows", 10, "2 rows").as_dict()["points"] == 10
