from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from src.config import settings
from src.utils.models import BreathCheckIn, BreathResponse
from src.utils.scoring import calculate_coherence
from src.utils.memory import store_checkin, get_user_history
from src.agent import generate_response
from src.routes import ecg_routes, fitbit_routes
from src.logger import get_logger

logger = get_logger(__name__)

app = FastAPI()

# Add session middleware for handling session data (e.g., for OAuth state)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.APP_SECRET_KEY,
    https_only=False,
    same_site="lax",
)

#TODO: Will need to change the * to specific domains in production once we have the app deployed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the fitbit authentication routes
app.include_router(ecg_routes.router)
app.include_router(fitbit_routes.router)

@app.post("/breath-check-in", response_model=BreathResponse)
def breath_check_in(data: BreathCheckIn):
    # 1. Store check-in
    store_checkin(data.user_id, data.model_dump())

    # 2. Calculate coherence score
    score = calculate_coherence(data.breath_rate, data.hrv)

    # 3. Determine trend (bonus)
    history = get_user_history(data.user_id)
    if len(history) >= 3:
        trend_values = [entry['breath_rate'] for entry in history]
        is_rising = all(earlier < later for earlier, later in zip(trend_values, trend_values[1:]))
        trend_info = "User's breath rate has been rising over the last 3 check-ins." if is_rising else None
    else:
        trend_info = None


    # 4. Generate AI response
    response_msg = generate_response(
        data.text,
        score,
        trend=trend_info
    )
    logger.info(f"Generated response: {response_msg} and coherence score: {score}")
    return BreathResponse(coherence_score=score, message=response_msg)
