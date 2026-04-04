from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Gestion Retranscriptions"
    APP_ENV: str = "development"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Database — Railway injecte "postgres://", SQLAlchemy exige "postgresql://"
    DATABASE_URL: str

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Encryption (IBAN AES-256)
    ENCRYPTION_KEY: str

    # Files
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 500

    # Email SMTP — optionnel, les emails sont loggés si absent
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = ""    # "A2C Retranscriptions <contact@a2c.fr>"
    ADMIN_EMAIL: str = ""   # Notifié quand un correcteur livre

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    model_config = {"env_file": ".env"}


settings = Settings()
