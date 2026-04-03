import os
import json
import requests
import logging
from datetime import date

logger = logging.getLogger(__name__)

API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": os.environ.get("FOOTBALL_API_KEY", "")}

TOP_LEAGUES = {
    "Premier League 🏴󠁧󠁢󠁥󠁮󠁧󠁿": 39,
    "La Liga 🇪🇸": 140,
    "Serie A 🇮🇹": 135,
    "Bundesliga 🇩🇪": 78,
    "Ligue 1 🇫🇷": 61,
    "Champions League 🏆": 2,
}

BOOKMAKERS = {
    "Bet365": 8,
    "Bwin": 6,
    "1xBet": 36,
}


def _get(endpoint: str, params: dict = {}) -> list:
    try:
        resp = requests.get(
            f"{API_BASE}/{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            logger.error(f"API errors: {data['errors']}")
            return []
        return data.get("response", [])
    except requests.exceptions.Timeout:
        logger.error("API request timed out")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return []


def get_fixtures_by_league(league_id: int, season: int = 2025) -> list:
    from datetime import date, timedelta
    today = date.today().isoformat()
    next_week = (date.today() + timedelta(days=7)).isoformat()
    return _get("fixtures", {
        "league": league_id,
        "season": season,
        "from": today,
        "to": next_week,
    })


def get_fixtures_by_team(team_id: int, season: int = 2025, next: int = 5) -> list:
    from datetime import date, timedelta
    today = date.today().isoformat()
    next_month = (date.today() + timedelta(days=30)).isoformat()
    return _get("fixtures", {
        "team": team_id,
        "season": season,
        "from": today,
        "to": next_month,
    })


def get_fixture_by_id(fixture_id: int) -> dict:
    results = _get("fixtures", {"id": fixture_id})
    return results[0] if results else {}


def get_h2h(team1_id: int, team2_id: int, last: int = 5) -> list:
    return _get("fixtures/headtohead", {"h2h": f"{team1_id}-{team2_id}", "last": last})


def get_team_last5(team_id: int) -> list:
    """Fetch last 5 completed matches for a team."""
    return _get("fixtures", {"team": team_id, "last": 5})


def get_team_statistics(team_id: int, league_id: int, season: int = 2025) -> dict:
    results = _get("teams/statistics", {
        "team": team_id,
        "league": league_id,
        "season": season,
    })
    return results if isinstance(results, dict) else {}


def get_odds(fixture_id: int) -> list:
    all_odds = []
    for bookmaker_name, bookmaker_id in BOOKMAKERS.items():
        results = _get("odds", {
            "fixture": fixture_id,
            "bookmaker": bookmaker_id,
            "bet": 1,
        })
        if results:
            all_odds.append({
                "bookmaker": bookmaker_name,
                "data": results[0],
            })
    return all_odds


def search_team(name: str) -> list:
    return _get("teams", {"search": name})


# ── POLYMARKET ─────────────────────────────────────────────────────────────

POLYMARKET_BASE = "https://gamma-api.polymarket.com"


def get_polymarket_data(home_team: str, away_team: str) -> dict:
    """Search Polymarket for a match market and return volume + win %."""
    try:
        kw1 = home_team.split()[0]
        kw2 = away_team.split()[0]
        query = f"{kw1} {kw2}"

        resp = requests.get(
            f"{POLYMARKET_BASE}/markets",
            params={"search": query, "active": "true", "limit": 10},
            timeout=10,
        )
        resp.raise_for_status()
        markets = resp.json()

        if not markets:
            return {"available": False}

        best = None
        for m in markets:
            title = m.get("question", "").lower()
            if kw1.lower() in title and kw2.lower() in title:
                best = m
                break

        if not best:
            return {"available": False}

        volume = float(best.get("volume", 0) or 0)

        try:
            outcomes = best.get("outcomes", "[]")
            outcome_list = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
            prices_raw = best.get("outcomePrices", "[]")
            prices = [float(p) for p in (json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw)]
        except Exception:
            return {"available": False}

        result = {
            "available": True,
            "title": best.get("question", ""),
            "volume_usdc": volume,
            "outcomes": [],
        }

        for i, outcome in enumerate(outcome_list):
            pct = round(prices[i] * 100, 1) if i < len(prices) else 0.0
            result["outcomes"].append({"name": outcome, "pct": pct})

        return result

    except Exception as e:
        logger.error(f"Polymarket error: {e}")
        return {"available": False}
