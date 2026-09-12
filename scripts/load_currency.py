"""Download BTC data for a fixed date from the fawazahmed0 currency API."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL_TEMPLATE = (
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}"
    "/v1/currencies/{currency}.json"
)

CURRENCY = "btc"
DATE = "2026-09-01"
OUTPUT_DIR = Path("scripts/data")


def build_url(currency: str, date: str) -> str:
    """Return the API URL for one currency on one date."""
    return URL_TEMPLATE.format(date=date, currency=currency)


def download_json(url: str) -> object:
    """Download and decode a JSON response."""
    request = Request(url, headers={"User-Agent": "currency-loader/1.0"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def write_json(data: object, output_path: Path) -> None:
    """Write JSON atomically so an interrupted download does not corrupt output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    try:
        temporary_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    """Download the fixed currency and date, then write it under OUTPUT_DIR."""
    url = build_url(CURRENCY, DATE)
    output_path = OUTPUT_DIR / DATE / f"{CURRENCY}.json"

    try:
        data = download_json(url)
        write_json(data, output_path)
    except (
        OSError,
        HTTPError,
        URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        # Exit non-zero so a scheduler does not treat a failed download as
        # a successful run.
        sys.exit(f"Error: {error}")

    print(f"Loaded {url}")
    print(f"Wrote  {output_path}")


if __name__ == "__main__":
    main()
