from pydantic import BaseModel
from typing import Optional

class BreathCheckIn(BaseModel):
    user_id: str
    text: str
    breath_rate: int
    hrv: int

class BreathResponse(BaseModel):
    coherence_score: float
    message: str
