"""Small, compliant connector for public SEC EDGAR company facts."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class SECFact:
    text: str
    source_ref: str
    valid_from: date | None
    metadata: dict[str, str]


class SECEDGARConnector:
    """Fetch public company facts. SEC requires a descriptive User-Agent."""

    def __init__(self, user_agent: str) -> None:
        if "@" not in user_agent:
            raise ValueError(
                "SEC User-Agent must identify the application and include a contact email"
            )
        self.user_agent = user_agent

    def latest_facts(self, cik: str, limit: int = 20) -> list[SECFact]:
        normalized_cik = str(cik).zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{normalized_cik}.json"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        company = payload.get("entityName", f"CIK {normalized_cik}")
        facts: list[SECFact] = []
        for concept, detail in payload.get("facts", {}).get("us-gaap", {}).items():
            label = detail.get("label", concept)
            unit_sets = detail.get("units", {})
            latest = next((values[-1] for values in unit_sets.values() if values), None)
            if not latest or "val" not in latest:
                continue
            filed = latest.get("filed", "unknown")
            end = latest.get("end")
            facts.append(
                SECFact(
                    text=f"{company} disclosed {label}: {latest['val']} (period end {end}, filed {filed}).",
                    source_ref=f"SEC-EDGAR:CIK{normalized_cik}:{latest.get('form', 'filing')}:{filed}",
                    valid_from=date.fromisoformat(end) if end else None,
                    metadata={"cik": normalized_cik, "concept": concept, "filed": filed},
                )
            )
        return facts[:limit]
