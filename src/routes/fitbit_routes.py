from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import requests, secrets, hashlib, base64

from src.config import settings
from src.adapters.fitbit_adapter import FitbitAdapter
from src.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/fitbit", tags=["Fitbit Authentication"])

token_auth_scheme = HTTPBearer()

def generate_pkce_codes():
    """Generates a code_verifier and a code_challenge for the PKCE flow."""
    code_verifier = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(hashed).decode('utf-8').replace('=', '')
    return {"verifier": code_verifier, "challenge": code_challenge}

@router.get("/login")
def login_to_fitbit(request: Request):
    request.session.pop('fitbit_pkce_verifier', None)
    request.session.pop('fitbit_oauth_state', None)
    pkce_codes = generate_pkce_codes()
    state = secrets.token_urlsafe(16)
    request.session['fitbit_pkce_verifier'] = pkce_codes["verifier"]
    request.session['fitbit_oauth_state'] = state
    scope = "heartrate profile"
    base_auth_url = (
        f"https://www.fitbit.com/oauth2/authorize?client_id={settings.FITBIT_CLIENT_ID}"
        f"&response_type=code"
        f"&code_challenge={pkce_codes['challenge']}"
        f"&code_challenge_method=S256"
        f"&scope={scope.replace(' ', '+')}"
        f"&state={state}"
    )
    auth_url = f"{base_auth_url}&prompt=login+consent"

    return RedirectResponse(url=auth_url, status_code=302)

@router.get("/callback")
def handle_fitbit_callback(request: Request):
    """
    Handles the redirect from Fitbit after user authorization.
    Exchanges the authorization code for an access token.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    stored_state = request.session.get('fitbit_oauth_state')
    code_verifier = request.session.get('fitbit_pkce_verifier')
    if not state or state != stored_state:
        return {"error": "Invalid authorization response."}
    if not code:
        return {"error": "Authorization code not found."}
    token_url = "https://api.fitbit.com/oauth2/token"
    payload = {
        "client_id": settings.FITBIT_CLIENT_ID,
        "grant_type": "authorization_code",
        "redirect_uri": settings.REDIRECT_URL,
        "code": code,
        "code_verifier": code_verifier
    }
    auth_header = requests.auth.HTTPBasicAuth(settings.FITBIT_CLIENT_ID, settings.FITBIT_CLIENT_SECRET)
    try:
        response = requests.post(token_url, auth=auth_header, data=payload)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data.get("access_token")
        return {"status": "success", "access_token": access_token}
    except requests.exceptions.RequestException as e:
        logger.error(f"Error exchanging code for token: {e.response.text}")
        return {"error": "Could not obtain access token from Fitbit."}

@router.get("/get-live-hrv")
def get_live_hrv_data(access_token: HTTPAuthorizationCredentials = Depends(token_auth_scheme)):
    """
    Uses a valid access token to initialize the FitbitAdapter and fetch
    live HRV data from the Fitbit API.
    """
    access_token = access_token.credentials
    try:
        fitbit_adapter = FitbitAdapter(access_token=access_token)
        if not fitbit_adapter.connect():
            raise HTTPException(status_code=401, detail="Failed to connect to Fitbit API. Token may be invalid or expired.")

        hrv_data = fitbit_adapter.fetch_data()
        if not hrv_data:
            return {"message": "No HRV data found for today."}
        return {"status": "success", "data": hrv_data}
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail="An unexpected error occurred while fetching data.")
