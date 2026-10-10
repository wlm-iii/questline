from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from questline.config import Settings


def create_database(settings: Settings):
    # Keep pools small for a shared Supabase instance. No connections at import time.
    engine = create_async_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        hide_parameters=True,
        pool_size=3,
        max_overflow=2,
        connect_args={"connect_timeout": 10},
    )
    return engine, async_sessionmaker(engine, expire_on_commit=False)
