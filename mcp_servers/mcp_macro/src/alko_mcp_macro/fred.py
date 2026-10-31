"""FRED API client: observations as pandas Series, cached in memory for an hour.

The API key comes only from the FRED_API_KEY environment variable and is kept out of error messages.
Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

API_URL = "https://api.stlouisfed.org/fred/series/observations"
CACHE_SECONDS = 3600
_cache: dict[tuple, tuple[float, pd.Series]] = {}


class FredError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        raise FredError(
            "FRED_API_KEY is not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html and "
            "add FRED_API_KEY=<key> to the project's .env file (or export it), then restart the backend."
        )
    return key


def _redact(text: str, key: str) -> str:
    return text.replace(key, "***") if key else text


def series(series_id: str, units: str = "lin", start: str = "2010-01-01") -> pd.Series:
    """Observations for one series. `units` is a FRED transformation: lin, chg, pch, pc1 (% change a year ago)."""
    cache_key = (series_id, units, start)
    hit = _cache.get(cache_key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]

    key = api_key()
    query = urlencode(
        {
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "units": units,
            "observation_start": start,
        }
    )
    try:
        with urlopen(f"{API_URL}?{query}", timeout=30) as response:
            payload = json.load(response)
    except HTTPError as e:
        detail = ""
        try:
            detail = json.load(e).get("error_message", "")
        except Exception:
            pass
        raise FredError(
            _redact(f"FRED request for {series_id} failed (HTTP {e.code}). {detail}", key)
        ) from None
    except URLError as e:
        raise FredError(f"Could not reach FRED for {series_id}: {e.reason}") from None

    obs = payload.get("observations", [])
    values = pd.to_numeric(pd.Series({o["date"]: o["value"] for o in obs}), errors="coerce")  # "." = missing
    values.index = pd.to_datetime(values.index)
    result = values.dropna().astype(float)
    _cache[cache_key] = (time.monotonic(), result)
    return result


def many(requests: dict[str, tuple[str, str, str]]) -> dict[str, pd.Series]:
    """Fetch several series concurrently: {name: (series_id, units, start)}. A failed series comes back empty;
    if every series fails (e.g. an invalid key), the first error is raised instead."""
    api_key()  # fail fast, once, when the key is missing
    errors: list[FredError] = []

    def fetch(item):
        name, (sid, units, start) = item
        try:
            return name, series(sid, units, start)
        except FredError as e:
            errors.append(e)
            return name, pd.Series(dtype=float)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(pool.map(fetch, requests.items()))
    if requests and len(errors) == len(requests):
        raise errors[0]
    return results
