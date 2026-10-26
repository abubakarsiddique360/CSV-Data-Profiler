"""Command line entry point: profile, columns, correlations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from csv_data_profiler.columns import profile_table
from csv_data_profiler.report import ProfileReport
from csv_data_profiler.table import TableError, parse_table


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise TableError(f"cannot read {path}: {exc.strerror or exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csv-profile",
        description="Describe a CSV file: types, statistics, correlations and data quality.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    profile_cmd = sub.add_parser("profile", help="full profile")
    profile_cmd.add_argument("file")
    profile_cmd.add_argument("--top", type=int, default=3, help="how many common values per column")
    profile_cmd.add_argument("--min-r", type=float, default=0.5, help="minimum |r| for correlations")
    profile_cmd.add_argument("--json", action="store_true")
    profile_cmd.add_argument("--markdown", action="store_true")

    columns_cmd = sub.add_parser("columns", help="one line per column")
    columns_cmd.add_argument("file")
    columns_cmd.add_argument("--top", type=int, default=3)

    corr_cmd = sub.add_parser("correlations", help="numeric pairs above a threshold")
    corr_cmd.add_argument("file")
    corr_cmd.add_argument("--min-r", type=float, default=0.5)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        table = parse_table(_read(args.file))
    except TableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    source = Path(args.file).name
    top = getattr(args, "top", 3)
    minimum = getattr(args, "min_r", 0.5)
    report = ProfileReport(table=table, source=source, top=top, minimum_correlation=minimum)

    if args.command == "columns":
        for profile in profile_table(table, top=top):
            print(
                f"{profile.name:<20}{profile.kind:<9}missing={profile.missing:<5}distinct={profile.distinct:<6}"
                f"min={profile.minimum} max={profile.maximum}"
            )
        return 0

    if args.command == "correlations":
        found = report.found_correlations
        if not found:
            print(f"no numeric pair reaches |r| >= {minimum:g}")
            return 0
        for item in found:
            print(f"{item.left:<18}{item.right:<18}r={item.coefficient:+.2f}  {item.strength:<12}n={item.samples}")
        return 0

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, default=str))
    elif args.markdown:
        print(report.render_markdown())
    else:
        print(report.render())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
