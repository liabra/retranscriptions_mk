from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import DbDep, CurrentUser, require_admin
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, TokenResponse
from app.services.journal import log_action
from app.models.journal import TypeActionEnum

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: DbDep = Depends()):
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
    db: DbDep = Depends(),
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
