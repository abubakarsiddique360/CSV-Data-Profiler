# CSV-Data-Profiler

[![CI](https://github.com/abubakarsiddique360/CSV-Data-Profiler/actions/workflows/ci.yml/badge.svg)](https://github.com/abubakarsiddique360/CSV-Data-Profiler/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.12-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![dependencies](https://img.shields.io/badge/dependencies-none-success)

Answer "what is in this file?" in one command: real column types, missing values, distribution
statistics, outlier counts, numeric correlations and a data quality score. Text, markdown or
JSON output. Standard library only, no pandas, no notebook.

## Why it exists

Exploratory data analysis usually starts by writing the same twenty lines of pandas again:
`dtypes`, `isna`, `describe`, `value_counts`, a correlation matrix. Then someone loads a file with
semicolons, a stray blank line and `NA` in a numeric column, and the notebook dies on the first
row. This tool does the boring part deterministically, works on any delimited file, and prints a
report you can paste into a pull request.

## Install

```bash
pip install -e .
```

Python 3.10+, zero runtime dependencies.

## Usage

```bash
csv-profile profile data/orders.csv              # readable report
csv-profile profile data/orders.csv --markdown   # markdown tables for a PR or issue
csv-profile profile data/orders.csv --json       # everything, for dashboards
csv-profile columns data/orders.csv              # one line per column
csv-profile correlations data/orders.csv --min-r 0.6
```

Every command exits `0` on success and `2` when the file cannot be read as a table.

## Example

```text
orders.csv  -  24 row(s) x 9 column(s)  (delimiter ',')
quality score 85/100   duplicate rows 1

COLUMN              KIND       MISS  DISTINCT           MIN           MAX          MEAN
order_id            integer       0        23          1001          1023       1011.62
region              string        0         4             -             -             -
units               integer       0        14             4            30         15.50
revenue             float         0        18            40           300        148.08
order_date          date          0        23    2025-01-01    2025-01-23             -
notes               string       18         3             -             -             -

Most common values
  region: West (7), East (6), South (6)
  shipped: true (16), false (8)

Correlations with |r| >= 0.5
  units <-> revenue  r=+0.92  very strong  n=24
  order_id <-> revenue  r=+0.65  strong  n=24

Issues
  - 10  high-missing     'notes' is 75% empty
  -  5  constant-column  'flag' always holds 'y'
```

## What the profiler does

| Step | Behaviour |
| --- | --- |
| Delimiter | Sniffed with `csv.Sniffer` across comma, semicolon, tab and pipe, with a frequency fallback for tiny or irregular files. |
| Header | Whitespace trimmed, blank names numbered `column_2`, duplicates suffixed `_2` so every name stays unique. |
| Ragged rows | Short rows padded with empty cells, long rows trimmed, fully blank lines dropped. |
| Nulls | `''`, `-`, `--`, `na`, `n/a`, `nil`, `none`, `null`, `nan` (case insensitive). |
| Types | `integer`, `float`, `boolean`, `date` (`YYYY-MM-DD`), `string`, `empty`; a column is numeric only if every non-null value parses. |
| Numeric stats | Min, max, mean, median, sample standard deviation and an IQR outlier count. |
| Other stats | Distinct count and the most common values. |
| Correlations | Pearson `r` for every numeric pair, filtered by `--min-r` (default `0.5`) and labelled moderate / strong / very strong. |

### Quality score

The score starts at 100 and subtracts:

| Code | Points | Trigger |
| --- | --- | --- |
| `empty-column` | 15 each, capped at 30 | A column has no values. |
| `high-missing` | 10 each, capped at 20 | More than 20% of a column is empty. |
| `constant-column` | 5 each, capped at 10 | A column has exactly one distinct value. |
| `outlier-heavy` | 5 each, capped at 10 | More than 5% of a column's values fall outside 1.5 x IQR. |
| `duplicate-rows` | 10 | More than 5% of rows repeat an earlier row. |
| `tiny-table` | 20 | Fewer than two data rows, so statistics mean nothing. |

The score is a triage signal, not a verdict: a legitimately sparse survey file can score 85 and
still be perfectly usable.

## Design notes

- **No dependencies, on purpose.** The library imports only `csv`, `re`, `math` and `dataclasses`,
  which makes it safe to drop into a locked-down environment.
- **Statistics are explicit.** Quartiles use linear interpolation on the sorted values, the
  standard deviation is the sample (`n - 1`) version, and correlation needs at least three paired
  samples before it reports anything.
- **Constant columns return no correlation** instead of a division by zero, because a column that
  never changes carries no signal.
- **Markdown output** exists because the most common use of a profile is quoting it in a review or
  an issue, not reading it in a terminal.
- **The report is a view.** `ProfileReport` recomputes from the parsed `Table`, so text, markdown
  and JSON can never disagree.

## Project layout

```text
src/csv_data_profiler/
  table.py    delimiter sniffing, null tokens, header repair, ragged row handling
  columns.py  type inference, quantiles, per-column statistics, Pearson correlations
  quality.py  quality issues and the score
  report.py   ProfileReport with text, markdown and JSON rendering
  cli.py      profile / columns / correlations
data/
  orders.csv  a 24-row sample with a duplicate row, a constant column and a sparse column
tests/        66 tests across parsing, statistics, quality and the CLI
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

CI runs the suite on Python 3.10 and 3.12, checks formatting, then profiles and correlates the
sample data so the documented output stays honest.

## Limitations

- Everything is held in memory, so multi-gigabyte files are out of scope by design.
- Dates are recognised only in `YYYY-MM-DD` (optionally with a time); anything else stays a string.
- Correlation is Pearson only, so non-linear relationships are invisible. Categorical association
  is not attempted.
- Numbers are read with a decimal point; `1.234,56` style data is treated as text.
- A column that is numeric except for one typo falls back to `string` rather than reporting a
  coercion count.

## License

MIT, copyright (c) 2026 ABU BAKAR SIDDIQUE.
