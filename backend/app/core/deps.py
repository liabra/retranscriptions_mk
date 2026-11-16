import uuid
from typing import Generator, Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.permissions import has_permission, is_internal, PRESTATAIRE_ROLES
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User, RoleEnum

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbDep = Annotated[Session, Depends(get_db)]


def _user_from_token(db: Session, token: str) -> User:
    decoded = decode_access_token(token)
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session invalide ou expirée",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not decoded:
        raise unauthorized
    user_id, token_version = decoded
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise unauthorized
    user = db.query(User).filter(User.id == uid, User.actif == True).first()  # noqa: E712
    # fix: jeton révoqué après changement de mot de passe / désactivation
    if not user or (user.token_version or 0) != token_version:
        raise unauthorized
    return user


def get_current_user_any(
    db: DbDep, token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Utilisateur authentifié, même si un changement de mot de passe est exigé."""
    return _user_from_token(db, token)


def get_current_user(user: Annotated[User, Depends(get_current_user_any)]) -> User:
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="Changement de mot de passe requis")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentUserAny = Annotated[User, Depends(get_current_user_any)]


def require_permission(*perms: str):
    """Exige au moins une des permissions indiquées."""
    def checker(current_user: CurrentUser) -> User:
        if not any(has_permission(current_user, p) for p in perms):
            raise HTTPException(status_code=403, detail="Accès refusé")
        return current_user
    return checker


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != RoleEnum.ADMINISTRATRICE:
        raise HTTPException(status_code=403, detail="Réservé à l'administratrice")
    return current_user


def require_internal(current_user: CurrentUser) -> User:
    if not is_internal(current_user):
        raise HTTPException(status_code=403, detail="Accès refusé")
    return current_user


def require_prestataire(current_user: CurrentUser) -> User:
    if current_user.role not in PRESTATAIRE_ROLES or not current_user.prestataire_id:
        raise HTTPException(status_code=403, detail="Réservé aux retranscripteurs")
    return current_user


def require_client(current_user: CurrentUser) -> User:
    if current_user.role != RoleEnum.CLIENT or not current_user.client_id:
        raise HTTPException(status_code=403, detail="Réservé aux clients")
    return current_user


def client_ip(request) -> Optional[str]:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:45]
    return request.client.host[:45] if request.client else None
