#!/bin/sh

# Portable Linux container entrypoint. Keep this file LF-only.
set -eu

echo "Starting application (${APP_ENV:-development})"

if [ "${APP_ENV:-development}" = "development" ]; then
    echo "Waiting for database"
    python utils/wait_for_db.py
fi

echo "Running database migrations"
alembic upgrade head

echo "Seeding Command Center configuration"
python scripts/seed_db.py

if [ "${APP_ENV:-development}" = "production" ]; then
    echo "Starting production server"
    exec gunicorn -c gunicorn/prod.py app.main:app
fi

echo "Starting development server"
exec gunicorn -c gunicorn/dev.py app.main:app
