from __future__ import annotations

from pathlib import Path

import pytest

from csv_data_profiler.columns import (
    Correlation,
    detect_kind,
    mean,
    numeric_columns,
    pearson,
    profile_column,
    profile_table,
    quantile,
    stdev,
    to_number,
)
from csv_data_profiler.table import parse_table

DATA = Path(__file__).resolve().parent.parent / "data" / "orders.csv"

SIMPLE = """name,score,price,when,active
a,10,1.5,2025-01-01,true
b,20,2.5,2025-02-01,false
c,30,3.5,2025-03-01,true
d,40,4.5,2025-04-01,true
"""


@pytest.fixture
def simple_table():
    return parse_table(SIMPLE)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("10", 10), ("-3", -3), ("1,234", 1234), ("2.5", 2.5), ("", None), ("abc", None)],
)
def test_to_number(raw: str, expected) -> None:
    assert to_number(raw) == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["1", "2"], "integer"),
        (["1", "2.5"], "float"),
        (["true", "no"], "boolean"),
        (["2025-01-01", "2025-02-03"], "date"),
        (["a", "b"], "string"),
        ([], "empty"),
    ],
)
def test_detect_kind(values: list[str], expected: str) -> None:
    assert detect_kind(values) == expected


def test_quantile_and_mean() -> None:
    ordered = [1.0, 2.0, 3.0, 4.0]
    assert quantile(ordered, 0.5) == 2.5
    assert quantile(ordered, 0.0) == 1.0
    assert quantile(ordered, 1.0) == 4.0
    assert quantile([], 0.5) == 0.0
    assert mean(ordered) == 2.5
    assert mean([]) == 0.0


def test_stdev_is_sample_based() -> None:
    values = [10.0, 20.0, 30.0, 40.0]
    assert stdev(values) == pytest.approx((500 / 3) ** 0.5)
    assert stdev([1.0]) == 0.0


def test_integer_column_statistics(simple_table) -> None:
    profile = profile_column(simple_table, 1)
    assert profile.kind == "integer"
    assert profile.numeric is True
    assert profile.minimum == 10.0
    assert profile.maximum == 40.0
    assert profile.average == 25.0
    assert profile.median == 25.0
    assert profile.deviation == pytest.approx((500 / 3) ** 0.5)
    assert profile.outliers == 0
    assert profile.missing == 0
    assert profile.distinct == 4


def test_string_column_top_values(simple_table) -> None:
    profile = profile_column(simple_table, 0, top=2)
    assert profile.kind == "string"
    assert profile.top_values == (("a", 1), ("b", 1))
    assert profile.minimum is None


def test_boolean_and_date_columns(simple_table) -> None:
    active = profile_column(simple_table, 4)
    assert active.kind == "boolean"
    assert active.distinct == 2
    when = profile_column(simple_table, 3)
    assert when.kind == "date"
    assert when.minimum == "2025-01-01"
    assert when.maximum == "2025-04-01"


def test_missing_values_are_counted() -> None:
    table = parse_table("v\n1\n\nNA\n3\n")
    profile = profile_column(table, 0)
    assert profile.present == 2
    assert profile.missing == 1
    assert profile.absent_ratio == pytest.approx(1 / 3)


def test_empty_column_kind() -> None:
    table = parse_table("a,b\n1,\n2,\n")
    profile = profile_column(table, 1)
    assert profile.kind == "empty"
    assert profile.present == 0
    assert profile.absent_ratio == 1.0


def test_outliers_are_detected() -> None:
    values = ["1"] * 10 + ["1000"]
    table = parse_table("v\n" + "\n".join(values) + "\n")
    assert profile_column(table, 0).outliers == 1


def test_profile_table_covers_every_column(simple_table) -> None:
    profiles = profile_table(simple_table)
    assert [profile.name for profile in profiles] == ["name", "score", "price", "when", "active"]


def test_pearson_edge_cases() -> None:
    assert pearson([1.0, 2.0], [1.0, 2.0]) is None
    assert pearson([1.0, 2.0, 3.0], [2.0, 2.0, 2.0]) is None
    assert pearson([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_numeric_columns_skips_text(simple_table) -> None:
    assert sorted(numeric_columns(simple_table)) == [1, 2]


def test_correlations_find_the_linear_pair(simple_table) -> None:
    from csv_data_profiler.columns import correlations

    found = correlations(simple_table, minimum=0.9)
    assert len(found) == 1
    assert {found[0].left, found[0].right} == {"score", "price"}
    assert found[0].coefficient == pytest.approx(1.0)
    assert found[0].strength == "very strong"
    assert found[0].samples == 4


def test_correlations_threshold_excludes_pairs(simple_table) -> None:
    from csv_data_profiler.columns import correlations

    assert correlations(simple_table, minimum=1.1) == []


def test_correlation_strength_and_dict() -> None:
    assert Correlation("a", "b", -0.65, 10).strength == "strong"
    assert Correlation("a", "b", 0.55, 10).strength == "moderate"
    payload = Correlation("a", "b", 0.9123, 10).as_dict()
    assert payload["coefficient"] == 0.912
    assert payload["strength"] == "very strong"


def test_sample_correlates_units_with_revenue() -> None:
    from csv_data_profiler.columns import correlations

    table = parse_table(DATA.read_text(encoding="utf-8"))
    found = {frozenset((item.left, item.right)) for item in correlations(table, minimum=0.8)}
    assert frozenset(("units", "revenue")) in found
