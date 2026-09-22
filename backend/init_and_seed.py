import os
import sys
from pathlib import Path

from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.db.models import Connection, Flow, PlanVersion, Run, FlowSchedule, AuditLog
from app.core.security import encrypt
import seed_ecommerce_db

def init_and_seed_all():
    print("🔄 Ensuring database tables are created...")
    Base.metadata.create_all(bind=engine)

    # 1. Seed ecommerce database if it does not exist
    ecom_db_path = seed_ecommerce_db.DB_PATH
    if not ecom_db_path.exists():
        print(f"🌱 Seeding sample E-Commerce database at {ecom_db_path}...")
        seed_ecommerce_db.create_and_seed_db()
    else:
        print(f"✓ E-Commerce sample database already exists at {ecom_db_path}")

    # 2. Ensure default connection in app metadata DB
    db = SessionLocal()
    try:
        conn = db.query(Connection).filter_by(name="E-Commerce Analytics").first()
        absolute_ecom_path = str(ecom_db_path.resolve())
        if not conn:
            print("🌱 Creating default 'E-Commerce Analytics' connection...")
            conn = Connection(
                name="E-Commerce Analytics",
                type="sqlite",
                host="localhost",
                port=0,
                database_name=absolute_ecom_path,
                username="analytics_user",
                encrypted_secret=encrypt(""),
                is_read_only=True,
                created_by="system_seeder",
            )
            db.add(conn)
            db.commit()
            print("✓ Default connection created!")
        else:
            # Sync path if running inside container or moved
            if conn.database_name != absolute_ecom_path:
                print(f"🔄 Updating connection database path to {absolute_ecom_path}...")
                conn.database_name = absolute_ecom_path
                db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    init_and_seed_all()
