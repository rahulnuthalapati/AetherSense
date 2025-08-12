from abc import ABC, abstractmethod
from typing import List, Dict

class DeviceAdapter(ABC):
    """
    An abstract base class that defines the standard interface for all
    wearable device adapters.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establishes and tests a connection to the device's API.
        Returns True if successful, False otherwise.
        """
        pass

    @abstractmethod
    def fetch_data(self) -> List[Dict]:
        """
        Fetches the latest data from the device API.
        This method should handle errors and retries.
        """
        pass

    @abstractmethod
    def normalize_data(self, raw_data: any) -> List[Dict]:
        """
        Converts the raw data from the API into the standard project schema
        (e.g., [{'timestamp': str, 'hrv_value': int}]).
        """
        pass