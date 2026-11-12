from quant_algo.strategies.redbar.reference import Candle, ist_day, select_reference
from quant_algo.strategies.redbar.config import FIVE, MIN

D = ist_day("2026-11-12")
def mk(start, o, c, h=None, l=None):
    return Candle(start, o, h or max(o, c) + 1, l or min(o, c) - 1, c)

def series(colors):
    """5-min candles from 09:15; colors[i] 'R' red / 'G' green."""
    out = {}
    for i, col in enumerate(colors):
        t = D.open + i * FIVE
        out[t] = mk(t, 100, 99) if col == "R" else mk(t, 100, 101)
    return out

def test_rb5_first_red_from_0920():
    c = series("RGRRRRRRRR")          # 09:15 red is X (ignored), 09:20 green, 09:25 red
    s = select_reference("RB5", D, c, D.open + 60 * MIN)
    assert s.status == "LOCKED" and s.reference.candle_time == D.open + 2 * FIVE

def test_rb5_waits_and_blocks_on_gap():
    assert select_reference("RB5", D, {}, D.open + 3 * MIN).status == "WAITING"
    c = series("RGGG"); del c[D.open + 2 * FIVE]
    assert select_reference("RB5", D, c, D.open + 60 * MIN).status == "BLOCKED"

def test_mid_ignores_colour():
    c = series("G" * 50)
    s = select_reference("MID", D, c, D.open + 240 * MIN)
    assert s.status == "LOCKED" and s.reference.candle_time == D.open + 210 * MIN
    assert s.reference.locked_at == D.open + 240 * MIN

def test_fib_levels():
    c = series("RGRRRRRRRR"); r = select_reference("RB5", D, c, D.open + 60 * MIN).reference
    assert abs(r.fib560 - (r.low + 0.56 * r.range)) < 1e-9 and abs(r.fib440 - (r.low + 0.44 * r.range)) < 1e-9
