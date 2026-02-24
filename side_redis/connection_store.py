"""Persist named Redis connection configurations to ~/.sideredis/connections.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path.home() / ".sideredis"
_CONFIG_FILE = _CONFIG_DIR / "connections.json"


def _ensure_dir() -> None:
    """Ensure config directory exists."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _read_all() -> dict[str, Any]:
    """Read all connection configurations."""
    if not _CONFIG_FILE.exists():
        return {"connections": {}, "last_used": ""}
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        if "connections" not in data:
            data["connections"] = {}
        return data
    except (json.JSONDecodeError, OSError):
        return {"connections": {}, "last_used": ""}


def _write_all(data: dict[str, Any]) -> None:
    """Write all connection configurations."""
    _ensure_dir()
    _CONFIG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ---- Public API ----


def list_connections() -> dict[str, dict]:
    """Return {name: config_dict} for all saved connections."""
    return _read_all().get("connections", {})


def get_connection(name: str) -> dict | None:
    """Get a specific connection configuration by name."""
    return list_connections().get(name)


def save_connection(name: str, config: dict) -> None:
    """Save a connection configuration."""
    data = _read_all()
    data["connections"][name] = config
    _write_all(data)


def delete_connection(name: str) -> None:
    """Delete a connection configuration."""
    data = _read_all()
    data["connections"].pop(name, None)
    if data.get("last_used") == name:
        data["last_used"] = ""
    _write_all(data)


def get_last_used() -> str:
    """Get the name of the last used connection."""
    return _read_all().get("last_used", "")


def set_last_used(name: str) -> None:
    """Set the last used connection name."""
    data = _read_all()
    data["last_used"] = name
    _write_all(data)


def make_config(
    host: str = "localhost",
    port: int = 6379,
    db: int = 0,
    username: str = "",
    password: str = "",
) -> dict:
    """Create a connection configuration dictionary."""
    return {
        "host": host,
        "port": port,
        "db": db,
        "username": username,
        "password": password,
    }
