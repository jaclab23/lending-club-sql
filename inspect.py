#!/usr/bin/env python3
"""
inspect.py - print the database schema: tables, columns, keys, relationships.

    python inspect.py                  # tables, columns, keys, row counts
    python inspect.py --mermaid        # Mermaid ER diagram (paste into a README)
    python inspect.py --table fact_loan

Read-only. It never modifies the database.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def row_count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def columns(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    """pragma_table_info returns cid, name, type, notnull, dflt_value, pk."""
    return list(conn.execute(f'PRAGMA table_info("{table}")'))


def foreign_keys(conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    """pragma_foreign_key_list returns id, seq, table, from, to, on_update, on_delete."""
    return list(conn.execute(f'PRAGMA foreign_key_list("{table}")'))


def indexes(conn: sqlite3.Connection, table: str) -> list[str]:
    return [
        row[1]
        for row in conn.execute(f'PRAGMA index_list("{table}")')
        if not row[1].startswith("sqlite_autoindex")
    ]


def print_table(conn: sqlite3.Connection, table: str) -> None:
    count = row_count(conn, table)
    print()
    print(f"{table}  ({count:,} rows)")

    fk_by_column = {fk["from"]: fk for fk in foreign_keys(conn, table)}

    width_name = max([len(c["name"]) for c in columns(conn, table)] + [4])
    width_type = max([len(c["type"] or "") for c in columns(conn, table)] + [4])

    for col in columns(conn, table):
        bits = []
        if col["pk"]:
            bits.append("PK")
        if col["notnull"]:
            bits.append("NOT NULL")
        fk = fk_by_column.get(col["name"])
        if fk:
            bits.append(f"FK -> {fk['table']}.{fk['to']}")
        suffix = ("  " + ", ".join(bits)) if bits else ""
        name = col["name"].ljust(width_name)
        ctype = (col["type"] or "").ljust(width_type)
        print(f"  {name}  {ctype}{suffix}")

    idx = indexes(conn, table)
    if idx:
        print(f"  indexes: {', '.join(idx)}")


def print_mermaid(conn: sqlite3.Connection) -> None:
    """A Mermaid erDiagram block. GitHub renders these inside ```mermaid fences."""
    print("```mermaid")
    print("erDiagram")

    for table in tables(conn):
        print(f"    {table} {{")
        for col in columns(conn, table):
            ctype = (col["type"] or "TEXT").split("(")[0]
            key = " PK" if col["pk"] else ""
            print(f"        {ctype} {col['name']}{key}")
        print("    }")

    for table in tables(conn):
        for fk in foreign_keys(conn, table):
            # many-to-one: many fact rows point at one dimension row
            print(f'    {fk["table"]} ||--o{{ {table} : "{fk["from"]}"')

    print("```")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=Path("lending_club.db"))
    parser.add_argument("--table", help="show only this table")
    parser.add_argument("--mermaid", action="store_true", help="print a Mermaid ER diagram")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"error: no database at {args.db}", file=sys.stderr)
        print("       run build_db.py first", file=sys.stderr)
        return 2

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        if args.mermaid:
            print_mermaid(conn)
            return 0

        if args.table:
            if args.table not in tables(conn):
                print(f"error: no table {args.table}. Have: {', '.join(tables(conn))}", file=sys.stderr)
                return 2
            print_table(conn, args.table)
            return 0

        print(f"database: {args.db}")
        for table in tables(conn):
            print_table(conn, table)

        print()
        print("relationships")
        found = False
        for table in tables(conn):
            for fk in foreign_keys(conn, table):
                found = True
                print(f"  {table}.{fk['from']}  ->  {fk['table']}.{fk['to']}")
        if not found:
            print("  (none declared)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
