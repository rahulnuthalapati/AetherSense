import json
import time
from typing import Any, Dict, Callable
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import requests

# Import your FastAPI app
from main import app

# ----------------------------- Core client ----------------------------------
@pytest.fixture
def client() -> TestClient:
    """Shared FastAPI TestClient."""
    return TestClient(app)

# ----------------------------- Time control ---------------------------------
@pytest.fixture
def fixed_time(monkeypatch) -> int:
    """Freeze time.time() for deterministic expiry math."""
    now = 1_725_000_000  # arbitrary fixed epoch
    monkeypatch.setattr(time, "time", lambda: now)
    return now

# ----------------------------- Session patch --------------------------------
class _SessionMockFactory:
    @staticmethod
    def build(backing: Dict[str, Any]) -> MagicMock:
        m = MagicMock()
        def _get(k, default=None): 
            return backing.get(k, default)
        def _setitem(k, v): 
            backing[k] = v
        def _getitem(k): 
            return backing[k]
        m.get.side_effect = _get
        m.__setitem__.side_effect = _setitem
        m.__getitem__.side_effect = _getitem
        m.update.side_effect = backing.update
        return m

@pytest.fixture
def session_state() -> Dict[str, Any]:
    """Per-test mutable dict that represents the user's session store."""
    return {}

@pytest.fixture(autouse=True)
def patch_request_session(monkeypatch, session_state):
    """Auto-patch fastapi.Request.session for all tests."""
    mock_session = _SessionMockFactory.build(session_state)
    monkeypatch.setattr("fastapi.Request.session", mock_session, raising=False)
    return mock_session

# ----------------------------- Token payloads --------------------------------
@pytest.fixture
def fitbit_token_success() -> Dict[str, Any]:
    return { "access_token": "access_abc", "refresh_token": "refresh_xyz", "expires_in": 3600 }

@pytest.fixture
def fitbit_token_missing_access() -> Dict[str, Any]:
    return { "refresh_token": "refresh_xyz", "expires_in": 3600 }

@pytest.fixture
def fitbit_token_refresh_success() -> Dict[str, Any]:
    return { "access_token": "access_refreshed", "refresh_token": "refresh_new", "expires_in": 3600 }

# ----------------------------- Session presets -------------------------------
@pytest.fixture
def fresh_session_state(session_state, fixed_time) -> Dict[str, Any]:
    session_state.update({
        "fitbit_access_token": "access_abc",
        "fitbit_refresh_token": "refresh_xyz",
        "fitbit_token_expires_at": fixed_time + 300,
        "fitbit_oauth_state": "state123",
        "fitbit_pkce_verifier": "pkce123",
    })
    return session_state

@pytest.fixture
def expired_session_state(session_state, fixed_time) -> Dict[str, Any]:
    session_state.update({
        "fitbit_access_token": "expired_access",
        "fitbit_refresh_token": "refresh_xyz",
        "fitbit_token_expires_at": fixed_time - 10,
        "fitbit_oauth_state": "state123",
        "fitbit_pkce_verifier": "pkce123",
    })
    return session_state

@pytest.fixture
def expired_refresh_session_state(session_state, fixed_time) -> Dict[str, Any]:
    session_state.update({
        "fitbit_access_token": "expired_access",
        "fitbit_refresh_token": "expired_refresh",
        "fitbit_token_expires_at": fixed_time - 10,
        "fitbit_oauth_state": "state123",
        "fitbit_pkce_verifier": "pkce123",
    })
    return session_state

# ----------------------------- HRV payloads ----------------------------------
@pytest.fixture
def hrv_payload_valid() -> Dict[str, Any]:
    return { "hrv": [{"value": {"deep": 80}, "timestamp": "2025-08-14T10:02:00Z"}] }

@pytest.fixture
def hrv_payload_empty() -> Dict[str, Any]:
    return {"hrv": []}

@pytest.fixture
def hrv_payload_all_malformed() -> Dict[str, Any]:
    return { "hrv": [{"value": {"deep": None}}, {"timestamp": None}] }

@pytest.fixture
def hrv_payload_mixed() -> Dict[str, Any]:
    return { "hrv": [{"value": {"deep": None}}, {"value": {"deep": 82}, "timestamp": "2025-08-14T10:03:00Z"}] }

# ----------------------------- ECG payloads ------------------------------------
@pytest.fixture
def malformed_csv_data() -> str:
    """CSV data with missing timestamp and signal."""
    return (
        "timestamp,signal,value,unit\n"
        "2025-08-17T17:00:00Z,ecg,0.8,mV\n"
        ",ecg,0.9,mV\n"
        "2025-08-17T17:00:02Z,,0.9,mV\n"
        "2025-08-17T17:00:03Z,ecg,1.0,mV\n"
    )

@pytest.fixture
def duplicate_csv_data() -> str:
    """CSV data with unsorted and duplicate records."""
    return (
        "timestamp,signal,value\n"
        "2025-08-17T17:00:02Z,ecg,0.9\n"
        "2025-08-17T17:00:00Z,ecg,0.8\n"
        "2025-08-17T17:00:00Z,ecg,0.8\n"
        "2025-08-17T17:00:01Z,r_peak,\n"
    )

# ----------------------------- HTTP response shim ----------------------------
class _Resp:
    def __init__(self, status_code: int, json_obj: Dict[str, Any]):
        self.status_code = status_code
        self._json = json_obj
        self.text = json.dumps(json_obj)
    def json(self) -> Dict[str, Any]: return self._json
    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise requests.exceptions.HTTPError(f"HTTP {self.status_code}", response=self)
@pytest.fixture
def make_response() -> Callable[[int, Dict[str, Any]], _Resp]:
    def _make(status: int, body: Dict[str, Any]) -> _Resp: return _Resp(status, body)
    return _make