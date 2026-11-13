#!/usr/bin/env python3
"""
check.py - self-checker for the SQL exercises.

Write your answer to a file, then:

    python check.py --exercise 5 --file my_answer.sql

It runs your query and the reference query against lending_club.db, compares
the result sets, and tells you pass or fail. It never prints the reference
SQL, so failing tells you *that* you are wrong and roughly where, not what to
write. Read the hint in exercises.md instead, fix it, run it again.

    python check.py --selftest        # verify every reference still runs
    python check.py --list            # list the exercises with row counts
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Reference implementations. Do not read this file while working - the point
# is to write the query yourself, and every one here is a different answer
# from the one you will produce.
#
# order_matters: whether the row ORDER is part of the acceptance criteria.
# ---------------------------------------------------------------------------
EXERCISES: dict[int, dict] = {
    1: {
        "title": "2017 defaults over 20,000",
        "order_matters": True,
        "sql": """
            SELECT loan_id, issue_date, loan_amount, fico
            FROM fact_loan
            WHERE issue_year = 2017
              AND default_flag = 1
              AND loan_amount > 20000
            ORDER BY loan_amount DESC, loan_id
            LIMIT 10
        """,
    },
    2: {
        "title": "Loans with no FICO score",
        "order_matters": False,
        "mutation_test": True,
        "sql": """
            SELECT COUNT(*) AS missing_fico
            FROM fact_loan
            WHERE fico IS NULL
        """,
    },
    3: {
        "title": "Top 10 states by loan count",
        "order_matters": True,
        "sql": """
            SELECT state_code, COUNT(*) AS loans
            FROM fact_loan
            GROUP BY state_code
            ORDER BY loans DESC, state_code
            LIMIT 10
        """,
    },
    4: {
        "title": "Overall default rate",
        "order_matters": False,
        "mutation_test": True,
        "sql": """
            SELECT ROUND(100.0 * AVG(default_flag), 2) AS default_rate_pct
            FROM fact_loan
        """,
    },
    5: {
        "title": "Default rate by home ownership",
        "order_matters": True,
        "sql": """
            SELECT home_ownership,
                   COUNT(*)                              AS loans,
                   ROUND(100.0 * AVG(default_flag), 2)   AS default_rate_pct
            FROM fact_loan
            GROUP BY home_ownership
            ORDER BY default_rate_pct DESC
        """,
    },
    6: {
        "title": "Loans and average amount by issue year",
        "order_matters": True,
        "sql": """
            SELECT issue_year,
                   COUNT(*)                   AS loans,
                   ROUND(AVG(loan_amount), 2) AS avg_loan_amount
            FROM fact_loan
            GROUP BY issue_year
            ORDER BY issue_year
        """,
    },
    7: {
        "title": "Default rate by purpose name",
        "order_matters": True,
        "sql": """
            SELECT p.purpose_name,
                   COUNT(*)                            AS loans,
                   ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct
            FROM fact_loan   AS f
            JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
            GROUP BY p.purpose_name
            ORDER BY default_rate_pct DESC
        """,
    },
    8: {
        "title": "Default rate by census region",
        "order_matters": True,
        "sql": """
            SELECT s.census_region,
                   COUNT(*)                              AS loans,
                   ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct
            FROM fact_loan AS f
            JOIN dim_state AS s ON s.state_code = f.state_code
            GROUP BY s.census_region
            ORDER BY default_rate_pct DESC
        """,
    },
    9: {
        "title": "States in the dimension with no loans",
        "order_matters": False,
        "mutation_test": True,
        "sql": """
            SELECT s.state_code
            FROM dim_state    AS s
            LEFT JOIN fact_loan AS f ON f.state_code = s.state_code
            WHERE f.loan_id IS NULL
            ORDER BY s.state_code
        """,
    },
    10: {
        "title": "Big purposes with a high default rate",
        "order_matters": True,
        "sql": """
            SELECT p.purpose_name,
                   COUNT(*)                              AS loans,
                   ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct
            FROM fact_loan   AS f
            JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
            GROUP BY p.purpose_name
            HAVING COUNT(*) > 50000
               AND AVG(f.default_flag) > 0.20
            ORDER BY default_rate_pct DESC
        """,
    },
    11: {
        "title": "Default rate by FICO band",
        "order_matters": True,
        "mutation_test": True,
        "sql": """
            SELECT CASE
                       WHEN fico IS NULL THEN 'unknown'
                       WHEN fico <  680  THEN '1. < 680'
                       WHEN fico <  700  THEN '2. 680-699'
                       WHEN fico <  720  THEN '3. 700-719'
                       WHEN fico <  740  THEN '4. 720-739'
                       WHEN fico <  760  THEN '5. 740-759'
                       ELSE                   '6. 760+'
                   END                                   AS fico_band,
                   COUNT(*)                              AS loans,
                   ROUND(100.0 * AVG(default_flag), 2)   AS default_rate_pct
            FROM fact_loan
            GROUP BY fico_band
            ORDER BY fico_band
        """,
    },
    12: {
        "title": "Purposes above the portfolio default rate",
        "order_matters": True,
        "sql": """
            SELECT p.purpose_name,
                   COUNT(*)                              AS loans,
                   ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct
            FROM fact_loan   AS f
            JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
            GROUP BY p.purpose_name
            HAVING AVG(f.default_flag) > (SELECT AVG(default_flag) FROM fact_loan)
            ORDER BY default_rate_pct DESC
        """,
    },
    13: {
        "title": "Same answer, but built with a CTE",
        "order_matters": True,
        "sql": """
            WITH purpose_rates AS (
                SELECT p.purpose_name,
                       COUNT(*)                              AS loans,
                       AVG(f.default_flag)                   AS rate
                FROM fact_loan   AS f
                JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
                GROUP BY p.purpose_name
            ),
            portfolio AS (
                SELECT AVG(default_flag) AS rate FROM fact_loan
            )
            SELECT r.purpose_name,
                   r.loans,
                   ROUND(100.0 * r.rate, 2) AS default_rate_pct
            FROM purpose_rates AS r
            CROSS JOIN portfolio AS b
            WHERE r.rate > b.rate
            ORDER BY default_rate_pct DESC
        """,
    },
    14: {
        "title": "Loans above their own purpose average",
        "order_matters": True,
        "sql": """
            WITH purpose_avg AS (
                SELECT purpose_id, AVG(loan_amount) AS avg_amount
                FROM fact_loan
                GROUP BY purpose_id
            )
            SELECT p.purpose_name,
                   COUNT(*) AS loans_above_avg
            FROM fact_loan AS f
            JOIN purpose_avg AS a ON a.purpose_id = f.purpose_id
            JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
            WHERE f.loan_amount > a.avg_amount
            GROUP BY p.purpose_name
            ORDER BY loans_above_avg DESC, p.purpose_name
        """,
    },
    15: {
        "title": "States ranked inside their own region",
        "order_matters": True,
        "sql": """
            WITH state_rates AS (
                SELECT s.census_region,
                       s.state_code,
                       COUNT(*)                              AS loans,
                       ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct
                FROM fact_loan AS f
                JOIN dim_state AS s ON s.state_code = f.state_code
                GROUP BY s.census_region, s.state_code
            )
            SELECT census_region,
                   state_code,
                   loans,
                   default_rate_pct,
                   RANK() OVER (PARTITION BY census_region ORDER BY default_rate_pct DESC) AS rank_in_region
            FROM state_rates
            ORDER BY census_region, rank_in_region, state_code
        """,
    },
    16: {
        "title": "Running total of loans by month",
        "order_matters": True,
        "sql": """
            WITH monthly AS (
                SELECT issue_date, COUNT(*) AS loans
                FROM fact_loan
                GROUP BY issue_date
            )
            SELECT issue_date,
                   loans,
                   SUM(loans) OVER (ORDER BY issue_date ROWS UNBOUNDED PRECEDING) AS cumulative_loans
            FROM monthly
            ORDER BY issue_date
        """,
    },
    17: {
        "title": "Three-month moving average default rate",
        "order_matters": True,
        "sql": """
            WITH monthly AS (
                SELECT issue_date,
                       ROUND(100.0 * AVG(default_flag), 2) AS default_rate_pct
                FROM fact_loan
                GROUP BY issue_date
            )
            SELECT issue_date,
                   default_rate_pct,
                   ROUND(AVG(default_rate_pct) OVER (
                       ORDER BY issue_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                   ), 2) AS moving_avg_3m
            FROM monthly
            ORDER BY issue_date
        """,
    },
    18: {
        "title": "Top 3 purposes by volume in each region",
        "order_matters": True,
        "sql": """
            WITH region_counts AS (
                SELECT s.census_region,
                       p.purpose_name,
                       COUNT(*) AS loans
                FROM fact_loan   AS f
                JOIN dim_state   AS s ON s.state_code = f.state_code
                JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
                GROUP BY s.census_region, p.purpose_name
            ),
            ranked AS (
                SELECT census_region, purpose_name, loans,
                       ROW_NUMBER() OVER (PARTITION BY census_region ORDER BY loans DESC) AS rn
                FROM region_counts
            )
            SELECT census_region, rn AS position, purpose_name, loans
            FROM ranked
            WHERE rn <= 3
            ORDER BY census_region, rn
        """,
    },
    19: {
        "title": "Month-over-month change in default rate",
        "order_matters": True,
        "sql": """
            WITH monthly AS (
                SELECT issue_date,
                       ROUND(100.0 * AVG(default_flag), 2) AS default_rate_pct
                FROM fact_loan
                GROUP BY issue_date
            )
            SELECT issue_date,
                   default_rate_pct,
                   ROUND(default_rate_pct - LAG(default_rate_pct) OVER (ORDER BY issue_date), 2) AS change_vs_prev
            FROM monthly
            ORDER BY issue_date
        """,
    },
    20: {
        "title": "Second-highest default rate among large purposes",
        "order_matters": False,
        "sql": """
            WITH rates AS (
                SELECT p.purpose_name,
                       COUNT(*)                            AS loans,
                       ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct
                FROM fact_loan   AS f
                JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
                GROUP BY p.purpose_name
                HAVING COUNT(*) > 10000
            )
            SELECT purpose_name, loans, default_rate_pct
            FROM rates
            ORDER BY default_rate_pct DESC
            LIMIT 1 OFFSET 1
        """,
    },
}


def normalise(rows: list[tuple]) -> list[tuple]:
    """Make values comparable: floats to 2dp, NULL to a marker, rest to str."""
    out = []
    for row in rows:
        cells = []
        for value in row:
            if value is None:
                cells.append("NULL")
            elif isinstance(value, float):
                cells.append(f"{round(value, 2):.2f}")
            else:
                cells.append(str(value))
        out.append(tuple(cells))
    return out


def strip_comments(sql: str) -> str:
    """Remove -- and /* */ comments so a table name cannot hide in one."""
    out = []
    i = 0
    in_line = False
    in_block = False
    while i < len(sql):
        if in_line:
            if sql[i] == "\n":
                in_line = False
                out.append("\n")
            i += 1
            continue
        if in_block:
            if sql.startswith("*/", i):
                in_block = False
                i += 2
            else:
                i += 1
            continue
        if sql.startswith("--", i):
            in_line = True
            i += 2
            continue
        if sql.startswith("/*", i):
            in_block = True
            i += 2
            continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def mentions(sql: str, table: str) -> bool:
    """True if `table` appears as a whole word in the query."""
    import re

    return re.search(rf"\b{re.escape(table)}\b", strip_comments(sql), re.IGNORECASE) is not None


# Tables that hold data. A query has to read at least the ones the reference
# reads, otherwise it is answering from a literal instead of from the table.
# Derived from the reference so the two can never drift apart.
KNOWN_TABLES = ("fact_loan", "dim_state", "dim_purpose", "dim_emp_length")


def tables_used(sql: str) -> list[str]:
    """The known tables a query refers to, in a stable order."""
    return [name for name in KNOWN_TABLES if mentions(sql, name)]


def check_tables_read(exercise_id: int, user_sql: str) -> bool:
    """Fail a query that never touches the tables the answer has to come from.

    `SELECT 19.98` and `SELECT loan_id FROM fact_loan WHERE 1 = 0` both return
    something that looks right. They are not answers, so name the gap instead
    of scoring them as a pass.
    """
    required = tables_used(EXERCISES[exercise_id]["sql"])
    missing = [name for name in required if not mentions(user_sql, name)]
    if not missing:
        return True
    print(f"  FAIL - your query never reads: {', '.join(missing)}")
    print("    The number or row has to come out of the data, not be typed in.")
    print(f"    This exercise reads: {', '.join(required)}")
    return False


def has_top_level_order_by(sql: str) -> bool:
    """True if ORDER BY appears outside parentheses.

    `OVER (ORDER BY ...)` sorts inside a window and does not order the output,
    so it does not count. Only a statement-level ORDER BY does.
    """
    text = strip_comments(sql)
    depth = 0
    for i, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and text[i : i + 8].lower() == "order by":
            return True
    return False


def check_order_by(exercise_id: int, user_sql: str) -> bool:
    """Fail a query that leaves out an ORDER BY the exercise asks for.

    Without it SQL promises no order at all. A query can look right because
    SQLite happened to read the rows that way, and that is not the same thing
    as asking for the order - it breaks the moment the data or the plan
    changes.
    """
    if not EXERCISES[exercise_id]["order_matters"]:
        return True
    if has_top_level_order_by(user_sql):
        return True
    print("  FAIL - this exercise asks for a specific row order, and your query")
    print("    has no ORDER BY. The rows may well look sorted; SQL does not")
    print("    promise that. Ask for the order you want.")
    return False


# ---------------------------------------------------------------------------
# Mutation test.
#
# Exercise 9 expects zero rows, so any query returning nothing would pass. To
# test it properly we build a tiny throwaway database where the answer is
# NOT empty, and require the same query to find it. A query that returns
# nothing for the wrong reason returns nothing here too, and fails.
# ---------------------------------------------------------------------------
TOY_SCHEMA = """
CREATE TABLE dim_state (
    state_code TEXT PRIMARY KEY, state_name TEXT NOT NULL, census_region TEXT NOT NULL);
CREATE TABLE dim_purpose (
    purpose_id INTEGER PRIMARY KEY, purpose_name TEXT NOT NULL UNIQUE);
CREATE TABLE dim_emp_length (
    emp_length_id INTEGER PRIMARY KEY, emp_length_label TEXT NOT NULL UNIQUE,
    years_min INTEGER, years_max INTEGER);
CREATE TABLE fact_loan (
    loan_id INTEGER PRIMARY KEY, issue_date TEXT NOT NULL, issue_year INTEGER NOT NULL,
    loan_amount REAL NOT NULL, annual_income REAL, dti REAL, fico INTEGER,
    home_ownership TEXT NOT NULL, purpose_id INTEGER NOT NULL,
    state_code TEXT NOT NULL, emp_length_id INTEGER, default_flag INTEGER NOT NULL);
"""

TOY_SEED = """
INSERT INTO dim_state VALUES ('AA','State A','Northeast');
INSERT INTO dim_state VALUES ('BB','State B','South');
INSERT INTO dim_state VALUES ('CC','State C','West');
INSERT INTO dim_state VALUES ('DD','State D','Midwest');
INSERT INTO dim_purpose VALUES (1,'debt_consolidation');
INSERT INTO dim_emp_length VALUES (1,'10+ years',10,99);
-- Loans exist in AA and BB only. CC and DD are the orphaned dimension members.
INSERT INTO fact_loan VALUES (1,'2015-01-01',2015,10000,50000,10.0,700,'RENT',1,'AA',1,0);
INSERT INTO fact_loan VALUES (2,'2015-02-01',2015,12000,60000,15.0,720,'OWN',1,'AA',1,1);
INSERT INTO fact_loan VALUES (3,'2016-03-01',2016, 8000,40000, 5.0,680,'RENT',1,'BB',1,0);
-- One loan with no FICO score, so a count of them is not zero here.
INSERT INTO fact_loan VALUES (4,'2016-04-01',2016, 9000,45000, 8.0,NULL,'RENT',1,'BB',1,0);
"""


def build_toy() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(TOY_SCHEMA)
    conn.executescript(TOY_SEED)
    return conn


def mutation_test(exercise_id: int, user_sql: str) -> bool:
    """Re-run the user's query on a small dataset where the answer is non-empty."""
    toy = build_toy()
    try:
        _, expected = run(toy, EXERCISES[exercise_id]["sql"])
        if not expected:
            print("  (mutation test skipped - reference returns nothing on the toy data)")
            return True
        try:
            _, actual = run(toy, user_sql)
        except sqlite3.Error as exc:
            print(f"  FAIL - your query errors on a small alternative dataset: {exc}")
            return False
        if not EXERCISES[exercise_id]["order_matters"]:
            expected = sorted(expected, key=str)
            actual = sorted(actual, key=str)
        if actual != expected:
            print("  FAIL - your query passes on the real data but not on a small test dataset.")
            print("    That usually means it returns the right thing by accident, not by logic.")
            for line in describe_diff(expected, actual):
                print(f"    {line}")
            return False
        print(f"  also passes the mutation test ({len(expected)} row(s) on the small dataset)")
        return True
    finally:
        toy.close()



# ---------------------------------------------------------------------------
# Guard cases: queries that produce the right-looking output without doing
# the work. Each one MUST be rejected. If a guard case starts passing, the
# checker has been loosened and the exercises stop being worth anything.
# ---------------------------------------------------------------------------
GUARD_CASES: list[tuple[int, str, str]] = [
    (2, "SELECT COUNT(fico) FROM fact_loan WHERE fico IS NULL",
        "COUNT(column) skips the NULLs it is meant to count"),
    (4, "SELECT 19.98", "typed-in literal, never reads the table"),
    (4, "SELECT 19.98 FROM fact_loan LIMIT 1", "reads the table but ignores it"),
    (9, "SELECT state_code FROM dim_state WHERE 1 = 0", "empty set, wrong by accident"),
    (9, "SELECT s.state_code FROM dim_state AS s WHERE 1 = 0 -- fact_loan",
        "table name hidden in a comment"),
    (9, "SELECT s.state_code FROM dim_state AS s "
        "JOIN fact_loan AS f ON f.state_code = s.state_code WHERE 1 = 0",
        "join that can never match"),
    (11, "SELECT CASE WHEN fico < 680 THEN '1. < 680' WHEN fico < 700 THEN '2. 680-699' "
         "WHEN fico < 720 THEN '3. 700-719' WHEN fico < 740 THEN '4. 720-739' "
         "WHEN fico < 760 THEN '5. 740-759' WHEN fico >= 760 THEN '6. 760+' END AS band, "
         "COUNT(*) FROM fact_loan GROUP BY band ORDER BY band",
        "missing scores fall through to an unlabelled NULL group"),
    (6, "SELECT issue_year, COUNT(*) FROM fact_loan GROUP BY issue_year",
        "no ORDER BY, so the order is whatever the storage engine hands back"),
    (16, "SELECT issue_date, SUM(COUNT(*)) OVER (ORDER BY issue_date) FROM fact_loan "
         "GROUP BY issue_date",
        "ORDER BY only inside OVER() - it sorts the window, not the output"),
]


def guards(conn: sqlite3.Connection) -> int:
    """Prove the known cheats are still rejected. Returns the failure count."""
    print("\nguard cases (each must FAIL):")
    failures = 0
    for exercise_id, sql, why in GUARD_CASES:
        verdict = check(exercise_id, sql, conn)
        ok = not verdict
        failures += 0 if ok else 1
        state = "rejected" if ok else "ACCEPTED - hole open"
        print(f"  [{state}] exercise {exercise_id}: {why}\n")
    print(f"guard cases: {len(GUARD_CASES) - failures}/{len(GUARD_CASES)} rejected")
    return failures


def run(conn: sqlite3.Connection, sql: str) -> tuple[list[str], list[tuple]]:
    cur = conn.execute(sql)
    headers = [d[0] for d in (cur.description or [])]
    return headers, normalise(cur.fetchall())


def describe_diff(expected: list[tuple], actual: list[tuple]) -> list[str]:
    """Explain a mismatch without revealing the reference rows."""
    lines = []
    if len(expected) != len(actual):
        lines.append(f"row count: got {len(actual)}, expected {len(expected)}")
        return lines
    for i, (want, got) in enumerate(zip(expected, actual), start=1):
        if want != got:
            if len(want) != len(got):
                lines.append(f"row {i}: got {len(got)} column(s), expected {len(want)}")
            else:
                differing = [j + 1 for j, (a, b) in enumerate(zip(want, got)) if a != b]
                lines.append(
                    f"row {i}: column(s) {differing} differ - yours reads {[got[j-1] for j in differing]}"
                )
                if len(lines) >= 5:
                    lines.append("... (further differences not listed)")
                    break
            if len(lines) >= 6:
                break
    if not lines and expected != actual:
        lines.append("the rows match as a set but not in order - check your ORDER BY")
    return lines


def check(exercise_id: int, user_sql: str, conn: sqlite3.Connection) -> bool:
    spec = EXERCISES[exercise_id]
    expected_headers, expected = run(conn, spec["sql"])

    try:
        got_headers, actual = run(conn, user_sql)
    except sqlite3.Error as exc:
        print(f"  SQL ERROR: {exc}")
        return False

    if not check_tables_read(exercise_id, user_sql):
        return False

    if not check_order_by(exercise_id, user_sql):
        return False

    if len(got_headers) != len(expected_headers):
        print(f"  FAIL - you returned {len(got_headers)} column(s), "
              f"{len(expected_headers)} are expected: {expected_headers}")
        return False

    if len(actual) == len(expected) and len(actual) > 1 and not spec["order_matters"]:
        expected = sorted(expected, key=str)
        actual = sorted(actual, key=str)

    if actual != expected:
        print(f"  FAIL - exercise {exercise_id}: {spec['title']}")
        for line in describe_diff(expected, actual):
            print(f"    {line}")
        return False

    if spec.get("mutation_test"):
        print(f"  matches the real data: {len(actual)} row(s), columns {got_headers}")
        if not mutation_test(exercise_id, user_sql):
            return False
        print(f"  PASS - {len(actual)} row(s), columns {got_headers}")
        return True

    print(f"  PASS - {len(actual)} row(s), columns {got_headers}")
    return True


def selftest(conn: sqlite3.Connection) -> int:
    failures = 0
    for exercise_id in sorted(EXERCISES):
        spec = EXERCISES[exercise_id]
        try:
            headers, rows = run(conn, spec["sql"])
        except sqlite3.Error as exc:
            print(f"{exercise_id:>2}  ERROR  {spec['title']}: {exc}")
            failures += 1
            continue
        print(f"{exercise_id:>2}  {len(rows):>4} rows  {len(headers)} cols  {spec['title']}")
        # A reference that trips its own guards would make the exercise
        # impossible to pass, so check that here rather than find out later.
        if not check_tables_read(exercise_id, spec["sql"]):
            failures += 1
        if not check_order_by(exercise_id, spec["sql"]):
            failures += 1
    if failures == 0:
        failures += guards(conn)
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--exercise", type=int, help="exercise number to check")
    parser.add_argument("--file", type=Path, help="file containing your SQL answer")
    parser.add_argument("--db", type=Path, default=Path("lending_club.db"))
    parser.add_argument("--list", action="store_true", help="list exercises")
    parser.add_argument("--selftest", action="store_true", help="verify the reference queries run")
    parser.add_argument("--guards", action="store_true",
                        help="verify the known cheat queries are still rejected")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"error: no database at {args.db}", file=sys.stderr)
        print("       run: python build_db.py --source ..\\lending-club\\LC_loans_granting_model_dataset.csv --db lending_club.db", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    try:
        if args.selftest:
            return 1 if selftest(conn) else 0

        if args.guards:
            return 1 if guards(conn) else 0

        if args.list:
            for exercise_id in sorted(EXERCISES):
                spec = EXERCISES[exercise_id]
                _, rows = run(conn, spec["sql"])
                print(f"{exercise_id:>2}. {spec['title']}  ({len(rows)} row(s))")
            return 0

        if not args.exercise or not args.file:
            parser.print_help()
            return 2
        if args.exercise not in EXERCISES:
            print(f"error: no exercise {args.exercise}", file=sys.stderr)
            return 2
        if not args.file.exists():
            print(f"error: {args.file} not found", file=sys.stderr)
            return 2

        spec = EXERCISES[args.exercise]
        print(f"Exercise {args.exercise}: {spec['title']}")
        ok = check(args.exercise, args.file.read_text(encoding="utf-8-sig"), conn)
        return 0 if ok else 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
