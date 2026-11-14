"""Control panel of a hosted Python strategy, shown through the owner's own login.

A strategy that serves a small web page and command channel on 127.0.0.1 declares its port in a header comment
(utils/strategy_panel_port.py). This blueprint is only a door: it checks the signed-in owner, checks the strategy
is theirs and running, and forwards three fixed paths to that loopback port. It knows nothing about any strategy.

    GET  /python/<id>/panel/            the page
    GET  /python/<id>/panel/api/state   JSON state
    POST /python/<id>/panel/api/cmd     a command (needs the X-QA-Panel header, so a page on another site cannot send one)
"""

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
        return _page("The strategy is not running. Start it on the Python Strategies page, then reopen the panel.", 503)
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
        return _page("The strategy panel did not answer. It may still be starting; refresh in a few seconds.", 502)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith(PASS_TYPES):
        return _page("Unexpected answer from the strategy panel.", 502)
    return Response(r.content, r.status_code, {"Content-Type": ctype, "Cache-Control": "no-store"})
