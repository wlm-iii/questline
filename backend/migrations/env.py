from alembic import context
from sqlalchemy import create_engine, pool, text

from questline.config import get_settings
from questline.models import Base


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == "questline"
    if type_ == "table":
        # Queue tables are owned and migrated by Procrastinate, not Alembic.
        return name in {table.name for table in Base.metadata.tables.values()}
    return True


def run_migrations_online():
    # Keep reflection's default schema as public so explicitly qualified
    # questline tables/FKs are compared correctly. Application connections use questline.
    url = get_settings().sqlalchemy_url.update_query_dict({"options": "-csearch_path=public"})
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        connection.execute(text("CREATE SCHEMA IF NOT EXISTS questline"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table_schema="questline",
            include_schemas=True,
            include_name=include_name,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Use online migrations with DATABASE_URL configured")
else:
    run_migrations_online()
