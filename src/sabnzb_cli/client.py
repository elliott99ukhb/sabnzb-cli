"""Minimal SABnzbd JSON API client."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

from .config import Config

REQUEST_TIMEOUT = 5.0  # seconds for normal polling calls
UPLOAD_TIMEOUT = 30.0  # seconds for uploading an .nzb file

# SABnzbd priority names → API integer values.
PRIORITY_MAP = {
    "default": -100,
    "paused": -2,
    "low": -1,
    "normal": 0,
    "high": 1,
    "force": 2,
}


class SabError(Exception):
    """Raised for connection problems or API-level errors."""


class SabClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._session = requests.Session()
        # If configured, send Cloudflare Access service-token headers on every
        # request so we pass the Access application in front of SABnzbd.
        if config.access_client_id and config.access_client_secret:
            self._session.headers.update({
                "CF-Access-Client-Id": config.access_client_id,
                "CF-Access-Client-Secret": config.access_client_secret,
            })

    def _request(self, do_request: Callable[[], requests.Response]) -> Dict[str, Any]:
        """Run a request callable and normalise errors into SabError."""
        try:
            resp = do_request()
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError as exc:
            raise SabError(
                f"Could not connect to SABnzbd at {self.config.base_url}. "
                "Is it running and reachable?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise SabError(
                f"Request to {self.config.base_url} timed out."
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise SabError(f"HTTP error from SABnzbd: {exc}") from exc
        except ValueError as exc:  # invalid JSON
            raise SabError(
                "SABnzbd returned an unexpected (non-JSON) response. "
                "Check the host, port and that this is a SABnzbd instance."
            ) from exc

        # SABnzbd signals API errors with {"status": false, "error": "..."}.
        if isinstance(data, dict) and data.get("status") is False:
            raise SabError(f"SABnzbd API error: {data.get('error', 'unknown error')}")
        return data

    def _get(self, mode: str, **params: Any) -> Dict[str, Any]:
        query = {
            "mode": mode,
            "output": "json",
            "apikey": self.config.apikey,
            **params,
        }
        return self._request(
            lambda: self._session.get(
                self.config.api_url, params=query, timeout=REQUEST_TIMEOUT
            )
        )

    # --- Reads -----------------------------------------------------------
    def get_queue(self) -> Dict[str, Any]:
        return self._get("queue").get("queue", {})

    def get_history(self, limit: int = 8) -> Dict[str, Any]:
        return self._get("history", limit=limit).get("history", {})

    # --- Whole-queue controls -------------------------------------------
    def pause(self) -> None:
        self._get("pause")

    def resume(self) -> None:
        self._get("resume")

    # --- Per-item controls ----------------------------------------------
    def pause_item(self, nzo_id: str) -> None:
        self._get("queue", name="pause", value=nzo_id)

    def resume_item(self, nzo_id: str) -> None:
        self._get("queue", name="resume", value=nzo_id)

    def delete_item(self, nzo_id: str, del_files: bool = False) -> None:
        self._get("queue", name="delete", value=nzo_id,
                  del_files=1 if del_files else 0)

    # --- Adding jobs -----------------------------------------------------
    @staticmethod
    def _resolve_priority(priority: Optional[str]) -> Optional[int]:
        if priority is None:
            return None
        try:
            return PRIORITY_MAP[priority.lower()]
        except KeyError:
            raise SabError(
                f"Unknown priority {priority!r}. Choose one of: "
                + ", ".join(PRIORITY_MAP)
            )

    def add_file(self, path: str, cat: Optional[str] = None,
                 priority: Optional[str] = None) -> Dict[str, Any]:
        """Upload a local .nzb file to SABnzbd."""
        p = Path(path).expanduser()
        if not p.is_file():
            raise SabError(f"No such .nzb file: {p}")
        params: Dict[str, Any] = {
            "mode": "addfile",
            "output": "json",
            "apikey": self.config.apikey,
            "nzbname": p.stem,
        }
        if cat:
            params["cat"] = cat
        resolved = self._resolve_priority(priority)
        if resolved is not None:
            params["priority"] = resolved

        with p.open("rb") as fh:
            files = {"name": (p.name, fh, "application/x-nzb")}
            return self._request(
                lambda: self._session.post(
                    self.config.api_url, params=params, files=files,
                    timeout=UPLOAD_TIMEOUT,
                )
            )

    def add_url(self, url: str, cat: Optional[str] = None,
                priority: Optional[str] = None) -> Dict[str, Any]:
        """Add a job from a URL that SABnzbd will fetch."""
        return self._get("addurl", **self._add_params(url, cat, priority))

    def add_local_file(self, path: str, cat: Optional[str] = None,
                       priority: Optional[str] = None) -> Dict[str, Any]:
        """Add an .nzb that already exists on the SABnzbd server's filesystem."""
        return self._get("addlocalfile", **self._add_params(path, cat, priority))

    def _add_params(self, name: str, cat: Optional[str],
                    priority: Optional[str]) -> Dict[str, Any]:
        params: Dict[str, Any] = {"name": name}
        if cat:
            params["cat"] = cat
        resolved = self._resolve_priority(priority)
        if resolved is not None:
            params["priority"] = resolved
        return params

    def add(self, target: str, cat: Optional[str] = None,
            priority: Optional[str] = None) -> Dict[str, Any]:
        """Add a job, routing by what ``target`` is.

        * an http(s) URL         → SABnzbd fetches it (addurl)
        * a file on this machine → uploaded to SABnzbd (addfile)
        * anything else          → treated as a path on the SABnzbd server
                                   (addlocalfile), e.g. /mnt/myraid/file.nzb
        """
        if target.startswith(("http://", "https://")):
            return self.add_url(target, cat, priority)
        if Path(target).expanduser().is_file():
            return self.add_file(target, cat, priority)
        return self.add_local_file(target, cat, priority)
