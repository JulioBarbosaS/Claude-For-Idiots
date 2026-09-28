# Alembic's migration directory can be named anything -- `alembic init
# migrations` is a common alternative to the `alembic init alembic` default,
# especially for teams used to Django's "migrations" naming. Same role as
# tests/fixtures/fastapi/alembic/env.py, different directory name.
from alembic import context

config = context.config
