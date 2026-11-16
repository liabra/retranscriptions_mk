#!/bin/bash
# Démarrage Railway.
# fix : une migration en échec bloque le démarrage (plus de serveur sur un schéma incohérent),
# et aucune information de connexion n'est écrite dans les logs.
set -u

export PATH="/opt/venv/bin:$PATH"

# Railway injecte DATABASE_URL avec "postgres://" mais SQLAlchemy exige "postgresql://"
export DATABASE_URL="${DATABASE_URL/postgres:\/\//postgresql:\/\/}"

echo "=== Vérification de la configuration ==="
for var in DATABASE_URL SECRET_KEY ENCRYPTION_KEY; do
    if [ -z "${!var:-}" ]; then
        echo "ERREUR : variable $var absente" >&2
        exit 1
    fi
done
echo "APP_ENV=${APP_ENV:-development}"

echo "=== Migrations ==="
if ! alembic upgrade head; then
    echo "ERREUR : migration en échec — démarrage interrompu" >&2
    exit 1
fi

echo "=== Comptes internes ==="
python seed.py || echo "AVERTISSEMENT : amorçage des comptes en échec" >&2

echo "=== Grilles tarifaires ==="
python seed_grilles.py || echo "AVERTISSEMENT : amorçage des grilles en échec" >&2

echo "=== Délais et paramètres ==="
python seed_parametres.py || echo "AVERTISSEMENT : amorçage des paramètres en échec" >&2

echo "=== Démarrage du serveur ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
