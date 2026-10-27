import os

# Tests never touch the dev database. Must run before anything imports app.config.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/talotrace_test"
)
