"""Shared test setup that never depends on external policy or database state."""

import os
import tempfile
from pathlib import Path

os.environ["COMMAND_CENTER_POLICY_STORE"] = "local"
_TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / (
    f"autopilot-template-pytest-{os.getpid()}.db"
)
_TEST_DATABASE_PATH.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DATABASE_PATH.as_posix()}"
os.environ.pop("COMMAND_CENTER_DB_SCHEMA", None)

import pytest

from app import models  # noqa: F401 - registers all model metadata
from app.core.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def create_test_schema():
    Base.metadata.create_all(bind=engine)
    yield
    engine.dispose()
    _TEST_DATABASE_PATH.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def reset_test_data(create_test_schema):
    """Give every test a clean database without touching development data."""

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
