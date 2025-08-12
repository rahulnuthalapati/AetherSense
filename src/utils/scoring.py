def calculate_coherence(breath_rate: int, hrv: int) -> float:
    # Assume optimal breath_rate = 12–18, hrv = 60–100
    breath_score = max(0, 1 - abs(breath_rate - 16) / 10)
    hrv_score = min(hrv / 100, 1)
    coherence = round((0.5 * breath_score + 0.5 * hrv_score) * 100, 2)
    return coherence
