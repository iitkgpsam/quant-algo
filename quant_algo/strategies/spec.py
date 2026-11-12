"""Strategy spec loader. The owner's approved rules live in a YAML file; any field left
null/missing is a hard error. No default is ever invented."""
from __future__ import annotations
import yaml

class SpecIncomplete(Exception):
    pass

def load_spec(path: str, required: list[str]) -> dict:
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    missing = [k for k in required if d.get(k) in (None, "", "TO_BE_SUPPLIED_BY_OWNER")]
    if missing:
        raise SpecIncomplete(f"Owner-approved values missing: {missing}")
    if not d.get("approved_by_owner"):
        raise SpecIncomplete("approved_by_owner must be true")
    return d
