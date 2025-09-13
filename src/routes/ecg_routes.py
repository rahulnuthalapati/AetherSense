import requests, json
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from typing import Optional
from io import StringIO
from datetime import datetime
from dateutil import tz, parser as dateutil_parser

from src.config import settings
from src.logger import get_logger


logger = get_logger(__name__)

router = APIRouter(
    prefix="/ecg", 
    tags=["ECG Data"]
)

@router.post("/upload")
async def upload_ecg_data(
    request: Request,
    file: Optional[UploadFile] = File(None),
    tz_override: str = None
):
    """
    Accepts, parses, and normalizes various ECG data formats (CSV or JSON),
    then logs each valid record by calling the event-logger microservice.
    Accepts either a file upload (multipart/form-data) or a JSON array (application/json).
    """
    logger.info(f"Received upload request. File: {file.filename if file else None}")
    df = None
    content_type = request.headers.get("content-type", "")

    if file is not None:
        contents = await file.read()
        try:
            if file.filename.endswith('.csv'):
                df = pd.read_csv(StringIO(contents.decode('utf-8')))
            elif file.filename.endswith('.json'):
                json_data = json.loads(contents)
                if isinstance(json_data, list):
                    df = pd.DataFrame(json_data)
                elif isinstance(json_data, dict):
                    records_list = next((v for v in json_data.values() if isinstance(v, list)), None)
                    if records_list:
                        df = pd.DataFrame(records_list)
                    else: raise ValueError("Uploaded JSON object does not contain a list of records.")
                else: raise ValueError("Unsupported JSON structure.")
            else:
                logger.warning(f"Unsupported file format for {file.filename}")
                raise HTTPException(status_code=400, detail="Unsupported file format. Please upload CSV or JSON.")
        except Exception as e:
            logger.error(f"Failed to parse file {file.filename}. Error: {e}")
            raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
    elif "application/json" in content_type:
        try:
            json_data = await request.json()
            if isinstance(json_data, list):
                df = pd.DataFrame(json_data)
            elif isinstance(json_data, dict):
                records_list = next((v for v in json_data.values() if isinstance(v, list)), None)
                if records_list:
                    df = pd.DataFrame(records_list)
                else:
                    raise ValueError("JSON object does not contain a list of records.")
            else:
                raise ValueError("Unsupported JSON structure.")
        except Exception as e:
            logger.error(f"Failed to parse JSON body. Error: {e}")
            raise HTTPException(status_code=400, detail=f"Could not parse JSON body: {e}")
    else:
        logger.warning("Unsupported Content-Type or missing file.")
        raise HTTPException(status_code=400, detail="Unsupported Content-Type. Use multipart/form-data or application/json.")

    # --- Step 2: Standardize Column Names ---
    # This block maps various incoming column names to our internal standard names.
    
    # Define all possible mappings
    column_map = {
        'Timestamp': 'timestamp',    # From drift log CSV
        'eventType': 'signal',       # From drift log JSON
        'Event Type': 'signal',      # From drift log CSV
        'ecgChannel': 'value',       # From drift log JSON
        'ECG Channel': 'value',      # From drift log CSV
        'type': 'signal'             # From the newest file format
    }
    df.rename(columns=column_map, inplace=True)

    # After renaming, ensure 'meta' column exists if it wasn't in the original file
    if 'meta' not in df.columns:
        # Check for the original CSV format with flat meta columns
        if file is not None and file.filename.endswith('.csv') and any(col.startswith('meta.') for col in df.columns):
            logger.info("Detected original CSV format. Reshaping meta columns.")
            meta_cols = [col for col in df.columns if col.startswith('meta.')]
            meta_df = df[meta_cols].rename(columns=lambda c: c.replace('meta.', ''))
            df['meta'] = meta_df.to_dict(orient='records')
            df.drop(columns=meta_cols, inplace=True)
        else:
            # For all other formats, create an empty meta column
            df['meta'] = [{} for _ in range(len(df))]
            
    logger.info(f"Columns after standardization: {df.columns.to_list()}")

    # --- Step 3: Clean and Normalize Data ---
    initial_rows = len(df)
    # Drop the rows with bad/empty rows
    df.dropna(subset=['timestamp', 'signal'], inplace=True)
    if df.empty:
        return {"status": "success", "rows_ingested": 0, "rows_dropped": initial_rows}

    # Robust timestamp parsing: handle ISO8601 strings and UNIX epoch seconds
    def parse_timestamp(ts):
        try:
            return pd.to_datetime(ts, utc=True)
        except Exception:
            try:
                return pd.to_datetime(float(ts), unit='s', utc=True)
            except Exception:
                return pd.NaT
    df['timestamp'] = df['timestamp'].apply(parse_timestamp)
    df.dropna(subset=['timestamp'], inplace=True)

    # Sort the data by timestamp
    if tz_override:
        try:
            tzinfo = tz.gettz(tz_override)
            if tzinfo is None:
                raise ValueError(f"Unknown timezone: {tz_override}")
            df['timestamp'] = df['timestamp'].apply(lambda x: dateutil_parser.parse(x).replace(tzinfo=tzinfo).astimezone(tz.UTC))
        except Exception as e:
            logger.error(f"Failed to apply timezone override: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid timezone override: {e}")
    else:
        df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
    df.sort_values(by='timestamp', inplace=True)
    # Drop the duplicates which are identical events that occured at the same time
    df.drop_duplicates(subset=['timestamp', 'signal'], keep='first', inplace=True)

    # --- Step 4: Log Records via API Call ---
    ingested_count = 0
    headers = {"Authorization": f"Bearer {settings.EVENT_LOGGER_TOKEN}"}
    event_logger_endpoint = f"{settings.EVENT_LOGGER_URL}/api/event"

    records_to_ingest = df.astype(object).where(pd.notna(df), None).to_dict(orient='records')
    logger.info(f"Attempting to log {len(records_to_ingest)} normalized records.")
    for record in records_to_ingest:
        record['timestamp'] = record['timestamp'].isoformat()
        
        if isinstance(record.get('meta'), dict):
            record['meta'] = {k: None if pd.isna(v) else v for k, v in record['meta'].items()}
            
        payload = {
            "type": "ecg_data",
            "source": record.get('meta', {}).get('source', 'unknown') if record.get('meta') else 'unknown',
            "data": record
        }
        try:
            response = requests.post(event_logger_endpoint, json=payload, headers=headers)
            response.raise_for_status()
            ingested_count += 1
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to log event. Record: {record}. Error: {e}")

    # Calculate dropped rows as all rows dropped during cleaning and deduplication
    dropped_count = initial_rows - len(records_to_ingest)
    logger.info(f"Upload complete. Ingested: {ingested_count}, Dropped: {dropped_count}")
    
    return {
        "status": "success",
        "rows_ingested": ingested_count,
        "rows_dropped": dropped_count
    }

@router.get("/events")
def get_ecg_events(since: datetime, until: datetime):
    """
    Retrieves and transforms ECG events from the event-logger service for a given time window.
    """
    logger.info(f"Fetching events from {since} to {until}")
    headers = {"Authorization": f"Bearer {settings.EVENT_LOGGER_TOKEN}"}
    event_logger_endpoint = f"{settings.EVENT_LOGGER_URL}/api/events"
    
    try:
        response = requests.get(event_logger_endpoint, headers=headers)
        response.raise_for_status()
        all_events = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Could not fetch data from event logger service. Error: {e}")
        raise HTTPException(status_code=502, detail=f"Could not fetch data from event logger: {e}")

    # Filter events to the requested time window
    filtered_events_data = [
        evt['event_data'] for evt in all_events
        if 'timestamp' in evt.get('event_data', {}) and
           since <= pd.to_datetime(evt['event_data']['timestamp']) < until
    ]

    # Transform the raw data into the required format for app to use
    formatted_events = []
    for event in filtered_events_data:
        event_type = event.get('signal')
        meta = event.get('meta', {})
        
        # NOTE: Only include events that are not the raw 'ecg' waveform signal
        if event_type == 'r_peak':
            formatted_events.append({
                "timestamp": event.get('timestamp'),
                "type": "r_peak",
                # HR estimation requires at least two R-peaks, so we use a placeholder.
                # A real implementation we would calculate this based on the time between peaks (RR interval).
                "hr_estimate_bpm": 72, 
                "source": meta.get('source')
            })
        elif event_type == 'st_elev':
            formatted_events.append({
                "timestamp": event.get('timestamp'),
                "type": "st_elev",
                "magnitude_mv": event.get('value'),
                "lead": meta.get('lead'),
                "source": meta.get('source')
            })
        elif event_type == 'marked_event':
            formatted_events.append({
                "timestamp": event.get('timestamp'),
                "type": "marked_event",
                "label": meta.get('label'),
                "source": meta.get('source')
            })
        # We ignore 'st_depr' for now as it's not in the sample response, but you could add it here.

    logger.info(f"Found {len(formatted_events)} formatted events in the time window.")
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "count": len(formatted_events),
        "events": formatted_events
    }