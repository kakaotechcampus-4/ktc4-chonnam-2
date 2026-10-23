"""Recording migrations use only the runner's caller-owned Connection."""

from alembic import context

config = context.config
connection = config.attributes["connection"]
if not connection.in_transaction():
    raise RuntimeError("Recording migrations require a caller-owned transaction")
context.configure(connection=connection, target_metadata=None,
                  version_table=config.get_main_option("version_table"))
with context.begin_transaction():
    context.run_migrations()
