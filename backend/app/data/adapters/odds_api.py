import httpx
from datetime import datetime, timezone
from typing import Optional
from ..schemas import Odds
from .base import BaseAdapter

BASE_URL = "https://api.the-odds-api.com/v4/sports"

class OddsApiAdapter(BaseAdapter):
    name = "the-odds-api"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def get_odds(self, fixture_id: str) -> Optional[Odds]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{BASE_URL}/soccer_epl/odds",
                params={"apiKey": self.api_key, "regions": "uk", "markets": "h2h,totals,both_teams_to_score", "oddsFormat": "decimal"},
            )
            r.raise_for_status()
            data = r.json()
        for event in data:
            if str(event.get("id")) != str(fixture_id):
                continue
            for book in event.get("bookmakers", []):
                h2h = next((m for m in book.get("markets", []) if m["key"] == "h2h"), None)
                totals = next((m for m in book.get("markets", []) if m["key"] == "totals"), None)
                btts = next((m for m in book.get("markets", []) if m["key"] == "both_teams_to_score"), None)
                if not h2h:
                    continue
                prices = {o["name"]: o["price"] for o in h2h.get("outcomes", [])}
                over = next((o["price"] for o in (totals or {}).get("outcomes", []) if o["name"] == "Over"), 1.90)
                under = next((o["price"] for o in (totals or {}).get("outcomes", []) if o["name"] == "Under"), 1.90)
                yes = next((o["price"] for o in (btts or {}).get("outcomes", []) if o["name"] == "Yes"), 1.80)
                no = next((o["price"] for o in (btts or {}).get("outcomes", []) if o["name"] == "No"), 2.00)
                return Odds(
                    fixture_id=str(fixture_id),
                    bookmaker=book.get("title", "Bookmaker"),
                    home=float(prices.get("Home", 2.0)),
                    draw=float(prices.get("Draw", 3.4)),
                    away=float(prices.get("Away", 3.8)),
                    over_25=float(over),
                    under_25=float(under),
                    btts_yes=float(yes),
                    btts_no=float(no),
                    updated_at=datetime.now(timezone.utc),
                )
        return None
