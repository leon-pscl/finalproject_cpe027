import pytest
from app.main import app as fastapi_app

@pytest.fixture(autouse=True)
def clear_all_overrides():
    yield
    fastapi_app.dependency_overrides.clear()
