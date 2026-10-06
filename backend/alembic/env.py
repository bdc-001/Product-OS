from __future__ import annotations

from alembic import context as alembic_context
from sqlalchemy import pool

from app import models  # noqa: F401
from app.config import settings
from app.database import Base, make_engine

config = alembic_context.config
target_metadata = Base.metadata


def _url() -> str:
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def run_migrations_offline() -> None:
    url = _url()
    alembic_context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )
    with alembic_context.begin_transaction():
        alembic_context.run_migrations()


def run_migrations_online() -> None:
    url = _url()
    connectable = make_engine(url)
    with connectable.connect() as connection:
        alembic_context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=url.startswith("sqlite"),
            compare_type=True,
        )
        with alembic_context.begin_transaction():
            alembic_context.run_migrations()
    connectable.dispose()


if alembic_context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
