import pytest, os
from quant_algo.risk import RiskGuard, RiskLimits, RiskRejected
from quant_algo.orders import OrderGateway, DuplicateOrder, LiveBlocked, ReentryController
from quant_algo.execlog import ExecutionLog, latency_summary

L = RiskLimits(10, 1e6, 2, 1000, 5, 3)
def gw(tmp_path, **kw):
    sent = []
    g = OrderGateway(lambda **a: sent.append(a) or {"status": "success"}, RiskGuard(L), ExecutionLog(str(tmp_path / "e.jsonl")), **kw)
    return g, sent
def p(g, **o):
    a = dict(strategy="s", symbol="X", side="BUY", qty=1, price=100, bar_ts="t1"); a.update(o); return g.place(**a)

def test_unset_limits_rejected():
    with pytest.raises(ValueError): RiskGuard(RiskLimits())
def test_duplicate_blocked(tmp_path):
    g, sent = gw(tmp_path); p(g)
    with pytest.raises(DuplicateOrder): p(g)
    assert len(sent) == 1
def test_risk_qty_and_positions(tmp_path):
    g, _ = gw(tmp_path)
    with pytest.raises(RiskRejected): p(g, qty=11)
    p(g, bar_ts="a"); p(g, bar_ts="b")
    with pytest.raises(RiskRejected): p(g, bar_ts="c")
def test_daily_loss_halts(tmp_path):
    g, _ = gw(tmp_path); g.risk.record_pnl(-1000)
    with pytest.raises(RiskRejected): p(g)
def test_live_blocked_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("QA_LIVE_ENABLED", raising=False)
    g, sent = gw(tmp_path, analyzer_mode=False)
    with pytest.raises(LiveBlocked): p(g)
    assert not sent
def test_failed_send_keeps_key_reserved(tmp_path):
    def boom(**a): raise RuntimeError("net")
    g = OrderGateway(boom, RiskGuard(L), ExecutionLog(str(tmp_path / "e.jsonl")))
    with pytest.raises(RuntimeError): p(g)
    with pytest.raises(DuplicateOrder): p(g)
def test_reentry():
    r = ReentryController(1, 60); r.on_exit("X", 0)
    assert not r.allowed("X", 30) and r.allowed("X", 61)
    r.on_reentry("X"); assert not r.allowed("X", 999)
def test_latency_logged(tmp_path):
    import time
    g, _ = gw(tmp_path); p(g, signal_t0=time.perf_counter())
    assert latency_summary(str(tmp_path / "e.jsonl"))["n"] == 1
