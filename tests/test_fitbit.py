import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.adapters.fitbit_adapter import FitbitAdapter
from src.routes.fitbit_routes import get_valid_fitbit_adapter
import requests, time
from main import app  # Import your FastAPI app

client = TestClient(app)

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
    mock_post.return_value.json.return_value = {
        "access_token": "mock_test_token",
        "refresh_token": "mock_refresh_token",
        "expires_in": 3600
    }

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
    assert response.json() == {"status": "success", "message": "Fitbit account linked successfully."}

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

@patch('requests.post')
@patch('fastapi.Request.session', new_callable=MagicMock)
def test_fitbit_callback_token_exchange_failure(mock_session, mock_post):
    """
    Tests the /fitbit/callback endpoint for a token exchange failure.
    """
    # 1. Mock the post request to fail with an API down exception
    mock_post.side_effect = requests.exceptions.RequestException("API is down")

    # 2. Mock the session to contain the correct values
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
    assert "Could not obtain access token from Fitbit" in response.json().get("error")

@patch('requests.get')
@patch('src.adapters.fitbit_adapter.FitbitAdapter.connect')
def test_get_live_hrv_data_with_malformed_payload(mock_connect, mock_get):
    """
    Tests the get_live_hrv_data endpoint with a malformed HRV payload,
    ensuring the adapter's normalization logic is correctly applied.
    """
    mock_connect.return_value = True

    # 1. Mock the raw API response from Fitbit that fetch_data will process
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "hrv": [
            # Malformed entries that should be discarded
            {"value": {"deep": "not_a_float"}, "timestamp": "2025-08-14T10:00:00"},
            {"value": {}, "timestamp": "2025-08-14T10:01:00"},
            {"value": {"deep": None}, "timestamp": "2025-08-14T10:01:30"},
            # A single valid entry
            {"value": {"deep": 80}, "timestamp": "2025-08-14T10:02:00"}
        ]
    }
    mock_get.return_value = mock_response

    # 2. Directly instantiate and test the adapter's methods with a mocked adapter
    adapter = FitbitAdapter(access_token="fake_token_for_testing")
    normalized_data = adapter.normalize_data(mock_response.json())

    # 3. Assert that the normalization logic works as expected
    assert len(normalized_data) == 1
    assert normalized_data[0]['hrv_value'] == 80

@patch('requests.get')
@patch('requests.post')
def test_get_live_hrv_data_with_token_refresh(mock_post, mock_get):
    """
    Tests that the /get-live-hrv endpoint automatically refreshes an expired token
    by overriding the dependency to inject a mocked, expired session state.
    """
    # 1. Mock the response for the token refresh API call
    mock_post.return_value.raise_for_status.return_value = None
    mock_post.return_value.json.return_value = {
        "access_token": "new_refreshed_access_token",
        "refresh_token": "new_refreshed_refresh_token",
        "expires_in": 3600
    }
    
    # 2. Mock the API calls for connect() and fetch_data()
    mock_get.side_effect = [
        MagicMock(
            **{"raise_for_status.return_value": None, 
               "json.return_value": {"user": {"encodedId": "XYZ"}}}
        ),
        MagicMock(
            **{"raise_for_status.return_value": None, 
               "json.return_value": {"hrv": [{"value": {"deep": 75}, "timestamp": "2025-08-14T12:00:00"}]}}
        )
    ]

    # 3. Define the override dependency to simulate an expired session
    def override_get_expired_adapter():
        mock_request = MagicMock()
        mock_request.session = {
            'fitbit_access_token': "expired_access_token",
            'fitbit_refresh_token': "valid_refresh_token",
            'fitbit_token_expires_at': time.time() - 60  # Expired
        }
        # Run the actual dependency logic with our mocked request
        return get_valid_fitbit_adapter(mock_request)

    # 4. Apply the override to the FastAPI app
    app.dependency_overrides[get_valid_fitbit_adapter] = override_get_expired_adapter

    # 5. Make the request
    response = client.get("/fitbit/get-live-hrv")
    
    # 6. Clean up the override after the test
    app.dependency_overrides = {}

    # 7. Assertions
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs['data']['refresh_token'] == 'valid_refresh_token'
    assert mock_get.call_args_list[0].kwargs['headers']['Authorization'] == "Bearer new_refreshed_access_token"