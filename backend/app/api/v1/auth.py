from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import DbDep, CurrentUser, require_admin
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserOut, TokenResponse
from app.services.journal import log_action
from app.models.journal import TypeActionEnum

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(db: DbDep, form_data: OAuth2PasswordRequestForm = Depends()):
    user = db.query(User).filter(
        User.email == form_data.username,
        User.actif == True
    ).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    log_action(db, type_action=TypeActionEnum.AUTH, utilisateur_id=user.id,
               detail={"action": "login", "email": user.email})

    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/register", response_model=UserOut)
def register(
    payload: UserCreate,
    db: DbDep,
    _admin: User = Depends(require_admin),
):
    """Création d'utilisateur réservée à l'administratrice."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email déjà utilisé")

    user = User(
        email=payload.email,
        nom=payload.nom,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
def get_me(current_user: CurrentUser):
    return UserOut.model_validate(current_user)


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: DbDep,
    _admin: User = Depends(require_admin),
):
    """Liste tous les utilisateurs — réservé à l'administratrice."""
    return db.query(User).order_by(User.nom).all()


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: DbDep,
    admin: User = Depends(require_admin),
):
    """Modifier nom, rôle, statut actif, ou réinitialiser le mot de passe."""
    from app.core.security import hash_password
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if payload.nom is not None:
        user.nom = payload.nom
    if payload.role is not None:
        user.role = payload.role
    if payload.actif is not None:
        user.actif = payload.actif
    if payload.password:
        user.hashed_password = hash_password(payload.password)
    log_action(
        db, TypeActionEnum.AUTH,
        utilisateur_id=admin.id,
        detail={"action": "update_user", "target_user_id": str(user_id)},
    )
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)
