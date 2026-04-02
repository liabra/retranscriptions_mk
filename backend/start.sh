#!/bin/bash
set -e

# Activer le venv nixpacks (Railway ne source pas /root/.profile)
export PATH="/opt/venv/bin:$PATH"

# Railway injecte DATABASE_URL avec "postgres://" mais SQLAlchemy exige "postgresql://"
export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"

echo "=== Env check ==="
echo "PORT=${PORT}"
echo "DATABASE_URL prefix=${DATABASE_URL:0:20}..."
echo "SECRET_KEY set=$([ -n "$SECRET_KEY" ] && echo yes || echo NO)"
echo "ENCRYPTION_KEY set=$([ -n "$ENCRYPTION_KEY" ] && echo yes || echo NO)"

echo "=== Running migrations ==="
alembic upgrade head

echo "=== Starting server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
