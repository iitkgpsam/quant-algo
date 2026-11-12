from __future__ import annotations
import json, os, threading, time

class ExecutionLog:
    """Append-only JSONL. One line per event with monotonic latency stamps (ns)."""
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._lock = threading.Lock()

    def write(self, event: str, **fields):
        rec = {"ts": time.time(), "event": event, **fields}
        with self._lock, open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

def latency_summary(path: str) -> dict:
    """Percentiles of signal->ack ms from 'order_ack' events. Measured, never assumed."""
    xs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("event") == "order_ack" and "signal_to_ack_ms" in r:
                xs.append(r["signal_to_ack_ms"])
    if not xs:
        return {"n": 0}
    xs.sort()
    q = lambda p: xs[min(len(xs) - 1, int(p * len(xs)))]
    return {"n": len(xs), "p50": q(.5), "p95": q(.95), "max": xs[-1]}
