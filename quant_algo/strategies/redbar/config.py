"""Red Bar constants. Source: owner-approved rules as implemented in QUANT (13 Nov 2026 spec) plus
owner decisions for quant-algo. Nothing here is a tunable default invented by this project."""
IST_OFFSET_MS = 5 * 3600_000 + 30 * 60_000
MIN = 60_000
FIVE = 5 * MIN
SESSION_OPEN_MIN = 9 * 60 + 15          # 09:15 IST
SESSION_CLOSE_MIN = 15 * 60 + 30        # 15:30 IST
CUTOFF_AFTER_OPEN_MIN = 345             # no new entry from 15:00
SQUAREOFF_AFTER_OPEN_MIN = 360          # forced exit at 15:15
FIB_BUY, FIB_SELL = 0.56, 0.44
ENTRY_BUFFER = 3.0                      # SPOT points
STOP_POINTS = 10.0                      # initial stop, every entry (owner 12 Nov)
PROTECT_GAP = 5.0                       # Protect: 5-point gap, 1-point ratchet
TICK_MAX_AGE_MS = 8_000
ZONES = ("MID", "RB30", "RB5")          # also the tie-break order
PREMIUM_TARGET = {"NIFTY": 40.0, "SENSEX": 120.0}   # owner: TRUE NEAREST, no band
SUPPORTED_INDEXES = ("NIFTY", "SENSEX")
