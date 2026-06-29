"""Transparency labels shown to readers.

Three variants, chosen by the attribution band from scoring.classify().
Text is intentionally soft: it always says "estimate, not certainty" and points
to the appeal path, because a false accusation against a human is the worst
outcome.
"""


def make_label(confidence, attribution):
    """Return plain-language label text for a confidence score (0-1)."""
    pct = round(confidence * 100)
    if attribution == "likely_ai":
        return (
            f"🤖 This content is likely AI-generated. Our analysis found strong "
            f"signals of automated writing (confidence: {pct}%). This is an "
            f"automated estimate, not a certainty — the creator can appeal."
        )
    if attribution == "likely_human":
        return (
            f"✍️ This content appears to be human-written. We found no strong "
            f"signs of AI generation (confidence it is human: {100 - pct}%). "
            f"This is an automated estimate, not a guarantee."
        )
    return (
        f"❓ We're not sure who wrote this. Our signals were mixed, so we can't "
        f"confidently say whether it is AI-generated or human-written "
        f"(AI-likelihood: {pct}%). Treat this result with caution."
    )
