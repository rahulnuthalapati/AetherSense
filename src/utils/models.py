from datetime import datetime
from pydantic import BaseModel
from typing import Any, Dict, Literal, Optional

class BreathCheckIn(BaseModel):
    user_id: str
    text: str
    breath_rate: int
    hrv: int

class BreathResponse(BaseModel):
    coherence_score: float
    message: str

class EGCRecord(BaseModel):
    timestamp: datetime
    signal: Literal["ecg", "r_peak", "st_elev", "st_depr", "marked_event"]
    value: Optional[float] = None
    unit: Optional[Literal["mV", "bpm"]] = None
    meta: Dict[str, Any]