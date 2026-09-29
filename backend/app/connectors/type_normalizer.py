import re


def normalize_data_type(raw_type: str) -> str:
    """Cleans up verbose dialect data types (like MySQL's
    'VARCHAR(50) COLLATE "utf8mb3_unicode_ci"' or 'TINYINT(1)')
    into clean, standardized, and LLM-friendly canonical types:
    STRING, INTEGER, BIGINT, FLOAT, DECIMAL, BOOLEAN, DATE, DATETIME, JSON, TEXT.
    """
    if not raw_type:
        return "STRING"

    # Strip collation clauses and extra quotes
    clean = re.sub(r'COLLATE\s+["\']?[^"\']+["\']?', "", raw_type, flags=re.IGNORECASE)
    clean = clean.strip()
    upper = clean.upper()

    # Boolean detection
    if upper in ("BOOLEAN", "BOOL") or upper.startswith("TINYINT(1)"):
        return "BOOLEAN"

    # Integers
    if "BIGINT" in upper:
        return "BIGINT"
    if any(i in upper for i in ("SMALLINT", "MEDIUMINT", "TINYINT", "INTEGER", "INT")):
        return "INTEGER"

    # Floats / Decimals
    if any(d in upper for d in ("DECIMAL", "NUMERIC")):
        # Keep precision if present e.g. DECIMAL(10,2)
        match = re.search(r"DECIMAL\s*\([^)]+\)|NUMERIC\s*\([^)]+\)", upper)
        return match.group(0) if match else "DECIMAL"
    if any(f in upper for f in ("FLOAT", "DOUBLE", "REAL")):
        return "FLOAT"

    # Date / Time
    if "DATETIME" in upper or "TIMESTAMP" in upper:
        return "DATETIME"
    if "TIME" in upper and "DATE" not in upper:
        return "TIME"
    if "DATE" in upper:
        return "DATE"

    # Text / Long strings
    if any(t in upper for t in ("LONGTEXT", "MEDIUMTEXT", "TEXT", "CLOB")):
        return "TEXT"
    if "JSON" in upper:
        return "JSON"

    # Varchar / Char: standardize to VARCHAR(N) or STRING
    match = re.search(r"(?:VARCHAR|CHAR)\s*\(\s*(\d+)\s*\)", upper)
    if match:
        return f"VARCHAR({match.group(1)})"

    return "STRING"
