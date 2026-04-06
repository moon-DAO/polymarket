import os
import json
import requests
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

API_BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": os.environ.get("FOOTBALL_DATA_API_KEY", "")}

TOP_LEAGUES = {
    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿": "PL",
    "La Liga 🇪🇸": "PD",
    "Serie A 🇮🇹": "SA",
    "Bundesliga 🇩🇪": "BL1",
    "Ligue 1 🇫🇷": "FL1",
    "Champions League 🏆": "CL",
}


def _get(endpoint: str, params: dict = {}) -> dict:
    try:
        resp = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        logger.error("API timed out")
        return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"API error: {e}")
        return {}


def get_fixtures_by_league(league_code: str) -> list:
    today = date.today().isoformat()
    next_month = (date.today() + timedelta(days=30)).isoformat()
    data = _get(f"competitions/{league_code}/matches", {
        "status": "SCHEDULED",
        "dateFrom": today,
        "dateTo": next_month,
    })
    return data.get("matches", [])[:10]


def get_fixture_by_id(fixture_id: int) -> dict:
    return _get(f"matches/{fixture_id}")


def get_h2h(fixture_id: int) -> list:
    data = _get(f"matches/{fixture_id}/head2head", {"limit": 5})
    return data.get("matches", [])


def get_team_last5(team_id: int) -> list:
    data = _get(f"teams/{team_id}/matches", {"status": "FINISHED", "limit": 5})
    matches = data.get("matches", [])
    # Return most recent first
    return list(reversed(matches[-5:]))


def get_team_next5(team_id: int) -> list:
    data = _get(f"teams/{team_id}/matches", {"status": "SCHEDULED", "limit": 5})
    return data.get("matches", [])[:5]


def search_team(name: str) -> list:
    results = []
    for league_code in list(TOP_LEAGUES.values()):
        data = _get(f"competitions/{league_code}/teams")
        for t in data.get("teams", []):
            if name.lower() in t.get("name", "").lower() or \
               name.lower() in t.get("shortName", "").lower():
                t["_league"] = league_code
                results.append(t)
    return results[:6]


# ── POLYMARKET ──────────────────────────────────────────────────────────────

POLYMARKET_BASE = "https://gamma-api.polymarket.com"


def get_polymarket_data(home_team: str, away_team: str) -> dict:
    try:
        kw1 = home_team.split()[0]
        kw2 = away_team.split()[0]
        resp = requests.get(
            f"{POLYMARKET_BASE}/markets",
            params={"search": f"{kw1} {kw2}", "active": "true", "limit": 10},
            timeout=10,
        )
        resp.raise_for_status()
        markets = resp.json()
        if not markets:
            return {"available": False}

        best = next(
            (m for m in markets
             if kw1.lower() in m.get("question", "").lower()
             and kw2.lower() in m.get("question", "").lower()),
            None
        )
        if not best:
            return {"available": False}

        volume = float(best.get("volume", 0) or 0)
        outcomes = best.get("outcomes", "[]")
        outcome_list = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        prices_raw = best.get("outcomePrices", "[]")
        prices = [float(p) for p in (json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw)]

        return {
            "available": True,
            "title": best.get("question", ""),
            "volume_usdc": volume,
            "outcomes": [
                {"name": o, "pct": round(prices[i] * 100, 1) if i < len(prices) else 0.0}
                for i, o in enumerate(outcome_list)
            ],
        }
    except Exception as e:
        logger.error(f"Polymarket error: {e}")
        return {"available": False}
