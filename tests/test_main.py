import pytest
from fastapi.testclient import TestClient
from main import app  # Import your FastAPI app

client = TestClient(app)

def test_breath_check_in():
    """
    Tests the /breath-check-in endpoint to ensure it processes data
    and returns a coherence score and a message.
    """
    check_in_data = {
        "user_id": "test_user_123",
        "text": "Feeling calm",
        "breath_rate": 15,
        "hrv": 70
    }
    response = client.post("/breath-check-in", json=check_in_data)
    assert response.status_code == 200
    data = response.json()
    assert "coherence_score" in data
    assert "message" in data
    assert isinstance(data["coherence_score"], float)
    assert isinstance(data["message"], str)