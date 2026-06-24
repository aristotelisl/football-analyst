import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# --- Config ---
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BOOKMAKER_KEY = "paddypower"  # Paddy Power's key in The Odds API
MIN_EDGE = 0.03  # minimum edge to alert (3%) — tune this up/down

LEAGUES = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
    "soccer_uefa_champs_league",
    "soccer_fifa_world_cup",
]


# --- Telegram ---
def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    response = requests.post(url, json=payload)
    if not response.ok:
        print(f"Telegram error: {response.text}")


# --- Odds API ---
def fetch_odds(sport: str):
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu",
        "markets": "h2h",  # head-to-head (1X2)
        "oddsFormat": "decimal",
        "bookmakers": "paddypower,bet365,williamhill,unibet,betfair,marathonbet,pinnacle",
    }
    response = requests.get(url, params=params)
    if response.status_code == 200:
        remaining = response.headers.get("x-requests-remaining", "?")
        print(f"  ✓ {sport} — {len(response.json())} matches | Requests remaining: {remaining}")
        return response.json()
    else:
        print(f"  ✗ {sport} — API error {response.status_code}: {response.text}")
        return []


# --- Core Logic ---
def get_market_average(bookmakers: list, outcome_name: str) -> float:
    """Calculate average odds for an outcome across all bookmakers (excluding Paddy Power)."""
    prices = []
    for bm in bookmakers:
        if bm["key"] == BOOKMAKER_KEY:
            continue
        for market in bm.get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    if outcome["name"] == outcome_name:
                        prices.append(outcome["price"])
    if not prices:
        return None
    return sum(prices) / len(prices)


def get_paddy_power_odds(bookmakers: list) -> dict:
    """Extract Paddy Power's odds for each outcome."""
    for bm in bookmakers:
        if bm["key"] == BOOKMAKER_KEY:
            for market in bm.get("markets", []):
                if market["key"] == "h2h":
                    return {o["name"]: o["price"] for o in market["outcomes"]}
    return {}


def analyze_match(match: dict) -> list:
    """Compare Paddy Power odds vs market average. Return value bets found."""
    value_bets = []

    home = match["home_team"]
    away = match["away_team"]
    bookmakers = match.get("bookmakers", [])

    pp_odds = get_paddy_power_odds(bookmakers)
    if not pp_odds:
        return []  # Paddy Power not covering this match

    outcomes = [home, away, "Draw"]

    for outcome in outcomes:
        pp_price = pp_odds.get(outcome)
        if not pp_price:
            continue

        market_avg = get_market_average(bookmakers, outcome)
        if not market_avg:
            continue

        # implied probabilities
        pp_implied = 1 / pp_price
        market_implied = 1 / market_avg

        # edge = how much better PP is vs the market
        edge = market_implied - pp_implied

        if edge >= MIN_EDGE:
            value_bets.append({
                "outcome": outcome,
                "pp_odds": pp_price,
                "market_avg_odds": round(market_avg, 3),
                "edge": round(edge * 100, 2),  # as percentage
                "pp_implied_prob": round(pp_implied * 100, 1),
                "market_implied_prob": round(market_implied * 100, 1),
            })

    return value_bets


def format_alert(match: dict, value_bets: list) -> str:
    home = match["home_team"]
    away = match["away_team"]
    kickoff_utc = match.get("commence_time", "")

    # parse and format kickoff time
    try:
        dt = datetime.fromisoformat(kickoff_utc.replace("Z", "+00:00"))
        kickoff_str = dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        kickoff_str = kickoff_utc

    lines = [
        f"🟢 <b>VALUE BET DETECTED</b>",
        f"━━━━━━━━━━━━━━━━━━",
        f"⚽ <b>{home} vs {away}</b>",
        f"🕐 Kickoff: {kickoff_str}",
        f"",
    ]

    for vb in value_bets:
        lines += [
            f"💡 <b>Bet: {vb['outcome']}</b>",
            f"   Paddy Power odds: <b>{vb['pp_odds']}</b>",
            f"   Market average:   {vb['market_avg_odds']}",
            f"   Edge: <b>+{vb['edge']}%</b>",
            f"   PP implied prob:  {vb['pp_implied_prob']}%",
            f"   Market consensus: {vb['market_implied_prob']}%",
            f"",
        ]

    lines.append("⚠️ Bet responsibly. This is analysis only.")
    return "\n".join(lines)


# --- Main ---
def run():
    print(f"\n🔍 Football Value Bet Scanner — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    total_matches = 0
    total_value_bets = 0

    for league in LEAGUES:
        print(f"\n📋 Checking {league}...")
        matches = fetch_odds(league)

        for match in matches:
            total_matches += 1
            value_bets = analyze_match(match)

            if value_bets:
                total_value_bets += len(value_bets)
                alert = format_alert(match, value_bets)
                print(f"\n  🟢 Value bet found: {match['home_team']} vs {match['away_team']}")
                send_telegram(alert)

    summary = (
        f"✅ Scan complete — {datetime.now().strftime('%H:%M UTC')}\n"
        f"Matches checked: {total_matches}\n"
        f"Value bets found: {total_value_bets}"
    )
    print(f"\n{summary}")
    send_telegram(f"📊 {summary}")


if __name__ == "__main__":
    run()
