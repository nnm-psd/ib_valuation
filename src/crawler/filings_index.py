"""
Discover ESEF filings for a given company via filings.xbrl.org.

filings.xbrl.org exposes a JSON:API-style index of every ESEF filing it has
mirrored from national OAMs (AMF for France, etc.). This module wraps that
index so the rest of the pipeline can ask "give me every annual report
filing for company X between year A and year B" without screen-scraping.

IMPORTANT: the exact query parameters below (filter[entity.name], etc.)
follow the documented JSON:API convention used by filings.xbrl.org, but
this sandbox cannot reach the live host to verify the current schema.
Run `python scripts/inspect_filings_api.py` (see scripts/) once you have
network access, print the raw response, and adjust the field names here
if the API has since changed shape.
"""
from __future__ import annotations

import requests
from dataclasses import dataclass

from config.settings import FILINGS_XBRL_ORG_API


@dataclass
class FilingRecord:
    entity_name: str
    country: str
    period_end: str
    filing_index_url: str   # the JSON metadata for this specific filing
    package_url: str        # the downloadable ESEF zip package


def search_filings(company_name: str, country: str = "FR", limit: int = 20) -> list[FilingRecord]:
    """
    Query filings.xbrl.org for all filings matching a company name.

    Parameters
    ----------
    company_name : free-text company name, e.g. "STMicroelectronics"
    country : ISO country code of the OAM to filter on (FR, DE, IT, ...)
    limit : max number of filing records to return

    Returns
    -------
    list[FilingRecord]
    """
    params = {
        "filter[entity.name]": company_name,
        "filter[country]": country,
        "page[size]": limit,
        "include": "entity",
    }
    resp = requests.get(FILINGS_XBRL_ORG_API, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    records: list[FilingRecord] = []
    for item in payload.get("data", []):
        attrs = item.get("attributes", {})
        records.append(
            FilingRecord(
                entity_name=attrs.get("entity_name", company_name),
                country=attrs.get("country", country),
                period_end=attrs.get("period_end", ""),
                filing_index_url=attrs.get("json_url", ""),
                package_url=attrs.get("package_url", ""),
            )
        )
    return records


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "STMicroelectronics"
    for f in search_filings(name):
        print(f)
