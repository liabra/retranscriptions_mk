import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Tuple

import jwt  # fix: PyJWT remplace python-jose (CVE connues)
import bcrypt
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())

PASSWORD_MIN_LENGTH = 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    # bcrypt direct (passlib n'est plus maintenu) — empreintes $2b$ existantes compatibles
    try:
        data = (plain or "").encode()
        if len(data) > 72:
            return False
        return bcrypt.checkpw(data, hashed.encode())
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """Retourne un message d'erreur ou None si le mot de passe est acceptable."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN_LENGTH} caractères"
    if len(password.encode()) > 72:
        return "Le mot de passe est trop long (72 octets maximum)"
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 3:
        return "Utilisez au moins 3 types de caractères (minuscules, majuscules, chiffres, symboles)"
    return None


def generate_password(length: int = 16) -> str:
    """Mot de passe temporaire robuste (remis une seule fois, changement imposé)."""
    alphabet = string.ascii_letters + string.digits + "-_!@#%"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if validate_password_strength(pwd) is None:
            return pwd


def create_access_token(subject: Any, token_version: int = 0,
                        expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": str(subject), "exp": expire, "iat": now, "tv": token_version}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[Tuple[str, int]]:
    """Retourne (user_id, token_version) ou None."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return str(payload["sub"]), int(payload.get("tv", 0))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


def encrypt_secret(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt_secret(encrypted: str) -> Optional[str]:
    try:
        return _fernet.decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return None


# Compatibilité : chiffrement IBAN existant (même clé, même format)
def encrypt_iban(iban: str) -> str:
    return encrypt_secret(iban)


def decrypt_iban(encrypted: str) -> str:
    return _fernet.decrypt(encrypted.encode()).decode()
