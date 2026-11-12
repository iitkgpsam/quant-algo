from __future__ import annotations
import hashlib, time
from dataclasses import dataclass
from typing import Callable, Optional
from .config import live_enabled
from .execlog import ExecutionLog
from .risk import RiskGuard, RiskRejected

class DuplicateOrder(Exception):
    pass

class LiveBlocked(Exception):
    pass

def signal_key(strategy: str, symbol: str, side: str, bar_ts: str, tag: str = "") -> str:
    """Same signal on same bar => same key => sent at most once."""
    return hashlib.sha256(f"{strategy}|{symbol}|{side}|{bar_ts}|{tag}".encode()).hexdigest()[:24]

class ReentryController:
    """Re-entry rules come from the owner's spec; limits are explicit, never defaulted."""
    def __init__(self, max_reentries: int, cooldown_s: float):
        self.max, self.cool = max_reentries, cooldown_s
        self._n: dict[str, int] = {}
        self._last_exit: dict[str, float] = {}

    def on_exit(self, symbol: str, now: float):
        self._last_exit[symbol] = now

    def allowed(self, symbol: str, now: float) -> bool:
        if self._n.get(symbol, 0) >= self.max:
            return False
        return now - self._last_exit.get(symbol, -1e18) >= self.cool

    def on_reentry(self, symbol: str):
        self._n[symbol] = self._n.get(symbol, 0) + 1

@dataclass
class OrderGateway:
    """Single choke point for every order. send_fn = OpenAlgo placeorder call."""
    send_fn: Callable[..., dict]
    risk: RiskGuard
    log: ExecutionLog
    analyzer_mode: bool = True            # PAPER by default
    clock: Callable[[], float] = time.time

    def __post_init__(self):
        self._seen: set[str] = set()

    def place(self, *, strategy, symbol, side, qty, price, bar_ts, opens_position=True,
              closes_position=False, signal_t0: Optional[float] = None, tag="", **extra) -> dict:
        if not self.analyzer_mode and not live_enabled():
            self.log.write("blocked_live", strategy=strategy, symbol=symbol)
            raise LiveBlocked("LIVE not enabled; run in Analyzer/PAPER mode")
        key = signal_key(strategy, symbol, side, bar_ts, tag)
        if key in self._seen:
            self.log.write("duplicate_blocked", key=key, strategy=strategy, symbol=symbol)
            raise DuplicateOrder(key)
        now = self.clock()
        try:
            self.risk.check(qty, price, opens_position, now)
        except RiskRejected as e:
            self.log.write("risk_rejected", key=key, reason=str(e), strategy=strategy, symbol=symbol)
            raise
        self._seen.add(key)                      # reserve before send: no double-fire on retry
        self.log.write("order_sent", key=key, strategy=strategy, symbol=symbol, side=side, qty=qty,
                       price=price, analyzer=self.analyzer_mode)
        t_send = time.perf_counter()
        try:
            resp = self.send_fn(strategy=strategy, symbol=symbol, action=side, quantity=qty, **extra)
        except Exception as e:
            self.log.write("order_error", key=key, error=repr(e))
            raise                                  # key stays reserved: owner reviews before any retry
        ack_ms = (time.perf_counter() - t_send) * 1000
        rec = {"send_to_ack_ms": round(ack_ms, 3)}
        if signal_t0 is not None:
            rec["signal_to_ack_ms"] = round((time.perf_counter() - signal_t0) * 1000, 3)
        self.log.write("order_ack", key=key, response=resp, **rec)
        self.risk.commit(opens_position, closes_position, now)
        return resp
