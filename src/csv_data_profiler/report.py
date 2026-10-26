"""Assemble the profile into text, markdown or JSON."""

from __future__ import annotations

from dataclasses import dataclass

from csv_data_profiler.columns import ColumnProfile, Correlation, correlations, profile_table
from csv_data_profiler.quality import Issue, duplicate_rows, quality_issues, quality_score
from csv_data_profiler.table import Table


def _number(value: float | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    if float(value).is_integer():
        return f"{int(value)}"
    return f"{value:.2f}"


@dataclass
class ProfileReport:
    table: Table
    source: str = "table"
    top: int = 3
    minimum_correlation: float = 0.5

    @property
    def profiles(self) -> list[ColumnProfile]:
        return profile_table(self.table, top=self.top)

    @property
    def found_correlations(self) -> list[Correlation]:
        return correlations(self.table, minimum=self.minimum_correlation)

    @property
    def issues(self) -> list[Issue]:
        return quality_issues(self.table, self.profiles)

    @property
    def score(self) -> int:
        return quality_score(self.issues)

    @property
    def duplicates(self) -> int:
        return duplicate_rows(self.table)

    def as_dict(self) -> dict:
        return {
            "source": self.source,
            "columns": self.table.width,
            "rows": self.table.height,
            "delimiter": self.table.delimiter,
            "duplicate_rows": self.duplicates,
            "score": self.score,
            "profiles": [profile.as_dict() for profile in self.profiles],
            "correlations": [item.as_dict() for item in self.found_correlations],
            "issues": [issue.as_dict() for issue in self.issues],
        }

    def render(self) -> str:
        lines = [
            f"{self.source}  -  {self.table.height} row(s) x {self.table.width} column(s)  "
            f"(delimiter {self.table.delimiter!r})",
            f"quality score {self.score}/100   duplicate rows {self.duplicates}",
            "",
            f"{'COLUMN':<20}{'KIND':<9}{'MISS':>6}{'DISTINCT':>10}{'MIN':>14}{'MAX':>14}{'MEAN':>14}",
        ]
        for profile in self.profiles:
            lines.append(
                f"{profile.name[:19]:<20}{profile.kind:<9}{profile.missing:>6}{profile.distinct:>10}"
                f"{_number(profile.minimum):>14}{_number(profile.maximum):>14}{_number(profile.average):>14}"
            )

        interesting = [profile for profile in self.profiles if profile.top_values and not profile.numeric]
        if interesting:
            lines += ["", "Most common values"]
            for profile in interesting:
                rendered = ", ".join(f"{value} ({count})" for value, count in profile.top_values)
                lines.append(f"  {profile.name}: {rendered}")

        if self.found_correlations:
            lines += ["", f"Correlations with |r| >= {self.minimum_correlation:g}"]
            for item in self.found_correlations:
                lines.append(
                    f"  {item.left} <-> {item.right}  r={item.coefficient:+.2f}  {item.strength}  n={item.samples}"
                )

        if self.issues:
            lines += ["", "Issues"]
            for issue in self.issues:
                lines.append(f"  -{issue.points:>3}  {issue.code:<16} {issue.message}")
        else:
            lines += ["", "No data quality issues found."]

        return "\n".join(lines)

    def render_markdown(self) -> str:
        lines = [
            f"### {self.source}",
            "",
            f"- rows: **{self.table.height}**",
            f"- columns: **{self.table.width}**",
            f"- delimiter: `{self.table.delimiter}`",
            f"- duplicate rows: **{self.duplicates}**",
            f"- quality score: **{self.score}/100**",
            "",
            "| Column | Kind | Missing | Distinct | Min | Max | Mean |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for profile in self.profiles:
            lines.append(
                f"| {profile.name} | {profile.kind} | {profile.missing} | {profile.distinct} | "
                f"{_number(profile.minimum)} | {_number(profile.maximum)} | {_number(profile.average)} |"
            )

        if self.found_correlations:
            lines += ["", "| Pair | r | Strength | Samples |", "| --- | --- | --- | --- |"]
            for item in self.found_correlations:
                lines.append(
                    f"| {item.left} / {item.right} | {item.coefficient:+.2f} | {item.strength} | {item.samples} |"
                )

        if self.issues:
            lines += ["", "**Issues**", ""]
            lines += [f"- `{issue.code}` (-{issue.points}) {issue.message}" for issue in self.issues]
        return "\n".join(lines)
