import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from api import (
    get_fixtures_by_league,
    get_fixture_by_id,
    get_team_next5,
    search_team,
    TOP_LEAGUES,
)
from analysis import analyze_match
from formatter import format_fixture_list, format_analysis, format_search_results

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")


# ─── COMMANDS ──────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚽ *Sports Betting Analysis Bot*\n\n"
        "Pick any match and get a full breakdown:\n"
        "• 📊 Win / Draw / Loss prediction\n"
        "• ⬆️⬇️ Over / Under 2.5 goals tip\n"
        "• 🔁 Last 5 H2H results\n"
        "• 📈 Each team's last 5 matches & form\n"
        "• 📈 Polymarket volume & crowd prediction\n\n"
        "📌 *Commands*\n"
        "• /fixtures — Upcoming matches\n"
        "• /leagues — Browse top leagues\n"
        "• /search <team> — Find a team\n"
        "• /help — Show this message\n\n"
        "⚠️ _For entertainment only. Always bet responsibly._"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_leagues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"league_{code}")]
        for name, code in TOP_LEAGUES.items()
    ]
    await update.message.reply_text(
        "🏆 *Select a league:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cmd_fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"league_{code}")]
        for name, code in TOP_LEAGUES.items()
    ]
    await update.message.reply_text(
        "📅 *Which league?*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text(
            "Usage: /search <team name>\nExample: /search Arsenal"
        )
        return

    await update.message.reply_text(f"🔍 Searching for *{query}*…", parse_mode="Markdown")
    teams = search_team(query)
    text, buttons = format_search_results(teams, query)

    if buttons:
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"team_{tid}")]
            for name, tid in buttons
        ]
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown")


# ─── CALLBACKS ─────────────────────────────────────────────────────────────


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # ── League → fixtures ──────────────────────────────────────────
    if data.startswith("league_"):
        league_code = data.split("_", 1)[1]
        league_name = next((n for n, c in TOP_LEAGUES.items() if c == league_code), league_code)
        await query.edit_message_text(f"⏳ Fetching fixtures for {league_name}…")

        fixtures = get_fixtures_by_league(league_code)
        text = format_fixture_list(fixtures, league_name)

        if fixtures:
            keyboard = [
                [InlineKeyboardButton(
                    f"{f.get('homeTeam', {}).get('name', '?')} vs {f.get('awayTeam', {}).get('name', '?')}",
                    callback_data=f"fixture_{f['id']}"
                )]
                for f in fixtures[:8]
            ]
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(text, parse_mode="Markdown")

    # ── Fixture → full analysis ────────────────────────────────────
    elif data.startswith("fixture_"):
        fixture_id = int(data.split("_")[1])
        await query.edit_message_text(
            "🔬 Running full analysis…\n_(Fetching H2H, form, Polymarket — ~10s)_",
            parse_mode="Markdown",
        )

        fixture = get_fixture_by_id(fixture_id)
        if not fixture or "id" not in fixture:
            await query.edit_message_text("❌ Could not load fixture. Try again.")
            return

        try:
            result = analyze_match(fixture)
            text = format_analysis(result)
            if len(text) > 4000:
                mid = text.rfind("\n", 0, 4000)
                await query.edit_message_text(text[:mid], parse_mode="Markdown")
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text[mid:],
                    parse_mode="Markdown",
                )
            else:
                await query.edit_message_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Analysis error: {e}", exc_info=True)
            await query.edit_message_text(
                "⚠️ Analysis failed. Try again shortly."
            )

    # ── Team → upcoming fixtures ───────────────────────────────────
    elif data.startswith("team_"):
        team_id = int(data.split("_")[1])
        await query.edit_message_text("⏳ Loading upcoming fixtures…")

        fixtures = get_team_next5(team_id)
        if not fixtures:
            await query.edit_message_text("❌ No upcoming fixtures found for this team.")
            return

        team_name = fixtures[0].get("homeTeam", {}).get("name", "Team")
        text = format_fixture_list(fixtures, team_name)
        keyboard = [
            [InlineKeyboardButton(
                f"{f.get('homeTeam', {}).get('name', '?')} vs {f.get('awayTeam', {}).get('name', '?')}",
                callback_data=f"fixture_{f['id']}"
            )]
            for f in fixtures[:5]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "I didn't understand that. Use /help to see available commands."
    )


# ─── MAIN ──────────────────────────────────────────────────────────────────


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN environment variable is not set.")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("leagues", cmd_leagues))
    app.add_handler(CommandHandler("fixtures", cmd_fixtures))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_unknown))

    logger.info("✅ Bot started.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
