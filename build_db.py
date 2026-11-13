#!/usr/bin/env python3
"""
build_db.py - load the Lending Club loan extract into a SQLite star schema.

Standard library only: no pandas, no SQLAlchemy, no driver to install.
Run from the repository root:

    python build_db.py --source sample/loans_sample.csv --db lending_club.db

The full dataset used for the results in README.md is 1,347,681 rows and
takes about 40 seconds to load on a laptop. The bundled sample is a random
20,000-row draw from the same file and runs in about a second.

The load is a single transaction: either every row lands or the database is
left as it was. Foreign keys are enforced during the load, so a row
referencing a purpose or state that is not in its dimension stops the run
rather than silently loading.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# US Census Bureau reference data. These are public administrative facts
# about the states, not facts derived from the loan file.
# --------------------------------------------------------------------------
STATE_REFERENCE: dict[str, tuple[str, str]] = {
    "AL": ("Alabama", "South"),
    "AK": ("Alaska", "West"),
    "AZ": ("Arizona", "West"),
    "AR": ("Arkansas", "South"),
    "CA": ("California", "West"),
    "CO": ("Colorado", "West"),
    "CT": ("Connecticut", "Northeast"),
    "DE": ("Delaware", "South"),
    "DC": ("District of Columbia", "South"),
    "FL": ("Florida", "South"),
    "GA": ("Georgia", "South"),
    "HI": ("Hawaii", "West"),
    "ID": ("Idaho", "West"),
    "IL": ("Illinois", "Midwest"),
    "IN": ("Indiana", "Midwest"),
    "IA": ("Iowa", "Midwest"),
    "KS": ("Kansas", "Midwest"),
    "KY": ("Kentucky", "South"),
    "LA": ("Louisiana", "South"),
    "ME": ("Maine", "Northeast"),
    "MD": ("Maryland", "South"),
    "MA": ("Massachusetts", "Northeast"),
    "MI": ("Michigan", "Midwest"),
    "MN": ("Minnesota", "Midwest"),
    "MS": ("Mississippi", "South"),
    "MO": ("Missouri", "Midwest"),
    "MT": ("Montana", "West"),
    "NE": ("Nebraska", "Midwest"),
    "NV": ("Nevada", "West"),
    "NH": ("New Hampshire", "Northeast"),
    "NJ": ("New Jersey", "Northeast"),
    "NM": ("New Mexico", "West"),
    "NY": ("New York", "Northeast"),
    "NC": ("North Carolina", "South"),
    "ND": ("North Dakota", "Midwest"),
    "OH": ("Ohio", "Midwest"),
    "OK": ("Oklahoma", "South"),
    "OR": ("Oregon", "West"),
    "PA": ("Pennsylvania", "Northeast"),
    "RI": ("Rhode Island", "Northeast"),
    "SC": ("South Carolina", "South"),
    "SD": ("South Dakota", "Midwest"),
    "TN": ("Tennessee", "South"),
    "TX": ("Texas", "South"),
    "UT": ("Utah", "West"),
    "VT": ("Vermont", "Northeast"),
    "VA": ("Virginia", "South"),
    "WA": ("Washington", "West"),
    "WV": ("West Virginia", "South"),
    "WI": ("Wisconsin", "Midwest"),
    "WY": ("Wyoming", "West"),
}

# Employment length as the source records it, resolved to a numeric band so
# the dimension sorts and aggregates. "NI" is not a zero - it is a missing
# answer, so both bounds stay NULL.
EMP_LENGTH_BANDS: list[tuple[str, int | None, int | None]] = [
    ("NI", None, None),
    ("< 1 year", 0, 0),
] + [(f"{n} years" if n > 1 else "1 year", n, n) for n in range(1, 10)] + [
    ("10+ years", 10, 99),
]

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def parse_issue_date(raw: str) -> tuple[str, int]:
    """'Dec-2015' -> ('2015-12-01', 2015). Raises on anything unexpected."""
    month_abbr, _, year_text = raw.strip().partition("-")
    try:
        month = MONTHS[month_abbr]
        year = int(year_text)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"unparseable issue_d {raw!r}") from exc
    return f"{year:04d}-{month:02d}-01", year


def to_float(raw: str) -> float | None:
    raw = raw.strip()
    return float(raw) if raw else None


def to_int(raw: str) -> int | None:
    raw = raw.strip()
    return int(float(raw)) if raw else None


def build(source: Path, db_path: Path, schema_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN")

        # ------------------------------------------------------------------
        # Dimensions
        # ------------------------------------------------------------------
        for idx, (label, lo, hi) in enumerate(EMP_LENGTH_BANDS, start=1):
            conn.execute(
                "INSERT INTO dim_emp_length (emp_length_id, emp_length_label, years_min, years_max) "
                "VALUES (?, ?, ?, ?)",
                (idx, label, lo, hi),
            )
        emp_length_ids = {
            row[0]: row[1]
            for row in conn.execute("SELECT emp_length_label, emp_length_id FROM dim_emp_length")
        }

        purposes: dict[str, int] = {}
        states: set[str] = set()
        loans: list[tuple] = []

        with source.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {
                "id", "issue_d", "loan_amnt", "revenue", "dti_n", "fico_n",
                "emp_length", "purpose", "home_ownership_n", "addr_state", "Default",
            }
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise SystemExit(f"source is missing columns: {sorted(missing)}")

            for row in reader:
                purpose = row["purpose"].strip()
                state = row["addr_state"].strip()
                emp_label = row["emp_length"].strip()

                if purpose not in purposes:
                    purposes[purpose] = len(purposes) + 1
                states.add(state)

                issue_date, issue_year = parse_issue_date(row["issue_d"])

                loans.append((
                    to_int(row["id"]),
                    issue_date,
                    issue_year,
                    to_float(row["loan_amnt"]),
                    to_float(row["revenue"]),
                    to_float(row["dti_n"]),
                    to_int(row["fico_n"]),
                    row["home_ownership_n"].strip(),
                    purposes[purpose],
                    state,
                    emp_length_ids.get(emp_label),
                    to_int(row["Default"]),
                ))

        unknown_states = states - STATE_REFERENCE.keys()
        if unknown_states:
            raise SystemExit(f"state codes with no reference row: {sorted(unknown_states)}")

        conn.executemany(
            "INSERT INTO dim_purpose (purpose_id, purpose_name) VALUES (?, ?)",
            [(pid, name) for name, pid in purposes.items()],
        )
        conn.executemany(
            "INSERT INTO dim_state (state_code, state_name, census_region) VALUES (?, ?, ?)",
            [(code, *STATE_REFERENCE[code]) for code in sorted(states)],
        )
        conn.executemany(
            "INSERT INTO fact_loan (loan_id, issue_date, issue_year, loan_amount, annual_income, "
            "dti, fico, home_ownership, purpose_id, state_code, emp_length_id, default_flag) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            loans,
        )

        conn.commit()

        # ------------------------------------------------------------------
        # Sanity checks - fail loudly rather than ship a wrong database
        # ------------------------------------------------------------------
        fact_rows = conn.execute("SELECT COUNT(*) FROM fact_loan").fetchone()[0]
        if fact_rows != len(loans):
            raise SystemExit(f"expected {len(loans)} rows, fact table has {fact_rows}")

        orphans = conn.execute("""
            SELECT COUNT(*) FROM fact_loan f
            WHERE NOT EXISTS (SELECT 1 FROM dim_purpose p WHERE p.purpose_id = f.purpose_id)
               OR NOT EXISTS (SELECT 1 FROM dim_state s WHERE s.state_code = f.state_code)
        """).fetchone()[0]
        if orphans:
            raise SystemExit(f"{orphans} fact rows do not resolve to a dimension")

        default_rate = conn.execute(
            "SELECT ROUND(100.0 * SUM(default_flag) / COUNT(*), 2) FROM fact_loan"
        ).fetchone()[0]

        print(f"database      : {db_path}")
        print(f"fact_loan     : {fact_rows:,} rows")
        print(f"dim_purpose   : {len(purposes)} rows")
        print(f"dim_state     : {len(states)} rows")
        print(f"dim_emp_length: {len(EMP_LENGTH_BANDS)} rows")
        print(f"default rate  : {default_rate}%")
        print("integrity     : ok (no orphan keys)")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, required=True, help="loan extract CSV")
    parser.add_argument("--db", type=Path, default=Path("lending_club.db"), help="SQLite file to create")
    parser.add_argument("--schema", type=Path, default=Path("schema.sql"), help="schema to apply")
    args = parser.parse_args()

    for path, label in ((args.source, "--source"), (args.schema, "--schema")):
        if not path.exists():
            print(f"error: {label} not found: {path}", file=sys.stderr)
            return 2

    build(args.source, args.db, args.schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
