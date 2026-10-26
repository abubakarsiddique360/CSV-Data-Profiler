from __future__ import annotations

from pathlib import Path

import pytest

from csv_data_profiler.table import TableError, is_null, parse_table, sniff_delimiter

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


@pytest.fixture
def sample_csv() -> Path:
    return DATA


def test_parses_header_and_rows() -> None:
    table = parse_table(SIMPLE)
    assert table.header == ("name", "score", "price", "when", "active")
    assert table.height == 4
    assert table.width == 5
    assert table.delimiter == ","
    assert table.rows[0][0] == "a"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("a;b;c\n1;2;3\n", ";"),
        ("a\tb\n1\t2\n", "\t"),
        ("a|b\n1|2\n", "|"),
        ("a,b\n1,2\n", ","),
    ],
)
def test_delimiter_sniffing(text: str, expected: str) -> None:
    assert parse_table(text).delimiter == expected


def test_delimiter_falls_back_to_comma() -> None:
    assert sniff_delimiter("single") == ","


def test_null_tokens() -> None:
    for token in ["", " NA ", "n/a", "NULL", "none", "nan", "-"]:
        assert is_null(token)
    assert not is_null("0")
    assert not is_null("north")


def test_duplicate_header_names_are_made_unique() -> None:
    table = parse_table("a,a,a\n1,2,3\n")
    assert table.header == ("a", "a_2", "a_3")


def test_blank_header_names_are_numbered() -> None:
    table = parse_table("a,,c\n1,2,3\n")
    assert table.header == ("a", "column_2", "c")


def test_short_rows_are_padded() -> None:
    table = parse_table("a,b,c\n1,2\n")
    assert table.rows[0] == ("1", "2", "")


def test_long_rows_are_trimmed() -> None:
    table = parse_table("a,b\n1,2,3,4\n")
    assert table.rows[0] == ("1", "2")


def test_blank_lines_are_dropped() -> None:
    assert parse_table("a,b\n\n1,2\n\n").height == 1


def test_empty_file_is_rejected() -> None:
    with pytest.raises(TableError, match="empty"):
        parse_table("   \n\n")


def test_header_only_file_has_no_rows() -> None:
    assert parse_table("a,b\n").height == 0


def test_header_only_whitespace_is_rejected() -> None:
    with pytest.raises(TableError):
        parse_table("\n\n")


def test_crlf_is_handled() -> None:
    assert parse_table("a,b\r\n1,2\r\n").rows == (("1", "2"),)


def test_column_and_as_dict(simple_table) -> None:
    assert simple_table.column(1) == ["10", "20", "30", "40"]
    payload = simple_table.as_dict()
    assert payload["columns"] == 5
    assert payload["rows"] == 4
    assert payload["header"][0] == "name"


def test_sample_csv_parses(sample_csv) -> None:
    table = parse_table(sample_csv.read_text(encoding="utf-8"))
    assert table.height == 24
    assert table.width == 9
    assert table.header[0] == "order_id"
