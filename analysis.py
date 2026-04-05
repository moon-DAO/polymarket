from api import get_h2h, get_team_last5, get_team_statistics, get_odds, get_polymarket_data


def analyze_match(fixture: dict) -> dict:
    fixture_id = fixture["fixture"]["id"]
    home = fixture["teams"]["home"]
    away = fixture["teams"]["away"]
    league = fixture["league"]

    # ── Fetch all data ──────────────────────────────────────────────
    h2h = get_h2h(home["id"], away["id"], last=5)
    home_last5 = get_team_last5(home["id"])
    away_last5 = get_team_last5(away["id"])
    home_stats = get_team_statistics(home["id"], league["id"])
    away_stats = get_team_statistics(away["id"], league["id"])
    odds_data = get_odds(fixture_id)
    polymarket = get_polymarket_data(home["name"], away["name"])

    # ── Run modules ────────────────────────────────────────────────
    prediction = _predict_result(home, away, home_stats, away_stats, h2h)
    ou_tip = _over_under_tip(home_stats, away_stats, h2h)
    h2h_summary = _summarize_h2h(home, away, h2h)
    home_form = _team_form(home["id"], home["name"], home_last5)
    away_form = _team_form(away["id"], away["name"], away_last5)
    odds_summary = _parse_odds(home["name"], away["name"], odds_data)

    return {
        "fixture_id": fixture_id,
        "home": home["name"],
        "away": away["name"],
        "league": league["name"],
        "date": fixture["fixture"]["date"],
        "prediction": prediction,
        "over_under": ou_tip,
        "h2h": h2h_summary,
        "home_form": home_form,
        "away_form": away_form,
        "odds": odds_summary,
        "polymarket": polymarket,
    }


# ── PREDICTION ENGINE ──────────────────────────────────────────────────────


def _form_score(stats: dict) -> float:
    if not stats:
        return 5.0
    fixtures = stats.get("fixtures", {})
    played = fixtures.get("played", {}).get("total", 1) or 1
    wins = fixtures.get("wins", {}).get("total", 0)
    goals_for = stats.get("goals", {}).get("for", {}).get("total", {}).get("total", 0)
    goals_against = stats.get("goals", {}).get("against", {}).get("total", {}).get("total", 0)

    win_rate = wins / played
    goal_diff = (goals_for - goals_against) / played
    score = (win_rate * 6) + (goal_diff * 2) + 2
    return max(0.0, min(10.0, score))


def _predict_result(home, away, home_stats, away_stats, h2h) -> dict:
    home_pts = _form_score(home_stats) + 1.5   # home advantage
    away_pts = _form_score(away_stats)

    for match in h2h[:5]:
        if match["teams"]["home"]["winner"] and match["teams"]["home"]["id"] == home["id"]:
            home_pts += 0.5
        elif match["teams"]["away"]["winner"] and match["teams"]["away"]["id"] == away["id"]:
            away_pts += 0.5
        elif match["teams"]["home"]["winner"] and match["teams"]["home"]["id"] == away["id"]:
            away_pts += 0.5
        elif match["teams"]["away"]["winner"] and match["teams"]["away"]["id"] == home["id"]:
            home_pts += 0.5

    draw_pts = (home_pts + away_pts) * 0.25
    total = home_pts + away_pts + draw_pts or 1

    home_pct = round(home_pts / total * 100)
    away_pct = round(away_pts / total * 100)
    draw_pct = max(5, 100 - home_pct - away_pct)
    home_pct = 100 - away_pct - draw_pct

    if home_pct >= away_pct and home_pct >= draw_pct:
        tip = f"🏠 {home['name']} Win"
        confidence = home_pct
    elif away_pct > home_pct and away_pct >= draw_pct:
        tip = f"✈️ {away['name']} Win"
        confidence = away_pct
    else:
        tip = "🤝 Draw"
        confidence = draw_pct

    stars = "⭐" * max(1, confidence // 25)

    return {
        "tip": tip,
        "confidence": confidence,
        "stars": stars,
        "home_pct": home_pct,
        "draw_pct": draw_pct,
        "away_pct": away_pct,
    }


# ── OVER / UNDER ───────────────────────────────────────────────────────────


def _over_under_tip(home_stats, away_stats, h2h) -> dict:
    h2h_over = sum(
        1 for m in h2h[:5]
        if (m["goals"]["home"] or 0) + (m["goals"]["away"] or 0) > 2
    )
    h2h_pct = (h2h_over / max(len(h2h[:5]), 1)) * 100

    def avg_goals(stats):
        if not stats:
            return 1.3
        played = stats.get("fixtures", {}).get("played", {}).get("total", 1) or 1
        scored = stats.get("goals", {}).get("for", {}).get("total", {}).get("total", 0)
        return scored / played

    combined_avg = avg_goals(home_stats) + avg_goals(away_stats)
    avg_score = min(combined_avg / 3.0 * 100, 100)
    final_pct = round((h2h_pct * 0.6) + (avg_score * 0.4))

    if final_pct >= 55:
        tip = "⬆️ Over 2.5 Goals"
        color = "🟢"
    else:
        tip = "⬇️ Under 2.5 Goals"
        color = "🔴"
        final_pct = 100 - final_pct

    return {"tip": tip, "confidence": final_pct, "color": color}


# ── TEAM FORM ──────────────────────────────────────────────────────────────


def _team_form(team_id: int, team_name: str, matches: list) -> dict:
    if not matches:
        return {"available": False, "team": team_name}

    results = []
    form_str = ""

    for m in matches:
        h_id = m["teams"]["home"]["id"]
        h_name = m["teams"]["home"]["name"]
        a_name = m["teams"]["away"]["name"]
        h_goals = m["goals"]["home"] or 0
        a_goals = m["goals"]["away"] or 0
        date_str = m["fixture"]["date"][:10]
        is_home = h_id == team_id
        location = "H" if is_home else "A"

        if m["teams"]["home"]["winner"] is None:
            outcome = "D"
            emoji = "🟡"
        elif (m["teams"]["home"]["winner"] and is_home) or (m["teams"]["away"]["winner"] and not is_home):
            outcome = "W"
            emoji = "🟢"
        else:
            outcome = "L"
            emoji = "🔴"

        opponent = a_name if is_home else h_name
        score = f"{h_goals}–{a_goals}"

        results.append({
            "date": date_str,
            "opponent": opponent,
            "score": score,
            "location": location,
            "outcome": outcome,
            "emoji": emoji,
        })
        form_str += outcome

    return {
        "available": True,
        "team": team_name,
        "form_str": form_str,
        "matches": results,
    }


# ── H2H SUMMARY ───────────────────────────────────────────────────────────


def _summarize_h2h(home, away, h2h) -> dict:
    if not h2h:
        return {"available": False}

    home_wins = away_wins = draws = 0
    recent = []

    for m in h2h[:5]:
        h_goals = m["goals"]["home"] or 0
        a_goals = m["goals"]["away"] or 0
        h_name = m["teams"]["home"]["name"]
        a_name = m["teams"]["away"]["name"]
        date_str = m["fixture"]["date"][:10]
        total_goals = h_goals + a_goals

        if m["teams"]["home"]["winner"]:
            winner = h_name
            if m["teams"]["home"]["id"] == home["id"]:
                home_wins += 1
            else:
                away_wins += 1
        elif m["teams"]["away"]["winner"]:
            winner = a_name
            if m["teams"]["away"]["id"] == away["id"]:
                away_wins += 1
            else:
                home_wins += 1
        else:
            winner = "Draw"
            draws += 1

        recent.append({
            "date": date_str,
            "match": f"{h_name} {h_goals}–{a_goals} {a_name}",
            "winner": winner,
            "total_goals": total_goals,
        })

    return {
        "available": True,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "recent": recent,
    }


# ── ODDS + IMPLIED WIN % ───────────────────────────────────────────────────


def _implied_pct(odd: float) -> float:
    """Convert decimal odd to raw implied probability %."""
    if not odd or odd <= 0:
        return 0.0
    return round((1 / odd) * 100, 1)


def _normalize(home_raw, draw_raw, away_raw) -> tuple:
    """Remove bookmaker overround — normalize to 100%."""
    total = home_raw + draw_raw + away_raw
    if total == 0:
        return 0, 0, 0
    return (
        round(home_raw / total * 100, 1),
        round(draw_raw / total * 100, 1),
        round(away_raw / total * 100, 1),
    )


def _parse_odds(home_name: str, away_name: str, odds_data: list) -> dict:
    if not odds_data:
        return {"available": False}

    parsed = []
    best_value = {"bookmaker": None, "pick": None, "odd": 0.0}

    home_implied_sum = draw_implied_sum = away_implied_sum = 0
    count = 0

    for entry in odds_data:
        bookmaker = entry["bookmaker"]
        try:
            bets = entry["data"]["bookmakers"][0]["bets"]
            match_winner = next((b for b in bets if b["id"] == 1), None)
            if not match_winner:
                continue

            values = {v["value"]: float(v["odd"]) for v in match_winner["values"]}
            home_odd = values.get("Home", 0)
            draw_odd = values.get("Draw", 0)
            away_odd = values.get("Away", 0)

            # Raw implied %
            h_raw = _implied_pct(home_odd)
            d_raw = _implied_pct(draw_odd)
            a_raw = _implied_pct(away_odd)

            # Normalized (overround removed)
            h_norm, d_norm, a_norm = _normalize(h_raw, d_raw, a_raw)

            parsed.append({
                "bookmaker": bookmaker,
                "home_odd": home_odd,
                "draw_odd": draw_odd,
                "away_odd": away_odd,
                "home_pct": h_norm,
                "draw_pct": d_norm,
                "away_pct": a_norm,
            })

            home_implied_sum += h_norm
            draw_implied_sum += d_norm
            away_implied_sum += a_norm
            count += 1

            for pick, odd in [("Home", home_odd), ("Draw", draw_odd), ("Away", away_odd)]:
                if odd > best_value["odd"]:
                    best_value = {"bookmaker": bookmaker, "pick": pick, "odd": odd}

        except (KeyError, IndexError, StopIteration):
            continue

    # Consensus (average across bookmakers)
    consensus = None
    if count:
        ch = round(home_implied_sum / count, 1)
        cd = round(draw_implied_sum / count, 1)
        ca = round(away_implied_sum / count, 1)
        if ch >= cd and ch >= ca:
            consensus_pick = f"🏠 {home_name}"
        elif ca > ch and ca >= cd:
            consensus_pick = f"✈️ {away_name}"
        else:
            consensus_pick = "🤝 Draw"
        consensus = {
            "home_pct": ch,
            "draw_pct": cd,
            "away_pct": ca,
            "pick": consensus_pick,
        }

    return {
        "available": bool(parsed),
        "bookmakers": parsed,
        "best_value": best_value,
        "consensus": consensus,
    }
