#!/usr/bin/env python3
"""
run_queries.py - execute queries.sql and print each result set.

Provided so the repository runs without the sqlite3 command-line tool
installed, which is the common case on Windows.

    python run_queries.py                          # runs ./queries.sql
    python run_queries.py queries.sql              # or name the file
    python run_queries.py --query 8                # only the "Q8" statement
    python run_queries.py --db other.db --sql f.sql

Splitting on ';' is safe here because no query contains a semicolon inside a
string literal. If you add one, quote it or use the sqlite3 CLI.
"""

from __future__ import annotations

import argparse
import sqlite3
import sqlite3 as _sqlite3
import sys
from pathlib import Path

PRAGMA_PREFIXES = ("PRAGMA", "BEGIN", "COMMIT", "CREATE", "INSERT", "DROP", "ALTER")


def split_statements(sql: str) -> list[str]:
    """Split on ';' outside of '--' line comments and quoted literals."""
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


def title_for(statement: str) -> str:
    """Pull the 'Qn ...' label out of the preceding comment block."""
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped.startswith("-- Q"):
            return stripped.lstrip("- ").strip()
    head = " ".join(statement.split())[:70]
    return head


def sql_body(statement: str) -> str:
    """The statement with its leading comment and blank lines removed."""
    lines = statement.splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return "\n".join(lines[index:])
    return ""


def render(cursor: sqlite3.Cursor) -> str:
    if cursor.description is None:
        return f"({cursor.rowcount} row(s) affected)"
    headers = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    widths = [len(h) for h in headers]
    for row in rows:
        for i, value in enumerate(row):
            widths[i] = max(widths[i], len("NULL" if value is None else str(value)))

    def line(values: list[str]) -> str:
        return " | ".join(v.ljust(widths[i]) for i, v in enumerate(values))

    out = [line(headers), "-+-".join("-" * w for w in widths)]
    for row in rows:
        out.append(line(["NULL" if v is None else str(v) for v in row]))
    out.append(f"({len(rows)} row(s))")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", nargs="?", type=Path, help="sql file to run (default: queries.sql)")
    parser.add_argument("--db", type=Path, default=Path("lending_club.db"))
    parser.add_argument("--sql", type=Path, help="same as the positional path")
    parser.add_argument("--query", type=int, help="run only this query number, e.g. 8")
    args = parser.parse_args()

    sql_path = args.path or args.sql or Path("queries.sql")

    if not args.db.exists():
        raise SystemExit(f"database not found: {args.db} (run build_db.py first)")
    if not sql_path.exists():
        raise SystemExit(f"sql file not found: {sql_path}")

    conn = sqlite3.connect(args.db)
    matched = 0
    try:
        # utf-8-sig, not utf-8: Windows editors routinely prefix the file with a
        # BOM, which would otherwise make the first statement look like a comment.
        for statement in split_statements(sql_path.read_text(encoding="utf-8-sig")):
            label = title_for(statement)
            body = sql_body(statement)
            if not body.upper().startswith(("SELECT", "WITH")):
                continue
            if args.query is not None:
                digits = "".join(ch for ch in label[:4] if ch.isdigit())
                # No label means it cannot be the query you asked for. Running it
                # anyway is how "--query 8" ends up printing Q1.
                if not digits or int(digits) != args.query:
                    continue
            matched += 1
            print()
            print("=" * 78)
            print(label)
            print("=" * 78)
            print(render(conn.execute(body)))
    finally:
        conn.close()
    if args.query is not None and matched == 0:
        print(f"no statement labelled 'Q{args.query}' in {sql_path}"
              " - a comment line starting '-- Q8' above the statement is what"
              " identifies it", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
