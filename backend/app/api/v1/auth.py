import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.deps import DbDep, CurrentUser, CurrentUserAny, require_admin, client_ip
from app.core.permissions import PERMISSIONS, DEFAULTS, effective_permissions
from app.core.security import (
    hash_password, verify_password, create_access_token, validate_password_strength, generate_password,
)
from app.models.client import Client
from app.models.journal import TypeActionEnum
from app.models.prestataire import Prestataire
from app.models.user import User, RoleEnum
from app.services.journal import log_action

router = APIRouter()

ROLES_CREABLES = {RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE, RoleEnum.RETRANSCRIPTEUR,
                  RoleEnum.COMPTABILITE, RoleEnum.LECTURE_SEULE, RoleEnum.CLIENT}


# ── Anti-bruteforce (mémoire du processus) ───────────────────────────────────
class _LoginLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)

    def _purge(self, key: str, now: float):
        window = settings.LOGIN_WINDOW_MINUTES * 60
        q = self._hits[key]
        while q and q[0] < now - window:
            q.popleft()

    def blocked(self, *keys: str) -> bool:
        now = time.time()
        with self._lock:
            for k in keys:
                self._purge(k, now)
                if len(self._hits[k]) >= settings.LOGIN_MAX_ATTEMPTS * (4 if k.startswith("ip:") else 1):
                    return True
        return False

    def fail(self, *keys: str):
        with self._lock:
            for k in keys:
                self._hits[k].append(time.time())

    def reset(self, key: str):
        with self._lock:
            self._hits.pop(key, None)


limiter = _LoginLimiter()
_DUMMY_HASH = hash_password("verification-a-temps-constant")


# ── Schémas ─────────────────────────────────────────────────────────────────
class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    nom: str
    role: RoleEnum
    actif: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    must_change_password: bool = False
    notif_email: bool = True
    prestataire_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    permissions: List[str] = []
    permissions_personnalisees: Optional[dict] = None


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, nom=u.nom, role=u.role, actif=u.actif, created_at=u.created_at,
        last_login=u.last_login, must_change_password=u.must_change_password, notif_email=u.notif_email,
        prestataire_id=u.prestataire_id, client_id=u.client_id,
        permissions=sorted(effective_permissions(u)), permissions_personnalisees=u.permissions,
    )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class PasswordChange(BaseModel):
    ancien_mot_de_passe: str
    nouveau_mot_de_passe: str


class PreferencesUpdate(BaseModel):
    notif_email: bool


class UserCreate(BaseModel):
    email: EmailStr
    nom: str
    role: RoleEnum
    password: Optional[str] = None  # absent = mot de passe temporaire généré
    prestataire_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    nom: Optional[str] = None
    role: Optional[RoleEnum] = None
    actif: Optional[bool] = None
    permissions: Optional[Dict[str, bool]] = None
    reinitialiser_mot_de_passe: bool = False


class UserCreated(BaseModel):
    user: UserOut
    mot_de_passe_temporaire: Optional[str] = None


# ── Connexion ───────────────────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse)
def login(request: Request, db: DbDep, form_data: OAuth2PasswordRequestForm = Depends()):
    email = (form_data.username or "").strip().lower()
    ip = client_ip(request) or "inconnue"
    keys = (f"email:{email}", f"ip:{ip}")
    if limiter.blocked(*keys):
        raise HTTPException(status_code=429, detail="Trop de tentatives. Réessayez dans quelques minutes.")

    user = db.query(User).filter(User.email == email, User.actif == True).first()  # noqa: E712
    # fix: vérification bcrypt même pour un compte inconnu (pas d'énumération par le temps de réponse)
    ok = verify_password(form_data.password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not ok:
        limiter.fail(*keys)
        log_action(db, TypeActionEnum.AUTH, utilisateur_id=user.id if user else None,
                   detail={"action": "login_echec"}, ip_source=ip)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect")

    limiter.reset(f"email:{email}")
    user.last_login = datetime.now(timezone.utc)
    # fix B2 : journal enregistré dans la même transaction que la connexion
    log_action(db, TypeActionEnum.AUTH, utilisateur_id=user.id, detail={"action": "login"}, ip_source=ip)
    db.commit()
    db.refresh(user)
    token = create_access_token(subject=str(user.id), token_version=user.token_version or 0)
    return TokenResponse(access_token=token, user=user_out(user))


@router.get("/me", response_model=UserOut)
def get_me(current_user: CurrentUserAny):
    return user_out(current_user)


@router.post("/change-password", response_model=TokenResponse)
def change_password(payload: PasswordChange, request: Request, db: DbDep, current_user: CurrentUserAny):
    if not verify_password(payload.ancien_mot_de_passe, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")
    err = validate_password_strength(payload.nouveau_mot_de_passe)
    if err:
        raise HTTPException(status_code=400, detail=err)
    if payload.nouveau_mot_de_passe == payload.ancien_mot_de_passe:
        raise HTTPException(status_code=400, detail="Le nouveau mot de passe doit être différent")
    current_user.hashed_password = hash_password(payload.nouveau_mot_de_passe)
    current_user.must_change_password = False
    current_user.token_version = (current_user.token_version or 0) + 1  # révoque les anciennes sessions
    log_action(db, TypeActionEnum.AUTH, utilisateur_id=current_user.id,
               detail={"action": "changement_mot_de_passe"}, ip_source=client_ip(request))
    db.commit()
    db.refresh(current_user)
    token = create_access_token(subject=str(current_user.id), token_version=current_user.token_version)
    return TokenResponse(access_token=token, user=user_out(current_user))


@router.patch("/me/preferences", response_model=UserOut)
def update_preferences(payload: PreferencesUpdate, db: DbDep, current_user: CurrentUser):
    current_user.notif_email = payload.notif_email
    db.commit()
    db.refresh(current_user)
    return user_out(current_user)


# ── Gestion des utilisateurs (administratrice) ──────────────────────────────
@router.get("/permissions")
def catalogue_permissions(_admin: User = Depends(require_admin)):
    return {
        "permissions": [{"code": k, "libelle": v} for k, v in PERMISSIONS.items()],
        "par_defaut": {r.value: sorted(p) for r, p in DEFAULTS.items()},
    }


def _lier_compte(db, role: RoleEnum, prestataire_id, client_id, user: Optional[User] = None):
    if role == RoleEnum.RETRANSCRIPTEUR:
        if not prestataire_id:
            raise HTTPException(status_code=400, detail="Sélectionnez la fiche retranscripteur à associer")
        if not db.query(Prestataire).filter(Prestataire.id == prestataire_id).first():
            raise HTTPException(status_code=404, detail="Fiche retranscripteur introuvable")
        other = db.query(User).filter(User.prestataire_id == prestataire_id).first()
        if other and (user is None or other.id != user.id):
            raise HTTPException(status_code=400, detail="Cette fiche est déjà associée à un compte")
        return prestataire_id, None
    if role == RoleEnum.CLIENT:
        if not client_id or not db.query(Client).filter(Client.id == client_id).first():
            raise HTTPException(status_code=400, detail="Sélectionnez le client à associer")
        return None, client_id
    return None, None


@router.get("/users", response_model=List[UserOut])
def list_users(db: DbDep, _admin: User = Depends(require_admin)):
    return [user_out(u) for u in db.query(User).order_by(User.nom).all()]


@router.post("/users", response_model=UserCreated, status_code=201)
def create_user(payload: UserCreate, request: Request, db: DbDep, admin: User = Depends(require_admin)):
    if payload.role not in ROLES_CREABLES:
        raise HTTPException(status_code=400, detail="Rôle non disponible")
    email = payload.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    temp = None
    if payload.password:
        err = validate_password_strength(payload.password)
        if err:
            raise HTTPException(status_code=400, detail=err)
        pwd = payload.password
    else:
        pwd = temp = generate_password()
    pid, cid = _lier_compte(db, payload.role, payload.prestataire_id, payload.client_id)
    user = User(email=email, nom=payload.nom.strip()[:255], hashed_password=hash_password(pwd),
                role=payload.role, prestataire_id=pid, client_id=cid, must_change_password=True)
    db.add(user)
    db.flush()
    log_action(db, TypeActionEnum.AUTH, utilisateur_id=admin.id, ip_source=client_ip(request),
               detail={"action": "creation_utilisateur", "cible": str(user.id), "role": payload.role.value})
    db.commit()
    db.refresh(user)
    return UserCreated(user=user_out(user), mot_de_passe_temporaire=temp)


# Compatibilité avec l'ancien client
@router.post("/register", response_model=UserCreated, status_code=201, include_in_schema=False)
def register(payload: UserCreate, request: Request, db: DbDep, admin: User = Depends(require_admin)):
    return create_user(payload, request, db, admin)


@router.patch("/users/{user_id}", response_model=UserCreated)
def update_user(user_id: uuid.UUID, payload: UserUpdate, request: Request, db: DbDep,
                admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.id == admin.id and (payload.actif is False or (payload.role and payload.role != RoleEnum.ADMINISTRATRICE)):
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas retirer vos propres droits")
    changes = {}
    if payload.email is not None and payload.email.lower() != user.email:
        email = payload.email.strip().lower()
        if db.query(User).filter(User.email == email, User.id != user.id).first():
            raise HTTPException(status_code=400, detail="Email déjà utilisé")
        user.email = email
        changes["email"] = True
    if payload.nom is not None:
        user.nom = payload.nom.strip()[:255]
        changes["nom"] = True
    if payload.role is not None and payload.role != user.role:
        if payload.role not in ROLES_CREABLES:
            raise HTTPException(status_code=400, detail="Rôle non disponible")
        user.role = payload.role
        user.token_version = (user.token_version or 0) + 1
        changes["role"] = payload.role.value
    if payload.actif is not None:
        user.actif = payload.actif
        if not payload.actif:
            user.token_version = (user.token_version or 0) + 1
        changes["actif"] = payload.actif
    if payload.permissions is not None:
        user.permissions = {k: bool(v) for k, v in payload.permissions.items() if k in PERMISSIONS}
        changes["permissions"] = user.permissions
    temp = None
    if payload.reinitialiser_mot_de_passe:
        temp = generate_password()
        user.hashed_password = hash_password(temp)
        user.must_change_password = True
        user.token_version = (user.token_version or 0) + 1
        changes["reinitialisation_mot_de_passe"] = True
    log_action(db, TypeActionEnum.AUTH, utilisateur_id=admin.id, ip_source=client_ip(request),
               detail={"action": "modification_utilisateur", "cible": str(user_id), "changements": changes})
    db.commit()
    db.refresh(user)
    return UserCreated(user=user_out(user), mot_de_passe_temporaire=temp)
