# 🧘 Breath-Aware AI Agent (FastAPI)

This project implements a lightweight **emotionally-aware AI backend**. The system is designed to process emotional check-ins and provide coherence-aware feedback based on biometric signals like breath rate and HRV (heart rate variability).

---

## ✨ Features

* `POST /breath-check-in` endpoint to log user check-ins
* Calculates a **coherence score** from breath rate and HRV
* Generates AI-driven **emotionally sensitive responses**
* Includes a **memory module** that detects breath rate trends (e.g., rising breath rate)
* Modular, readable FastAPI codebase

---

## 🏗 Architecture

```
.
├── agent.py      # Handles AI message generation using LangChain + OpenAI
├── main.py             # FastAPI app with endpoint logic
├── memory.py           # Stores last 3 check-ins per user (in-memory)
├── models.py           # Pydantic schemas for request/response
├── scoring.py          # Coherence score logic based on breath + HRV
├── requirements.txt    # Python package requirements
└── README.md           # You're here
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

4. **Set your OpenAI API key**

```bash
export OPENAI_API_KEY=your_openai_key_here  # Or add to .env
```

5. **Run the server**

```bash
uvicorn main:app --reload
```

The server will run at `http://localhost:8000`

---

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
* UI layer for dashboarding

---

## 👨‍💻 Author

Shaik Mohammed
\[shaik.md.zubaidi@gmail.com]
