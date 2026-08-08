import pytest
from sqlalchemy.engine import make_url

from app.core.database import (
    resolve_database_schema,
    resolve_database_url,
    search_path_statement,
)


def test_supabase_database_url_enforces_tls():
    result = resolve_database_url(
        "${SUPABASE_DB_URL}",
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
        "",
    )

    assert result.startswith("postgresql://postgres:secret@")
    assert "sslmode=require" in result


def test_supabase_database_url_uses_configured_session_pooler():
    result = resolve_database_url(
        "${SUPABASE_DB_URL}",
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
        "ap-southeast-1",
    )

    parsed = make_url(result)
    assert parsed.username == "postgres.example"
    assert parsed.host == "aws-0-ap-southeast-1.pooler.supabase.com"
    assert "sslmode=require" in result


def test_supabase_database_defaults_to_command_center_schema():
    database_url = (
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
    )

    assert resolve_database_schema(database_url, "") == "command_center"
    assert (
        search_path_statement("command_center")
        == 'SET search_path TO "command_center", public'
    )


def test_sqlite_ignores_postgres_schema_configuration():
    assert resolve_database_schema("sqlite:///test.db", "command_center") is None


def test_invalid_schema_name_is_rejected():
    with pytest.raises(ValueError, match="valid SQL identifier"):
        resolve_database_schema(
            "postgresql://postgres:secret@localhost:5432/postgres",
            "command_center; drop schema public",
        )
