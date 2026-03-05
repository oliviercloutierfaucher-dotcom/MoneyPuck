#!/usr/bin/env bash
set -euo pipefail

# MoneyPuck Edge Model v2 — One-command deploy
# Usage: bash deploy.sh

BOLD='\033[1m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  MoneyPuck Edge Model v2 — Deploy${NC}"
echo -e "${BOLD}========================================${NC}"
echo

# 1. Python check
echo -e "${BOLD}[1/5] Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PY=python3
elif command -v python &>/dev/null; then
    PY=python
else
    echo -e "${RED}  Python not found. Install Python 3.9+ first.${NC}"
    exit 1
fi
PY_VER=$($PY --version 2>&1)
echo -e "  ${GREEN}Found: $PY_VER${NC}"

# 2. Install dependencies
echo
echo -e "${BOLD}[2/5] Installing dependencies...${NC}"
$PY -m pip install --quiet --upgrade pip
$PY -m pip install --quiet numpy
echo -e "  ${GREEN}Dependencies installed${NC}"

# 3. Check for Odds API key
echo
echo -e "${BOLD}[3/5] Checking API key...${NC}"
if [ -n "${ODDS_API_KEY:-}" ]; then
    echo -e "  ${GREEN}ODDS_API_KEY is set (${#ODDS_API_KEY} chars)${NC}"
else
    echo -e "  ${YELLOW}ODDS_API_KEY not set${NC}"
    echo -e "  ${YELLOW}Get a free key at: https://the-odds-api.com${NC}"
    echo
    read -rp "  Enter your API key (or press Enter to skip): " key
    if [ -n "$key" ]; then
        export ODDS_API_KEY="$key"
        echo -e "  ${GREEN}Key set for this session${NC}"
        echo
        echo -e "  To make it permanent, add to your shell profile:"
        echo -e "    echo 'export ODDS_API_KEY=\"$key\"' >> ~/.bashrc"
    else
        echo -e "  ${YELLOW}Skipping — will use demo mode${NC}"
    fi
fi

# 4. Quick sanity test
echo
echo -e "${BOLD}[4/5] Running sanity check...${NC}"
$PY -c "
from app.core.agents import TeamStrengthAgent, EdgeScoringAgent, RiskAgent
from app.core.models import TrackerConfig, TeamMetrics, ValueCandidate
from app.math.math_utils import logistic_win_probability, kelly_fraction
print('  All modules loaded successfully')
" || {
    echo -e "${RED}  Module import failed. Check your Python path.${NC}"
    exit 1
}
echo -e "  ${GREEN}Model pipeline OK${NC}"

# 5. First run
echo
echo -e "${BOLD}[5/5] Running first prediction cycle...${NC}"
echo
if [ -n "${ODDS_API_KEY:-}" ]; then
    $PY tracker.py --tonight --region ca
else
    echo -e "  ${YELLOW}No API key — launching web dashboard in demo mode${NC}"
    echo -e "  ${GREEN}Open http://localhost:8080?demo=1${NC}"
    $PY -m app.web.web_preview
fi

echo
echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  Deploy complete!${NC}"
echo -e "${BOLD}========================================${NC}"
echo
echo -e "Quick commands:"
echo -e "  ${GREEN}python -m app.web.web_preview${NC}             # Web dashboard"
echo -e "  ${GREEN}python tracker.py --tonight${NC}               # Tonight's bets"
echo -e "  ${GREEN}python tracker.py --tonight --json${NC}        # JSON output (for bots)"
echo -e "  ${GREEN}python tracker.py --army${NC}                  # 5 strategy profiles"
echo -e "  ${GREEN}python live_preview.py${NC}                    # CLI power rankings preview"
echo
echo -e "Tuning:"
echo -e "  ${GREEN}--bankroll 5000${NC}         Your bankroll"
echo -e "  ${GREEN}--min-edge 1.5${NC}          Minimum edge (pp)"
echo -e "  ${GREEN}--kelly-fraction 0.25${NC}   Quarter-Kelly (conservative)"
echo -e "  ${GREEN}--region us${NC}             US sportsbooks"
