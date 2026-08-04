import pytest
from fastapi.testclient import TestClient
from ran_chatbot_service import app


@pytest.fixture()
def client():
    return TestClient(app)
