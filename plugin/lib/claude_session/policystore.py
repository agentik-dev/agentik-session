"""Persistence for the budget policy."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from . import config, store
from .budget import Policy

POLICY_FILE = "policy.json"


def _path(name: str) -> Path:
    return config.STATE_DIR / name


def load_policy() -> Policy:
    p = _path(POLICY_FILE)
    if p.exists():
        try:
            d = json.loads(p.read_text())
            pol = Policy(
                reserve_pct=float(d.get("reserve_pct", 8.0)),
                notice_pct=float(d.get("notice_pct", 80.0)),
                winddown_pct=float(d.get("winddown_pct", 90.0)),
            )
            pol.validate()
            return pol
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            pass
    return Policy()


def save_policy(policy: Policy) -> None:
    policy.validate()
    config.ensure_dirs()
    store._write_private(_path(POLICY_FILE), json.dumps(asdict(policy), indent=2))
