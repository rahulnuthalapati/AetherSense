import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
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

def test_fitbit_login_redirect():
    """
    Tests the /fitbit/login endpoint to ensure it correctly redirects
    to the Fitbit authorization URL.
    """
    response = client.get("/fitbit/login", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert response.headers["location"].startswith("https://www.fitbit.com/oauth2/authorize")

@patch('requests.post')
@patch('fastapi.Request.session', new_callable=MagicMock)
def test_fitbit_callback_success(mock_session, mock_post):
    """
    Tests the /fitbit/callback endpoint with a mocked successful token exchange.
    """
    # 1. Mock the response from the external Fitbit API
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {"access_token": "mock_test_token"}

    # 2. Mock the session's .get() method to return the correct values
    def session_get_side_effect(key, default=None):
        if key == 'fitbit_oauth_state':
            return 'test_state'
        if key == 'fitbit_pkce_verifier':
            return 'test_verifier'
        return default
    mock_session.get.side_effect = session_get_side_effect

    # 3. Make the request to the callback endpoint
    response = client.get("/fitbit/callback?code=test_code&state=test_state")

    assert response.status_code == 200
    assert response.json() == {"status": "success", "access_token": "mock_test_token"}

@patch('requests.post') # We need to mock post here too to prevent real network calls
@patch('fastapi.Request.session', new_callable=MagicMock)
def test_fitbit_callback_invalid_state(mock_session, mock_post):
    """
    Tests that the /fitbit/callback endpoint correctly handles an invalid state.
    """
    # 1. Mock the session to contain a different state than the one in the URL
    mock_session.get.return_value = 'correct_state_in_session'

    # 2. Make the request with the wrong state in the URL
    response = client.get("/fitbit/callback?code=any_code&state=wrong_state_from_url")
    
    # Assert that the security check fails with a 400 error
    assert response.status_code == 400
    assert "Invalid authorization response state" in response.text