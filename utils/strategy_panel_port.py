"""Which local port a hosted Python strategy serves its control panel on.

A strategy opts in with one comment near the top of its file:

    # openalgo-panel-port: 5157

The port must be in PANEL_PORT_RANGE (loopback only). Nothing else is read from the file.
"""

import re
from pathlib import Path

PANEL_PORT_RANGE = range(5100, 5200)
_HEADER = re.compile(r"^#\s*openalgo-panel-port:\s*(\d{4,5})\s*$")
_cache: dict[str, tuple[float, int | None]] = {}


def panel_port_for_file(path) -> int | None:
    """The declared panel port of a strategy file, or None. Cached by file modification time."""
    try:
        p = Path(path)
        mtime = p.stat().st_mtime
    except (OSError, TypeError, ValueError):
        return None
    key = str(p)
    hit = _cache.get(key)
    if hit and hit[0] == mtime:
        return hit[1]
    port = None
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 60:
                    break
                m = _HEADER.match(line.strip())
                if m and int(m.group(1)) in PANEL_PORT_RANGE:
                    port = int(m.group(1))
                    break
    except OSError:
        port = None
    if len(_cache) > 256:
        _cache.clear()
    _cache[key] = (mtime, port)
    return port
