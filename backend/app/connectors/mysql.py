from sqlalchemy import create_engine, text

from app.connectors.base import DBConnector, SQLAlchemyConnectorMixin


class MySQLConnector(SQLAlchemyConnectorMixin, DBConnector):
    _system_schemas = {"information_schema", "performance_schema", "mysql", "sys"}

    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        url = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
        self._engine = create_engine(url, pool_pre_ping=True)

    def check_read_only(self) -> bool:
        # MySQL grantee is formatted like "'user'@'host'". Checked across
        # global (user_privileges), schema and table grants for defense in
        # depth - a user could be read-only globally but writable on one db.
        query = text(
            """
            SELECT COUNT(*) FROM (
                SELECT privilege_type FROM information_schema.user_privileges
                WHERE grantee LIKE CONCAT("'", SUBSTRING_INDEX(CURRENT_USER(), '@', 1), "'@%")
                  AND privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE','CREATE','DROP','ALTER')
                UNION ALL
                SELECT privilege_type FROM information_schema.schema_privileges
                WHERE grantee LIKE CONCAT("'", SUBSTRING_INDEX(CURRENT_USER(), '@', 1), "'@%")
                  AND privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE','CREATE','DROP','ALTER')
            ) AS write_grants
            """
        )
        with self._engine.connect() as conn:
            count = conn.execute(query).scalar()
        return count == 0

    def sample_rows(self, table: str, schema: str | None, limit: int) -> list[dict]:
        from app.connectors.base import quote_identifier
        # If schema is 'main' (sqlite default artifact) or None or matches current db, omit schema or use backticks
        if schema and schema not in ("main", "None", ""):
            qualified = f"{quote_identifier(schema, dialect='mysql')}.{quote_identifier(table, dialect='mysql')}"
        else:
            qualified = quote_identifier(table, dialect="mysql")
        with self._engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {qualified} LIMIT :limit"), {"limit": limit})
            return [dict(row._mapping) for row in result]
