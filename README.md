# MoneyPuck Edge Platform (NHL)

Production-oriented tracker that compares **market moneyline odds** with **MoneyPuck-derived team strength** to identify value bets for Canada/US books.

## Executive model: 5 specialized agents

The app is intentionally structured like a real desk with clear ownership:

1. **market-odds-agent** – fetches live bookmaker lines from The Odds API.
2. **moneypuck-data-agent** – fetches MoneyPuck game-level xG data.
3. **team-strength-agent** – builds team ratings from historical xG share.
4. **edge-scoring-agent** – converts ratings + prices into edge and EV-ranked bets.
5. **risk-agent** – applies Kelly + bankroll caps for stake sizing.

`market-odds-agent` and `moneypuck-data-agent` run in parallel to reduce cycle latency.

---

## Fastest one-hour team demo (recommended)

The preview UI now uses a data-dense, Quiver-inspired dashboard layout with KPI cards, controls, and a sortable-style table feel for team presentations.

If you need to show a preview quickly, use the built-in web preview app:

```bash
export ODDS_API_KEY="your_key_here"
python3 -m app.web_preview
```

Then open:
- HTML preview: `http://localhost:8080/`
- JSON API: `http://localhost:8080/api/opportunities`

No API key yet? Use demo mode:
- `http://localhost:8080/?demo=1`
- `http://localhost:8080/api/opportunities?demo=1`

You can tune parameters in query string, for example:

```text
http://localhost:8080/?region=ca&min_edge=1.5&min_ev=0.01&bankroll=5000
```

---


## Agent Army mode (parallel strategy desk)

Run all five strategy profiles at once (scout, balanced, sniper, aggressive, capital-preservation):

```bash
python3 tracker.py --army --region ca --season 2024 --bankroll 5000
```

This returns JSON with each profile's thresholds and top opportunities so your team can compare conviction levels side-by-side.
All army profiles now share one market snapshot per run for faster execution and consistent apples-to-apples comparisons.

---


## Model upgrades for deployment-night edge

- Bayesian-shrunk team strength from MoneyPuck xG share (less noisy than raw average)
- Home-ice advantage parameter (`--home-advantage-pp`)
- No-vig market consensus extraction per matchup
- Blended model (`--market-blend`) to reduce overfitting to one signal
- Best-line selection across books for each side
- Confidence-aware fractional Kelly sizing (`--kelly-scale`)

## CLI quick start

### 1) Requirements

- Python 3.11+
- Odds API key from [The Odds API](https://the-odds-api.com)

### 2) Run locally

```bash
export ODDS_API_KEY="your_key_here"
python3 tracker.py --region ca --season 2024 --min-edge 2 --min-ev 0.02 --bankroll 5000
```

### 3) JSON output (for dashboards / automation)

```bash
python3 tracker.py --json
```

---

## Deployment options

## Option A: Docker (recommended)

### Build

```bash
docker build -t moneypuck-edge:latest .
```

### Run CLI

```bash
docker run --rm \
  -e ODDS_API_KEY="$ODDS_API_KEY" \
  moneypuck-edge:latest \
  python tracker.py --region ca --json
```

### Run web preview

```bash
docker run --rm -p 8080:8080 \
  -e ODDS_API_KEY="$ODDS_API_KEY" \
  moneypuck-edge:latest \
  python -m app.web_preview
```

## Option B: Scheduled job (Linux server / VM)

Run every 15 minutes:

```bash
*/15 * * * * cd /opt/moneypuck && /usr/bin/python3 tracker.py --json >> /var/log/moneypuck/tracker.log 2>&1
```

## Option C: GitHub Actions cron

Use a scheduled workflow to run `tracker.py --json`, archive artifacts, and send to Slack/Discord.

---

## CLI flags

- `--region`: `ca` (default) or `us`
- `--bookmakers`: optional filtered book list
- `--season`: MoneyPuck season year
- `--min-edge`: minimum model edge in probability points
- `--min-ev`: minimum EV per dollar stake
- `--bankroll`: bankroll basis for stake sizing
- `--max-fraction-per-bet`: risk cap per bet (default 3%)
- `--home-advantage-pp`: home-ice probability boost in percentage points
- `--market-blend`: blend weight toward no-vig market consensus (0 to 0.85)
- `--kelly-scale`: fractional Kelly sizing scale (0.05 to 1.0)
- `--json`: machine-readable output

---

## Risk and compliance notes

- This is a quantitative decision-support tool, **not financial advice**.
- Sports betting is regulated differently per province (Quebec included); ensure legal compliance where you operate.
- Consider adding limits, monitoring, and audit logs before production wagering.
