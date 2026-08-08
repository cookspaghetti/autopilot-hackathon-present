#!/usr/bin/env python3
"""
Database reset script.
Drops and recreates all tables in the public schema.
For local development use only.
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

# Add the project root to the Python path to allow importing 'app'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app.core.database import Base, engine


def reset_database():
    """Drops and recreates all tables in the public schema."""
    log.info("Connecting to the database...")

    try:
        # Use a raw connection to execute DDL statements outside a transaction block
        with engine.connect() as connection:
            log.info("Dropping public schema...")
            # Use CASCADE to drop dependent objects
            connection.execute(text("DROP SCHEMA public CASCADE;"))
            log.info("Creating new public schema...")
            connection.execute(text("CREATE SCHEMA public;"))
            connection.commit()

        log.info("Creating all tables from SQLAlchemy metadata...")
        Base.metadata.create_all(bind=engine)

        log.info("✅ Database reset successfully.")
    except Exception as e:
        log.error(f"❌ An error occurred during database reset: {e}")
        sys.exit(1)


if __name__ == "__main__":
    log.info("--- Starting Database Reset ---")
    reset_database()
