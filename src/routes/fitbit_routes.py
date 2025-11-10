import time, random
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import requests, secrets, hashlib, base64

from src.config import settings
from src.adapters.fitbit_adapter import FitbitAdapter, SCOPE as FITBIT_SCOPE
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/fitbit", tags=["Fitbit Authentication"])

#-------- Helper functions--------
def _update_session_with_tokens(request: Request, token_data: dict):
    """Helper to update the user's session with new token data."""
    request.session['fitbit_access_token'] = token_data["access_token"]
    request.session['fitbit_refresh_token'] = token_data["refresh_token"]
    request.session['fitbit_token_expires_at'] = time.time() + token_data["expires_in"]

def _refresh_fitbit_token(refresh_token: str) -> dict | None:
    """Helper function to refresh a Fitbit access token."""
    logger.info("Attempting to refresh Fitbit access token.")
    token_url = "https://api.fitbit.com/oauth2/token"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    auth_header = requests.auth.HTTPBasicAuth(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
    
    try:
        # Send the request to the Fitbit API to refresh the token
        response = requests.post(token_url, auth=auth_header, data=payload)
        response.raise_for_status()
        new_token_data = response.json()
        logger.info("Successfully refreshed Fitbit token.")
        return new_token_data
    except requests.exceptions.RequestException as e:
        # Log the error if the token refresh fails
        logger.error(f"Failed to refresh Fitbit token: {e.response.text if e.response else e}")
        return None

def get_valid_fitbit_adapter(request: Request) -> FitbitAdapter:
    """
    Dependency that provides a FitbitAdapter with a valid (refreshed if needed) token.
    It retrieves token details from the session and handles the refresh flow.
    """
    logger.info("--- Entering get_valid_fitbit_adapter ---")
    
    # Log the entire session content to see what's available
    logger.info(f"Session content: {request.session}")

    # Retrieve token details from the session
    access_token = request.session.get('fitbit_access_token')
    refresh_token = request.session.get('fitbit_refresh_token')
    expires_at = request.session.get('fitbit_token_expires_at', 0)

    logger.info(f"Retrieved access_token from session: {'Yes' if access_token else 'No'}")
    logger.info(f"Retrieved refresh_token from session: {'Yes' if refresh_token else 'No'}")

    # Raise an error if the user is not authenticated with Fitbit
    if not all([access_token, refresh_token]):
        logger.error("Authentication failed: access_token or refresh_token missing from session.")
        raise HTTPException(status_code=401, detail="User not authenticated with Fitbit.")

    # Refresh token if it's expired or will expire in the next 5 minutes (300 seconds)
    if time.time() > expires_at - 300:
        logger.info("Token is expired or close to expiring. Attempting refresh.")
        new_token_data = _refresh_fitbit_token(refresh_token)
        if not new_token_data:
            logger.error("Token refresh failed.")
            raise HTTPException(status_code=401, detail="Could not refresh Fitbit token. Please re-authenticate to reconnect your account.")
        
        # Update session with new token info
        _update_session_with_tokens(request, new_token_data)
        access_token = new_token_data["access_token"]
        logger.info("Token refresh successful. Proceeding with new access token.")
    else:
        logger.info("Token is valid and not expired.")
    
    logger.info("--- Exiting get_valid_fitbit_adapter ---")
    return FitbitAdapter(access_token=access_token)
def generate_pkce_codes():
    """Generates a code_verifier and a code_challenge for the PKCE flow."""
    code_verifier = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).decode('utf-8').replace('=', '')
    return {"verifier": code_verifier, "challenge": code_challenge}

#-------- Routes--------
@router.get("/login")
def login_to_fitbit(request: Request):
    
    # Clear any old session data to ensure a fresh login attempt
    request.session.pop('fitbit_pkce_verifier', None)
    request.session.pop('fitbit_oauth_state', None)

    # Generate the PKCE codes and state
    pkce_codes = generate_pkce_codes()
    state = secrets.token_urlsafe(16)

    # Store the verifier and state in the session to verify in the callback
    request.session['fitbit_pkce_verifier'] = pkce_codes["verifier"]
    request.session['fitbit_oauth_state'] = state

    # The scope parameter specifies the data we want to access from the Fitbit API
    scope = FITBIT_SCOPE

    # Build the authorization URL with the PKCE codes and state
    base_auth_url = (
        f"https://www.fitbit.com/oauth2/authorize?client_id={settings.FITBIT_CLIENT_ID}"
        f"&response_type=code"
        f"&code_challenge={pkce_codes['challenge']}"
        f"&code_challenge_method=S256"
        f"&scope={scope.replace(' ', '+')}"
        f"&state={state}"
    )

    # The prompt parameter forces the login and consent screens for demo purposes
    auth_url = f"{base_auth_url}&prompt=login+consent"

    return RedirectResponse(url=auth_url, status_code=302)

@router.get("/callback")
def handle_fitbit_callback(request: Request):
    """
    Handles the redirect from Fitbit after user authorization.
    Exchanges the authorization code for an access token.
    """
    # Get the authorization code and state from the query parameters
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    stored_state = request.session.get('fitbit_oauth_state')
    code_verifier = request.session.get('fitbit_pkce_verifier')

    # Security check: ensure the state matches to prevent CSRF attacks
    if not state or state != stored_state:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?fitbit_status=error_state")
    if not code:
        return {"error": "Authorization code not found."}

    # Exchange the authorization code for an access token
    token_url = "https://api.fitbit.com/oauth2/token"
    payload = {
        "client_id": settings.FITBIT_CLIENT_ID,
        "grant_type": "authorization_code",
        "redirect_uri": settings.REDIRECT_URL,
        "code": code,
        "code_verifier": code_verifier
    }

    # Use the client ID and secret to authenticate the request
    auth_header = requests.auth.HTTPBasicAuth(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
    try:
        # Send the request to the Fitbit API to exchange the code for an access token
        response = requests.post(token_url, auth=auth_header, data=payload)
        response.raise_for_status()
        token_data = response.json()

        if "access_token" not in token_data or "refresh_token" not in token_data:
            logger.error(f"Incomplete token data received from Fitbit: {token_data}")
            raise HTTPException(status_code=500, detail="Incomplete token data received from Fitbit.")

        _update_session_with_tokens(request, token_data)

        return RedirectResponse(url=f"{settings.FRONTEND_URL}?fitbit_status=success")
    except requests.exceptions.RequestException as e:
        error_message = f"Error exchanging code for token: {e}"
        # Check if the exception has a response object before accessing it
        if e.response is not None:
            error_message += f" - {e.response.text}"
        logger.error(error_message)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}?fitbit_status=error_token")

@router.get("/get-live-hrv")
def get_live_hrv_data(request: Request, fitbit_adapter: FitbitAdapter = Depends(get_valid_fitbit_adapter)):
    """
    Uses a valid access token to initialize the FitbitAdapter and fetch
    live HRV data from the Fitbit API, or returns fake data if enabled.
    """
    if settings.FAKE_HRV_DATA:
        # Return a random HRV value between 60 and 100, simulating a real response structure
        fake_hrv = [{"timestamp": time.time(), "hrv_value": random.randint(60, 100)}]
        return {"status": "success", "data": fake_hrv}
    try:
        # Check if the user is authenticated with Fitbit
        if not fitbit_adapter.connect():
            raise HTTPException(status_code=401, detail="Failed to connect to Fitbit API. Token may be invalid or expired.")

        # Fetch the HRV data from the Fitbit API
        hrv_data = fitbit_adapter.fetch_data()
        
        # An empty list is a valid, successful response. Always return the standard structure.
        return {"status": "success", "data": hrv_data}
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching data.")

@router.get("/status")
def get_fitbit_status(request: Request):
    """
    Checks the server-side session to see if a valid Fitbit access token exists.
    """
    # If the access token is in the user's session, they are connected.
    if request.session.get('fitbit_access_token'):
        return {"status": "connected"}
    else:
        return {"status": "disconnected"}
