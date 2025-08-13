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

---

## 🏗 Architecture

```
.
├── src
│ ├── adapters
│ │ ├── base_adapter.py     # Abstract interface for all device adapters
│ │ └── fitbit_adapter.py   # Fitbit-specific implementation of the adapter
│ ├── routes
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

## 🔗 Fitbit Integration

To connect to a user's Fitbit account, the application uses the standard OAuth 2.0 flow:

Login: Direct the user to http://127.0.0.1:8000/fitbit/login. This will redirect them to the Fitbit website to log in and grant permissions.

Callback: After granting permission, the user will be redirected back to the REDIRECT_URL specified in your settings, where the application will securely exchange an authorization code for an access token.

Fetch Data: With a valid access token, you can make requests to endpoints like /get-live-hrv to fetch real-time data from the Fitbit API.


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
