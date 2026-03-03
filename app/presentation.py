from __future__ import annotations

import html
import json
from typing import Any


def to_serializable(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in recommendations:
        candidate = item["candidate"]
        rows.append(
            {
                "commence_time_utc": candidate.commence_time_utc,
                "home_team": candidate.home_team,
                "away_team": candidate.away_team,
                "side": candidate.side,
                "sportsbook": candidate.sportsbook,
                "american_odds": candidate.american_odds,
                "implied_probability": round(candidate.implied_probability, 4),
                "model_probability": round(candidate.model_probability, 4),
                "edge_probability_points": round(candidate.edge_probability_points, 4),
                "expected_value_per_dollar": round(candidate.expected_value_per_dollar, 4),
                "kelly_fraction": round(candidate.kelly_fraction, 4),
                "confidence": round(candidate.confidence, 4),
                "recommended_stake": item["recommended_stake"],
                "stake_fraction": item["stake_fraction"],
            }
        )
    return rows


def render_html_preview(recommendations: list[dict[str, Any]]) -> str:
    """Legacy simple preview — kept for backward compatibility."""
    rows = to_serializable(recommendations)
    return render_dashboard({"value_bets": rows, "games": [], "summary": {}, "books": [], "config": {}})


def render_dashboard(data: dict[str, Any]) -> str:
    """Render the full multi-book comparison dashboard.

    *data* should contain:
      - games: list of game dicts with per-book odds
      - value_bets: list of value bet dicts
      - summary: dict of KPI stats
      - books: list of active book names
      - config: current config dict
      - rankings: optional list of (team, composite) for power rankings
    """
    data_json = json.dumps(data)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>MoneyPuck Edge Intelligence</title>
  <style>
    :root {{
      --bg: #06080f;
      --bg-2: #0c1120;
      --panel: #111827;
      --panel-2: #1a2236;
      --panel-3: #1e293b;
      --text: #f1f5f9;
      --text-2: #cbd5e1;
      --muted: #64748b;
      --accent: #06b6d4;
      --accent-2: #22d3ee;
      --green: #10b981;
      --green-bg: rgba(16,185,129,0.1);
      --green-border: rgba(16,185,129,0.25);
      --red: #ef4444;
      --amber: #f59e0b;
      --amber-bg: rgba(245,158,11,0.1);
      --border: #1e293b;
      --border-2: #334155;
      --shadow: 0 4px 24px rgba(0,0,0,0.4);
      --radius: 12px;
      --radius-sm: 8px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      min-height: 100vh;
    }}
    .app {{ max-width: 1400px; margin: 0 auto; padding: 0 20px 40px; }}

    /* ---- HEADER ---- */
    .header {{
      padding: 24px 0 20px;
      border-bottom: 1px solid var(--border);
      margin-bottom: 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .brand {{ display: flex; align-items: center; gap: 14px; }}
    .logo {{
      width: 44px; height: 44px;
      background: linear-gradient(135deg, var(--accent), #8b5cf6);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; font-weight: 900; color: #fff;
    }}
    .brand h1 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.02em; }}
    .brand .sub {{ color: var(--muted); font-size: 13px; margin-top: 2px; }}
    .header-actions {{ display: flex; gap: 10px; align-items: center; }}
    .badge {{
      display: inline-flex; align-items: center; gap: 6px;
      background: var(--panel); border: 1px solid var(--border-2);
      border-radius: 20px; padding: 6px 14px; font-size: 12px;
      font-weight: 600; color: var(--text-2);
    }}
    .badge.live {{ border-color: var(--green); }}
    .badge.live::before {{
      content: ''; width: 8px; height: 8px;
      background: var(--green); border-radius: 50%;
      animation: pulse 2s infinite;
    }}
    .badge.demo {{ border-color: var(--amber); color: var(--amber); }}
    @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.4; }} }}

    /* ---- CONTROLS ---- */
    .controls {{
      display: flex; gap: 10px; flex-wrap: wrap;
      margin-bottom: 20px; align-items: center;
    }}
    .control-group {{
      display: flex; align-items: center; gap: 8px;
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 6px 12px;
    }}
    .control-group label {{
      color: var(--muted); font-size: 11px;
      text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;
      white-space: nowrap;
    }}
    .control-group input, .control-group select {{
      background: var(--panel-2); border: 1px solid var(--border-2);
      border-radius: 6px; padding: 5px 8px; color: var(--text);
      font-size: 13px; width: 80px;
    }}
    .control-group select {{ width: auto; cursor: pointer; }}
    .btn {{
      background: var(--accent); color: #0a1628; font-weight: 700;
      border: none; border-radius: var(--radius-sm); padding: 8px 18px;
      font-size: 13px; cursor: pointer; transition: all 0.15s;
      white-space: nowrap;
    }}
    .btn:hover {{ background: var(--accent-2); transform: translateY(-1px); }}
    .btn-ghost {{
      background: transparent; border: 1px solid var(--border-2);
      color: var(--text-2);
    }}
    .btn-ghost:hover {{ border-color: var(--accent); color: var(--accent); background: transparent; }}

    /* ---- KPI CARDS ---- */
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }}
    .kpi {{
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 16px 18px;
      position: relative; overflow: hidden;
    }}
    .kpi::after {{
      content: ''; position: absolute; top: 0; left: 0; right: 0;
      height: 3px; background: linear-gradient(90deg, var(--accent), transparent);
    }}
    .kpi.green::after {{ background: linear-gradient(90deg, var(--green), transparent); }}
    .kpi .kpi-label {{
      color: var(--muted); font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600;
    }}
    .kpi .kpi-value {{
      font-size: 28px; font-weight: 800; margin-top: 4px;
      font-variant-numeric: tabular-nums;
    }}
    .kpi .kpi-sub {{ color: var(--muted); font-size: 12px; margin-top: 2px; }}

    /* ---- BOOKS BAR ---- */
    .books-bar {{
      display: flex; gap: 8px; flex-wrap: wrap;
      margin-bottom: 24px; align-items: center;
    }}
    .books-bar .label {{
      color: var(--muted); font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600; margin-right: 4px;
    }}
    .book-chip {{
      display: inline-flex; align-items: center; gap: 6px;
      background: var(--panel); border: 1px solid var(--border-2);
      border-radius: 20px; padding: 5px 14px; font-size: 12px;
      font-weight: 600; cursor: pointer; transition: all 0.15s;
      user-select: none; color: var(--text-2);
    }}
    .book-chip.active {{
      background: rgba(6,182,212,0.12); border-color: var(--accent);
      color: var(--accent);
    }}
    .book-chip:hover {{ border-color: var(--accent); }}

    /* ---- SECTION TITLES ---- */
    .section-title {{
      font-size: 14px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--text-2);
      margin-bottom: 16px; display: flex; align-items: center; gap: 10px;
    }}
    .section-title::after {{
      content: ''; flex: 1; height: 1px; background: var(--border);
    }}
    .section-title .count {{
      background: var(--accent); color: #0a1628; border-radius: 10px;
      padding: 1px 8px; font-size: 11px; font-weight: 700;
    }}

    /* ---- GAME CARDS ---- */
    .games-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
      gap: 16px; margin-bottom: 32px;
    }}
    .game-card {{
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: hidden;
      transition: border-color 0.2s;
    }}
    .game-card:hover {{ border-color: var(--border-2); }}
    .game-card.has-value {{ border-color: var(--green-border); }}
    .game-header {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 14px 18px; border-bottom: 1px solid var(--border);
      background: var(--panel-2);
    }}
    .game-matchup {{
      display: flex; align-items: center; gap: 12px; font-weight: 700;
      font-size: 15px;
    }}
    .team-badge {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 36px; height: 36px; border-radius: 8px;
      background: var(--panel-3); font-size: 11px; font-weight: 800;
      color: var(--text); letter-spacing: 0.02em;
    }}
    .vs {{ color: var(--muted); font-size: 12px; font-weight: 400; }}
    .game-time {{ color: var(--muted); font-size: 12px; }}
    .game-value-tag {{
      background: var(--green-bg); color: var(--green);
      border: 1px solid var(--green-border); border-radius: 6px;
      padding: 2px 10px; font-size: 11px; font-weight: 700;
    }}

    /* Probability bar */
    .prob-bar-wrap {{ padding: 12px 18px; }}
    .prob-labels {{
      display: flex; justify-content: space-between; font-size: 12px;
      margin-bottom: 6px;
    }}
    .prob-labels .team {{ font-weight: 700; }}
    .prob-labels .pct {{ font-weight: 600; color: var(--accent); }}
    .prob-bar {{
      height: 6px; background: var(--panel-3); border-radius: 3px;
      overflow: hidden; position: relative;
    }}
    .prob-bar .fill {{
      height: 100%; border-radius: 3px;
      background: linear-gradient(90deg, var(--accent), var(--green));
      transition: width 0.4s ease;
    }}

    /* Book odds table inside game card */
    .book-odds {{ padding: 0 18px 14px; }}
    .book-odds table {{ width: 100%; border-collapse: collapse; }}
    .book-odds th {{
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600; padding: 6px 0;
      text-align: left; border-bottom: 1px solid var(--border);
    }}
    .book-odds td {{
      padding: 7px 0; font-size: 13px; border-bottom: 1px solid rgba(30,41,59,0.5);
      font-variant-numeric: tabular-nums;
    }}
    .book-odds tr:last-child td {{ border-bottom: none; }}
    .book-odds .book-name {{ font-weight: 600; color: var(--text-2); }}
    .book-odds .odds {{ font-weight: 600; }}
    .book-odds .edge-positive {{ color: var(--green); font-weight: 700; }}
    .book-odds .edge-negative {{ color: var(--muted); }}
    .book-odds .best-line {{
      background: var(--green-bg); border-radius: 4px; padding: 1px 6px;
    }}
    .book-odds .value-badge {{
      display: inline-flex; align-items: center; gap: 3px;
      font-size: 10px; font-weight: 700; color: var(--green);
    }}

    /* ---- VALUE BETS TABLE ---- */
    .value-section {{ margin-bottom: 32px; }}
    .value-table-wrap {{
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: auto;
    }}
    .value-table {{ border-collapse: collapse; width: 100%; min-width: 900px; }}
    .value-table th {{
      padding: 12px 14px; text-align: left;
      color: var(--muted); font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600;
      background: var(--panel-2); border-bottom: 1px solid var(--border);
      position: sticky; top: 0; cursor: pointer;
    }}
    .value-table th:hover {{ color: var(--accent); }}
    .value-table td {{
      padding: 10px 14px; border-bottom: 1px solid var(--border);
      font-size: 13px; font-variant-numeric: tabular-nums;
    }}
    .value-table tr:hover td {{ background: rgba(6,182,212,0.03); }}
    .value-table .edge-col {{
      font-weight: 700; color: var(--green);
    }}
    .value-table .ev-col {{ font-weight: 600; color: var(--green); }}
    .value-table .odds-col {{ font-weight: 600; }}
    .value-table .stake-col {{ font-weight: 700; }}
    .edge-bar {{
      display: inline-block; height: 4px; border-radius: 2px;
      background: var(--green); margin-left: 8px; vertical-align: middle;
      min-width: 4px;
    }}
    .conf-dot {{
      display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    }}
    .conf-high {{ background: var(--green); }}
    .conf-med {{ background: var(--amber); }}
    .conf-low {{ background: var(--red); }}

    /* ---- BANKROLL METER ---- */
    .bankroll-bar {{
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 18px;
      display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
      margin-bottom: 24px;
    }}
    .bankroll-bar .info {{ flex: 1; min-width: 200px; }}
    .bankroll-bar .info .label {{
      color: var(--muted); font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600;
    }}
    .bankroll-bar .info .amount {{ font-size: 20px; font-weight: 700; margin-top: 2px; }}
    .meter {{ flex: 2; min-width: 200px; }}
    .meter .meter-track {{
      height: 10px; background: var(--panel-3); border-radius: 5px;
      overflow: hidden; position: relative;
    }}
    .meter .meter-fill {{
      height: 100%; border-radius: 5px; transition: width 0.4s ease;
      background: linear-gradient(90deg, var(--green), var(--accent));
    }}
    .meter .meter-fill.warn {{ background: linear-gradient(90deg, var(--amber), var(--red)); }}
    .meter .meter-labels {{
      display: flex; justify-content: space-between; font-size: 11px;
      color: var(--muted); margin-top: 4px;
    }}

    /* ---- EMPTY STATE ---- */
    .empty {{
      text-align: center; padding: 60px 20px; color: var(--muted);
    }}
    .empty .icon {{ font-size: 48px; margin-bottom: 12px; opacity: 0.5; }}
    .empty h3 {{ color: var(--text-2); margin-bottom: 8px; }}

    /* ---- RESPONSIVE ---- */
    @media (max-width: 768px) {{
      .app {{ padding: 0 12px 24px; }}
      .header {{ flex-direction: column; align-items: flex-start; }}
      .kpis {{ grid-template-columns: repeat(2, 1fr); }}
      .games-grid {{ grid-template-columns: 1fr; }}
      .kpi .kpi-value {{ font-size: 22px; }}
      .controls {{ flex-direction: column; }}
    }}

    /* ---- PLAYS CARDS ---- */
    .plays-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 14px; margin-bottom: 32px;
    }}
    .play-card {{
      background: linear-gradient(135deg, rgba(16,185,129,0.08), rgba(6,182,212,0.05));
      border: 1px solid var(--green-border);
      border-radius: var(--radius); padding: 18px; position: relative;
    }}
    .play-card .play-num {{
      position: absolute; top: 14px; right: 16px;
      background: var(--green); color: #041109; width: 28px; height: 28px;
      border-radius: 50%; display: flex; align-items: center;
      justify-content: center; font-size: 13px; font-weight: 800;
    }}
    .play-card .play-action {{
      font-size: 18px; font-weight: 800; color: var(--green);
      margin-bottom: 6px;
    }}
    .play-card .play-game {{
      color: var(--muted); font-size: 13px; margin-bottom: 10px;
    }}
    .play-details {{
      display: grid; grid-template-columns: 1fr 1fr 1fr;
      gap: 8px; font-size: 12px;
    }}
    .play-details .detail-label {{ color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .play-details .detail-value {{ font-weight: 700; font-size: 15px; margin-top: 2px; }}
    .play-details .detail-value.green {{ color: var(--green); }}

    /* ---- MARKET TABS ---- */
    .market-tabs {{
      display: flex; gap: 0; border-bottom: 1px solid var(--border);
      padding: 0 18px;
    }}
    .market-tab {{
      padding: 8px 16px; font-size: 11px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.06em;
      color: var(--muted); cursor: pointer; border-bottom: 2px solid transparent;
      transition: all 0.15s;
    }}
    .market-tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
    .market-tab:hover {{ color: var(--text-2); }}
    .market-panel {{ display: none; }}
    .market-panel.active {{ display: block; }}

    /* ---- FOOTER ---- */
    .footer {{
      text-align: center; padding: 24px; color: var(--muted);
      font-size: 12px; border-top: 1px solid var(--border); margin-top: 16px;
    }}
    .footer code {{
      background: var(--panel-2); padding: 2px 6px;
      border-radius: 4px; border: 1px solid var(--border);
    }}
  </style>
</head>
<body>
<div class="app">

  <!-- HEADER -->
  <div class="header">
    <div class="brand">
      <div class="logo">MP</div>
      <div>
        <h1>MoneyPuck Edge Intelligence</h1>
        <div class="sub">Multi-book NHL betting edge detection — Quebec</div>
      </div>
    </div>
    <div class="header-actions">
      <div class="badge" id="mode-badge">DEMO</div>
      <button class="btn" id="btn-refresh" onclick="refreshDashboard()">Refresh</button>
    </div>
  </div>

  <!-- CONTROLS -->
  <div class="controls">
    <div class="control-group">
      <label>Region</label>
      <select id="ctl-region">
        <option value="qc" selected>Quebec</option>
        <option value="on">Ontario</option>
        <option value="ca">Canada</option>
        <option value="us">US</option>
      </select>
    </div>
    <div class="control-group">
      <label>Bankroll</label>
      <input id="ctl-bankroll" type="number" step="100" value="1000">
    </div>
    <div class="control-group">
      <label>Min Edge</label>
      <input id="ctl-min-edge" type="number" step="0.5" value="2.0">
    </div>
    <div class="control-group">
      <label>Min EV</label>
      <input id="ctl-min-ev" type="number" step="0.01" value="0.02">
    </div>
    <div class="control-group">
      <label>Season</label>
      <input id="ctl-season" type="number" value="2024">
    </div>
    <button class="btn btn-ghost" onclick="refreshDashboard(true)">Demo Data</button>
  </div>

  <!-- BOOK FILTER -->
  <div class="books-bar" id="books-bar">
    <span class="label">Books</span>
  </div>

  <!-- KPI CARDS -->
  <div class="kpis">
    <div class="kpi"><div class="kpi-label">Active Books</div><div class="kpi-value" id="kpi-books">0</div></div>
    <div class="kpi"><div class="kpi-label">Games Tonight</div><div class="kpi-value" id="kpi-games">0</div></div>
    <div class="kpi green"><div class="kpi-label">Value Bets</div><div class="kpi-value" id="kpi-bets">0</div></div>
    <div class="kpi green"><div class="kpi-label">Avg Edge</div><div class="kpi-value" id="kpi-edge">0pp</div><div class="kpi-sub">probability points</div></div>
    <div class="kpi"><div class="kpi-label">Best Edge</div><div class="kpi-value" id="kpi-best">0pp</div></div>
    <div class="kpi"><div class="kpi-label">Total Stake</div><div class="kpi-value" id="kpi-stake">$0</div></div>
  </div>

  <!-- BANKROLL METER -->
  <div class="bankroll-bar">
    <div class="info">
      <div class="label">Bankroll Exposure</div>
      <div class="amount" id="bankroll-amount">$0 / $1,000</div>
    </div>
    <div class="meter">
      <div class="meter-track"><div class="meter-fill" id="meter-fill" style="width:0%"></div></div>
      <div class="meter-labels"><span>0%</span><span id="meter-pct">0%</span><span>Cap 15%</span></div>
    </div>
  </div>

  <!-- TODAY'S PLAYS (clear action items) -->
  <div class="section-title" id="plays-title">Today's Plays <span class="count" id="plays-count">0</span></div>
  <div class="plays-grid" id="plays-grid"></div>

  <!-- GAMES -->
  <div class="section-title">Tonight's Games <span class="count" id="games-count">0</span></div>
  <div class="games-grid" id="games-grid"></div>

  <!-- VALUE BETS (detailed table) -->
  <div class="value-section">
    <div class="section-title">Detailed Breakdown <span class="count" id="bets-count">0</span></div>
    <div class="value-table-wrap">
      <table class="value-table">
        <thead>
          <tr>
            <th onclick="sortBets('game')">#</th>
            <th onclick="sortBets('game')">Game</th>
            <th onclick="sortBets('side')">Pick</th>
            <th onclick="sortBets('sportsbook')">Book</th>
            <th onclick="sortBets('american_odds')">American</th>
            <th>Decimal</th>
            <th onclick="sortBets('implied_probability')">Market %</th>
            <th onclick="sortBets('model_probability')">Model %</th>
            <th onclick="sortBets('edge_probability_points')">Edge</th>
            <th onclick="sortBets('expected_value_per_dollar')">EV/$</th>
            <th onclick="sortBets('confidence')">Conf</th>
            <th onclick="sortBets('recommended_stake')">Stake</th>
          </tr>
        </thead>
        <tbody id="bets-body"></tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Model: 16-metric composite | Logistic win probability | Confidence-adj Kelly<br>
    API: <code>/api/dashboard</code> | <code>/api/opportunities</code>
  </div>
</div>

<script>
const D = {data_json};
let activeBooks = new Set((D.books || []).map(b => b));
let currentData = D;
let sortKey = 'edge_probability_points';
let sortDesc = true;

function init() {{
  renderBooks(D.books || []);
  render(D);
}}

function renderBooks(books) {{
  const bar = document.getElementById('books-bar');
  bar.innerHTML = '<span class="label">Books</span>';
  books.forEach(b => {{
    const chip = document.createElement('div');
    chip.className = 'book-chip' + (activeBooks.has(b) ? ' active' : '');
    chip.textContent = b;
    chip.onclick = () => {{
      if (activeBooks.has(b)) activeBooks.delete(b); else activeBooks.add(b);
      chip.classList.toggle('active');
      render(currentData);
    }};
    bar.appendChild(chip);
  }});
}}

function fmtOdds(n) {{ return n > 0 ? '+' + n : '' + n; }}
function toDecimal(am) {{ return am > 0 ? (am/100 + 1).toFixed(2) : (100/Math.abs(am) + 1).toFixed(2); }}
function pct(v) {{ return (v * 100).toFixed(1) + '%'; }}
function n(v, d) {{ return Number(v).toFixed(d || 2); }}

function render(data) {{
  currentData = data;
  const games = data.games || [];
  const bets = (data.value_bets || []).filter(b => activeBooks.has(b.sportsbook));
  const summary = data.summary || {{}};
  const bankroll = Number(document.getElementById('ctl-bankroll').value) || 1000;

  // Filter game book odds by active books
  const filteredGames = games.map(g => ({{
    ...g,
    books: (g.books || []).filter(b => activeBooks.has(b.name))
  }}));

  // KPIs
  document.getElementById('kpi-books').textContent = activeBooks.size;
  document.getElementById('kpi-games').textContent = games.length;
  document.getElementById('kpi-bets').textContent = bets.length;
  const avgEdge = bets.length ? bets.reduce((a,b) => a + b.edge_probability_points, 0) / bets.length : 0;
  const bestEdge = bets.length ? Math.max(...bets.map(b => b.edge_probability_points)) : 0;
  const totalStake = bets.reduce((a,b) => a + b.recommended_stake, 0);
  document.getElementById('kpi-edge').textContent = '+' + n(avgEdge) + 'pp';
  document.getElementById('kpi-best').textContent = '+' + n(bestEdge) + 'pp';
  document.getElementById('kpi-stake').textContent = '$' + n(totalStake);

  // Mode badge
  const badge = document.getElementById('mode-badge');
  if (data.mode === 'live') {{
    badge.className = 'badge live'; badge.textContent = 'LIVE';
  }} else {{
    badge.className = 'badge demo'; badge.textContent = 'DEMO';
  }}

  // Bankroll meter
  const exposurePct = bankroll > 0 ? (totalStake / bankroll) * 100 : 0;
  document.getElementById('bankroll-amount').textContent = '$' + n(totalStake) + ' / $' + bankroll.toLocaleString();
  const fill = document.getElementById('meter-fill');
  fill.style.width = Math.min(exposurePct, 100) + '%';
  fill.className = 'meter-fill' + (exposurePct > 15 ? ' warn' : '');
  document.getElementById('meter-pct').textContent = n(exposurePct, 1) + '%';

  // Plays (clear action items)
  document.getElementById('plays-count').textContent = bets.length;
  renderPlays(bets);

  // Games
  gameIdCounter = 0;
  document.getElementById('games-count').textContent = filteredGames.length;
  const grid = document.getElementById('games-grid');
  if (!filteredGames.length) {{
    grid.innerHTML = '<div class="empty"><div class="icon">&#127954;</div><h3>No games loaded</h3><p>Click Refresh or Demo Data to load games</p></div>';
  }} else {{
    grid.innerHTML = filteredGames.map(g => renderGameCard(g, bets)).join('');
  }}

  // Value bets table
  document.getElementById('bets-count').textContent = bets.length;
  renderBets(bets);
}}

function renderPlays(bets) {{
  const grid = document.getElementById('plays-grid');
  if (!bets.length) {{
    grid.innerHTML = '<div class="empty" style="grid-column:1/-1;padding:30px"><h3>No plays found</h3><p>Adjust thresholds or check back later</p></div>';
    return;
  }}
  grid.innerHTML = bets.slice(0, 8).map((b, i) => {{
    const game = b.away_team + ' @ ' + b.home_team;
    const decOdds = b.decimal_odds || toDecimal(b.american_odds);
    return `
      <div class="play-card">
        <div class="play-num">${{i+1}}</div>
        <div class="play-action">BET ${{b.side}} ${{b.market || 'ML'}}</div>
        <div class="play-game">${{game}}</div>
        <div class="play-details">
          <div><div class="detail-label">Book</div><div class="detail-value">${{b.sportsbook}}</div></div>
          <div><div class="detail-label">Odds</div><div class="detail-value">${{fmtOdds(b.american_odds)}} / ${{decOdds}}</div></div>
          <div><div class="detail-label">Stake</div><div class="detail-value green">$${{n(b.recommended_stake)}}</div></div>
          <div><div class="detail-label">Edge</div><div class="detail-value green">+${{n(b.edge_probability_points)}}pp</div></div>
          <div><div class="detail-label">Model</div><div class="detail-value">${{pct(b.model_probability)}}</div></div>
          <div><div class="detail-label">EV/$1</div><div class="detail-value green">${{n(b.expected_value_per_dollar, 3)}}</div></div>
        </div>
      </div>`;
  }}).join('');
}}

let gameIdCounter = 0;
function renderGameCard(g, bets) {{
  const gid = 'g' + (gameIdCounter++);
  const hasValue = bets.some(b => (b.home_team === g.home && b.away_team === g.away) || (b.home_team === g.away && b.away_team === g.home));
  const hp = (g.home_prob * 100).toFixed(1);
  const ap = (g.away_prob * 100).toFixed(1);
  const time = g.commence ? new Date(g.commence).toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit', timeZone:'America/New_York'}}) + ' ET' : '';

  const hasSpread = g.books && g.books.some(b => b.home_spread_odds);
  const hasTotal = g.books && g.books.some(b => b.over_odds);

  let mlHtml = '', spreadHtml = '', totalHtml = '';
  if (g.books && g.books.length) {{
    const bestHomeOdds = Math.max(...g.books.map(b => b.home_odds || -9999));
    const bestAwayOdds = Math.max(...g.books.map(b => b.away_odds || -9999));
    mlHtml = `<table>
      <tr><th>Book</th><th>${{g.home}} ML</th><th>Dec</th><th>${{g.away}} ML</th><th>Dec</th><th>Edge</th></tr>
      ${{g.books.map(b => {{
        const homeEdge = b.home_edge || 0;
        const awayEdge = b.away_edge || 0;
        const bestEdge = Math.max(homeEdge, awayEdge);
        const isBestHome = b.home_odds === bestHomeOdds;
        const isBestAway = b.away_odds === bestAwayOdds;
        return `<tr>
          <td class="book-name">${{b.name}}</td>
          <td class="odds ${{isBestHome ? 'best-line' : ''}}">${{fmtOdds(b.home_odds)}}</td>
          <td class="muted">${{toDecimal(b.home_odds)}}</td>
          <td class="odds ${{isBestAway ? 'best-line' : ''}}">${{fmtOdds(b.away_odds)}}</td>
          <td class="muted">${{toDecimal(b.away_odds)}}</td>
          <td class="${{bestEdge > 0 ? 'edge-positive' : 'edge-negative'}}">
            ${{bestEdge > 0 ? '+' + n(bestEdge) + 'pp' : '-'}}
            ${{bestEdge >= 2 ? '<span class="value-badge">VALUE</span>' : ''}}
          </td>
        </tr>`;
      }}).join('')}}</table>`;

    if (hasSpread) {{
      const sb = g.books.filter(b => b.home_spread_odds);
      const spread = sb[0]?.home_spread || -1.5;
      spreadHtml = `<table>
        <tr><th>Book</th><th>${{g.home}} ${{spread}}</th><th>Dec</th><th>${{g.away}} ${{-spread}}</th><th>Dec</th></tr>
        ${{sb.map(b => `<tr>
          <td class="book-name">${{b.name}}</td>
          <td class="odds">${{fmtOdds(b.home_spread_odds)}}</td>
          <td class="muted">${{toDecimal(b.home_spread_odds)}}</td>
          <td class="odds">${{fmtOdds(b.away_spread_odds)}}</td>
          <td class="muted">${{toDecimal(b.away_spread_odds)}}</td>
        </tr>`).join('')}}</table>`;
    }}

    if (hasTotal) {{
      const tb = g.books.filter(b => b.over_odds);
      const line = tb[0]?.total_line || 5.5;
      totalHtml = `<table>
        <tr><th>Book</th><th>Over ${{line}}</th><th>Dec</th><th>Under ${{line}}</th><th>Dec</th></tr>
        ${{tb.map(b => `<tr>
          <td class="book-name">${{b.name}}</td>
          <td class="odds">${{fmtOdds(b.over_odds)}}</td>
          <td class="muted">${{toDecimal(b.over_odds)}}</td>
          <td class="odds">${{fmtOdds(b.under_odds)}}</td>
          <td class="muted">${{toDecimal(b.under_odds)}}</td>
        </tr>`).join('')}}</table>`;
    }}
  }}

  return `
    <div class="game-card ${{hasValue ? 'has-value' : ''}}">
      <div class="game-header">
        <div class="game-matchup">
          <span class="team-badge">${{g.away}}</span>
          <span class="vs">@</span>
          <span class="team-badge">${{g.home}}</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          ${{hasValue ? '<span class="game-value-tag">VALUE</span>' : ''}}
          <span class="game-time">${{time}}</span>
        </div>
      </div>
      <div class="prob-bar-wrap">
        <div class="prob-labels">
          <div><span class="team">${{g.away}}</span> <span class="pct">${{ap}}%</span></div>
          <div><span class="pct">${{hp}}%</span> <span class="team">${{g.home}}</span></div>
        </div>
        <div class="prob-bar"><div class="fill" style="width:${{hp}}%"></div></div>
      </div>
      <div class="market-tabs">
        <div class="market-tab active" onclick="switchTab('${{gid}}','ml',this)">Moneyline</div>
        ${{hasSpread ? `<div class="market-tab" onclick="switchTab('${{gid}}','spread',this)">Puck Line</div>` : ''}}
        ${{hasTotal ? `<div class="market-tab" onclick="switchTab('${{gid}}','total',this)">Over/Under</div>` : ''}}
      </div>
      <div class="book-odds">
        <div class="market-panel active" id="${{gid}}-ml">${{mlHtml}}</div>
        ${{hasSpread ? `<div class="market-panel" id="${{gid}}-spread">${{spreadHtml}}</div>` : ''}}
        ${{hasTotal ? `<div class="market-panel" id="${{gid}}-total">${{totalHtml}}</div>` : ''}}
      </div>
    </div>`;
}}

function renderBets(bets) {{
  const body = document.getElementById('bets-body');
  const sorted = [...bets].sort((a,b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === 'game') {{ av = a.away_team + a.home_team; bv = b.away_team + b.home_team; }}
    if (typeof av === 'string') return sortDesc ? bv.localeCompare(av) : av.localeCompare(bv);
    return sortDesc ? bv - av : av - bv;
  }});
  if (!sorted.length) {{
    body.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:30px;color:var(--muted);">No value bets found at current thresholds</td></tr>';
    return;
  }}
  body.innerHTML = sorted.map((b, i) => {{
    const game = b.away_team + ' @ ' + b.home_team;
    const edgeW = Math.min(b.edge_probability_points * 4, 80);
    const conf = b.confidence || 0;
    const confClass = conf >= 0.7 ? 'conf-high' : conf >= 0.4 ? 'conf-med' : 'conf-low';
    const decOdds = b.decimal_odds || toDecimal(b.american_odds);
    return `<tr>
      <td>${{i+1}}</td>
      <td>${{game}}</td>
      <td style="font-weight:700">${{b.side}} ${{b.market || 'ML'}}</td>
      <td>${{b.sportsbook}}</td>
      <td class="odds-col">${{fmtOdds(b.american_odds)}}</td>
      <td class="odds-col">${{decOdds}}</td>
      <td>${{pct(b.implied_probability)}}</td>
      <td style="font-weight:600">${{pct(b.model_probability)}}</td>
      <td class="edge-col">+${{n(b.edge_probability_points)}}pp <span class="edge-bar" style="width:${{edgeW}}px"></span></td>
      <td class="ev-col">${{n(b.expected_value_per_dollar, 3)}}</td>
      <td><span class="conf-dot ${{confClass}}"></span> ${{pct(conf)}}</td>
      <td class="stake-col">$${{n(b.recommended_stake)}}</td>
    </tr>`;
  }}).join('');
}}

function switchTab(gid, market, el) {{
  // Hide all panels for this game
  ['ml','spread','total'].forEach(m => {{
    const p = document.getElementById(gid + '-' + m);
    if (p) p.classList.remove('active');
  }});
  // Deactivate all tabs in this group
  el.parentElement.querySelectorAll('.market-tab').forEach(t => t.classList.remove('active'));
  // Show selected
  const panel = document.getElementById(gid + '-' + market);
  if (panel) panel.classList.add('active');
  el.classList.add('active');
}}

function sortBets(key) {{
  if (sortKey === key) sortDesc = !sortDesc;
  else {{ sortKey = key; sortDesc = true; }}
  render(currentData);
}}

async function refreshDashboard(demo) {{
  const btn = document.getElementById('btn-refresh');
  btn.textContent = 'Loading...'; btn.disabled = true;
  try {{
    const params = new URLSearchParams({{
      region: document.getElementById('ctl-region').value,
      bankroll: document.getElementById('ctl-bankroll').value,
      min_edge: document.getElementById('ctl-min-edge').value,
      min_ev: document.getElementById('ctl-min-ev').value,
      season: document.getElementById('ctl-season').value,
    }});
    if (demo) params.set('demo', '1');
    const res = await fetch('/api/dashboard?' + params.toString());
    const data = await res.json();
    if (!res.ok) {{ alert(data.error || 'Request failed'); return; }}
    activeBooks = new Set(data.books || []);
    renderBooks(data.books || []);
    render(data);
  }} catch(e) {{
    alert('Network error: ' + e.message);
  }} finally {{
    btn.textContent = 'Refresh'; btn.disabled = false;
  }}
}}

init();
</script>
</body>
</html>"""
