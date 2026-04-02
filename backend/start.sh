#!/bin/bash
set -e

# Railway injecte DATABASE_URL avec "postgres://" mais SQLAlchemy exige "postgresql://"
export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"

echo "Running migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
