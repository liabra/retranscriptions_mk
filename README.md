# Système de Gestion de Retranscriptions

Application de gestion de missions de retranscription pour instances représentatives du personnel (CE, CMAS, CSSCT).

> Document de référence : `docs/Cadrage_Retranscriptions_v2.pdf`

---

## Stack

| Couche | Technologie |
|--------|-------------|
| Frontend | React + TypeScript + Vite |
| Backend | FastAPI (Python 3.11+) |
| ORM | SQLAlchemy + Alembic |
| Base de données | PostgreSQL 15+ |
| Auth | JWT + RBAC |
| PDF | WeasyPrint |
| Deploy | Railway + GitHub CI/CD |

---

## Démarrage local

### Prérequis

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Remplir .env avec vos valeurs

# Migrations
alembic upgrade head

# Lancer
uvicorn app.main:app --reload
```

API disponible sur : http://localhost:8000
Docs Swagger : http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

App disponible sur : http://localhost:5173

---

## Structure du projet

```
├── backend/          # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── api/      # Endpoints REST
│   │   ├── core/     # Config, sécurité, dépendances
│   │   ├── models/   # Modèles SQLAlchemy
│   │   ├── schemas/  # Schémas Pydantic
│   │   ├── services/ # Logique métier (dont moteur tarifaire)
│   │   └── db/       # Session, base
│   └── alembic/      # Migrations
├── frontend/         # React + TypeScript + Vite
├── docs/             # Documents de référence
└── database/         # Scripts SQL utilitaires
```

---

## Sécurité

- Confidentialité maximale — données CE/CMAS/CSSCT
- Cloisonnement strict par rôle
- Un prestataire ne voit jamais le montant client
- Journal d'activité immuable
- IBAN stocké chiffré (AES-256)
