#!/usr/bin/env python3
"""
check_queries.py - shape checker for the eight questions in queries.sql.

    python check_queries.py               # all eight
    python check_queries.py --query 4     # one of them
    python check_queries.py --list        # what each question has to return

It does not hold a reference answer and it will not tell you how to write one.
It checks the properties a correct answer must have: the column count, the row
count, the grain, the ordering, and the consistency of the numbers with each
other. Those are strong enough to catch almost every wrong answer, and they
leave the query itself entirely yours.

A question is found by its `-- Q1` style comment, so put one above each
statement in queries.sql.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

TOTAL_LOANS = 1_347_681
PORTFOLIO_RATE = 19.9786893189  # 100 * 269249 / 1347681
TOL = 0.011  # tolerance on a rounded percentage


def num(value) -> float | None:
    return None if value is None else float(value)


# ---------------------------------------------------------------------------
# One validator per question. Each receives the result rows and returns a list
# of complaints. An empty list means it passed. Column positions follow the
# shape declared in QUESTIONS.
# ---------------------------------------------------------------------------


def v_q1(rows: list[tuple]) -> list[str]:
    out = []
    rates = [num(r[4]) for r in rows]
    small = [r for r in rows if num(r[2]) < 10_000]
    if small:
        out.append(f"{len(small)} row(s) have fewer than 10,000 loans - the floor is missing")
    if rates != sorted(rates, reverse=True):
        out.append("not ordered by default_rate_pct descending")
    # The volume column has to be millions, not raw dollars: the 17 surviving
    # combinations carry 18,408 of the book's 19,418 million.
    millions = sum(num(r[3]) for r in rows)
    if not 18_400 < millions < 18_420:
        out.append(f"total_loan_millions sums to {millions:,.1f} - if this is around"
                   " 18,408,200 the column is raw dollars, not millions")
    return out


def v_q2(rows: list[tuple]) -> list[str]:
    out = []
    total = sum(num(r[1]) for r in rows)
    if total != TOTAL_LOANS:
        out.append(f"loan counts sum to {total:,.0f}, not {TOTAL_LOANS:,}"
                   " - a band is being dropped or double counted")
    labels = [str(r[0]) for r in rows]
    ni = [r for r in rows if str(r[0]).strip().upper() == "NI"]
    if not ni:
        out.append("no NI row - the not-stated group is missing")
    elif num(ni[0][1]) != 78_188:
        out.append(f"the NI row holds {num(ni[0][1]):,.0f} loans, expected 78,188")
    pcts = [num(r[2]) for r in rows]
    if abs(sum(pcts) - 100.0) > 0.5:
        out.append(f"pct_of_portfolio sums to {sum(pcts):.2f}, not ~100")
    loans = [num(r[1]) for r in rows]
    if loans != sorted(loans, reverse=True):
        out.append("not ordered by loans descending")
    return out


def v_q3(rows: list[tuple]) -> list[str]:
    out = []
    for r in rows:
        rate, pts = num(r[2]), num(r[3])
        if rate is not None and rate <= PORTFOLIO_RATE:
            out.append(f"{r[0]} sits at {rate}%, at or below the portfolio rate")
        if rate is not None and pts is not None and abs(rate - PORTFOLIO_RATE - pts) > TOL:
            out.append(f"{r[0]}: pts_vs_portfolio {pts} is not rate minus the portfolio rate")
        if num(r[1]) is None or num(r[1]) < 5_000:
            out.append(f"{r[0]} has fewer than 5,000 loans - the floor is missing")
    rates = [num(r[2]) for r in rows]
    if rates != sorted(rates, reverse=True):
        out.append("not ordered by default_rate_pct descending")
    return out


def v_q4(rows: list[tuple]) -> list[str]:
    out = []
    states = {str(r[1]) for r in rows}
    if len(states) != len(rows):
        out.append("a state appears more than once - the grain is not one row per state")
    regions: dict[str, list[tuple]] = {}
    for r in rows:
        regions.setdefault(str(r[0]), []).append(r)
    if len(regions) != 4:
        out.append(f"{len(regions)} region(s) present, expected 4"
                   " - the volume floor is dropping a whole region")
    for region, group in regions.items():
        ranks = [int(r[4]) for r in group]
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            out.append(f"{region}: ranks are {sorted(ranks)[:6]}..., not 1..{len(ranks)}")
            continue
        # Rank has to mean something: walking up the ranks, the default rate may
        # never go up. This catches a rank computed on the wrong key.
        rates = [num(r[3]) for r in group]
        for i in range(1, len(rates)):
            if rates[i] > rates[i - 1] + TOL:
                out.append(f"{region}: {group[i][1]} outranks {group[i - 1][1]}"
                           " but defaults less - the ranking key is wrong")
                break
    key = [(str(r[0]), int(r[4])) for r in rows]
    if key != sorted(key):
        out.append("not ordered by census_region then rank_in_region")
    return out


def v_q5(rows: list[tuple]) -> list[str]:
    out = []
    cum = [num(r[3]) for r in rows]
    if any(cum[i] < cum[i - 1] for i in range(1, len(cum))):
        out.append("cumulative_loans decreases somewhere - the running total is wrong")
    if cum and cum[-1] != TOTAL_LOANS:
        out.append(f"final cumulative total is {cum[-1]:,.0f}, not {TOTAL_LOANS:,}")
    pcts = [num(r[4]) for r in rows]
    if any(p is None for p in pcts):
        out.append("cumulative_pct has NULLs")
    elif abs(pcts[-1] - 100.0) > 0.2:
        out.append(f"final cumulative_pct is {pcts[-1]}, not 100")
    return out


def v_q6(rows: list[tuple]) -> list[str]:
    out = []
    if rows and rows[0][4] is not None:
        out.append("the first month's change is not NULL - there is no previous month")
    if len(rows) > 1 and rows[1][4] is None:
        out.append("only the first month should have a NULL change")
    dates = [str(r[0]) for r in rows]
    if dates != sorted(dates):
        out.append("not ordered by issue_date")
    if any(num(r[3]) is None for r in rows):
        out.append("moving_avg_3m has NULLs")
    return out


def v_q7(rows: list[tuple]) -> list[str]:
    out = []
    regions: dict[str, list[tuple]] = {}
    for r in rows:
        regions.setdefault(str(r[0]), []).append(r)
    for region, group in regions.items():
        if len(group) != 3:
            out.append(f"{region} has {len(group)} row(s), expected 3")
        share = sum(num(r[4]) for r in group)
        # Three of fourteen purposes is most of a region, never the whole of it
        # and never a quarter of it. A national denominator lands near 20-25.
        if not 50.0 < share <= 100.0:
            out.append(f"{region}: pct_of_region sums to {share:.2f}, which looks like"
                       " a national denominator rather than a regional one")
    key = [(str(r[0]), int(r[1])) for r in rows]
    if key != sorted(key):
        out.append("not ordered by census_region then position")
    return out


def v_q8(rows: list[tuple]) -> list[str]:
    out = []
    total = sum(num(r[1]) for r in rows)
    if total != TOTAL_LOANS:
        out.append(f"band counts sum to {total:,.0f}, not {TOTAL_LOANS:,}"
                   " - this is the cross-check against the dashboard")
    bands = [str(r[0]) for r in rows]
    if bands != sorted(bands):
        out.append("not ordered by fico_band")
    for r in rows:
        if any(num(v) is None for v in r[3:6]):
            out.append(f"{r[0]}: one of the three tenure rates is NULL rather than a rate")
            break
    return out


QUESTIONS: dict[int, dict] = {
    1: {"title": "Region x purpose risk", "cols": 5, "rows": 17, "check": v_q1,
        "columns": "census_region, purpose_name, loans, total_loan_millions, default_rate_pct"},
    2: {"title": "Missing employment answers", "cols": 4, "rows": 12, "check": v_q2,
        "columns": "emp_length, loans, pct_of_portfolio, default_rate_pct"},
    3: {"title": "Purposes above the portfolio rate", "cols": 4, "rows": 6, "check": v_q3,
        "columns": "purpose_name, loans, default_rate_pct, pts_vs_portfolio"},
    4: {"title": "States ranked within region", "cols": 5, "rows": 50, "check": v_q4,
        "columns": "census_region, state_code, loans, default_rate_pct, rank_in_region"},
    5: {"title": "Volume build", "cols": 5, "rows": 139, "check": v_q5,
        "columns": "issue_date, loans, loan_millions, cumulative_loans, cumulative_pct"},
    6: {"title": "Trend under noise", "cols": 5, "rows": 139, "check": v_q6,
        "columns": "issue_date, loans, default_rate_pct, moving_avg_3m, change_vs_prev_month"},
    7: {"title": "Top three purposes per region", "cols": 5, "rows": 12, "check": v_q7,
        "columns": "census_region, position, purpose_name, loans, pct_of_region"},
    8: {"title": "FICO band x home ownership", "cols": 6, "rows": 6, "check": v_q8,
        "columns": "fico_band, loans, default_rate_pct, rate_mortgage, rate_rent, rate_own"},
}


def split_statements(sql: str) -> list[str]:
    """Split on ';' outside line comments and quoted literals."""
    statements: list[str] = []
    buf: list[str] = []
    in_line_comment = False
    quote: str | None = None
    for char in sql:
        if in_line_comment:
            buf.append(char)
            if char == "\n":
                in_line_comment = False
            continue
        if quote:
            buf.append(char)
            if char == quote:
                quote = None
            continue
        if char == "'":
            quote = char
            buf.append(char)
            continue
        if char == "-" and buf and buf[-1] == "-":
            in_line_comment = True
            buf.append(char)
            continue
        if char == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
            continue
        buf.append(char)
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def label_of(statement: str) -> str | None:
    """The number in a leading `-- Qn ...` comment, if there is one.

    Comment banners above the label are skipped; the first `-- Qn` wins. Stops
    at the first line that is real SQL.
    """
    for line in statement.splitlines():
        stripped = line.strip().lstrip("\ufeff")
        if not stripped:
            continue
        if not stripped.startswith("--"):
            return None
        text = stripped.lstrip("-").strip()
        if text[:1].upper() == "Q":
            digits = ""
            for char in text[1:]:
                if char.isdigit():
                    digits += char
                else:
                    break
            if digits:
                return digits
    return None


def body_of(statement: str) -> str:
    lines = statement.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return "\n".join(lines[index:])
    return ""


def declared_labels(sql: str) -> dict[int, int]:
    """Every `-- Qn` written in the file, with the line it sits on.

    A label can be written and still not be a statement label, which is the
    case when the previous statement is missing its ';' terminator.
    """
    out: dict[int, int] = {}
    for number, line in enumerate(sql.splitlines(), 1):
        stripped = line.strip()
        if not stripped.startswith("--"):
            continue
        text = stripped.lstrip("-").strip()
        if text[:1].upper() != "Q":
            continue
        digits = ""
        for char in text[1:]:
            if char.isdigit():
                digits += char
            else:
                break
        if digits:
            out.setdefault(int(digits), number)
    return out


def load(sql: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for statement in split_statements(sql):
        label = label_of(statement)
        if label is not None:
            found.setdefault(int(label), body_of(statement))
    return found


def preview(rows: list[tuple], limit: int = 3) -> str:
    """A few rows, so a number that cannot be right is visible at a glance."""
    out = []
    for row in rows[:limit]:
        out.append("    " + " | ".join("NULL" if v is None else str(v) for v in row))
    if len(rows) > limit:
        out.append(f"    ... {len(rows) - limit} more row(s)")
    return "\n".join(out)


def check_one(number: int, sql: str | None, conn: sqlite3.Connection,
              declared: dict[int, int] | None = None) -> bool:
    spec = QUESTIONS[number]
    print(f"\nQ{number} - {spec['title']}")
    print(f"  expects {spec['cols']} columns: {spec['columns']}")
    if sql is None:
        line = (declared or {}).get(number)
        if line is not None:
            print(f"  MISSING - the '-- Q{number}' on line {line} is not a statement of"
                  " its own. Every statement ends with ';', and the one before this"
                  " label has not ended, so both are read as one statement.")
        else:
            print(f"  MISSING - no statement labelled '-- Q{number}' in queries.sql")
        return False
    try:
        cur = conn.execute(sql)
    except sqlite3.Error as exc:
        print(f"  SQL ERROR: {exc}")
        return False
    heads = [d[0] for d in (cur.description or [])]
    rows = cur.fetchall()
    print(preview(rows))

    problems: list[str] = []
    if len(heads) != spec["cols"]:
        problems.append(f"{len(heads)} column(s), expected {spec['cols']}")
    if len(rows) != spec["rows"]:
        problems.append(f"{len(rows)} row(s), expected {spec['rows']}")
    if not problems:
        problems.extend(spec["check"](rows))

    if problems:
        for line in problems:
            print(f"  FAIL - {line}")
        return False
    print(f"  PASS - {len(rows)} row(s), {len(heads)} column(s)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", type=Path, default=Path("queries.sql"))
    parser.add_argument("--db", type=Path, default=Path("lending_club.db"))
    parser.add_argument("--query", type=int, help="check only this question")
    parser.add_argument("--list", action="store_true", help="print the expected shapes")
    args = parser.parse_args()

    if args.list:
        for number in sorted(QUESTIONS):
            spec = QUESTIONS[number]
            print(f"Q{number}. {spec['title']}")
            print(f"    {spec['rows']} rows, {spec['cols']} columns")
            print(f"    {spec['columns']}\n")
        return 0

    if not args.db.exists():
        print(f"error: no database at {args.db}", file=sys.stderr)
        return 2
    if not args.path.exists():
        print(f"error: {args.path} not found - write the eight questions first", file=sys.stderr)
        return 2

    found = load(args.path.read_text(encoding="utf-8-sig"))
    raw = args.path.read_text(encoding="utf-8-sig")
    declared = declared_labels(raw)
    statements = split_statements(raw)
    if not found and statements:
        print(f"note: {len(statements)} statement(s) in {args.path} but none carries a"
              " '-- Qn' label. A comment line starting '-- Q1', '-- Q2' and so on above"
              " each statement is what identifies it.", file=sys.stderr)
    numbers = [args.query] if args.query else sorted(QUESTIONS)
    conn = sqlite3.connect(args.db)
    try:
        results = [check_one(n, found.get(n), conn, declared) for n in numbers]
    finally:
        conn.close()

    passed = sum(results)
    print(f"\n{passed}/{len(results)} question(s) pass")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
