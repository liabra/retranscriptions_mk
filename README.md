# A2C Retranscriptions

Plateforme de gestion des retranscriptions de réunions (CSE, CMAS, CSSCT…) : réception des audios, attribution, production et relecture des PV, validation, facturation et règlements.

Documents de référence :
- `docs/REFONTE_A2C_AUDIT.md` — audit initial
- `docs/REFONTE_A2C_RAPPORT_FINAL.md` — rapport de la refonte (fonctionnalités, sécurité, tests, mise en production)
- `docs/CONFIGURATION_SERVICES_EXTERNES.md` — variables d'environnement, Microsoft Graph, Brevo

## Stack

| Couche | Technologie |
|---|---|
| Frontend | React 19 + TypeScript + Vite |
| Backend | FastAPI (Python 3.12), SQLAlchemy 2, Alembic |
| Base | PostgreSQL 15+ |
| Auth | JWT (PyJWT) + permissions configurables |
| Fichiers | Microsoft Graph (OneDrive) en proxy, PV en base ou OneDrive |
| Emails | Brevo (API v3) |
| Déploiement | Railway |

## Démarrage local

### Backend
```bash
cd backend
python3.12 -m venv .venv312 && source .venv312/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # renseigner SECRET_KEY, ENCRYPTION_KEY, DATABASE_URL
alembic upgrade head
python seed.py && python seed_grilles.py && python seed_parametres.py
python scripts/donnees_demo.py   # facultatif : jeu de démonstration (refusé en production)
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

## Tests
```bash
cd backend && python -m pytest -q        # PostgreSQL réel : pgserver local ou TEST_DATABASE_URL
cd frontend && npm test && npm run lint && npm run build
```
La CI GitHub (`.github/workflows/ci.yml`) exécute ces tests ainsi que `pip-audit` et `npm audit`.

## Principes de sécurité
- Les retranscripteurs n'accèdent qu'à leurs missions attribuées ; l'audio leur est transmis en flux par l'API, jamais par un lien OneDrive.
- Aucune donnée financière, note interne ou indicateur de performance n'est exposé aux retranscripteurs.
- Droits vérifiés côté serveur sur chaque ressource ; journal d'activité immuable.
- IBAN et liens privés chiffrés (Fernet) ; secrets uniquement en variables d'environnement.
