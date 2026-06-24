import os
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BOOKMAKER_KEY = "paddypower"
MIN_EDGE = 0.03

LEAGUES = {
    "worldcup": "soccer_fifa_world_cup",
    "epl": "soccer_epl",
    "laliga": "soccer_spain_la_liga",
    "seriea": "soccer_italy_serie_a",
    "bundesliga": "soccer_germany_bundesliga",
    "ligue1": "soccer_france_ligue_one",
    "ucl": "soccer_uefa_champs_league",
}

HELP_TEXT = """
⚽ <b>Football Value Bet Scanner</b>
━━━━━━━━━━━━━━━━━━
Available commands:

/worldcup — Today's World Cup matches
/epl — Premier League
/laliga — La Liga
/seriea — Serie A
/bundesliga — Bundesliga
/ligue1 — Ligue 1
/ucl — Champions League
/all — All leagues

Sends value bets where Paddy Power odds are better than the market average.
""".strip()


# --- Telegram API ---
def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 30, "offset": offset}
    try:
        response = requests.get(url, params=params, timeout=35)
        return response.json().get("result", [])
    except Exception as e:
        print(f"Error getting updates: {e}")
        return []


def send_message(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")


def send_typing(chat_id: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendChatAction"
    requests.post(url, json={"chat_id": chat_id, "action": "typing"})


# --- Odds API ---
def fetch_odds(sport: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
        "bookmakers": "paddypower,bet365,williamhill,unibet,betfair,marathonbet,pinnacle",
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        remaining = response.headers.get("x-requests-remaining", "?")
        print(f"  ✓ {sport} — {len(response.json())} matches | Requests remaining: {remaining}")
        return response.json()
    else:
        print(f"  ✗ {sport} error {response.status_code}")
        return []


def is_today(commence_time: str) -> bool:
    try:
        dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        today = datetime.now(timezone.utc).date()
        return dt.date() == today
    except Exception:
        return False


# --- Analysis ---
def get_market_average(bookmakers: list, outcome_name: str) -> float:
    prices = []
    for bm in bookmakers:
        if bm["key"] == BOOKMAKER_KEY:
            continue
        for market in bm.get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    if outcome["name"] == outcome_name:
                        prices.append(outcome["price"])
    return sum(prices) / len(prices) if prices else None


def get_paddy_power_odds(bookmakers: list) -> dict:
    for bm in bookmakers:
        if bm["key"] == BOOKMAKER_KEY:
            for market in bm.get("markets", []):
                if market["key"] == "h2h":
                    return {o["name"]: o["price"] for o in market["outcomes"]}
    return {}


def analyze_match(match: dict) -> list:
    value_bets = []
    bookmakers = match.get("bookmakers", [])
    home = match["home_team"]
    away = match["away_team"]

    pp_odds = get_paddy_power_odds(bookmakers)
    if not pp_odds:
        return []

    for outcome in [home, away, "Draw"]:
        pp_price = pp_odds.get(outcome)
        if not pp_price:
            continue

        market_avg = get_market_average(bookmakers, outcome)
        if not market_avg:
            continue

        pp_implied = 1 / pp_price
        market_implied = 1 / market_avg
        edge = market_implied - pp_implied

        if edge >= MIN_EDGE:
            value_bets.append({
                "outcome": outcome,
                "pp_odds": pp_price,
                "market_avg_odds": round(market_avg, 3),
                "edge": round(edge * 100, 2),
                "pp_implied_prob": round(pp_implied * 100, 1),
                "market_implied_prob": round(market_implied * 100, 1),
            })

    return value_bets


def format_match(match: dict, value_bets: list) -> str:
    home = match["home_team"]
    away = match["away_team"]

    try:
        dt = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
        kickoff_str = dt.strftime("%H:%M UTC")
    except Exception:
        kickoff_str = "?"

    lines = [f"⚽ <b>{home} vs {away}</b> — {kickoff_str}"]

    if value_bets:
        for vb in value_bets:
            lines.append(
                f"  🟢 <b>{vb['outcome']}</b> @ {vb['pp_odds']} "
                f"(market avg: {vb['market_avg_odds']} | edge: +{vb['edge']}%)"
            )
    else:
        pp_odds = get_paddy_power_odds(match.get("bookmakers", []))
        if pp_odds:
            odds_str = " | ".join([f"{k}: {v}" for k, v in pp_odds.items()])
            lines.append(f"  ℹ️ No value found — PP odds: {odds_str}")
        else:
            lines.append(f"  ⚪ Paddy Power not covering this match")

    return "\n".join(lines)


# --- Command Handler ---
def handle_command(chat_id: str, command: str):
    command = command.lower().split("@")[0]

    if command in ("/start", "/help"):
        send_message(chat_id, HELP_TEXT)
        return

    if command == "/all":
        leagues_to_scan = list(LEAGUES.items())
    elif command.lstrip("/") in LEAGUES:
        key = command.lstrip("/")
        leagues_to_scan = [(key, LEAGUES[key])]
    else:
        send_message(chat_id, "Unknown command. Send /help to see available commands.")
        return

    send_typing(chat_id)
    send_message(chat_id, "🔍 Scanning today's matches... hang on.")

    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    results = []
    total_matches = 0
    value_bet_count = 0

    for league_name, league_key in leagues_to_scan:
        matches = fetch_odds(league_key)
        today_matches = [m for m in matches if is_today(m.get("commence_time", ""))]

        if not today_matches:
            continue

        section_lines = [f"\n🏆 <b>{league_name.upper()}</b>"]

        for match in today_matches:
            total_matches += 1
            value_bets = analyze_match(match)
            value_bet_count += len(value_bets)
            section_lines.append(format_match(match, value_bets))

        results.append("\n".join(section_lines))

    if not results:
        send_message(chat_id, f"📭 No matches found today ({today}) for the selected league(s).")
        return

    header = f"📊 <b>Today's Analysis — {today}</b>\n━━━━━━━━━━━━━━━━━━"
    send_message(chat_id, header)

    for section in results:
        send_message(chat_id, section)

    summary = (
        f"\n✅ <b>Scan complete</b>\n"
        f"Matches today: {total_matches}\n"
        f"Value bets found: {value_bet_count}\n"
        f"⚠️ Always bet responsibly."
    )
    send_message(chat_id, summary)


# --- Main Loop ---
def run():
    print("🤖 Bot started — waiting for messages...")
    send_message(TELEGRAM_CHAT_ID, "🤖 Football analyst bot is online! Send /help to get started.")

    offset = None

    while True:
        updates = get_updates(offset)

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message", {})
            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))

            if not text or not chat_id:
                continue

            if chat_id != str(TELEGRAM_CHAT_ID):
                print(f"Ignored message from unknown chat: {chat_id}")
                continue

            if text.startswith("/"):
                print(f"Command received: {text}")
                handle_command(chat_id, text)

        time.sleep(1)


if __name__ == "__main__":
    run()