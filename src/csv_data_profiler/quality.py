"""Data quality checks that turn a profile into a single score."""

from __future__ import annotations

from dataclasses import dataclass

from csv_data_profiler.columns import ColumnProfile
from csv_data_profiler.table import Table


@dataclass(frozen=True)
class Issue:
    code: str
    points: int
    message: str

    def as_dict(self) -> dict:
        return {"code": self.code, "points": self.points, "message": self.message}


def duplicate_rows(table: Table) -> int:
    seen: set[tuple[str, ...]] = set()
    duplicates = 0
    for row in table.rows:
        if row in seen:
            duplicates += 1
        else:
            seen.add(row)
    return duplicates


def _capped(code: str, points: int, messages: list[str], cap: int) -> list[Issue]:
    if not messages:
        return []
    total = min(points * len(messages), cap)
    return [Issue(code=code, points=total, message="; ".join(messages[:5]))]


def quality_issues(table: Table, profiles: list[ColumnProfile]) -> list[Issue]:
    issues: list[Issue] = []

    empty = [profile.name for profile in profiles if profile.present == 0]
    issues += _capped("empty-column", 15, [f"'{name}' has no values" for name in empty], 30)

    sparse = [
        f"'{profile.name}' is {profile.absent_ratio * 100:.0f}% empty"
        for profile in profiles
        if profile.present > 0 and profile.absent_ratio > 0.2
    ]
    issues += _capped("high-missing", 10, sparse, 20)

    constant = [
        f"'{profile.name}' always holds '{profile.top_values[0][0]}'"
        for profile in profiles
        if profile.distinct == 1 and profile.present > 0
    ]
    issues += _capped("constant-column", 5, constant, 10)

    heavy = [
        f"'{profile.name}' has {profile.outliers} outlier(s)"
        for profile in profiles
        if profile.present > 0 and profile.outliers / profile.present > 0.05
    ]
    issues += _capped("outlier-heavy", 5, heavy, 10)

    if table.height < 2:
        issues.append(Issue("tiny-table", 20, f"only {table.height} data row, statistics are not meaningful"))

    duplicates = duplicate_rows(table)
    if table.height and duplicates / table.height > 0.05:
        issues.append(Issue("duplicate-rows", 10, f"{duplicates} of {table.height} rows repeat an earlier row"))

    return issues


def quality_score(issues: list[Issue]) -> int:
    return max(0, 100 - sum(issue.points for issue in issues))
