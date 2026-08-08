#!/usr/bin/env python3
"""
Database readiness checker script.
Waits for PostgreSQL to be ready before proceeding with migrations.
Supports both traditional connection params and DATABASE_URL format (including Cloud SQL Unix sockets).
"""

import logging
import os
import sys
import time
from urllib.parse import parse_qs, urlparse, urlunparse

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_database_url(url):
    """
    Parse DATABASE_URL into connection parameters.
    Supports both TCP and Unix socket (Cloud SQL) formats.

    Examples:
        - postgresql://user:pass@host:5432/dbname
        - postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance
    """
    parsed = urlparse(url)

    params = {
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
    }

    # Check for Unix socket in query params (Cloud SQL format)
    query_params = parse_qs(parsed.query)
    if "host" in query_params:
        # Unix socket path
        params["host"] = query_params["host"][0]
    elif parsed.hostname:
        # TCP connection
        params["host"] = parsed.hostname
        params["port"] = str(parsed.port or 5432)

    if "sslmode" in query_params:
        params["sslmode"] = query_params["sslmode"][0]
    elif (parsed.hostname or "").lower().endswith(".supabase.co"):
        params["sslmode"] = "require"

    return params


def resolve_database_url():
    """Resolve a database URL, including env-file references to Supabase."""
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if database_url in {"", "${SUPABASE_DB_URL}"}:
        database_url = (os.getenv("SUPABASE_DB_URL") or "").strip()
    pooler_region = (os.getenv("SUPABASE_DB_POOLER_REGION") or "").strip()
    parsed = urlparse(database_url)
    host_parts = (parsed.hostname or "").lower().split(".")
    if (
        pooler_region
        and len(host_parts) == 4
        and host_parts[0] == "db"
        and host_parts[2:] == ["supabase", "co"]
    ):
        project_ref = host_parts[1]
        raw_userinfo = parsed.netloc.rsplit("@", 1)[0]
        raw_username, separator, raw_password = raw_userinfo.partition(":")
        credentials = f"{raw_username}.{project_ref}"
        if separator:
            credentials += f":{raw_password}"
        netloc = (
            f"{credentials}"
            f"@aws-0-{pooler_region}.pooler.supabase.com:5432"
        )
        database_url = urlunparse(parsed._replace(netloc=netloc))
    return database_url or None


def check_db_connection():
    """
    Check if PostgreSQL is ready to accept connections.
    Returns True if connection is successful, False otherwise.
    """
    try:
        import psycopg2
        from psycopg2 import OperationalError

        # Check for DATABASE_URL first (Cloud Run / production)
        database_url = resolve_database_url()

        if database_url:
            # Parse the DATABASE_URL
            conn_params = parse_database_url(database_url)
            logger.debug(f"Using DATABASE_URL, host: {conn_params.get('host', 'N/A')}")
        else:
            # Fall back to individual environment variables (local dev)
            conn_params = {
                "host": os.getenv("POSTGRES_HOST", "postgres"),
                "port": os.getenv("POSTGRES_PORT", "5432"),
                "database": os.getenv("POSTGRES_DB", "app_db"),
                "user": os.getenv("POSTGRES_USER", "user"),
                "password": os.getenv("POSTGRES_PASSWORD", "password"),
            }

        # Add connection timeout
        conn_params["connect_timeout"] = 5

        # Remove None values
        conn_params = {k: v for k, v in conn_params.items() if v is not None}

        # Attempt to connect
        conn = psycopg2.connect(**conn_params)
        conn.close()
        logger.info("✅ Database connection successful!")
        return True

    except OperationalError as e:
        logger.debug(f"Database not ready: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking database: {e}")
        return False


def wait_for_database(max_retries=30, delay=2):
    """
    Wait for PostgreSQL to be ready with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
    """
    logger.info("🔍 Waiting for PostgreSQL to be ready...")

    for attempt in range(max_retries):
        if check_db_connection():
            logger.info(f"🎉 PostgreSQL is ready! (attempt {attempt + 1})")
            return True

        if attempt < max_retries - 1:
            wait_time = min(delay * (1.5**attempt), 30)  # Exponential backoff, max 30s
            logger.info(
                f"⏳ PostgreSQL not ready yet. Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(wait_time)

    logger.error(f"❌ Failed to connect to PostgreSQL after {max_retries} attempts")
    return False


if __name__ == "__main__":
    # Check if we should skip the wait (for testing purposes)
    if os.getenv("SKIP_DB_WAIT", "").lower() == "true":
        logger.info("⏭️  Skipping database wait (SKIP_DB_WAIT=true)")
        sys.exit(0)

    # Wait for database
    if wait_for_database():
        logger.info("✅ Database is ready, proceeding with application startup...")
        sys.exit(0)
    else:
        logger.error("❌ Database is not available, exiting...")
        sys.exit(1)
