"""Safety switches. LIVE trading is OFF unless BOTH conditions hold."""
import os

def live_enabled() -> bool:
    # Requires explicit owner opt-in. Default: never live.
    return os.getenv("QA_LIVE_ENABLED", "0") == "1" and os.getenv("QA_LIVE_CONFIRM", "") == "I_ACCEPT_LIVE_RISK"
