import pytest
from unittest.mock import patch
from main import app

# --- 1. Happy Path Tests (CSV & JSON) ---

@patch('requests.post')
def test_upload_csv_happy_path(mock_post, client):
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
def test_upload_json_happy_path(mock_post, client):
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
def test_malformed_rows_are_dropped(mock_post, client, malformed_csv_data):
    """
    Tests that rows with missing essential data (like timestamp or signal) are dropped
    and the summary counts are correct.
    """
    mock_post.return_value.raise_for_status.return_value = None
    
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
def test_deduplication_and_sorting(mock_post, client, duplicate_csv_data):
    """
    Tests that duplicate rows are dropped. While we can't test sorting without
    the GET endpoint, we can confirm that duplicates are not ingested.
    """
    mock_post.return_value.raise_for_status.return_value = None
    
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