from api import get_h2h, get_team_last5, get_fixture_by_id, get_polymarket_data


def analyze_match(fixture: dict) -> dict:
    fixture_id = fixture.get("id")
    home = fixture.get("homeTeam", {})
    away = fixture.get("awayTeam", {})
    competition = fixture.get("competition", {})

    h2h = get_h2h(fixture_id)
    home_last5 = get_team_last5(home.get("id"))
    away_last5 = get_team_last5(away.get("id"))
    polymarket = get_polymarket_data(home.get("name", ""), away.get("name", ""))

    prediction = _predict_result(home, away, home_last5, away_last5, h2h)
    ou_tip = _over_under_tip(home_last5, away_last5, h2h)
    h2h_summary = _summarize_h2h(home, away, h2h)
    home_form = _team_form(home.get("id"), home.get("name", ""), home_last5)
    away_form = _team_form(away.get("id"), away.get("name", ""), away_last5)

    return {
        "fixture_id": fixture_id,
        "home": home.get("name", ""),
        "away": away.get("name", ""),
        "league": competition.get("name", ""),
        "date": fixture.get("utcDate", ""),
        "prediction": prediction,
        "over_under": ou_tip,
        "h2h": h2h_summary,
        "home_form": home_form,
        "away_form": away_form,
        "odds": {"available": False},  # Football-Data free tier has no odds
        "polymarket": polymarket,
    }


# ── PREDICTION ENGINE ──────────────────────────────────────────────────────


def _form_score_from_matches(team_id: int, matches: list) -> float:
    if not matches:
        return 5.0
    score = 0.0
    for m in matches[-5:]:
        h_id = m.get("homeTeam", {}).get("id")
        h_score = m.get("score", {}).get("fullTime", {}).get("home") or 0
        a_score = m.get("score", {}).get("fullTime", {}).get("away") or 0
        is_home = h_id == team_id
        my_score = h_score if is_home else a_score
        opp_score = a_score if is_home else h_score
        winner = m.get("score", {}).get("winner")
        if (winner == "HOME_TEAM" and is_home) or (winner == "AWAY_TEAM" and not is_home):
            score += 3
        elif winner == "DRAW":
            score += 1
        score += (my_score - opp_score) * 0.2
    return max(0.0, min(10.0, score))


def _predict_result(home, away, home_last5, away_last5, h2h) -> dict:
    home_pts = _form_score_from_matches(home.get("id"), home_last5) + 1.5
    away_pts = _form_score_from_matches(away.get("id"), away_last5)

    for m in h2h[:5]:
        winner = m.get("score", {}).get("winner")
        h_id = m.get("homeTeam", {}).get("id")
        is_home_playing_home = h_id == home.get("id")
        if (winner == "HOME_TEAM" and is_home_playing_home) or \
           (winner == "AWAY_TEAM" and not is_home_playing_home):
            home_pts += 0.5
        elif (winner == "AWAY_TEAM" and is_home_playing_home) or \
             (winner == "HOME_TEAM" and not is_home_playing_home):
            away_pts += 0.5

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

    return {
        "tip": tip,
        "confidence": confidence,
        "stars": "⭐" * max(1, confidence // 25),
        "home_pct": home_pct,
        "draw_pct": draw_pct,
        "away_pct": away_pct,
    }


# ── OVER / UNDER ───────────────────────────────────────────────────────────


def _over_under_tip(home_last5, away_last5, h2h) -> dict:
    def avg_goals(matches, team_id=None):
        if not matches:
            return 1.3
        total = 0
        for m in matches:
            h = m.get("score", {}).get("fullTime", {}).get("home") or 0
            a = m.get("score", {}).get("fullTime", {}).get("away") or 0
            total += h + a
        return total / len(matches)

    h2h_over = sum(
        1 for m in h2h[:5]
        if ((m.get("score", {}).get("fullTime", {}).get("home") or 0) +
            (m.get("score", {}).get("fullTime", {}).get("away") or 0)) > 2
    )
    h2h_pct = (h2h_over / max(len(h2h[:5]), 1)) * 100
    combined_avg = avg_goals(home_last5) + avg_goals(away_last5)
    avg_score = min(combined_avg / 3.0 * 100, 100)
    final_pct = round((h2h_pct * 0.6) + (avg_score * 0.4))

    if final_pct >= 55:
        return {"tip": "⬆️ Over 2.5 Goals", "confidence": final_pct, "color": "🟢"}
    else:
        return {"tip": "⬇️ Under 2.5 Goals", "confidence": 100 - final_pct, "color": "🔴"}


# ── H2H SUMMARY ───────────────────────────────────────────────────────────


def _summarize_h2h(home, away, h2h) -> dict:
    if not h2h:
        return {"available": False}

    home_wins = away_wins = draws = 0
    recent = []

    for m in h2h[:5]:
        h_name = m.get("homeTeam", {}).get("name", "")
        a_name = m.get("awayTeam", {}).get("name", "")
        h_id = m.get("homeTeam", {}).get("id")
        h_goals = m.get("score", {}).get("fullTime", {}).get("home") or 0
        a_goals = m.get("score", {}).get("fullTime", {}).get("away") or 0
        date_str = m.get("utcDate", "")[:10]
        winner = m.get("score", {}).get("winner")
        total_goals = h_goals + a_goals

        if winner == "HOME_TEAM":
            w_name = h_name
            if h_id == home.get("id"):
                home_wins += 1
            else:
                away_wins += 1
        elif winner == "AWAY_TEAM":
            w_name = a_name
            if h_id != home.get("id"):
                away_wins += 1
            else:
                home_wins += 1
        else:
            w_name = "Draw"
            draws += 1

        recent.append({
            "date": date_str,
            "match": f"{h_name} {h_goals}–{a_goals} {a_name}",
            "winner": w_name,
            "total_goals": total_goals,
        })

    return {
        "available": True,
        "home_wins": home_wins,
        "away_wins": away_wins,
        "draws": draws,
        "recent": recent,
    }


# ── TEAM FORM ──────────────────────────────────────────────────────────────


def _team_form(team_id: int, team_name: str, matches: list) -> dict:
    if not matches:
        return {"available": False, "team": team_name}

    results = []
    form_str = ""

    for m in matches:
        h_id = m.get("homeTeam", {}).get("id")
        h_name = m.get("homeTeam", {}).get("name", "")
        a_name = m.get("awayTeam", {}).get("name", "")
        h_goals = m.get("score", {}).get("fullTime", {}).get("home") or 0
        a_goals = m.get("score", {}).get("fullTime", {}).get("away") or 0
        date_str = m.get("utcDate", "")[:10]
        is_home = h_id == team_id
        winner = m.get("score", {}).get("winner")

        if winner == "DRAW":
            outcome, emoji = "D", "🟡"
        elif (winner == "HOME_TEAM" and is_home) or (winner == "AWAY_TEAM" and not is_home):
            outcome, emoji = "W", "🟢"
        else:
            outcome, emoji = "L", "🔴"

        opponent = a_name if is_home else h_name
        score = f"{h_goals}–{a_goals}"
        location = "H" if is_home else "A"

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
