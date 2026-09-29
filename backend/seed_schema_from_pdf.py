#!/usr/bin/env python3
"""Script to parse test.pdf schema dump, clean and normalize data types,
and seed the cached schema into connection(s) in SQLite metadata DB.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.connectors.type_normalizer import normalize_data_type
from app.db.base import Base
from app.db.models.connection import Connection
from app.db.session import SessionLocal, engine
import app.db.models


def extract_schema_from_pdf(pdf_path: str = "/home/amit-sharma/Downloads/test.pdf") -> list[dict]:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found at {pdf_path}")

    # Use pdftotext to extract raw text
    txt_out = "/tmp/test_pdf_extracted_schema.txt"
    subprocess.run(["pdftotext", pdf_path, txt_out], check=True)

    with open(txt_out, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    start_idx = text.find('{"connected":true')
    end_idx = text.rfind('}]}') + 3
    if start_idx == -1 or end_idx <= 2:
        raise ValueError("Could not locate JSON payload in PDF text.")

    json_portion = text[start_idx:end_idx].replace('\x0c', '')
    clean_lines = [l.strip() for l in json_portion.split('\n') if l.strip()]
    rejoined = ''.join(clean_lines)

    obj = json.loads(rejoined)
    tables = obj.get("tables", [])

    normalized_tables = []
    for t in tables:
        cols = []
        for c in t.get("columns", []):
            cols.append({
                "name": c["name"],
                "data_type": normalize_data_type(c["data_type"]),
                "nullable": c.get("nullable", True),
            })
        normalized_tables.append({
            "name": t["name"],
            "schema": t.get("schema", "public"),
            "columns": cols,
        })

    return normalized_tables


def seed_schema(connection_id: str | None = None):
    # Ensure tables exist with latest columns
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        from sqlalchemy import text
        try:
            conn.execute(text("ALTER TABLE connections ADD COLUMN cached_schema_json TEXT"))
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE connections ADD COLUMN schema_updated_at TIMESTAMP"))
            conn.commit()
        except Exception:
            pass

    tables = extract_schema_from_pdf()
    cache_json = json.dumps({"tables": tables})

    with SessionLocal() as db:
        if connection_id:
            conns = [db.get(Connection, connection_id)]
            if not conns[0]:
                print(f"Connection {connection_id} not found.")
                return
        else:
            # Seed to all mysql connections or specified ID
            conns = db.query(Connection).filter(Connection.type == "mysql").all()
            if not conns:
                # Fallback to the ID from pdf curl: 376089f0-73d1-4092-a2fb-5508ca5620f1
                conns = [db.get(Connection, "376089f0-73d1-4092-a2fb-5508ca5620f1")]
                conns = [c for c in conns if c]

        if not conns:
            print("No matching connection found in DB to seed. Available connections:")
            for c in db.query(Connection).all():
                print(f"  - ID: {c.id} | Name: {c.name} | Type: {c.type}")
            return

        for conn in conns:
            conn.cached_schema_json = cache_json
            conn.schema_updated_at = datetime.now(timezone.utc)
            print(f"Seeded {len(tables)} tables into Connection: '{conn.name}' ({conn.id})")

        db.commit()
        print("Schema successfully cached!")


if __name__ == "__main__":
    target_id = sys.argv[1] if len(sys.argv) > 1 else None
    seed_schema(target_id)
