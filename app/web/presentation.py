from __future__ import annotations

import html
import json
from typing import Any


def to_serializable(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from app.web.deep_links import build_sportsbook_url

    rows: list[dict[str, Any]] = []
    for item in recommendations:
        candidate = item["candidate"]
        sportsbook_url = build_sportsbook_url(
            getattr(candidate, "sportsbook_key", ""),
            candidate.home_team,
            candidate.away_team,
            candidate.commence_time_utc,
        )
        rows.append(
            {
                "commence_time_utc": candidate.commence_time_utc,
                "home_team": candidate.home_team,
                "away_team": candidate.away_team,
                "side": candidate.side,
                "sportsbook": candidate.sportsbook,
                "sportsbook_url": sportsbook_url,
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
    # Escape </ sequences to prevent breaking out of <script> tags (XSS)
    data_json = json.dumps(data).replace("</", r"<\/")

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
      color: var(--muted); font-size: 12px;
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
      color: var(--muted); font-size: 12px; text-transform: uppercase;
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
      color: var(--muted); font-size: 12px; text-transform: uppercase;
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
      padding: 1px 8px; font-size: 12px; font-weight: 700;
    }}

    /* ---- GAME CARDS ---- */
    .games-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
      gap: 16px; margin-bottom: 32px;
    }}
    .game-card {{
      background: var(--panel); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: hidden;
      transition: border-color 0.2s; cursor: pointer;
    }}
    .game-card:hover {{ border-color: var(--accent); }}
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
      background: var(--panel-3); font-size: 12px; font-weight: 800;
      color: var(--text); letter-spacing: 0.02em;
    }}
    .vs {{ color: var(--muted); font-size: 12px; font-weight: 400; }}
    .game-time {{ color: var(--muted); font-size: 12px; }}
    .game-value-tag {{
      background: var(--green-bg); color: var(--green);
      border: 1px solid var(--green-border); border-radius: 6px;
      padding: 2px 10px; font-size: 12px; font-weight: 700;
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
      color: var(--muted); font-size: 12px; text-transform: uppercase;
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
      font-size: 12px; font-weight: 700; color: var(--green);
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
      color: var(--muted); font-size: 12px; text-transform: uppercase;
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
      color: var(--muted); font-size: 12px; text-transform: uppercase;
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
      display: flex; justify-content: space-between; font-size: 12px;
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
    .play-details .detail-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .play-details .detail-value {{ font-weight: 700; font-size: 15px; margin-top: 2px; }}
    .play-details .detail-value.green {{ color: var(--green); }}

    /* ---- ARB CARDS ---- */
    .arb-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
      gap: 14px; margin-bottom: 32px;
    }}
    .arb-card {{
      background: linear-gradient(135deg, rgba(245,158,11,0.08), rgba(239,68,68,0.04));
      border: 1px solid rgba(245,158,11,0.3);
      border-radius: var(--radius); padding: 18px; position: relative;
    }}
    .arb-card .arb-title {{
      font-size: 15px; font-weight: 800; color: var(--amber); margin-bottom: 4px;
    }}
    .arb-card .arb-game {{
      color: var(--muted); font-size: 12px; margin-bottom: 12px;
    }}
    .arb-leg {{
      display: flex; align-items: center; gap: 12px; padding: 8px 12px;
      background: rgba(245,158,11,0.05); border-radius: var(--radius-sm);
      margin-bottom: 6px; font-size: 13px;
    }}
    .arb-leg .leg-side {{ font-weight: 700; min-width: 80px; }}
    .arb-leg .leg-book {{ color: var(--text-2); min-width: 90px; }}
    .arb-leg .leg-odds {{ font-weight: 700; color: var(--amber); min-width: 50px; }}
    .arb-leg .leg-stake {{ font-weight: 700; color: var(--green); margin-left: auto; }}
    .arb-profit {{
      display: flex; justify-content: space-between; align-items: center;
      margin-top: 10px; padding-top: 10px; border-top: 1px solid rgba(245,158,11,0.15);
      font-size: 13px;
    }}
    .arb-profit .profit-label {{ color: var(--muted); }}
    .arb-profit .profit-value {{ font-weight: 800; color: var(--green); font-size: 16px; }}

    /* ---- MODAL ---- */
    .modal-backdrop {{
      display: none; position: fixed; inset: 0; z-index: 1000;
      background: rgba(0,0,0,0.7); backdrop-filter: blur(4px);
      justify-content: center; align-items: flex-start;
      padding: 40px 20px; overflow-y: auto;
    }}
    .modal-backdrop.open {{ display: flex; }}
    .modal-content {{
      background: var(--bg-2); border: 1px solid var(--border-2);
      border-radius: var(--radius); max-width: 720px; width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.6); position: relative;
    }}
    .modal-close {{
      position: absolute; top: 14px; right: 16px; background: none;
      border: none; color: var(--muted); font-size: 22px; cursor: pointer;
      width: 32px; height: 32px; display: flex; align-items: center;
      justify-content: center; border-radius: 6px; transition: all 0.15s;
    }}
    .modal-close:hover {{ background: var(--panel-3); color: var(--text); }}
    .modal-header {{
      padding: 20px 24px; border-bottom: 1px solid var(--border);
    }}
    .modal-header .modal-matchup {{
      font-size: 20px; font-weight: 800; display: flex;
      align-items: center; gap: 12px; margin-bottom: 12px;
    }}
    .modal-section {{
      padding: 16px 24px; border-bottom: 1px solid var(--border);
    }}
    .modal-section:last-child {{ border-bottom: none; }}
    .modal-section h3 {{
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); margin-bottom: 12px;
    }}
    .modal-section table {{ width: 100%; border-collapse: collapse; }}
    .modal-section th {{
      color: var(--muted); font-size: 12px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600; padding: 6px 0;
      text-align: left; border-bottom: 1px solid var(--border);
    }}
    .modal-section td {{
      padding: 7px 0; font-size: 13px; font-variant-numeric: tabular-nums;
      border-bottom: 1px solid rgba(30,41,59,0.5);
    }}
    .modal-section tr:last-child td {{ border-bottom: none; }}
    .top-bets {{
      background: var(--green-bg); border: 1px solid var(--green-border);
      border-radius: var(--radius-sm); padding: 14px 16px;
    }}
    .top-bet-row {{
      display: flex; align-items: center; gap: 10px; padding: 6px 0;
      font-size: 13px;
    }}
    .top-bet-row .rank {{
      background: var(--green); color: #041109; width: 22px; height: 22px;
      border-radius: 50%; display: flex; align-items: center;
      justify-content: center; font-size: 12px; font-weight: 800; flex-shrink: 0;
    }}
    .top-bet-row .bet-desc {{ font-weight: 700; }}
    .top-bet-row .bet-meta {{ color: var(--muted); font-size: 12px; margin-left: auto; }}
    .muted {{ color: var(--muted); }}
    .best-star {{ color: var(--green); font-weight: 700; }}
    .arb-badge {{ color: var(--amber); font-weight: 700; font-size: 12px; }}
    .no-arb {{ color: var(--muted); font-size: 12px; padding: 8px 0; }}

    /* ---- LOADING OVERLAY ---- */
    .loading-overlay {{
      display: none; position: fixed; inset: 0; z-index: 900;
      background: rgba(6,8,15,0.7); backdrop-filter: blur(2px);
      justify-content: center; align-items: center; flex-direction: column;
    }}
    .loading-overlay.active {{ display: flex; }}
    .loading-spinner {{
      width: 40px; height: 40px; border: 3px solid var(--border-2);
      border-top-color: var(--accent); border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }}
    .loading-text {{
      color: var(--text-2); font-size: 14px; font-weight: 600; margin-top: 14px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

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

  <!-- ARB ALERTS -->
  <div class="section-title">Arb Alerts <span class="count" id="arb-count">0</span></div>
  <div class="arb-grid" id="arb-grid"></div>

  <!-- GAMES -->
  <div class="section-title">Tonight's Games — click for details <span class="count" id="games-count">0</span></div>
  <div class="games-grid" id="games-grid"></div>

  <!-- VALUE BETS (detailed table) -->
  <div class="value-section">
    <div class="section-title">Detailed Breakdown <span class="count" id="bets-count">0</span></div>
    <div class="value-table-wrap">
      <table class="value-table">
        <thead>
          <tr>
            <th onclick="sortBets('game')" data-sort-key="game">#</th>
            <th onclick="sortBets('game')" data-sort-key="game">Game</th>
            <th onclick="sortBets('side')" data-sort-key="side">Pick</th>
            <th onclick="sortBets('sportsbook')" data-sort-key="sportsbook">Book</th>
            <th onclick="sortBets('decimal_odds')" data-sort-key="decimal_odds">Odds</th>
            <th onclick="sortBets('implied_probability')" data-sort-key="implied_probability">Market %</th>
            <th onclick="sortBets('model_probability')" data-sort-key="model_probability">Model %</th>
            <th onclick="sortBets('edge_probability_points')" data-sort-key="edge_probability_points">Edge</th>
            <th onclick="sortBets('expected_value_per_dollar')" data-sort-key="expected_value_per_dollar">EV/$</th>
            <th onclick="sortBets('confidence')" data-sort-key="confidence">Conf</th>
            <th onclick="sortBets('recommended_stake')" data-sort-key="recommended_stake">Stake</th>
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

<!-- LOADING OVERLAY -->
<div class="loading-overlay" id="loading-overlay">
  <div class="loading-spinner"></div>
  <div class="loading-text">Loading dashboard...</div>
</div>

<!-- GAME DETAIL MODAL -->
<div class="modal-backdrop" id="game-modal" onclick="if(event.target===this)closeGameModal()" role="dialog" aria-modal="true" aria-label="Game detail">
  <div class="modal-content" id="modal-body"></div>
</div>

<script type="application/json" id="app-data">{data_json}</script>
<script>
const D = JSON.parse(document.getElementById('app-data').textContent);
function esc(s){{const d=document.createElement('div');d.textContent=String(s);return d.innerHTML;}}
function bookLink(name, url){{if(url)return `<a href="${{esc(url)}}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none">${{esc(name)}}</a>`;return esc(name);}}
let activeBooks = new Set((D.books || []).map(b => b));
let currentData = D;
let currentFilteredGames = [];
let sortKey = 'edge_probability_points';
let sortDesc = true;

function savePrefs() {{
  try {{
    localStorage.setItem('mp_region', document.getElementById('ctl-region').value);
    localStorage.setItem('mp_bankroll', document.getElementById('ctl-bankroll').value);
    localStorage.setItem('mp_min_edge', document.getElementById('ctl-min-edge').value);
    localStorage.setItem('mp_min_ev', document.getElementById('ctl-min-ev').value);
    localStorage.setItem('mp_activeBooks', JSON.stringify([...activeBooks]));
  }} catch(e) {{}}
}}

function restorePrefs() {{
  try {{
    const region = localStorage.getItem('mp_region');
    if (region) document.getElementById('ctl-region').value = region;
    const bankroll = localStorage.getItem('mp_bankroll');
    if (bankroll) document.getElementById('ctl-bankroll').value = bankroll;
    const minEdge = localStorage.getItem('mp_min_edge');
    if (minEdge) document.getElementById('ctl-min-edge').value = minEdge;
    const minEv = localStorage.getItem('mp_min_ev');
    if (minEv) document.getElementById('ctl-min-ev').value = minEv;
    const savedBooks = localStorage.getItem('mp_activeBooks');
    if (savedBooks) {{
      const arr = JSON.parse(savedBooks);
      const available = new Set(D.books || []);
      activeBooks = new Set(arr.filter(b => available.has(b)));
    }}
  }} catch(e) {{}}
}}

function init() {{
  restorePrefs();
  renderBooks(D.books || []);
  render(D);
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeGameModal(); }});
  // Save prefs when controls change
  ['ctl-region','ctl-bankroll','ctl-min-edge','ctl-min-ev'].forEach(id => {{
    document.getElementById(id).addEventListener('change', savePrefs);
  }});
}}

function renderBooks(books) {{
  const bar = document.getElementById('books-bar');
  bar.innerHTML = '<span class="label">Books</span>';
  books.forEach(b => {{
    const chip = document.createElement('div');
    chip.className = 'book-chip' + (activeBooks.has(b) ? ' active' : '');
    chip.textContent = b;
    chip.setAttribute('role', 'button');
    chip.setAttribute('tabindex', '0');
    chip.setAttribute('aria-pressed', activeBooks.has(b) ? 'true' : 'false');
    const toggle = () => {{
      if (activeBooks.has(b)) activeBooks.delete(b); else activeBooks.add(b);
      chip.classList.toggle('active');
      chip.setAttribute('aria-pressed', activeBooks.has(b) ? 'true' : 'false');
      render(currentData);
      savePrefs();
    }};
    chip.onclick = toggle;
    chip.onkeydown = (e) => {{ if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); toggle(); }} }};
    bar.appendChild(chip);
  }});
}}

function dec(am) {{ return am > 0 ? (am/100 + 1).toFixed(2) : (100/Math.abs(am) + 1).toFixed(2); }}
function pct(v) {{ return (v * 100).toFixed(1) + '%'; }}
function n(v, d) {{ return Number(v).toFixed(d || 2); }}

function render(data) {{
  currentData = data;
  const games = data.games || [];
  const bets = (data.value_bets || []).filter(b => activeBooks.has(b.sportsbook));
  const arbs = (data.arb_opportunities || []).filter(a => activeBooks.has(a.side_a_book) && activeBooks.has(a.side_b_book));
  const bankroll = Number(document.getElementById('ctl-bankroll').value) || 1000;

  // Filter game book odds by active books
  currentFilteredGames = games.map(g => ({{
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

  // Plays
  document.getElementById('plays-count').textContent = bets.length;
  renderPlays(bets);

  // Arbs
  document.getElementById('arb-count').textContent = arbs.length;
  renderArbs(arbs);

  // Games (simplified clickable cards)
  document.getElementById('games-count').textContent = currentFilteredGames.length;
  const grid = document.getElementById('games-grid');
  if (!currentFilteredGames.length) {{
    grid.innerHTML = '<div class="empty"><div class="icon">&#127954;</div><h3>No games loaded</h3><p>Click Refresh or Demo Data to load games</p></div>';
  }} else {{
    grid.innerHTML = currentFilteredGames.map((g, i) => renderGameCard(g, bets, i)).join('');
  }}

  // Value bets table
  document.getElementById('bets-count').textContent = bets.length;
  renderBets(bets);
}}

/* ---- TODAY'S PLAYS (decimal only) ---- */
function renderPlays(bets) {{
  const grid = document.getElementById('plays-grid');
  if (!bets.length) {{
    grid.innerHTML = '<div class="empty" style="grid-column:1/-1;padding:30px"><h3>No plays found</h3><p>Adjust thresholds or check back later</p></div>';
    return;
  }}
  grid.innerHTML = bets.slice(0, 8).map((b, i) => {{
    const game = esc(b.away_team) + ' @ ' + esc(b.home_team);
    const odds = b.decimal_odds || dec(b.american_odds);
    return `
      <div class="play-card">
        <div class="play-num">${{i+1}}</div>
        <div class="play-action">BET ${{esc(b.side)}} ${{esc(b.market || 'ML')}}</div>
        <div class="play-game">${{game}}</div>
        <div class="play-details">
          <div><div class="detail-label">Book</div><div class="detail-value">${{bookLink(b.sportsbook, b.sportsbook_url)}}</div></div>
          <div><div class="detail-label">Odds</div><div class="detail-value">${{odds}}</div></div>
          <div><div class="detail-label">Stake</div><div class="detail-value green">$${{n(b.recommended_stake)}}</div></div>
          <div><div class="detail-label">Edge</div><div class="detail-value green">+${{n(b.edge_probability_points)}}pp</div></div>
          <div><div class="detail-label">Model</div><div class="detail-value">${{pct(b.model_probability)}}</div></div>
          <div><div class="detail-label">EV/$1</div><div class="detail-value green">${{n(b.expected_value_per_dollar, 3)}}</div></div>
        </div>
      </div>`;
  }}).join('');
}}

/* ---- ARB ALERTS ---- */
function renderArbs(arbs) {{
  const grid = document.getElementById('arb-grid');
  if (!arbs.length) {{
    grid.innerHTML = '<div class="empty" style="grid-column:1/-1;padding:20px;font-size:13px"><p>No arbitrage opportunities found — lines are tight</p></div>';
    return;
  }}
  grid.innerHTML = arbs.map(a => {{
    const game = esc(a.away_team) + ' @ ' + esc(a.home_team);
    const dollarA = (a.stake_a_pct).toFixed(2);
    const dollarB = (a.stake_b_pct).toFixed(2);
    return `
      <div class="arb-card">
        <div class="arb-title">ARB: ${{esc(a.market)}}</div>
        <div class="arb-game">${{game}}</div>
        <div class="arb-leg">
          <span class="leg-side">${{esc(a.side_a)}}</span>
          <span class="leg-book">${{bookLink(a.side_a_book, a.side_a_url)}}</span>
          <span class="leg-odds">${{n(a.side_a_odds)}}</span>
          <span class="leg-stake">${{n(a.stake_a_pct, 1)}}% ($${{dollarA}})</span>
        </div>
        <div class="arb-leg">
          <span class="leg-side">${{esc(a.side_b)}}</span>
          <span class="leg-book">${{bookLink(a.side_b_book, a.side_b_url)}}</span>
          <span class="leg-odds">${{n(a.side_b_odds)}}</span>
          <span class="leg-stake">${{n(a.stake_b_pct, 1)}}% ($${{dollarB}})</span>
        </div>
        <div class="arb-profit">
          <span class="profit-label">Per $100 wagered</span>
          <span class="profit-value">+$${{n(a.profit_pct, 2)}} (${{n(a.profit_pct, 1)}}%)</span>
        </div>
      </div>`;
  }}).join('');
}}

/* ---- SIMPLIFIED GAME CARD (clickable preview) ---- */
function renderGameCard(g, bets, idx) {{
  const hasValue = bets.some(b => (b.home_team === g.home && b.away_team === g.away) || (b.home_team === g.away && b.away_team === g.home));
  const hp = (g.home_prob * 100).toFixed(1);
  const ap = (g.away_prob * 100).toFixed(1);
  const time = g.commence ? new Date(g.commence).toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit', timeZone:'America/New_York'}}) + ' ET' : '';

  // Best ML line summary + Polymarket
  let bestLine = '';
  if (g.books && g.books.length) {{
    const bestH = Math.max(...g.books.map(b => b.home_odds || -9999));
    const bestA = Math.max(...g.books.map(b => b.away_odds || -9999));
    const polyLine = g.poly_home_prob ? ` &middot; <span style="color:var(--amber)">Poly: ${{esc(g.home)}} ${{pct(g.poly_home_prob)}}</span>` : '';
    bestLine = `<div style="padding:8px 18px 14px;font-size:12px;color:var(--text-2)">
      Best ML: <strong>${{esc(g.home)}} ${{dec(bestH)}}</strong> &middot;
      <strong>${{esc(g.away)}} ${{dec(bestA)}}</strong>
      &middot; ${{g.books.length}} books${{polyLine}}
    </div>`;
  }}

  return `
    <div class="game-card ${{hasValue ? 'has-value' : ''}}" onclick="openGameModal(${{idx}})" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();openGameModal(${{idx}})}}">
      <div class="game-header">
        <div class="game-matchup">
          <span class="team-badge">${{esc(g.away)}}</span>
          <span class="vs">@</span>
          <span class="team-badge">${{esc(g.home)}}</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          ${{hasValue ? '<span class="game-value-tag">VALUE</span>' : ''}}
          <span class="game-time">${{time}}</span>
        </div>
      </div>
      <div class="prob-bar-wrap">
        <div class="prob-labels">
          <div><span class="team">${{esc(g.away)}}</span> <span class="pct">${{ap}}%</span></div>
          <div><span class="pct">${{hp}}%</span> <span class="team">${{esc(g.home)}}</span></div>
        </div>
        <div class="prob-bar"><div class="fill" style="width:${{hp}}%"></div></div>
      </div>
      ${{bestLine}}
    </div>`;
}}

/* ---- GAME DETAIL MODAL ---- */
function openGameModal(idx) {{
  const g = currentFilteredGames[idx];
  if (!g) return;
  const hp = (g.home_prob * 100).toFixed(1);
  const ap = (g.away_prob * 100).toFixed(1);
  const time = g.commence ? new Date(g.commence).toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit', timeZone:'America/New_York'}}) + ' ET' : '';
  const arbs = (currentData.arb_opportunities || []).filter(a => a.home_team === g.home && a.away_team === g.away);

  // ---- TOP 3 BETS (by EV) across all markets + books ----
  let allBets = [];
  if (g.books) {{
    g.books.forEach(b => {{
      // ML bets
      const hDec = parseFloat(dec(b.home_odds));
      const aDec = parseFloat(dec(b.away_odds));
      const hImp = b.home_implied || 0;
      const aImp = b.away_implied || 0;
      const hEv = g.home_prob * (hDec - 1) - (1 - g.home_prob);
      const aEv = g.away_prob * (aDec - 1) - (1 - g.away_prob);
      if (hEv > 0) allBets.push({{ side: g.home, market: 'ML', book: b.name, odds: hDec, ev: hEv, edge: b.home_edge || 0 }});
      if (aEv > 0) allBets.push({{ side: g.away, market: 'ML', book: b.name, odds: aDec, ev: aEv, edge: b.away_edge || 0 }});
      // Spread bets (informational — no model edge)
      if (b.home_spread_odds) {{
        const sDec = parseFloat(dec(b.home_spread_odds));
        allBets.push({{ side: g.home + ' ' + (b.home_spread || -1.5), market: 'Spread', book: b.name, odds: sDec, ev: 0, edge: 0 }});
      }}
      if (b.away_spread_odds) {{
        const sDec = parseFloat(dec(b.away_spread_odds));
        allBets.push({{ side: g.away + ' ' + (b.away_spread || 1.5), market: 'Spread', book: b.name, odds: sDec, ev: 0, edge: 0 }});
      }}
    }});
  }}
  allBets.sort((a, b) => b.ev - a.ev);
  const top3 = allBets.filter(b => b.ev > 0).slice(0, 3);

  let top3Html = '';
  if (top3.length) {{
    top3Html = `<div class="top-bets">
      ${{top3.map((b, i) => `<div class="top-bet-row">
        <span class="rank">${{i+1}}</span>
        <span class="bet-desc">${{esc(b.side)}} ${{esc(b.market)}} @ ${{esc(b.book)}}</span>
        <span class="bet-meta">${{n(b.odds)}} &middot; EV +${{n(b.ev, 3)}} &middot; Edge +${{n(b.edge)}}pp</span>
      </div>`).join('')}}
    </div>`;
  }} else {{
    top3Html = '<div style="color:var(--muted);font-size:13px;padding:8px 0">No positive EV bets found for this game</div>';
  }}

  // ---- MONEYLINE TABLE ----
  let mlHtml = '';
  if (g.books && g.books.length) {{
    const bestH = Math.max(...g.books.map(b => b.home_odds || -9999));
    const bestA = Math.max(...g.books.map(b => b.away_odds || -9999));
    mlHtml = `<table>
      <tr><th>Book</th><th>${{esc(g.home)}}</th><th>${{esc(g.away)}}</th><th>Edge</th></tr>
      ${{g.books.map(b => {{
        const hE = b.home_edge || 0, aE = b.away_edge || 0;
        const best = Math.max(hE, aE);
        return `<tr>
          <td style="font-weight:600;color:var(--text-2)">${{bookLink(b.name, b.url)}}</td>
          <td class="odds">${{b.home_odds === bestH ? '<span class="best-star">' : ''}}\
${{dec(b.home_odds)}}${{b.home_odds === bestH ? ' &#9733;</span>' : ''}}</td>
          <td class="odds">${{b.away_odds === bestA ? '<span class="best-star">' : ''}}\
${{dec(b.away_odds)}}${{b.away_odds === bestA ? ' &#9733;</span>' : ''}}</td>
          <td class="${{best > 0 ? 'edge-positive' : 'edge-negative'}}">
            ${{best > 0 ? '+' + n(best) + 'pp' : '-'}}
            ${{best >= 2 ? '<span class="value-badge">VALUE</span>' : ''}}
          </td>
        </tr>`;
      }}).join('')}}</table>`;
  }}

  // ---- SPREAD TABLE ----
  let spreadHtml = '';
  const sb = (g.books || []).filter(b => b.home_spread_odds);
  if (sb.length) {{
    const spread = sb[0].home_spread || -1.5;
    const bestHS = Math.max(...sb.map(b => b.home_spread_odds || -9999));
    const bestAS = Math.max(...sb.map(b => b.away_spread_odds || -9999));
    spreadHtml = `<table>
      <tr><th>Book</th><th>${{esc(g.home)}} ${{spread}}</th><th>${{esc(g.away)}} ${{-spread}}</th></tr>
      ${{sb.map(b => `<tr>
        <td style="font-weight:600;color:var(--text-2)">${{bookLink(b.name, b.url)}}</td>
        <td class="odds">${{b.home_spread_odds === bestHS ? '<span class="best-star">' : ''}}\
${{dec(b.home_spread_odds)}}${{b.home_spread_odds === bestHS ? ' &#9733;</span>' : ''}}</td>
        <td class="odds">${{b.away_spread_odds === bestAS ? '<span class="best-star">' : ''}}\
${{dec(b.away_spread_odds)}}${{b.away_spread_odds === bestAS ? ' &#9733;</span>' : ''}}</td>
      </tr>`).join('')}}</table>`;
  }}

  // ---- TOTALS TABLE ----
  let totalHtml = '';
  const tb = (g.books || []).filter(b => b.over_odds);
  if (tb.length) {{
    const line = tb[0].total_line || 5.5;
    const bestO = Math.max(...tb.map(b => b.over_odds || -9999));
    const bestU = Math.max(...tb.map(b => b.under_odds || -9999));
    totalHtml = `<table>
      <tr><th>Book</th><th>Over ${{line}}</th><th>Under ${{line}}</th></tr>
      ${{tb.map(b => `<tr>
        <td style="font-weight:600;color:var(--text-2)">${{bookLink(b.name, b.url)}}</td>
        <td class="odds">${{b.over_odds === bestO ? '<span class="best-star">' : ''}}\
${{dec(b.over_odds)}}${{b.over_odds === bestO ? ' &#9733;</span>' : ''}}</td>
        <td class="odds">${{b.under_odds === bestU ? '<span class="best-star">' : ''}}\
${{dec(b.under_odds)}}${{b.under_odds === bestU ? ' &#9733;</span>' : ''}}</td>
      </tr>`).join('')}}</table>`;
  }}

  // ---- ARB CHECK ----
  let arbHtml = '';
  if (arbs.length) {{
    arbHtml = arbs.map(a => `<div class="arb-badge">ARB: ${{esc(a.market)}} — ${{esc(a.side_a)}} @ ${{esc(a.side_a_book)}} (${{n(a.side_a_odds)}}) vs ${{esc(a.side_b)}} @ ${{esc(a.side_b_book)}} (${{n(a.side_b_odds)}}) — +${{n(a.profit_pct)}}%</div>`).join('');
  }} else {{
    // Compute closest margin
    let closest = 999;
    if (g.books && g.books.length > 1) {{
      const homeDecAll = g.books.map(b => parseFloat(dec(b.home_odds)));
      const awayDecAll = g.books.map(b => parseFloat(dec(b.away_odds)));
      const bestHD = Math.max(...homeDecAll);
      const bestAD = Math.max(...awayDecAll);
      closest = 1/bestHD + 1/bestAD;
    }}
    arbHtml = `<div class="no-arb">No arb on this game${{closest < 999 ? ' (margin: ' + n(closest, 3) + ')' : ''}}</div>`;
  }}

  // ---- POLYMARKET COMPARISON ----
  let polyHtml = '';
  if (g.poly_home_prob) {{
    const pHP = pct(g.poly_home_prob);
    const pAP = pct(g.poly_away_prob);
    const modelDiffH = ((g.home_prob - g.poly_home_prob) * 100).toFixed(1);
    const modelDiffA = ((g.away_prob - g.poly_away_prob) * 100).toFixed(1);
    const diffColor = v => parseFloat(v) > 0 ? 'var(--green)' : parseFloat(v) < 0 ? 'var(--red)' : 'var(--muted)';
    polyHtml = `<div class="modal-section">
      <h3>Polymarket vs Model</h3>
      <table>
        <tr><th></th><th>${{esc(g.home)}}</th><th>${{esc(g.away)}}</th></tr>
        <tr>
          <td style="font-weight:600;color:var(--text-2)">Our Model</td>
          <td style="font-weight:700">${{hp}}%</td>
          <td style="font-weight:700">${{ap}}%</td>
        </tr>
        <tr>
          <td style="font-weight:600;color:var(--amber)">Polymarket</td>
          <td>${{pHP}}</td>
          <td>${{pAP}}</td>
        </tr>
        <tr>
          <td style="font-weight:600;color:var(--muted)">Edge vs Poly</td>
          <td style="font-weight:700;color:${{diffColor(modelDiffH)}}">${{modelDiffH > 0 ? '+' : ''}}${{modelDiffH}}pp</td>
          <td style="font-weight:700;color:${{diffColor(modelDiffA)}}">${{modelDiffA > 0 ? '+' : ''}}${{modelDiffA}}pp</td>
        </tr>
      </table>
    </div>`;
  }}

  // ---- BUILD MODAL ----
  const modal = document.getElementById('game-modal');
  document.getElementById('modal-body').innerHTML = `
    <button class="modal-close" onclick="closeGameModal()">&times;</button>
    <div class="modal-header">
      <div class="modal-matchup">
        <span class="team-badge">${{esc(g.away)}}</span>
        <span class="vs">@</span>
        <span class="team-badge">${{esc(g.home)}}</span>
        <span style="margin-left:auto;color:var(--muted);font-size:13px">${{time}}</span>
      </div>
      <div class="prob-bar-wrap" style="padding:0;margin-top:8px">
        <div class="prob-labels">
          <div><span class="team">${{esc(g.away)}}</span> <span class="pct">${{ap}}%</span></div>
          <div><span class="pct">${{hp}}%</span> <span class="team">${{esc(g.home)}}</span></div>
        </div>
        <div class="prob-bar"><div class="fill" style="width:${{hp}}%"></div></div>
      </div>
    </div>
    ${{polyHtml}}
    <div class="modal-section">
      <h3>Top 3 Best Bets (by EV)</h3>
      ${{top3Html}}
    </div>
    <div class="modal-section">
      <h3>Moneyline</h3>
      ${{mlHtml || '<div class="no-arb">No odds available</div>'}}
    </div>
    ${{spreadHtml ? `<div class="modal-section"><h3>Puck Line</h3>${{spreadHtml}}</div>` : ''}}
    ${{totalHtml ? `<div class="modal-section"><h3>Over / Under</h3>${{totalHtml}}</div>` : ''}}
    <div class="modal-section">
      <h3>Arb Check</h3>
      ${{arbHtml}}
    </div>
  `;
  modal.classList.add('open');
  document.body.style.overflow = 'hidden';
  // Focus trap: focus the close button and trap Tab
  const closeBtn = document.querySelector('.modal-close');
  if (closeBtn) closeBtn.focus();
  modal._prevFocus = document.activeElement;
  modal._trapHandler = function(e) {{
    if (e.key !== 'Tab') return;
    const focusable = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (e.shiftKey) {{
      if (document.activeElement === first) {{ e.preventDefault(); last.focus(); }}
    }} else {{
      if (document.activeElement === last) {{ e.preventDefault(); first.focus(); }}
    }}
  }};
  modal.addEventListener('keydown', modal._trapHandler);
}}

function closeGameModal() {{
  const modal = document.getElementById('game-modal');
  modal.classList.remove('open');
  document.body.style.overflow = '';
  if (modal._trapHandler) {{ modal.removeEventListener('keydown', modal._trapHandler); modal._trapHandler = null; }}
  if (modal._prevFocus) {{ modal._prevFocus.focus(); modal._prevFocus = null; }}
}}

/* ---- VALUE BETS TABLE (decimal only) ---- */
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
    const game = esc(b.away_team) + ' @ ' + esc(b.home_team);
    const edgeW = Math.min(b.edge_probability_points * 4, 80);
    const conf = b.confidence || 0;
    const confClass = conf >= 0.7 ? 'conf-high' : conf >= 0.4 ? 'conf-med' : 'conf-low';
    const odds = b.decimal_odds || dec(b.american_odds);
    return `<tr>
      <td>${{i+1}}</td>
      <td>${{game}}</td>
      <td style="font-weight:700">${{esc(b.side)}} ${{esc(b.market || 'ML')}}</td>
      <td>${{bookLink(b.sportsbook, b.sportsbook_url)}}</td>
      <td class="odds-col">${{odds}}</td>
      <td>${{pct(b.implied_probability)}}</td>
      <td style="font-weight:600">${{pct(b.model_probability)}}</td>
      <td class="edge-col">+${{n(b.edge_probability_points)}}pp <span class="edge-bar" style="width:${{edgeW}}px"></span></td>
      <td class="ev-col">${{n(b.expected_value_per_dollar, 3)}}</td>
      <td><span class="conf-dot ${{confClass}}"></span> ${{pct(conf)}}</td>
      <td class="stake-col">$${{n(b.recommended_stake)}}</td>
    </tr>`;
  }}).join('');
}}

function sortBets(key) {{
  if (sortKey === key) sortDesc = !sortDesc;
  else {{ sortKey = key; sortDesc = true; }}
  // Update aria-sort on table headers
  document.querySelectorAll('.value-table th[data-sort-key]').forEach(th => {{
    if (th.dataset.sortKey === key) {{
      th.setAttribute('aria-sort', sortDesc ? 'descending' : 'ascending');
    }} else {{
      th.removeAttribute('aria-sort');
    }}
  }});
  render(currentData);
}}

async function refreshDashboard(demo) {{
  const btn = document.getElementById('btn-refresh');
  const overlay = document.getElementById('loading-overlay');
  btn.textContent = 'Loading...'; btn.disabled = true;
  overlay.classList.add('active');
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
    savePrefs();
  }} catch(e) {{
    alert('Network error: ' + e.message);
  }} finally {{
    btn.textContent = 'Refresh'; btn.disabled = false;
    overlay.classList.remove('active');
  }}
}}

init();
</script>
</body>
</html>"""
