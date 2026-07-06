"""Configuration loading for sabnzb-cli.

Config is resolved in this precedence order:
  1. an explicit ``--config <path>``
  2. ``./config.json`` in the current directory
  3. ``~/.config/sabnzb-cli/config.json``
Environment variables (SABNZBD_HOST, SABNZBD_PORT, SABNZBD_APIKEY,
SABNZBD_HTTPS) fill in or override any missing values.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "sabnzb-cli"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.json"
LOCAL_CONFIG_PATH = Path("config.json")


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class Config:
    host: str
    apikey: str
    port: int = 8080
    https: bool = False
    # Optional Cloudflare Access service-token headers, for reaching a
    # SABnzbd instance published behind a Cloudflare Access application.
    access_client_id: Optional[str] = None
    access_client_secret: Optional[str] = None

    @property
    def base_url(self) -> str:
        scheme = "https" if self.https else "http"
        default_port = 443 if self.https else 80
        if self.port == default_port:
            return f"{scheme}://{self.host}"
        return f"{scheme}://{self.host}:{self.port}"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api"

    @property
    def netloc(self) -> str:
        """Host for display, omitting the port when it's the scheme default."""
        default_port = 443 if self.https else 80
        return self.host if self.port == default_port else f"{self.host}:{self.port}"


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def find_config_path(explicit: Optional[str] = None) -> Optional[Path]:
    """Return the config file that should be used, or None if none exists."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            raise ConfigError(f"Config file not found: {p}")
        return p
    if LOCAL_CONFIG_PATH.is_file():
        return LOCAL_CONFIG_PATH
    if DEFAULT_CONFIG_PATH.is_file():
        return DEFAULT_CONFIG_PATH
    return None


def load_config(explicit: Optional[str] = None) -> Config:
    """Load and validate configuration from file and/or environment."""
    data: dict = {}
    path = find_config_path(explicit)
    if path is not None:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ConfigError(f"Could not read config {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise ConfigError(f"Config {path} must be a JSON object.")

    # Environment variables override / fill in file values.
    host = os.environ.get("SABNZBD_HOST", data.get("host"))
    apikey = os.environ.get("SABNZBD_APIKEY", data.get("apikey"))
    port = os.environ.get("SABNZBD_PORT", data.get("port", 8080))
    https = os.environ.get("SABNZBD_HTTPS")
    https = _as_bool(https) if https is not None else _as_bool(data.get("https", False))

    missing = [name for name, val in (("host", host), ("apikey", apikey)) if not val]
    if missing:
        raise ConfigError(
            "Missing required config: "
            + ", ".join(missing)
            + ".\n\nCreate a config file with:\n"
            "  sabnzb-cli --init\n\n"
            f"…then edit {DEFAULT_CONFIG_PATH} with your host and API key.\n"
            "(Find your API key in SABnzbd under Config → General → API Key.)"
        )

    try:
        port_int = int(port)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Invalid port: {port!r}") from exc

    access_id = os.environ.get("SABNZBD_ACCESS_CLIENT_ID",
                               data.get("access_client_id"))
    access_secret = os.environ.get("SABNZBD_ACCESS_CLIENT_SECRET",
                                   data.get("access_client_secret"))

    return Config(
        host=str(host), apikey=str(apikey), port=port_int, https=https,
        access_client_id=str(access_id) if access_id else None,
        access_client_secret=str(access_secret) if access_secret else None,
    )


def write_starter_config(path: Path = DEFAULT_CONFIG_PATH) -> Path:
    """Write a template config file if one does not already exist."""
    if path.exists():
        raise ConfigError(f"Config already exists at {path} — not overwriting.")
    path.parent.mkdir(parents=True, exist_ok=True)
    template = {
        "host": "192.168.1.10",
        "port": 8080,
        "apikey": "YOUR_API_KEY_HERE",
        "https": False,
    }
    path.write_text(json.dumps(template, indent=2) + "\n")
    return path
