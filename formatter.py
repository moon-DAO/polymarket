from datetime import datetime


def format_fixture_list(fixtures: list, league_name: str = "") -> str:
    if not fixtures:
        return "⚠️ No upcoming fixtures found."

    header = "📅 *Upcoming Fixtures*"
    if league_name:
        header += f" — {league_name}"
    lines = [header, ""]

    for f in fixtures[:10]:
        home = f.get("homeTeam", {}).get("name", "?")
        away = f.get("awayTeam", {}).get("name", "?")
        try:
            dt = datetime.fromisoformat(f.get("utcDate", "").replace("Z", "+00:00"))
            time_str = dt.strftime("%d %b %H:%M UTC")
        except Exception:
            time_str = "TBD"

        status = f.get("status", "")
        if status == "IN_PLAY" or status == "PAUSED":
            h_score = f.get("score", {}).get("fullTime", {}).get("home", "?")
            a_score = f.get("score", {}).get("fullTime", {}).get("away", "?")
            lines.append(f"🔴 *{home}* {h_score}–{a_score} *{away}*  _(LIVE)_")
        elif status == "FINISHED":
            h_score = f.get("score", {}).get("fullTime", {}).get("home", "?")
            a_score = f.get("score", {}).get("fullTime", {}).get("away", "?")
            lines.append(f"✅ {home} {h_score}–{a_score} {away}  _(FT)_")
        else:
            lines.append(f"🕐 `{time_str}`  {home} vs {away}")

    lines += ["", "👆 Tap a match below to get full analysis."]
    return "\n".join(lines)


def format_analysis(result: dict) -> str:
    home = result["home"]
    away = result["away"]
    league = result["league"]
    pred = result["prediction"]
    ou = result["over_under"]
    h2h = result["h2h"]
    hf = result["home_form"]
    af = result["away_form"]
    poly = result["polymarket"]

    lines = []

    # ── Header ─────────────────────────────────────────────────────
    lines += [
        f"⚽ *{home}* vs *{away}*",
        f"🏆 {league}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # ── 1. Match Prediction ────────────────────────────────────────
    lines += [
        "📊 *MATCH PREDICTION*",
        f"🎯 Tip: *{pred['tip']}*  {pred['stars']}",
        f"Confidence: *{pred['confidence']}%*",
        "",
        f"  🏠 Home Win:  `{pred['home_pct']}%`",
        f"  🤝 Draw:      `{pred['draw_pct']}%`",
        f"  ✈️ Away Win:  `{pred['away_pct']}%`",
        "",
    ]

    # ── 2. Over / Under ────────────────────────────────────────────
    lines += [
        "⚽ *GOALS TIP — Over/Under 2.5*",
        f"{ou['color']} *{ou['tip']}*   confidence: {ou['confidence']}%",
        "",
    ]

    # ── 3. H2H Last 5 ─────────────────────────────────────────────
    lines.append("🔁 *HEAD TO HEAD — Last 5 Meetings*")
    if h2h.get("available"):
        lines.append(
            f"  {home}: {h2h['home_wins']}W  |  "
            f"Draws: {h2h['draws']}  |  "
            f"{away}: {h2h['away_wins']}W"
        )
        lines.append("")
        for m in h2h["recent"]:
            over_tag = " 🔥" if m["total_goals"] > 2 else ""
            lines.append(f"  📅 {m['date']}  {m['match']}{over_tag}  → {m['winner']}")
    else:
        lines.append("  No H2H data available.")
    lines.append("")

    # ── 4. Team Form ───────────────────────────────────────────────
    lines.append("📈 *RECENT FORM — Last 5 Matches*")
    for form in [hf, af]:
        if form.get("available"):
            form_icons = "".join(m["emoji"] for m in form["matches"])
            lines.append(f"\n  *{form['team']}*  {form_icons}  `{form['form_str']}`")
            for m in form["matches"]:
                lines.append(
                    f"  {m['emoji']} {m['date']}  [{m['location']}] vs {m['opponent']}  {m['score']}"
                )
        else:
            lines.append(f"\n  *{form['team']}*  No recent data.")
    lines.append("")

    # ── 5. Polymarket ──────────────────────────────────────────────
    lines.append("📈 *POLYMARKET — Prediction Market*")
    if poly.get("available"):
        vol = f"${poly['volume_usdc']:,.0f} USDC"
        lines.append(f"  📊 _{poly['title']}_")
        lines.append(f"  💵 Volume: *{vol}*")
        lines.append("")
        for o in poly["outcomes"]:
            bar_len = int(o["pct"] / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"  {o['name']:<10} {bar} {o['pct']}%")
    else:
        lines.append("  ⚪ Not listed on Polymarket.")
    lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "⚠️ _For entertainment only. Always bet responsibly._",
    ]

    return "\n".join(lines)


def format_search_results(teams: list, query: str) -> tuple:
    if not teams:
        return f"❌ No teams found for *{query}*.", []

    lines = [f"🔍 *Search results for \"{query}\"*", ""]
    buttons = []

    for t in teams[:6]:
        country = t.get("area", {}).get("name", "")
        lines.append(f"• {t['name']}  _{country}_")
        buttons.append((t["name"], t["id"]))

    return "\n".join(lines), buttons
