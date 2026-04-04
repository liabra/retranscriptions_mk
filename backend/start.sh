#!/bin/bash
# Ne pas utiliser set -e ici : on veut que le serveur démarre même si
# une étape de setup (migration, seed) échoue — l'erreur sera loggée.

# Activer le venv nixpacks (Railway ne source pas /root/.profile)
export PATH="/opt/venv/bin:$PATH"

# Railway injecte DATABASE_URL avec "postgres://" mais SQLAlchemy exige "postgresql://"
export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"

echo "=== Env check ==="
echo "PORT=${PORT:-8000}"
echo "DATABASE_URL prefix=${DATABASE_URL:0:30}..."
echo "SECRET_KEY set=$([ -n "$SECRET_KEY" ] && echo yes || echo NO)"
echo "ENCRYPTION_KEY set=$([ -n "$ENCRYPTION_KEY" ] && echo yes || echo NO)"

echo "=== Running migrations ==="
if alembic upgrade head; then
    echo "Migrations OK"
else
    echo "WARNING: alembic upgrade failed — server will start anyway" >&2
fi

echo "=== Seeding default admin ==="
if python seed.py; then
    echo "Seed OK"
else
    echo "WARNING: seed.py failed — server will start anyway" >&2
fi

echo "=== Starting server ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
