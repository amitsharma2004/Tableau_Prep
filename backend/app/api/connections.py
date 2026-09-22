from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.api.deps import get_current_actor, get_db
from app.connectors.factory import build_connector
from app.core.errors import DomainError
from app.core.security import decrypt
from app.db.models.connection import Connection
from app.schemas.connection import ConnectionCreate, ConnectionRead, ConnectionTestResult
from app.services import connection_service

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("", response_model=ConnectionRead, status_code=201)
def create_connection(
    payload: ConnectionCreate,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    try:
        conn = connection_service.create_connection(db, payload, actor)
        db.commit()
        db.refresh(conn)
        return conn
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[ConnectionRead])
def list_connections(db: Session = Depends(get_db)):
    return connection_service.list_connections(db)


@router.post("/{connection_id}/test", response_model=ConnectionTestResult)
def test_connection(
    connection_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    conn = db.get(Connection, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        result = connection_service.test_and_introspect(db, conn, actor)
        db.commit()
        return result
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{connection_id}/schema", response_model=ConnectionTestResult)
def get_connection_schema(
    connection_id: str,
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    conn = db.get(Connection, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        return connection_service.test_and_introspect(db, conn, actor)
    except DomainError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{connection_id}/sample")
def sample_table_data(
    connection_id: str,
    table: str,
    schema: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    conn = db.get(Connection, connection_id)
    if conn is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    try:
        secret = decrypt(conn.encrypted_secret)
        connector = build_connector(
            conn.type, conn.host, conn.port, conn.database_name, conn.username, secret
        )
        rows = connector.sample_rows(table, schema, limit)
        return {"rows": rows}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/upload", response_model=ConnectionRead, status_code=201)
async def upload_file_as_connection(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    table_name: str | None = Form(None),
    db: Session = Depends(get_db),
    actor: str = Depends(get_current_actor),
):
    import io
    import os
    import re
    import sqlite3
    import pandas as pd

    filename = file.filename or "uploaded_data"
    raw_name = name or os.path.splitext(filename)[0]
    clean_table = re.sub(r"\W+", "_", (table_name or raw_name)).strip("_").lower() or "dataset"

    # Read uploaded bytes
    content = await file.read()
    try:
        if filename.lower().endswith(".csv") or filename.lower().endswith(".txt"):
            df = pd.read_csv(io.BytesIO(content))
        elif filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls"):
            df = pd.read_excel(io.BytesIO(content))
        elif filename.lower().endswith(".json"):
            df = pd.read_json(io.BytesIO(content))
        else:
            # Try CSV fallback
            try:
                df = pd.read_csv(io.BytesIO(content))
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file format. Please upload CSV, Excel (.xlsx/.xls), or JSON.",
                )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}") from exc

    # Sanitize column names for SQLite
    df.columns = [re.sub(r"\W+", "_", str(c)).strip("_").lower() or f"col_{i}" for i, c in enumerate(df.columns)]

    # Store into SQLite database file
    upload_dir = os.path.abspath(os.path.join(os.getcwd(), "uploaded_files"))
    os.makedirs(upload_dir, exist_ok=True)
    db_path = os.path.join(upload_dir, f"{raw_name}_{actor.split('@')[0]}.db")

    with sqlite3.connect(db_path) as s_conn:
        df.to_sql(clean_table, s_conn, if_exists="replace", index=False)

    # Register as SQLite connection
    create_payload = ConnectionCreate(
        name=raw_name,
        type="sqlite",
        host="localhost",
        port=0,
        database_name=db_path,
        username="local",
        secret="local",
    )

    try:
        conn = connection_service.create_connection(db, create_payload, actor)
        db.commit()
        db.refresh(conn)
        return conn
    except DomainError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
