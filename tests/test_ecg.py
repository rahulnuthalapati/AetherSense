import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app # Import your main FastAPI app instance

# Create a client to make requests to your app
client = TestClient(app)

# --- 1. Happy Path Tests (CSV & JSON) ---

@patch('requests.post')
def test_upload_csv_happy_path(mock_post):
    """
    Tests the successful upload of a valid CSV file.
    Asserts that the file is processed and the correct number of rows are ingested.
    """
    # Mock the response from the event-logger service to avoid real network calls
    mock_post.return_value.raise_for_status.return_value = None
    
    # The sample CSV file has 9 unique, valid records
    file_path = "data/sample_egc_upload.csv" # Make sure this file is in your project's root or provide the correct path
    
    with open(file_path, "rb") as f:
        response = client.post("/ecg/upload", files={"file": ("sample.csv", f, "text/csv")})
        
    # Assertions
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    assert json_response["rows_ingested"] == 9
    assert json_response["rows_dropped"] == 0
    # Check that our mock was called 9 times, once for each valid record
    assert mock_post.call_count == 9

@patch('requests.post')
def test_upload_json_happy_path(mock_post):
    """
    Tests the successful upload of a valid JSON file.
    """
    mock_post.return_value.raise_for_status.return_value = None
    
    file_path = "data/sample_egc_upload.json" # Make sure this file is in your project's root
    
    with open(file_path, "rb") as f:
        response = client.post("/ecg/upload", files={"file": ("sample.json", f, "application/json")})
        
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    # The sample JSON file also has 9 unique records
    assert json_response["rows_ingested"] == 9
    assert json_response["rows_dropped"] == 0
    assert mock_post.call_count == 9

# --- 2. Malformed Rows Test ---

@patch('requests.post')
def test_malformed_rows_are_dropped(mock_post):
    """
    Tests that rows with missing essential data (like timestamp or signal) are dropped
    and the summary counts are correct.
    """
    mock_post.return_value.raise_for_status.return_value = None
    
    # Create a malformed CSV in memory
    malformed_csv_data = (
        "timestamp,signal,value,unit\n"
        "2025-08-17T17:00:00Z,ecg,0.8,mV\n"  # Valid
        ",ecg,0.9,mV\n"                     # Invalid (missing timestamp)
        "2025-08-17T17:00:02Z,,0.9,mV\n"   # Invalid (missing signal)
        "2025-08-17T17:00:03Z,ecg,1.0,mV\n"  # Valid
    )
    
    response = client.post(
        "/ecg/upload",
        files={"file": ("malformed.csv", malformed_csv_data, "text/csv")}
    )
        
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    # Expect 2 rows to be ingested and 2 to be dropped
    assert json_response["rows_ingested"] == 2
    assert json_response["rows_dropped"] == 2
    assert mock_post.call_count == 2 # API should only be called for the valid rows

# --- 3. Deduplication and Sorting Test ---

@patch('requests.post')
def test_deduplication_and_sorting(mock_post):
    """
    Tests that duplicate rows are dropped. While we can't test sorting without
    the GET endpoint, we can confirm that duplicates are not ingested.
    """
    mock_post.return_value.raise_for_status.return_value = None
    
    # Create a CSV with unsorted and duplicate data
    duplicate_csv_data = (
        "timestamp,signal,value\n"
        "2025-08-17T17:00:02Z,ecg,0.9\n"   # Later timestamp, first in file
        "2025-08-17T17:00:00Z,ecg,0.8\n"   # Earlier timestamp
        "2025-08-17T17:00:00Z,ecg,0.8\n"   # Exact duplicate
        "2025-08-17T17:00:01Z,r_peak,\n"
    )
    
    response = client.post(
        "/ecg/upload",
        files={"file": ("duplicates.csv", duplicate_csv_data, "text/csv")}
    )
        
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    # Original file has 4 rows, but only 3 are unique.
    assert json_response["rows_ingested"] == 3
    assert json_response["rows_dropped"] == 1 # 1 row was dropped by pandas dedup
    assert mock_post.call_count == 3