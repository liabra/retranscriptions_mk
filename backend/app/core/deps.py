from typing import Generator, Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

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


def get_current_user(
    db: DbDep,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == user_id, User.actif == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: RoleEnum):
    """Décorateur de dépendance pour restreindre l'accès par rôle."""
    def checker(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle requis : {[r.value for r in roles]}",
            )
        return current_user
    return checker


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != RoleEnum.ADMINISTRATRICE:
        raise HTTPException(status_code=403, detail="Réservé à l'administratrice")
    return current_user


def require_admin_or_coordinator(current_user: CurrentUser) -> User:
    if current_user.role not in (RoleEnum.ADMINISTRATRICE, RoleEnum.COORDINATRICE):
        raise HTTPException(status_code=403, detail="Réservé à l'administratrice ou coordinatrice")
    return current_user
