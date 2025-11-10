import pytest, requests
from unittest.mock import patch, MagicMock

from src.adapters.fitbit_adapter import FitbitAdapter
from src.config import settings
from tests.conftest import session_state

def test_fitbit_login_redirect(client):
    """
    Tests the /fitbit/login endpoint to ensure it correctly redirects
    to the Fitbit authorization URL.
    """
    response = client.get("/fitbit/login", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert response.headers["location"].startswith("https://www.fitbit.com/oauth2/authorize")

@patch('requests.post')
def test_fitbit_callback_success(mock_post, client, session_state, fitbit_token_success, make_response, fixed_time):
    """Tests the callback with a successful token exchange and asserts session is updated."""
    session_state['fitbit_oauth_state'] = 'test_state'
    session_state['fitbit_pkce_verifier'] = 'test_verifier'
    mock_post.return_value = make_response(200, fitbit_token_success)
    
    # Make the request but DO NOT follow the redirect, so we can inspect it
    response = client.get("/fitbit/callback?code=test_code&state=test_state", follow_redirects=False)

    # 1. Assert that the response is a redirect
    assert response.status_code == 307 # FastAPI's RedirectResponse defaults to 307
    
    # 2. Assert that it redirects to the correct frontend URL with a success status
    expected_url = f"{settings.FRONTEND_URL}?fitbit_status=success"
    assert response.headers["location"] == expected_url

    # 3. Assert that the session was still correctly updated in the background
    assert session_state['fitbit_access_token'] == "access_abc"
    assert session_state['fitbit_refresh_token'] == "refresh_xyz"
    assert session_state['fitbit_token_expires_at'] == fixed_time + 3600

@patch('fastapi.Request.session', new_callable=MagicMock)
def test_fitbit_callback_invalid_state(mock_session, client):
    """
    Tests that the /fitbit/callback endpoint correctly handles an invalid state.
    """
    # 1. Mock the session to contain a different state than the one in the URL
    mock_session.get.return_value = 'correct_state_in_session'

    # 2. Make the request with the wrong state in the URL
    response = client.get("/fitbit/callback?code=any_code&state=wrong_state_from_url", follow_redirects=False)
    
    # Assert that it redirects with an error status
    assert response.status_code == 307
    expected_url = f"{settings.FRONTEND_URL}?fitbit_status=error_state"
    assert response.headers["location"] == expected_url

@patch('requests.post')
@patch('fastapi.Request.session', new_callable=MagicMock)
def test_fitbit_callback_token_exchange_failure(mock_session, mock_post, client):
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
    response = client.get("/fitbit/callback?code=test_code&state=test_state", follow_redirects=False)

    # Assert that it redirects with an error status
    assert response.status_code == 307
    expected_url = f"{settings.FRONTEND_URL}?fitbit_status=error_token"
    assert response.headers["location"] == expected_url

@patch('requests.get')
@patch('requests.post')
def test_get_live_hrv_data_with_token_refresh(mock_post, mock_get, client, expired_session_state, fitbit_token_refresh_success, hrv_payload_valid, make_response):
    """Tests that the /get-live-hrv endpoint automatically refreshes an expired token."""
    mock_post.return_value = make_response(200, fitbit_token_refresh_success)
    mock_get.side_effect = [
        make_response(200, {"user": {"encodedId": "XYZ"}}), # For connect() call
        make_response(200, hrv_payload_valid)               # For fetch_data() call
    ]

    response = client.get("/fitbit/get-live-hrv")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs['data']['refresh_token'] == 'refresh_xyz'
    assert mock_get.call_args_list[1].kwargs['headers']['Authorization'] == "Bearer access_refreshed"

@patch("requests.get")
def test_get_live_hrv_rate_limit_retry(mock_get, client, make_response, hrv_payload_valid, fresh_session_state):
    """
    Tests that the adapter retries on a 429 rate limit error and eventually succeeds.
    """
    # 1. Simulate the sequence of API calls. The endpoint first calls connect() and then fetch_data().
    # We need to mock both. Let's assume connect() succeeds, and fetch_data() encounters the rate limit.
    mock_get.side_effect = [
        # First call is for connect() -> /profile.json
        make_response(200, {"user": {"encodedId": "XYZ"}}),
        
        # Subsequent calls are for fetch_data() -> /hrv/...
        make_response(429, {"error": "Too Many Requests"}), # First attempt fails
        make_response(429, {"error": "Too Many Requests"}), # Second attempt fails (1st retry)
        make_response(200, hrv_payload_valid)               # Third attempt succeeds (2nd retry)
    ]

    # 2. Make the request
    response = client.get("/fitbit/get-live-hrv")

    # 3. Assert success
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # The HRV payload from the fixture is nested under "hrv", but the normalized data is a flat list.
    assert response.json()["data"][0]["hrv_value"] == 80
    
    # 4. Assert that requests.get was called 4 times in total
    # (1 for connect + 3 for fetch_data with retries)
    assert mock_get.call_count == 4


# ---------------- Parametrized Tests ----------------
# The fixtures are the same as the ones in the tests below, but we parametrize the tests so we don't have to write them again.
@pytest.mark.parametrize(
    "hrv_payload_fixture, expected_length, expected_first_value",
    [
        ("hrv_payload_valid", 1, 80),
        ("hrv_payload_empty", 0, None),
        ("hrv_payload_all_malformed", 0, None),
        ("hrv_payload_mixed", 1, 82),
    ],
)
@patch("requests.get")
def test_get_live_hrv_payload_scenarios(
    mock_get, client, make_response, fresh_session_state, request,
    hrv_payload_fixture, expected_length, expected_first_value
):
    """
    Tests various HRV payload scenarios (valid, empty, malformed, mixed).
    """
    # Get the actual payload data from the fixture name
    hrv_payload = request.getfixturevalue(hrv_payload_fixture)
    
    # Mock the sequence of API calls: connect() then fetch_data()
    mock_get.side_effect = [
        make_response(200, {"user": {"encodedId": "XYZ"}}), # For connect()
        make_response(200, hrv_payload)                    # For fetch_data()
    ]

    response = client.get("/fitbit/get-live-hrv")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == expected_length
    if expected_length > 0:
        assert data[0]["hrv_value"] == expected_first_value

# ---------------- Edge Case Tests ----------------

@patch("requests.post")
def test_callback_missing_access_token(mock_post, client, session_state, fitbit_token_missing_access, make_response):
    """Token response missing access_token should fail gracefully."""
    mock_post.return_value = make_response(200, fitbit_token_missing_access)

    session_state['fitbit_oauth_state'] = 'state123'
    session_state['fitbit_pkce_verifier'] = 'pkce123'

    response = client.get("/fitbit/callback?code=abc&state=state123")

    # The app will raise a 500 error with a specific detail message
    assert response.status_code == 500
    assert "Incomplete token data" in response.json().get("detail", "")

@patch("requests.post")
def test_refresh_token_expired(mock_post, client, expired_refresh_session_state, make_response):
    """Expired refresh token should force a reconnect flow."""
    mock_post.return_value = make_response(400, {"error": "invalid_grant"})

    response = client.get("/fitbit/get-live-hrv")

    assert response.status_code == 401
    assert "re-authenticate" in response.json().get("detail", "").lower()