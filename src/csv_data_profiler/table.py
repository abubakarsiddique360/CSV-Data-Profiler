"""Sniff and read a delimited text table."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

DELIMITERS = (",", ";", "\t", "|")
NULL_TOKENS = frozenset({"", "-", "--", "na", "n/a", "nil", "none", "null", "nan"})


class TableError(ValueError):
    """Raised when a file cannot be read as a table."""


@dataclass(frozen=True)
class Table:
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...] = ()
    delimiter: str = ","

    @property
    def width(self) -> int:
        return len(self.header)

    @property
    def height(self) -> int:
        return len(self.rows)

    def column(self, index: int) -> list[str]:
        return [row[index] for row in self.rows]

    def as_dict(self) -> dict:
        return {
            "columns": len(self.header),
            "rows": self.height,
            "delimiter": self.delimiter,
            "header": list(self.header),
        }


def is_null(value: str) -> bool:
    return value.strip().lower() in NULL_TOKENS


def _unique(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for position, name in enumerate(names, start=1):
        label = name or f"column_{position}"
        if label in seen:
            seen[label] += 1
            label = f"{label}_{seen[label]}"
        else:
            seen[label] = 1
        result.append(label)
    return result


def sniff_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:20])
    try:
        return csv.Sniffer().sniff(sample, delimiters="".join(DELIMITERS)).delimiter
    except csv.Error:
        counts = {delimiter: sample.count(delimiter) for delimiter in DELIMITERS}
        best = max(counts, key=lambda delimiter: counts[delimiter])
        return best if counts[best] else ","


def parse_table(text: str) -> Table:
    if not text.strip():
        raise TableError("the file is empty")

    delimiter = sniff_delimiter(text)
    raw_rows = [
        row
        for row in csv.reader(io.StringIO(text.replace("\r\n", "\n")), delimiter=delimiter)
        if any(cell.strip() for cell in row)
    ]
    if not raw_rows:
        raise TableError("the file has no rows")

    header = _unique([cell.strip() for cell in raw_rows[0]])
    body: list[tuple[str, ...]] = []
    for row in raw_rows[1:]:
        padded = list(row) + [""] * (len(header) - len(row))
        body.append(tuple(cell.strip() for cell in padded[: len(header)]))

    return Table(header=tuple(header), rows=tuple(body), delimiter=delimiter)
