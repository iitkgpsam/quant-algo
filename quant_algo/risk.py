from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

class RiskRejected(Exception):
    pass

@dataclass(frozen=True)
class RiskLimits:
    """Every limit is explicit. None = not configured => the check is rejected
    at construction by RiskGuard unless allow_unset=True (tests only)."""
    max_order_qty: Optional[int] = None
    max_order_value: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_daily_loss: Optional[float] = None      # positive number, rupees
    max_orders_per_day: Optional[int] = None
    max_orders_per_minute: Optional[int] = None

class RiskGuard:
    def __init__(self, limits: RiskLimits, allow_unset: bool = False):
        missing = [k for k, v in limits.__dict__.items() if v is None]
        if missing and not allow_unset:
            raise ValueError(f"Risk limits not set by owner: {missing}")
        self.l = limits
        self.realized_pnl = 0.0
        self.orders_today = 0
        self.open_positions = 0
        self._minute_ts: list[float] = []
        self.halted = False

    def record_pnl(self, pnl: float):
        self.realized_pnl += pnl
        if self.l.max_daily_loss is not None and self.realized_pnl <= -abs(self.l.max_daily_loss):
            self.halted = True  # kill switch: no new entries for the day

    def check(self, qty: int, price: float, opens_position: bool, now: float) -> None:
        l = self.l
        if self.halted:
            raise RiskRejected("daily loss limit hit: trading halted")
        if l.max_order_qty is not None and qty > l.max_order_qty:
            raise RiskRejected(f"qty {qty} > max_order_qty {l.max_order_qty}")
        if l.max_order_value is not None and qty * price > l.max_order_value:
            raise RiskRejected("order value above limit")
        if opens_position and l.max_open_positions is not None and self.open_positions >= l.max_open_positions:
            raise RiskRejected("max open positions reached")
        if l.max_orders_per_day is not None and self.orders_today >= l.max_orders_per_day:
            raise RiskRejected("max orders per day reached")
        self._minute_ts = [t for t in self._minute_ts if now - t < 60]
        if l.max_orders_per_minute is not None and len(self._minute_ts) >= l.max_orders_per_minute:
            raise RiskRejected("max orders per minute reached")

    def commit(self, opens_position: bool, closes_position: bool, now: float):
        self.orders_today += 1
        self._minute_ts.append(now)
        if opens_position:
            self.open_positions += 1
        if closes_position and self.open_positions > 0:
            self.open_positions -= 1
