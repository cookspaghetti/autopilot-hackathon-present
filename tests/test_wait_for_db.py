from utils.wait_for_db import parse_database_url, resolve_database_url


def test_resolve_database_url_expands_supabase_reference(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "${SUPABASE_DB_URL}")
    monkeypatch.delenv("SUPABASE_DB_POOLER_REGION", raising=False)
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
    )

    assert resolve_database_url() == (
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
    )


def test_resolve_database_url_uses_configured_session_pooler(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "${SUPABASE_DB_URL}")
    monkeypatch.setenv(
        "SUPABASE_DB_URL",
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres",
    )
    monkeypatch.setenv("SUPABASE_DB_POOLER_REGION", "ap-southeast-1")

    assert resolve_database_url() == (
        "postgresql://postgres.example:secret@"
        "aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"
    )


def test_parse_database_url_requires_tls_for_supabase():
    params = parse_database_url(
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
    )

    assert params["sslmode"] == "require"


def test_parse_database_url_preserves_explicit_sslmode():
    params = parse_database_url(
        "postgresql://postgres:secret@db.example.supabase.co:5432/postgres"
        "?sslmode=verify-full"
    )

    assert params["sslmode"] == "verify-full"
