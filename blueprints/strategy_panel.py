"""Control panel of a hosted Python strategy, shown through the owner's own login.

A strategy that serves a small web page and command channel on 127.0.0.1 declares its port in a header comment
(utils/strategy_panel_port.py). This blueprint is only a door: it checks the signed-in owner, checks the strategy
is theirs and running, and forwards three fixed paths to that loopback port. It knows nothing about any strategy.

    GET  /python/<id>/panel/            the page
    GET  /python/<id>/panel/api/state   JSON state
    POST /python/<id>/panel/api/cmd     a command (needs the X-QA-Panel header, so a page on another site cannot send one)
"""

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Blueprint, Response, jsonify, request, session

from utils.httpx_client import get_httpx_client
from utils.logging import get_logger
from utils.session import check_session_validity
from utils.strategy_panel_port import panel_port_for_file

logger = get_logger(__name__)

strategy_panel_bp = Blueprint("strategy_panel", __name__, url_prefix="/python/<strategy_id>/panel")

ALLOWED = {("GET", ""), ("GET", "api/state"), ("POST", "api/cmd")}
MAX_BODY = 2048
TIMEOUT = 4.0
PASS_TYPES = ("text/html", "application/json")

# The panel is reachable at all times. While the strategy runs it is the strategy's own page. When the strategy is
# stopped (night, weekend, between sessions) the door shows the last page and the last data it saw, marked as stopped,
# and refuses commands. Nothing here comes from the browser: only what the strategy itself served is kept.
CACHE_DIR = Path("db") / "panel_cache"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_IST = timezone(timedelta(hours=5, minutes=30))
_last: dict[str, dict] = {}
_saved_at: dict[str, float] = {}
SAVE_EVERY = 60.0


def _cache_path(strategy_id: str):
    return CACHE_DIR / f"{strategy_id}.json" if _SAFE_ID.match(strategy_id or "") else None


def _remember(strategy_id: str, html=None, state=None) -> None:
    c = _last.setdefault(strategy_id, {})
    if html is not None:
        c["html"] = html
    if state is not None:
        c["state"] = state
        c["seen"] = time.time()
    now = time.time()
    path = _cache_path(strategy_id)
    if path and now - _saved_at.get(strategy_id, 0) >= SAVE_EVERY and c.get("html") and c.get("state"):
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(c), encoding="utf-8")
            _saved_at[strategy_id] = now
        except OSError:
            logger.warning("Strategy panel cache not saved")


def _recall(strategy_id: str) -> dict:
    c = _last.get(strategy_id)
    if c:
        return c
    path = _cache_path(strategy_id)
    try:
        if path and path.is_file():
            c = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(c, dict) and isinstance(c.get("html"), str) and isinstance(c.get("state"), dict):
                _last[strategy_id] = c
                return c
    except (OSError, ValueError):
        pass
    return {}


def _stopped_state(c: dict) -> dict:
    st = dict(c["state"])
    seen = datetime.fromtimestamp(c.get("seen", 0), _IST).strftime("%d %b %H:%M")
    st["banner"] = f"STRATEGY STOPPED. Showing the last data seen at {seen} IST. Commands are off until it runs again."
    st["offline"] = True
    return st


def _offline(strategy_id: str, method: str, sub: str):
    """What the door answers while the strategy is not running."""
    c = _recall(strategy_id)
    if method == "POST":
        return jsonify(status="error", message="The strategy is not running, so commands are off."), 409
    if sub == "api/state":
        if c:
            return Response(json.dumps(_stopped_state(c)), 200, {"Content-Type": "application/json", "Cache-Control": "no-store"})
        return jsonify(status="stopped", banner="STRATEGY NOT RUNNING. Nothing to show yet.", offline=True), 200
    if c:
        return Response(c["html"], 200, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"})
    return _page(
        "The strategy has not run yet, so there is nothing to show. Start it on the Python Strategies page, or wait "
        "for its scheduled start. This page then fills in by itself and stays available afterwards.",
        200,
    )


def _resolve(strategy_id: str, user_id: str):
    """(config, None) for the owner's own strategy, else (None, (response, status)). Imported late: the strategy
    module starts a scheduler on import and a door should not."""
    from blueprints.python_strategy import verify_strategy_ownership

    ok, res = verify_strategy_ownership(strategy_id, user_id, return_config=True)
    if not ok:
        return None, res
    return res, None


def _page(message: str, status: int) -> Response:
    html = (
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        "<title>Strategy panel</title><body style='font:16px system-ui;max-width:520px;margin:3rem auto;padding:0 1rem'>"
        f"<h2>Strategy panel</h2><p>{message}</p><p><a href='/python'>Back to Python Strategies</a></p></body>"
    )
    return Response(html, status, {"Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store"})


@strategy_panel_bp.route("/", defaults={"sub": ""}, methods=["GET"])
@strategy_panel_bp.route("/<path:sub>", methods=["GET", "POST"])
@check_session_validity
def panel(strategy_id, sub):
    method = request.method
    if (method, sub) not in ALLOWED:
        return _page("Not found.", 404)
    if method == "POST" and request.headers.get("X-QA-Panel") != "1":
        return jsonify(status="error", message="Missing panel header"), 403
    config, err = _resolve(strategy_id, session.get("user"))
    if err:
        return _page("This strategy is not yours or does not exist.", 403)
    port = panel_port_for_file(config.get("file_path", ""))
    if port is None:
        return _page("This strategy has no control panel.", 404)
    if not config.get("is_running"):
        return _offline(strategy_id, method, sub)
    body = request.get_data(cache=False)[: MAX_BODY + 1] if method == "POST" else None
    if body is not None and len(body) > MAX_BODY:
        return jsonify(status="error", message="Request too large"), 413
    try:
        r = get_httpx_client().request(
            method,
            f"http://127.0.0.1:{port}/{sub}",
            content=body,
            headers={"Content-Type": "application/json", "X-QA-Panel": "1"} if body is not None else None,
            timeout=TIMEOUT,
        )
    except Exception:
        logger.exception("Strategy panel upstream unreachable")
        if _recall(strategy_id):
            return _offline(strategy_id, method, sub)
        return _page("The strategy panel did not answer. It may still be starting; refresh in a few seconds.", 502)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith(PASS_TYPES):
        return _page("Unexpected answer from the strategy panel.", 502)
    if r.status_code == 200 and method == "GET":
        try:
            if sub == "":
                _remember(strategy_id, html=r.content.decode("utf-8"))
            elif sub == "api/state":
                data = json.loads(r.content)
                if isinstance(data, dict):
                    _remember(strategy_id, state=data)
        except (ValueError, UnicodeDecodeError):
            pass
    return Response(r.content, r.status_code, {"Content-Type": ctype, "Cache-Control": "no-store"})
