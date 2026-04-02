import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Load .env before importing app modules
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

config = context.config

# Override sqlalchemy.url with env var
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import Base with all models registered
from app.db.base import Base  # noqa
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Construire l'URL directement depuis l'env pour éviter l'interpolation
    # configparser qui échoue avec les clés en majuscules (%(DATABASE_URL)s)
    db_url = os.environ.get("DATABASE_URL", "")
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    from sqlalchemy import create_engine
    connectable = create_engine(db_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
