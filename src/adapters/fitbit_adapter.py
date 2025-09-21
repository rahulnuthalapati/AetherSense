import requests
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from src.adapters.base_adapter import DeviceAdapter
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


# --- Custom Exception Classes ---
class ApiConnectionError(Exception):
    """Custom exception for API connection failures."""
    pass

SCOPE = "heartrate profile"

class HRVEntry(BaseModel):
    timestamp: datetime = Field(..., description="ISO8601 timestamp of the HRV measurement")
    hrv_value: float = Field(..., description="HRV value (deep) as a float")
    
# --- Fitbit Adapter Implementation ---
class FitbitAdapter(DeviceAdapter):
    """
    Adapter for connecting to the Fitbit API, fetching, and validating HRV data.
    """
    def __init__(self, access_token: str = None):
        self.client_id = settings.FITBIT_CLIENT_ID
        self.client_secret = settings.FITBIT_CLIENT_SECRET
        self.access_token = access_token
        self.base_url = "https://api.fitbit.com/1/user/-"

        if not self.client_id or not self.client_secret:
            raise ValueError("FITBIT_CLIENT_ID and FITBIT_CLIENT_SECRET must be set in the .env file.")
    
    # Primarily using this connect method with profile API to check if authentication is working and API is reachable
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def connect(self) -> bool:
        """
        Tests the connection to the Fitbit API using the provided access token.
        """
        if not self.access_token:
            logger.error("Cannot connect without an access token.")
            return False
        
        try:
            #Using profile test connection to the Fitbit API and check if the token is valid
            response = requests.get(f"{self.base_url}/profile.json", headers=self._get_auth_headers())
            response.raise_for_status()
            print("response: ", response.json())
            logger.info("Successfully connected to Fitbit API.")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Fitbit API connection failed: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
        reraise=True
    )
    def fetch_data(self) -> List[Dict]:
        """
        Fetches the latest HRV data for the current day from the Fitbit API.
        This method automatically retries on failure.
        """
        if not self.access_token:
            raise ApiConnectionError("Cannot fetch data without an access token.")

        logger.info("Fetching daily HRV data from Fitbit...")
        #Using utc timezone to get the current date
        today = datetime.now(timezone.utc)
        formatted_date = today.strftime("%Y-%m-%d")

        # Fetch the HRV data for the current day from the Fitbit API
        response = requests.get(
            f"{self.base_url}/hrv/date/{formatted_date}.json",
            headers=self._get_auth_headers()
        )
        # Logging the profile to see if the data is being fetched
        logger.info("Response: ", response.json())
        response.raise_for_status()

        # Normalize the data to the standard application schema
        return self.normalize_data(response.json())

    def normalize_data(self, raw_data: Dict[str, Any]) -> List[Dict]:
        """
        Validates raw data and transforms it into the standard application schema.
        """
        cleaned_data = []
        hrv_entries = raw_data.get("hrv", [])
        
        logger.info(f"Received {len(hrv_entries)} HRV entries for validation.")

        for entry in hrv_entries:
            # Validating the data to ensure it is in the correct format
            if isinstance(entry, dict) and "value" in entry and "timestamp" in entry:
                hrv_value = entry["value"].get("deep")
                if hrv_value is not None:
                    try:
                        validated = HRVEntry(
                            timestamp=entry["timestamp"],
                            hrv_value=hrv_value
                        )
                        cleaned_data.append(validated.model_dump())
                    except Exception as e:
                        logger.warning(f"Validation failed for entry {entry}: {e}")
                else:
                    logger.warning(f"Discarding entry with missing 'deep' HRV value: {entry}")
            else:
                logger.warning(f"Discarding corrupted or malformed data entry: {entry}")
        
        logger.info(f"Successfully validated and cleaned {len(cleaned_data)} entries.")
        return cleaned_data

    def _get_auth_headers(self) -> Dict[str, str]:
        """A private helper method to create the authorization headers."""
        return {"Authorization": f"Bearer {self.access_token}"}