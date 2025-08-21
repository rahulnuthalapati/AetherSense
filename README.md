# 🧘 Breath-Aware AI Agent (FastAPI)

This project implements a lightweight **emotionally-aware AI backend**. The system is designed to process emotional check-ins and provide coherence-aware feedback based on biometric signals like breath rate and HRV (heart rate variability).

---

## ✨ Features

* `POST /breath-check-in` endpoint to log user check-ins
* Calculates a **coherence score** from breath rate and HRV
* Generates AI-driven **emotionally sensitive responses**
* Includes a **memory module** that detects breath rate trends (e.g., rising breath rate)
* Modular, readable FastAPI codebase
* **Fitbit API Integration** for secure user authentication and live data fetching.
* **Live Data Simulation** script to enable robust testing without a physical device.
* **Extensible Multi-Device Adapter** interface for easily adding support for other wearables.
* **ECG Data Ingestion** endpoint to accept and process raw ECG data from file uploads (CSV/JSON).

---

## 🏗 Architecture

```
.
├── src
│ ├── adapters
│ │ ├── base_adapter.py     # Abstract interface for all device adapters
│ │ └── fitbit_adapter.py   # Fitbit-specific implementation of the adapter
│ ├── routes
| | ├── ecg_routes.py       # Handles the ecg routes from the vercel app
│ │ └── fitbit_routes.py    # Handles Fitbit OAuth 2.0 authentication flow
│ ├── utils
│ │ ├── memory.py         # Stores last 3 check-ins per user (in-memory)
│ │ ├── models.py         # Pydantic schemas for request/response
│ │ └── scoring.py        # Coherence score logic based on breath + HRV
│ ├── agent.py              # Handles AI message generation using LangChain
│ ├── config.py             # Manages application settings (e.g., API keys)
│ └── main.py               # Main FastAPI app with endpoint logic
├── tools
│ ├── simulate_data.py      # Script to send sample data to the app
│ └── sample_hrv_data.json  # Sample data for the simulation script
├── tests
│ ├── test_ecg.py          # pytest cases for ecg routes
│ ├── test_fitbit.py       # pytest cases for fitbit routes
│ └── test_main.py         # pytest cases for base routes from main
├── .env                    # Environment variables (API keys, secrets)
├── requirements.txt        # Python package requirements
└── README.md               # You're here
```

---

## 📦 Setup Instructions

1. **Clone the repository**

```bash
git clone https://github.com/your-username/breath-agent.git
cd breath-agent
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Create and configure your .env file**
Create a file named .env in the root of the project and add the following keys. You will need to get these from the Fitbit and OpenAI developer portals.
```bash
# OpenAI API Key
OPENAI_API_KEY="your_openai_key_here"

# Fitbit Developer Credentials
FITBIT_CLIENT_ID="your_fitbit_client_id"
FITBIT_CLIENT_SECRET="your_fitbit_client_secret"

# Application Settings
APP_SECRET_KEY="generate_a_random_secret_string_for_sessions"
REDIRECT_URL="http://127.0.0.1:8000/fitbit/callback"
```

5. **Run the server**

```bash
uvicorn main:app --reload
```

The server will run at `http://localhost:8000`

---


## ⚡ API Endpoints

### ECG Data Ingestion API

This API provides endpoints for uploading and retrieving normalized ECG data.

#### Endpoints

  * **`POST /ecg/upload`**: Uploads a file containing ECG data.

      * **Body**: `multipart/form-data` containing the file.
      * **File Formats**: Accepts `.csv` and `.json` files.
      * **Query Parameters**:
          * `tz_override` (optional): A standard timezone name (e.g., `America/New_York`) to localize timestamps from the file before converting them to UTC. If omitted, timestamps are assumed to be in UTC.
      * **Success Response**:
        ```json
        {
          "status": "success",
          "rows_ingested": 9,
          "rows_dropped": 0
        }
        ```

  * **`GET /ecg/events`**: Retrieves formatted ECG events for a given time window.

      * **Query Parameters**:
          * `since` (required): The start of the time window in ISO 8601 format (e.g., `2025-08-17T17:00:00Z`).
          * `until` (required): The end of the time window in ISO 8601 format.

#### Normalized Data Schema

The application normalizes all uploaded data into the following Pydantic schema before it is logged.

```python
class EGCRecord(BaseModel):
    timestamp: datetime
    signal: Literal["ecg", "r_peak", "st_elev", "st_depr", "marked_event"]
    value: Optional[float] = None
    unit: Optional[Literal["mV", "bpm"]] = None
    meta: Dict[str, Any]
```

#### Field Mapping Table

The application can accept different file formats. The following table shows how incoming field names are mapped to the standardized `signal` field in the normalized schema.

| Incoming Field Name | Standardized `signal` Value |
| :--- | :--- |
| `R-peak` | `r_peak` |
| `ST Elevation` | `st_elev` |
| `ST Depression` | `st_depr` |
| `Marked Event` | `marked_event` |
| `Event Type` | (Varies) |
| `type` | (Varies) |


## 🔗 Fitbit Integration

To connect to a user's Fitbit account, the application uses the standard OAuth 2.0 flow:

1.  **Login:** Direct the user to `http://127.0.0.1:8000/fitbit/login`. This will redirect the user to the Fitbit website to log in and grant permissions.

2.  **Callback & Token Management:** After granting permission, the user is redirected back to the application. The backend securely exchanges the authorization code for an **access token** and a **refresh token**. These tokens are stored in the user's server-side session and are never exposed to the client.

3.  **Fetch Data & Auto-Refresh:** When you make a request to an endpoint like `/get-live-hrv`, the application automatically uses the stored access token. If the token has expired, it seamlessly uses the refresh token to get a new one in the background before fetching the data. This ensures continuous access without requiring the user to log in again.

So directly make a call to http://127.0.0.1:8000/fitbit/get-live-hrv to directly access the live hrv data.


## 🧪 How to Simulate Data
To test the application without a live Fitbit connection, you can use the simulation script to continuously feed it sample data.

Run the simulation:

```
python tools/simulate_data.py --simulate
```

This script will read from tools/sample_hrv_data.json and send a new POST request to the /breath-check-in endpoint every second, allowing you to test how the scoring and AI agent react under "live" conditions.


## 🧪 Example Trial Runs

### 📍 Check-In 1: Initial Discomfort

**Request:**

```json
{
  "user_id": "cx-12345",
  "text": "Feeling a bit off today.",
  "breath_rate": 20,
  "hrv": 50
}
```

**Response:**

```json
{
  "coherence_score": 55.0,
  "message": "I’m here for you. Let’s take a moment to check in with your breath..."
}
```

---

### 📍 Check-In 2: Subtle Tension

**Request:**

```json
{
  "user_id": "cx-12345",
  "text": "Still feeling some tension, not sure why.",
  "breath_rate": 22,
  "hrv": 47
}
```

**Response:**

```json
{
  "coherence_score": 43.5,
  "message": "Let’s take a moment to check in with your breath. If you’ve noticed it rising..."
}
```

---

### 📍 Check-In 3: Physical Tightness

**Request:**

```json
{
  "user_id": "cx-12345",
  "text": "I’m continuing to feel tight in my chest and short of breath.",
  "breath_rate": 24,
  "hrv": 38
}
```

**Response:**

```json
{
  "coherence_score": 29.0,
  "message": "Your breath rate has been rising. Let’s try a guided reset together..."
}
```

---

### 📍 Check-In 4: Sustained Stress

**Request:**

```json
{
  "user_id": "cx-12345",
  "text": "I’m continuing to feel tight in my chest and short of breath.",
  "breath_rate": 28,
  "hrv": 38
}
```

**Response:**

```json
{
  "coherence_score": 19.0,
  "message": "It sounds like you're going through a tough time... Let's take it one breath at a time."
}
```

---

## 📘 Notes

* Memory stores only **last 3 check-ins per user**
* Trend logic activates if breath rate is **rising consecutively**
* Coherence score = combination of breath rate proximity + HRV normalization
* AI model = `gpt-4o-mini` via LangChain

---

## 🚀 Future Improvements

* Persistent DB storage (instead of in-memory)
* Scheduled check-in reminders
* More nuanced trend detection (e.g., HRV drops over time)
* A UI layer for dashboarding and interacting with the app.
* Implement adapters for other devices like Apple Watch or Garmin.

---

## 👨‍💻 Author

Shaik Mohammed
\[shaik.md.zubaidi@gmail.com]
