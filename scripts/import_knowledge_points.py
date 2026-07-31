"""Import the legacy knowledge_points.sql into the UUID-v7 table.

Usage:
  .\\venv\\Scripts\\python.exe scripts/import_knowledge_points.py
  .\\venv\\Scripts\\python.exe scripts/import_knowledge_points.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from uuid_utils.compat import uuid7


DEFAULT_SQL = Path(r"E:\files\Wxwork\WXWork\1688856348324849\Cache\File\2026-07\knowledge_points.sql")
INSERT_RE = re.compile(r'INSERT INTO "public"\."knowledge_points" VALUES \((.*)\);$', re.I)


def split_sql_values(text: str) -> list[str]:
    values, buf, quoted, i = [], [], False, 0
    while i < len(text):
        ch = text[i]
        if ch == "'":
            buf.append(ch)
            if quoted and i + 1 < len(text) and text[i + 1] == "'":
                buf.append("'")
                i += 2
                continue
            quoted = not quoted
        elif ch == "," and not quoted:
            values.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
        i += 1
    values.append("".join(buf).strip())
    return values


def unquote(value: str) -> str:
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_rows(sql_path: Path) -> list[tuple[int, ...]]:
    rows = []
    with sql_path.open("r", encoding="utf-8-sig") as fh:
        for line_no, line in enumerate(fh, 1):
            match = INSERT_RE.search(line.strip())
            if not match:
                continue
            fields = split_sql_values(match.group(1))
            if len(fields) != 11:
                raise ValueError(f"line {line_no}: expected 11 fields, got {len(fields)}")
            row = [int(fields[0])]
            row.extend(unquote(v) for v in fields[1:10])
            raw_created = unquote(fields[10])
            row.append(datetime.fromisoformat(raw_created))
            rows.append(tuple(row))
    if not rows:
        raise ValueError(f"No knowledge_points INSERT records found in {sql_path}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", type=Path, default=DEFAULT_SQL)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = parse_rows(args.sql)
    print(f"Parsed {len(rows)} records from {args.sql}")
    print(f"Subjects: {sorted({r[1] for r in rows})}")
    print(f"ID range: {rows[0][0]}..{rows[-1][0]}")
    if args.dry_run:
        return

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "appdb"), user=os.getenv("DB_USER", "appuser"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='knowledge_points' AND column_name='id'")
                if cur.fetchone() != ("uuid",):
                    raise RuntimeError("public.knowledge_points.id is not uuid; refusing to import")
                cur.execute("SELECT count(*) FROM public.knowledge_points")
                existing = cur.fetchone()[0]
                if existing:
                    raise RuntimeError(f"target table is not empty ({existing} rows); refusing to duplicate data")
                sql = """INSERT INTO public.knowledge_points
                    (id, subject, stage, grade_index, grade_name, term, chapter, module, node_type, content, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
                for old_id, *data in rows:
                    cur.execute(sql, (str(uuid7()), *data))
        print(f"Imported {len(rows)} records successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
