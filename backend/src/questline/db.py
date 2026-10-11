import psycopg
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from questline.config import Settings


async def configure_queue_connection(connection: psycopg.AsyncConnection) -> None:
    # Session poolers may ignore startup options. SET outside a transaction so
    # rollbacks cannot reset the private schema, including on LISTEN connections.
    autocommit = connection.autocommit
    await connection.set_autocommit(True)
    try:
        await connection.execute("SET SESSION search_path TO questline")
    finally:
        await connection.set_autocommit(autocommit)


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

    @event.listens_for(engine.sync_engine, "connect")
    def set_private_schema(connection, record):
        autocommit = connection.autocommit
        connection.autocommit = True
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION search_path TO questline")
        finally:
            connection.autocommit = autocommit

    return engine, async_sessionmaker(engine, expire_on_commit=False)
