from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_NAME: str = "A2C Retranscriptions"
    APP_ENV: str = "development"          # development | test | production
    DEBUG: bool = False                    # fix: désactivé par défaut (docs Swagger non exposées)
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    APP_PUBLIC_URL: str = "http://localhost:5173"  # lien inséré dans les emails

    # Database — Railway injecte "postgres://", SQLAlchemy exige "postgresql://"
    DATABASE_URL: str

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Encryption (IBAN, liens OneDrive privés) — clé Fernet
    ENCRYPTION_KEY: str

    # Anti-bruteforce connexion
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_MINUTES: int = 15

    # Fichiers
    MAX_AUDIO_MB: int = 500
    MAX_DOCX_MB: int = 25
    # Stockage des PV : "database" (PostgreSQL, durable, défaut) ou "onedrive" (Graph)
    PV_STORAGE_BACKEND: str = "database"
    # Stockage des audios téléversés : "onedrive" (production) ou "local" (dev/test uniquement)
    AUDIO_STORAGE_BACKEND: str = "onedrive"
    LOCAL_STORAGE_DIR: str = "./stockage_local"

    # Microsoft Graph / OneDrive — optionnel ; aucune bascule silencieuse si absent
    ONEDRIVE_TENANT_ID: str = ""
    ONEDRIVE_CLIENT_ID: str = ""
    ONEDRIVE_CLIENT_SECRET: str = ""
    ONEDRIVE_DRIVE_ID: str = ""
    ONEDRIVE_ROOT_FOLDER: str = "A2C Retranscriptions"
    ONEDRIVE_INBOX_FOLDER: str = "A2C Retranscriptions/Nouveaux audios"  # surveillé (mode B)
    GRAPH_SYNC_INTERVAL_MINUTES: int = 0   # 0 = détection automatique désactivée

    # Emails transactionnels — Brevo (API v3). Absent = aucun email envoyé (statut "non_configure")
    BREVO_API_KEY: str = ""
    BREVO_SENDER_EMAIL: str = ""
    BREVO_SENDER_NAME: str = "A2C Retranscriptions"

    # Tâches périodiques (alertes échéance/retard)
    ENABLE_SCHEDULER: bool = False
    SCHEDULER_INTERVAL_MINUTES: int = 60

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def onedrive_configured(self) -> bool:
        return bool(self.ONEDRIVE_TENANT_ID and self.ONEDRIVE_CLIENT_ID
                    and self.ONEDRIVE_CLIENT_SECRET and self.ONEDRIVE_DRIVE_ID)

    @property
    def brevo_configured(self) -> bool:
        return bool(self.BREVO_API_KEY and self.BREVO_SENDER_EMAIL)

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        # fix: refuser une configuration de production faible
        if self.is_production:
            if len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY trop courte (32 caractères minimum en production)")
            if self.DEBUG:
                raise ValueError("DEBUG doit être désactivé en production")
            if self.AUDIO_STORAGE_BACKEND == "local":
                raise ValueError("Stockage local interdit en production (disque éphémère)")
        if self.PV_STORAGE_BACKEND not in ("database", "onedrive"):
            raise ValueError("PV_STORAGE_BACKEND doit valoir 'database' ou 'onedrive'")
        if self.AUDIO_STORAGE_BACKEND not in ("onedrive", "local"):
            raise ValueError("AUDIO_STORAGE_BACKEND doit valoir 'onedrive' ou 'local'")
        return self

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
