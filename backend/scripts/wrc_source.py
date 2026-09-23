"""Shared helpers for tracking USDA Forest Service Wildfire Risk to
Communities (WRC) data currency.

USDA doesn't expose a version-check API, but the download page at
WRC_DOWNLOAD_PAGE is a stable URL that always links to whatever the
current bulk-download file is — and that file's own name is date-stamped
(e.g. wrc_download_20260415.xlsx). So "is there a new release" reduces to
"does the linked filename differ from the one we last used," which is
exactly what check_wrc_update.py checks, and what fetch_static_layers.py
records after a successful pull.

Verified cadence (from wildfirerisk.org's own FAQ, checked 2026-09-23):
the model itself is only substantially revised every 2-4 years (2020,
2024, "planned for 2026") — so a monthly check is more than sufficient to
catch a new release promptly without polling a slow-moving source.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx

WRC_DOWNLOAD_PAGE = "https://wildfirerisk.org/download/"
XLSX_URL_PATTERN = re.compile(
    r"https://wildfirerisk\.org/wp-content/uploads/\d{4}/\d{2}/wrc_download_(\d{8})\.xlsx"
)

META_PATH = Path(__file__).resolve().parent.parent / "data" / "wrc_source_meta.json"


class WrcSourceError(Exception):
    pass


def discover_current_download_url(client: httpx.Client | None = None) -> str:
    """Fetches the WRC download page and returns the currently-linked
    .xlsx URL. Raises WrcSourceError if the page is unreachable or its
    markup no longer matches the expected pattern (better to fail loudly
    than silently report "no update" forever)."""
    owns_client = client is None
    client = client or httpx.Client(timeout=30.0, follow_redirects=True)
    try:
        resp = client.get(WRC_DOWNLOAD_PAGE, headers={"User-Agent": "EmberReady-DataCheck/1.0"})
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise WrcSourceError(f"Could not reach {WRC_DOWNLOAD_PAGE}: {exc}") from exc
    finally:
        if owns_client:
            client.close()

    match = XLSX_URL_PATTERN.search(resp.text)
    if not match:
        raise WrcSourceError(
            f"Could not find a wrc_download_*.xlsx link on {WRC_DOWNLOAD_PAGE} — "
            "the page markup may have changed."
        )
    return match.group(0)


def vintage_from_url(url: str) -> str:
    """Turns .../wrc_download_20260415.xlsx into '2026-04-15'."""
    match = XLSX_URL_PATTERN.search(url)
    if not match:
        return "unknown"
    raw = match.group(1)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def load_known_source() -> dict | None:
    if not META_PATH.exists():
        return None
    with META_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_known_source(download_url: str) -> dict:
    meta = {
        "download_url": download_url,
        "vintage": vintage_from_url(download_url),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    with META_PATH.open("w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    return meta
