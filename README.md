# ⚽ Football Value Bet Scanner

Scans upcoming football matches and alerts you via Telegram when Paddy Power is offering better odds than the market average — indicating a potential value bet.

## How it works

1. Fetches odds from The Odds API across 7 bookmakers
2. Calculates the market average implied probability for each outcome
3. Compares Paddy Power's odds vs the market average
4. If Paddy Power is paying out more than the market consensus by >3%, sends a Telegram alert

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/football-analyst.git
cd football-analyst
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up credentials
```bash
cp .env.example .env
# Edit .env and fill in your keys
```

### 4. Run locally
```bash
python main.py
```

## Deploy with GitHub Actions (free, runs every hour)

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions**
3. Add these 3 secrets:
   - `ODDS_API_KEY`
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. The scanner runs automatically every hour

## Tuning

In `main.py`, adjust `MIN_EDGE` to control sensitivity:
- `0.02` = alert on 2%+ edge (more alerts, more noise)
- `0.03` = alert on 3%+ edge (default, balanced)
- `0.05` = alert on 5%+ edge (fewer alerts, higher confidence)

## Leagues covered
- Premier League
- La Liga
- Serie A
- Bundesliga
- Ligue 1
- Champions League
- FIFA World Cup 2026

## Disclaimer
This tool is for informational purposes only. Always bet responsibly.
