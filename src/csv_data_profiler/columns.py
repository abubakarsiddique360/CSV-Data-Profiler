"""Infer column types and compute the statistics worth looking at."""

from __future__ import annotations

import re
from dataclasses import dataclass

from csv_data_profiler.table import Table, is_null

BOOL_TOKENS = frozenset({"true", "false", "yes", "no", "y", "n"})
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([T ][\d:.]+)?$")
INTEGER_RE = re.compile(r"^[+-]?\d+$")
KINDS = ("integer", "float", "boolean", "date", "string", "empty")


def to_number(value: str) -> int | float | None:
    text = value.strip().replace(",", "").replace("_", "")
    if not text:
        return None
    if INTEGER_RE.match(text):
        return int(text)
    try:
        return float(text)
    except ValueError:
        return None


def detect_kind(values: list[str]) -> str:
    if not values:
        return "empty"
    numbers = [to_number(value) for value in values]
    if all(isinstance(number, int) and not isinstance(number, bool) for number in numbers):
        return "integer"
    if all(number is not None for number in numbers):
        return "float"
    lowered = [value.strip().lower() for value in values]
    if all(value in BOOL_TOKENS for value in lowered):
        return "boolean"
    if all(DATE_RE.match(value.strip()) for value in lowered):
        return "date"
    return "string"


def quantile(ordered: list[float], fraction: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(ordered[lower]) * (1 - weight) + float(ordered[upper]) * weight


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    average = mean(values)
    variance = sum((value - average) ** 2 for value in values) / (len(values) - 1)
    return variance**0.5


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    index: int
    kind: str
    present: int
    missing: int
    distinct: int
    minimum: float | str | None = None
    maximum: float | str | None = None
    average: float | None = None
    median: float | None = None
    deviation: float | None = None
    outliers: int = 0
    top_values: tuple[tuple[str, int], ...] = ()

    @property
    def absent_ratio(self) -> float:
        total = self.present + self.missing
        return self.missing / total if total else 0.0

    @property
    def numeric(self) -> bool:
        return self.kind in {"integer", "float"}

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "index": self.index,
            "kind": self.kind,
            "present": self.present,
            "missing": self.missing,
            "missing_ratio": round(self.absent_ratio, 3),
            "distinct": self.distinct,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "average": None if self.average is None else round(self.average, 4),
            "median": None if self.median is None else round(self.median, 4),
            "deviation": None if self.deviation is None else round(self.deviation, 4),
            "outliers": self.outliers,
            "top_values": [{"value": value, "count": count} for value, count in self.top_values],
        }


def _top_values(values: list[str], limit: int) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return tuple(ordered[:limit])


def profile_column(table: Table, index: int, top: int = 3) -> ColumnProfile:
    raw = table.column(index)
    present_values = [value for value in raw if not is_null(value)]
    missing = len(raw) - len(present_values)
    kind = detect_kind(present_values)
    base = {
        "name": table.header[index],
        "index": index,
        "kind": kind,
        "present": len(present_values),
        "missing": missing,
        "distinct": len(set(present_values)),
    }

    if kind in {"integer", "float"}:
        numbers = [float(number) for number in (to_number(value) for value in present_values) if number is not None]
        ordered = sorted(numbers)
        q1, q3 = quantile(ordered, 0.25), quantile(ordered, 0.75)
        spread = q3 - q1
        outliers = sum(1 for number in numbers if number < q1 - 1.5 * spread or number > q3 + 1.5 * spread)
        return ColumnProfile(
            **base,
            minimum=ordered[0],
            maximum=ordered[-1],
            average=mean(numbers),
            median=quantile(ordered, 0.5),
            deviation=stdev(numbers),
            outliers=outliers,
            top_values=_top_values(present_values, top),
        )

    if kind == "date":
        ordered_dates = sorted(value.strip() for value in present_values)
        return ColumnProfile(**base, minimum=ordered_dates[0], maximum=ordered_dates[-1])

    return ColumnProfile(**base, top_values=_top_values(present_values, top))


def profile_table(table: Table, top: int = 3) -> list[ColumnProfile]:
    return [profile_column(table, index, top=top) for index in range(table.width)]


@dataclass(frozen=True)
class Correlation:
    left: str
    right: str
    coefficient: float
    samples: int

    @property
    def strength(self) -> str:
        magnitude = abs(self.coefficient)
        if magnitude >= 0.8:
            return "very strong"
        if magnitude >= 0.6:
            return "strong"
        return "moderate"

    def as_dict(self) -> dict:
        return {
            "left": self.left,
            "right": self.right,
            "coefficient": round(self.coefficient, 3),
            "samples": self.samples,
            "strength": self.strength,
        }


def pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    left_mean, right_mean = mean(left), mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_norm = sum((a - left_mean) ** 2 for a in left) ** 0.5
    right_norm = sum((b - right_mean) ** 2 for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return None
    return numerator / (left_norm * right_norm)


def numeric_columns(table: Table) -> dict[int, list[float]]:
    series: dict[int, list[float]] = {}
    for index in range(table.width):
        values: list[float] = []
        for cell in table.column(index):
            if is_null(cell):
                continue
            number = to_number(cell)
            if number is None:
                values = []
                break
            values.append(float(number))
        if len(values) >= 3:
            series[index] = values
    return series


def correlations(table: Table, minimum: float = 0.5) -> list[Correlation]:
    series = numeric_columns(table)
    found: list[Correlation] = []
    for left_index in sorted(series):
        for right_index in sorted(series):
            if right_index <= left_index:
                continue
            coefficient = pearson(series[left_index], series[right_index])
            if coefficient is None or abs(coefficient) < minimum:
                continue
            found.append(
                Correlation(
                    left=table.header[left_index],
                    right=table.header[right_index],
                    coefficient=coefficient,
                    samples=min(len(series[left_index]), len(series[right_index])),
                )
            )
    found.sort(key=lambda item: abs(item.coefficient), reverse=True)
    return found
