"""Red Bar RB5/RB30 -- SCAFFOLD ONLY.
Refuses to start until the owner supplies and approves every rule in spec.template.yaml.
The signal logic is intentionally NOT implemented: the exact rules have not been provided."""
from ..spec import load_spec

REQUIRED = ["variant", "instruments", "exchange", "red_bar_definition", "entry_rule", "stop_loss_rule",
            "target_rule", "session_window", "square_off_time", "position_size", "product", "reentry",
            "risk_limits"]

def load(path: str) -> dict:
    return load_spec(path, REQUIRED)

def on_bar(spec: dict, bar: dict):
    raise NotImplementedError("Red Bar signal rules pending owner-approved specification")
