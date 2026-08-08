#!/usr/bin/env python3
"""
Database cleanup script.
Drops all tables in the public schema and recreates it.
Used by the cleanup-db Cloud Run Job.
"""

import logging
import os
import sys

# Configure logging for scripts
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def cleanup_database():
    from sqlalchemy import create_engine, text

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        log.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    # Mask password in log output
    masked_url = database_url.split("@")[0] + "@***" if "@" in database_url else "***"
    log.info("🗑️  Cleaning database...")
    log.info(f"   URL: {masked_url}")

    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            # Drop all tables by dropping and recreating the public schema
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
            conn.commit()

        log.info("✅ Database cleaned! All tables dropped.")

    except Exception as e:
        log.error(f"❌ Error cleaning database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cleanup_database()
