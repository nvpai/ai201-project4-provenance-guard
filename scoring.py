"""Confidence scoring: combine the two signals into one calibrated score
and map it to an attribution band.

confidence = AI-likelihood (0.0 = human, 1.0 = AI).
Weighting: LLM 0.6 / stylometrics 0.4 (LLM reads meaning; stylometrics is
noisier). Thresholds are false-positive averse — the AI band starts high so a
human is rarely flagged by accident.
"""
LLM_WEIGHT = 0.6
STYLE_WEIGHT = 0.4

AI_THRESHOLD = 0.70       # >= -> likely AI
HUMAN_THRESHOLD = 0.40    # <  -> likely human; between -> uncertain


def combine(llm_score, style_score):
    """Return the combined confidence (AI-likelihood), rounded to 3 dp."""
    return round(LLM_WEIGHT * llm_score + STYLE_WEIGHT * style_score, 3)


def classify(confidence):
    """Map a confidence score to one of three attribution bands."""
    if confidence >= AI_THRESHOLD:
        return "likely_ai"
    if confidence < HUMAN_THRESHOLD:
        return "likely_human"
    return "uncertain"
