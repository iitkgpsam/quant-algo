"""Reference (Red Bar zone) selection from completed 5-minute candles. Pure; fail closed."""
from __future__ import annotations
import calendar, datetime as dt
from dataclasses import dataclass
from typing import Mapping, Optional
from .config import *

@dataclass(frozen=True)
class Candle:
    t: int          # start, epoch ms
    o: float; h: float; l: float; c: float

@dataclass(frozen=True)
class Day:
    date: str; open: int; close: int

def ist_day(date: str) -> Day:
    y, m, d = map(int, date.split("-"))
    midnight_utc = calendar.timegm((y, m, d, 0, 0, 0)) * 1000 - IST_OFFSET_MS
    return Day(date, midnight_utc + SESSION_OPEN_MIN * MIN, midnight_utc + SESSION_CLOSE_MIN * MIN)

@dataclass(frozen=True)
class Reference:
    id: str; zone: str; day: str; candle_time: int; locked_at: int
    high: float; low: float; range: float; fib560: float; fib440: float

@dataclass(frozen=True)
class Selection:
    status: str            # LOCKED | WAITING | BLOCKED | NONE
    reason: str = ""
    reference: Optional[Reference] = None

def _valid(c: Candle) -> bool:
    vals = (c.o, c.h, c.l, c.c)
    return all(isinstance(v, (int, float)) and v == v and v > 0 for v in vals) and c.h >= max(c.o, c.c) and c.l <= min(c.o, c.c)

def select_reference(zone: str, day: Day, candles5: Mapping[int, Candle], now: int) -> Selection:
    """RB5: first completed RED 5-min candle from 09:20. RB30: first completed RED 09:15-anchored 30-min
    candle from 09:45. MID: the 12:45-13:15 candle (colour NOT tested)."""
    span = FIVE if zone == "RB5" else 30 * MIN
    start = day.open + 210 * MIN if zone == "MID" else day.open + span
    end = start + span if zone == "MID" else day.close
    t = start
    while t + span <= end:
        parts = []
        for s in range(t, t + span, FIVE):
            if s + FIVE > now:
                return Selection("WAITING", f"{zone} candidate {t} has not completed")
            c = candles5.get(s)
            if c is None:
                return Selection("BLOCKED", f"missing completed 5-minute candle {s}: reference not guessed")
            if not _valid(c):
                return Selection("BLOCKED", f"invalid candle {s}: reference rejected")
            parts.append(c)
        if zone != "MID" and not (parts[-1].c < parts[0].o):
            t += span
            continue
        hi, lo = max(p.h for p in parts), min(p.l for p in parts)
        rng = hi - lo
        if not rng > 0:
            return Selection("BLOCKED", "the RED BAR has an invalid or zero range")
        return Selection("LOCKED", "", Reference(f"RB:{zone}:{day.date}:{t}", zone, day.date, t, t + span, hi, lo, rng,
                                                  lo + FIB_BUY * rng, lo + FIB_SELL * rng))
    return Selection("NONE", "no RED candle today") if now >= day.close else Selection("WAITING", "no RED candle yet")
