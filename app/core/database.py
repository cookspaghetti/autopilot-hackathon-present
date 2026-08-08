import os
import re

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

_SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SUPABASE_DIRECT_HOST = re.compile(r"^db\.([a-z0-9]+)\.supabase\.co$")


def _is_supabase_postgres_host(host: str) -> bool:
    return host.endswith(".supabase.co") or host.endswith(".pooler.supabase.com")


def resolve_database_url(
    database_url: str | None = None,
    supabase_db_url: str | None = None,
    supabase_pooler_region: str | None = None,
) -> str:
    """Resolve the control-plane database URL without copying credentials."""

    configured = (
        database_url
        if database_url is not None
        else os.getenv("DATABASE_URL", "")
    ).strip()
    supabase = (
        supabase_db_url
        if supabase_db_url is not None
        else os.getenv("SUPABASE_DB_URL", "")
    ).strip()
    if configured in {"${SUPABASE_DB_URL}", "$SUPABASE_DB_URL"}:
        configured = supabase
    if not configured:
        configured = supabase
    if not configured:
        raise ValueError(
            "DATABASE_URL or SUPABASE_DB_URL environment variable is not set"
        )

    url = make_url(configured)
    host = (url.host or "").lower()
    pooler_region = (
        supabase_pooler_region
        if supabase_pooler_region is not None
        else os.getenv("SUPABASE_DB_POOLER_REGION", "")
    ).strip()
    direct_match = _SUPABASE_DIRECT_HOST.fullmatch(host)
    if url.get_backend_name() == "postgresql" and direct_match and pooler_region:
        project_ref = direct_match.group(1)
        url = url.set(
            host=f"aws-0-{pooler_region}.pooler.supabase.com",
            username=f"{url.username}.{project_ref}",
            port=5432,
        )
        host = (url.host or "").lower()

    if url.get_backend_name() == "postgresql" and _is_supabase_postgres_host(host):
        if "sslmode" not in url.query:
            url = url.update_query_dict({"sslmode": "require"})
        return url.render_as_string(hide_password=False)
    return configured


def resolve_database_schema(
    database_url: str,
    configured_schema: str | None = None,
) -> str | None:
    """Return the PostgreSQL control schema; SQLite remains schema-free."""

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        return None

    configured = (
        configured_schema
        if configured_schema is not None
        else os.getenv("COMMAND_CENTER_DB_SCHEMA", "")
    ).strip()
    if not configured and _is_supabase_postgres_host((url.host or "").lower()):
        configured = "command_center"
    if not configured:
        return None
    if not _SCHEMA_NAME.fullmatch(configured):
        raise ValueError("COMMAND_CENTER_DB_SCHEMA must be a valid SQL identifier")
    return configured


def search_path_statement(schema: str) -> str:
    if not _SCHEMA_NAME.fullmatch(schema):
        raise ValueError("Database schema must be a valid SQL identifier")
    return f'SET search_path TO "{schema}", public'


DATABASE_URL = resolve_database_url()
COMMAND_CENTER_DB_SCHEMA = resolve_database_schema(DATABASE_URL)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

if COMMAND_CENTER_DB_SCHEMA:

    @event.listens_for(engine, "connect")
    def _set_command_center_search_path(dbapi_connection, _connection_record):
        previous_autocommit = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(search_path_statement(COMMAND_CENTER_DB_SCHEMA))
        finally:
            cursor.close()
            dbapi_connection.autocommit = previous_autocommit


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
