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
      - books: list of active book names
      - summary: dict with aggregate stats
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0a0e1a;
      --bg-2: #0f1525;
      --panel: rgba(17,24,39,0.8);
      --panel-solid: #111827;
      --panel-2: #1a2236;
      --panel-3: #1e293b;
      --text: #f1f5f9;
      --text-2: #94a3b8;
      --muted: #64748b;
      --accent: #06b6d4;
      --accent-2: #22d3ee;
      --accent-glow: rgba(6,182,212,0.15);
      --green: #10b981;
      --green-bg: rgba(16,185,129,0.08);
      --green-border: rgba(16,185,129,0.2);
      --green-glow: rgba(16,185,129,0.12);
      --red: #ef4444;
      --amber: #f59e0b;
      --amber-bg: rgba(245,158,11,0.08);
      --border: rgba(30,41,59,0.6);
      --border-2: rgba(51,65,85,0.5);
      --shadow: 0 4px 24px rgba(0,0,0,0.3);
      --shadow-lg: 0 12px 40px rgba(0,0,0,0.4);
      --radius: 12px;
      --radius-sm: 8px;
      --radius-lg: 16px;
    }}
    [data-theme="light"] {{
      --bg: #f8fafc;
      --bg-2: #ffffff;
      --panel: rgba(255,255,255,0.9);
      --panel-solid: #ffffff;
      --panel-2: #f1f5f9;
      --panel-3: #e2e8f0;
      --text: #0f172a;
      --text-2: #475569;
      --muted: #64748b;
      --accent: #0891b2;
      --accent-2: #06b6d4;
      --accent-glow: rgba(8,145,178,0.1);
      --green: #059669;
      --green-bg: rgba(5,150,105,0.06);
      --green-border: rgba(5,150,105,0.2);
      --green-glow: rgba(5,150,105,0.08);
      --red: #dc2626;
      --amber: #d97706;
      --amber-bg: rgba(217,119,6,0.06);
      --border: rgba(226,232,240,0.8);
      --border-2: rgba(203,213,225,0.6);
      --shadow: 0 4px 24px rgba(0,0,0,0.06);
      --shadow-lg: 0 12px 40px rgba(0,0,0,0.1);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      min-height: 100vh;
      -webkit-font-smoothing: antialiased;
    }}
    .app {{ max-width: 1400px; margin: 0 auto; padding: 0 24px 48px; }}

    /* ---- HEADER ---- */
    .header {{
      padding: 20px 0;
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .brand {{ display: flex; align-items: center; gap: 14px; }}
    .logo {{
      width: 40px; height: 40px;
      background: linear-gradient(135deg, var(--accent), #8b5cf6);
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 18px; font-weight: 900; color: #fff;
    }}
    .brand h1 {{ font-size: 20px; font-weight: 700; letter-spacing: -0.03em; }}
    .brand .sub {{ color: var(--muted); font-size: 12px; margin-top: 1px; }}
    .header-actions {{ display: flex; gap: 10px; align-items: center; }}
    .badge {{
      display: inline-flex; align-items: center; gap: 6px;
      background: var(--panel-solid); border: 1px solid var(--border-2);
      border-radius: 20px; padding: 5px 14px; font-size: 11px;
      font-weight: 600; color: var(--text-2); text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .badge.live {{ border-color: var(--green); box-shadow: 0 0 12px var(--green-glow); }}
    .badge.live::before {{
      content: ''; width: 7px; height: 7px;
      background: var(--green); border-radius: 50%;
      animation: pulse 2s infinite;
      box-shadow: 0 0 6px var(--green);
    }}
    .badge.demo {{ border-color: var(--amber); color: var(--amber); }}
    @keyframes pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:0.3; }} }}

    /* ---- CONTROLS ---- */
    .controls {{
      display: flex; gap: 8px; flex-wrap: wrap;
      margin-bottom: 16px; align-items: center;
    }}
    .control-group {{
      display: flex; align-items: center; gap: 6px;
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius-sm); padding: 5px 10px;
    }}
    .control-group label {{
      color: var(--muted); font-size: 11px;
      text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600;
      white-space: nowrap;
    }}
    .control-group input, .control-group select {{
      background: var(--panel-2); border: 1px solid var(--border-2);
      border-radius: 6px; padding: 4px 8px; color: var(--text);
      font-size: 13px; width: 72px; font-family: inherit;
    }}
    .control-group input:focus, .control-group select:focus {{
      outline: none; border-color: var(--accent);
    }}
    .control-group select {{ width: auto; cursor: pointer; }}
    .btn {{
      background: var(--accent); color: #0a1628; font-weight: 700;
      border: none; border-radius: var(--radius-sm); padding: 7px 16px;
      font-size: 12px; cursor: pointer; transition: all 0.2s;
      white-space: nowrap; font-family: inherit;
    }}
    .btn:hover {{ background: var(--accent-2); transform: translateY(-1px); box-shadow: 0 4px 12px var(--accent-glow); }}
    .btn-ghost {{
      background: transparent; border: 1px solid var(--border-2);
      color: var(--text-2);
    }}
    .btn-ghost:hover {{ border-color: var(--accent); color: var(--accent); background: transparent; }}

    /* ---- KPI STRIP ---- */
    .kpi-strip {{
      display: flex; align-items: stretch; gap: 1px;
      background: var(--border); border-radius: var(--radius);
      overflow: hidden; margin-bottom: 20px;
    }}
    .kpi {{
      flex: 1; background: var(--panel-solid); padding: 14px 16px;
      min-width: 0; text-align: center;
    }}
    .kpi:first-child {{ border-radius: var(--radius) 0 0 var(--radius); }}
    .kpi:last-child {{ border-radius: 0 var(--radius) var(--radius) 0; }}
    .kpi .kpi-label {{
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600;
    }}
    .kpi .kpi-value {{
      font-size: 24px; font-weight: 800; margin-top: 2px;
      font-variant-numeric: tabular-nums; letter-spacing: -0.02em;
    }}
    .kpi .kpi-sub {{ color: var(--muted); font-size: 10px; margin-top: 1px; }}
    .kpi.green .kpi-value {{ color: var(--green); }}
    .kpi.amber .kpi-value {{ color: var(--amber); }}

    /* ---- BOOKS BAR ---- */
    .books-bar {{
      display: flex; gap: 6px; flex-wrap: wrap;
      margin-bottom: 20px; align-items: center;
    }}
    .books-bar .label {{
      color: var(--muted); font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600; margin-right: 4px;
    }}
    .book-chip {{
      display: inline-flex; align-items: center;
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: 20px; padding: 4px 12px; font-size: 11px;
      font-weight: 600; cursor: pointer; transition: all 0.15s;
      user-select: none; color: var(--muted);
    }}
    .book-chip.active {{
      background: var(--accent-glow); border-color: var(--accent);
      color: var(--accent);
    }}
    .book-chip:hover {{ border-color: var(--accent); color: var(--text-2); }}

    /* ---- SECTION TITLES ---- */
    .section-title {{
      font-size: 12px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted);
      margin-bottom: 12px; display: flex; align-items: center; gap: 10px;
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
      display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
      gap: 12px; margin-bottom: 28px;
    }}
    .game-card {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: hidden;
      transition: all 0.2s; cursor: pointer;
    }}
    .game-card:hover {{
      border-color: rgba(6,182,212,0.3);
      box-shadow: 0 0 24px rgba(6,182,212,0.06);
      transform: translateY(-1px);
    }}
    .game-card.has-value {{ border-color: var(--green-border); box-shadow: 0 0 20px var(--green-glow); }}
    .game-header {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 12px 16px;
    }}
    .game-matchup {{
      display: flex; align-items: center; gap: 10px; font-weight: 700;
      font-size: 14px;
    }}
    .team-badge {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 34px; height: 34px; border-radius: 8px;
      background: var(--panel-3); font-size: 11px; font-weight: 800;
      color: var(--text); letter-spacing: 0.02em;
    }}
    .vs {{ color: var(--muted); font-size: 11px; font-weight: 400; }}
    .game-time {{ color: var(--muted); font-size: 11px; }}
    .game-value-tag {{
      background: var(--green-bg); color: var(--green);
      border: 1px solid var(--green-border); border-radius: 4px;
      padding: 1px 8px; font-size: 10px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.04em;
    }}
    /* Probability buttons (Polymarket-inspired) */
    .prob-buttons {{
      display: flex; gap: 8px; padding: 0 16px 12px;
    }}
    .prob-btn {{
      flex: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      padding: 10px 8px; border-radius: var(--radius-sm);
      background: var(--panel-2); border: 1px solid var(--border);
      transition: all 0.15s;
    }}
    .prob-btn:first-child {{ border-color: rgba(6,182,212,0.2); }}
    .prob-btn .prob-team {{ font-size: 11px; font-weight: 600; color: var(--text-2); }}
    .prob-btn .prob-pct {{ font-size: 22px; font-weight: 800; color: var(--text); letter-spacing: -0.02em; margin-top: 1px; }}
    .prob-btn.fav .prob-pct {{ color: var(--accent); }}
    /* Card footer info */
    .card-footer {{
      padding: 8px 16px 10px; font-size: 11px; color: var(--muted);
      border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 3px;
    }}
    .card-footer .best-line {{ display: flex; justify-content: space-between; }}
    .card-footer strong {{ color: var(--text-2); font-weight: 600; }}
    .card-footer .poly-strip {{
      display: flex; justify-content: space-between; align-items: center;
      color: var(--amber); font-weight: 500;
    }}
    .edge-badge {{
      display: inline-flex; padding: 1px 6px; border-radius: 4px;
      font-weight: 700; font-size: 10px; letter-spacing: 0.02em;
    }}
    .edge-badge.positive {{ background: var(--green-bg); color: var(--green); }}
    .edge-badge.negative {{ background: rgba(239,68,68,0.08); color: var(--red); }}
    .edge-badge.neutral {{ background: var(--amber-bg); color: var(--amber); }}

    /* ---- VALUE BETS TABLE ---- */
    .value-section {{ margin-bottom: 28px; }}
    .value-table-wrap {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: auto;
    }}
    .value-table {{ border-collapse: collapse; width: 100%; min-width: 900px; }}
    .value-table th {{
      padding: 10px 14px; text-align: left;
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600;
      background: var(--panel-2); border-bottom: 1px solid var(--border);
      position: sticky; top: 0; cursor: pointer;
    }}
    .value-table th:hover {{ color: var(--accent); }}
    .value-table td {{
      padding: 8px 14px; border-bottom: 1px solid var(--border);
      font-size: 13px; font-variant-numeric: tabular-nums;
    }}
    .value-table tr:nth-child(even) td {{ background: rgba(17,24,39,0.4); }}
    .value-table tr:hover td {{ background: var(--accent-glow); }}
    .value-table .edge-col {{ font-weight: 700; color: var(--green); }}
    .value-table .ev-col {{ font-weight: 600; color: var(--green); }}
    .value-table .odds-col {{ font-weight: 600; }}
    .value-table .stake-col {{ font-weight: 700; }}
    .value-table a {{ color: var(--accent); text-decoration: none; }}
    .value-table a:hover {{ text-decoration: underline; }}

    /* ---- BANKROLL METER ---- */
    .bankroll-bar {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 14px 18px;
      display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
      margin-bottom: 20px;
    }}
    .bankroll-bar .info {{ flex: 1; min-width: 180px; }}
    .bankroll-bar .info .label {{
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.08em; font-weight: 600;
    }}
    .bankroll-bar .info .amount {{ font-size: 18px; font-weight: 700; margin-top: 2px; }}
    .meter {{ flex: 2; min-width: 200px; }}
    .meter .meter-track {{
      height: 6px; background: var(--panel-3); border-radius: 3px;
      overflow: hidden; position: relative;
    }}
    .meter .meter-fill {{
      height: 100%; border-radius: 3px; transition: width 0.4s ease;
      background: linear-gradient(90deg, var(--green), var(--accent));
    }}
    .meter .meter-fill.warn {{ background: linear-gradient(90deg, var(--amber), var(--red)); }}
    .meter .meter-labels {{
      display: flex; justify-content: space-between; font-size: 10px;
      color: var(--muted); margin-top: 4px;
    }}

    /* ---- PLAYS CARDS ---- */
    .plays-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 10px; margin-bottom: 28px;
    }}
    .play-card {{
      background: var(--panel-solid); border: 1px solid var(--green-border);
      border-radius: var(--radius); padding: 16px; position: relative;
      transition: all 0.2s;
    }}
    .play-card:hover {{ box-shadow: 0 0 20px var(--green-glow); transform: translateY(-1px); }}
    .play-action {{
      display: inline-flex; padding: 4px 12px; border-radius: 6px;
      background: var(--green); color: #041109;
      font-size: 13px; font-weight: 800; margin-bottom: 8px;
      letter-spacing: 0.02em;
    }}
    .play-rank {{
      position: absolute; top: 14px; right: 14px;
      color: var(--muted); font-size: 11px; font-weight: 700;
    }}
    .play-game {{ color: var(--muted); font-size: 12px; margin-bottom: 10px; }}
    .play-details {{
      display: grid; grid-template-columns: 1fr 1fr 1fr;
      gap: 6px; font-size: 11px;
    }}
    .play-details .detail-label {{ color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; }}
    .play-details .detail-value {{ font-weight: 700; font-size: 14px; margin-top: 1px; }}
    .play-details .detail-value.green {{ color: var(--green); }}

    /* ---- ARB CARDS ---- */
    .arb-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 10px; margin-bottom: 28px;
    }}
    .arb-card {{
      background: var(--panel-solid); border: 1px solid rgba(245,158,11,0.2);
      border-radius: var(--radius); padding: 16px;
      transition: all 0.2s;
    }}
    .arb-card:hover {{ box-shadow: 0 0 20px rgba(245,158,11,0.08); }}
    .arb-card .arb-title {{
      font-size: 13px; font-weight: 800; color: var(--amber); margin-bottom: 3px;
    }}
    .arb-card .arb-game {{ color: var(--muted); font-size: 11px; margin-bottom: 10px; }}
    .arb-leg {{
      display: flex; align-items: center; gap: 10px; padding: 6px 10px;
      background: var(--panel-2); border-radius: 6px;
      margin-bottom: 4px; font-size: 12px;
    }}
    .arb-leg .leg-side {{ font-weight: 700; min-width: 70px; }}
    .arb-leg .leg-book {{ color: var(--text-2); min-width: 80px; }}
    .arb-leg .leg-book a {{ color: var(--accent); text-decoration: none; }}
    .arb-leg .leg-odds {{ font-weight: 700; color: var(--amber); min-width: 44px; }}
    .arb-leg .leg-stake {{ font-weight: 700; color: var(--green); margin-left: auto; }}
    .arb-profit {{
      display: flex; justify-content: space-between; align-items: center;
      margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(245,158,11,0.1);
      font-size: 12px;
    }}
    .arb-profit .profit-label {{ color: var(--muted); }}
    .arb-profit .profit-value {{ font-weight: 800; color: var(--green); font-size: 15px; }}

    /* ---- MODAL ---- */
    .modal-backdrop {{
      display: none; position: fixed; inset: 0; z-index: 1000;
      background: rgba(0,0,0,0.75); backdrop-filter: blur(8px);
      justify-content: center; align-items: flex-start;
      padding: 40px 20px; overflow-y: auto;
    }}
    .modal-backdrop.open {{ display: flex; }}
    .modal-content {{
      background: var(--bg-2); border: 1px solid var(--border-2);
      border-radius: var(--radius-lg); max-width: 700px; width: 100%;
      box-shadow: var(--shadow-lg); position: relative;
      animation: modalIn 0.2s ease-out;
    }}
    @keyframes modalIn {{ from {{ opacity:0; transform: translateY(12px); }} to {{ opacity:1; transform: translateY(0); }} }}
    .modal-close {{
      position: absolute; top: 12px; right: 14px; background: none;
      border: none; color: var(--muted); font-size: 20px; cursor: pointer;
      width: 30px; height: 30px; display: flex; align-items: center;
      justify-content: center; border-radius: 6px; transition: all 0.15s;
    }}
    .modal-close:hover {{ background: var(--panel-3); color: var(--text); }}
    .modal-header {{
      padding: 18px 22px; border-bottom: 1px solid var(--border);
    }}
    .modal-header .modal-matchup {{
      font-size: 18px; font-weight: 800; display: flex;
      align-items: center; gap: 10px; margin-bottom: 10px;
    }}
    .modal-section {{
      padding: 14px 22px; border-bottom: 1px solid var(--border);
    }}
    .modal-section:last-child {{ border-bottom: none; }}
    .modal-section h3 {{
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); margin-bottom: 10px;
    }}
    .modal-section table {{ width: 100%; border-collapse: collapse; }}
    .modal-section th {{
      color: var(--muted); font-size: 11px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600; padding: 5px 0;
      text-align: left; border-bottom: 1px solid var(--border);
    }}
    .modal-section td {{
      padding: 6px 0; font-size: 13px; font-variant-numeric: tabular-nums;
      border-bottom: 1px solid rgba(30,41,59,0.3);
    }}
    .modal-section td a {{ color: var(--accent); text-decoration: none; }}
    .modal-section tr:last-child td {{ border-bottom: none; }}
    .top-bets {{
      background: var(--green-bg); border: 1px solid var(--green-border);
      border-radius: var(--radius-sm); padding: 12px 14px;
    }}
    .top-bet-row {{
      display: flex; align-items: center; gap: 8px; padding: 5px 0;
      font-size: 12px;
    }}
    .top-bet-row .rank {{
      background: var(--green); color: #041109; width: 20px; height: 20px;
      border-radius: 50%; display: flex; align-items: center;
      justify-content: center; font-size: 11px; font-weight: 800; flex-shrink: 0;
    }}
    .top-bet-row .bet-desc {{ font-weight: 700; }}
    .top-bet-row .bet-meta {{ color: var(--muted); font-size: 11px; margin-left: auto; }}
    .muted {{ color: var(--muted); }}
    .best-star {{ color: var(--green); font-weight: 700; }}
    .arb-badge {{ color: var(--amber); font-weight: 700; font-size: 12px; }}
    .no-arb {{ color: var(--muted); font-size: 12px; padding: 6px 0; }}
    /* Poly comparison in modal */
    .poly-compare {{
      display: flex; gap: 16px; align-items: stretch;
    }}
    .poly-col {{
      flex: 1; text-align: center; padding: 12px;
      border-radius: var(--radius-sm); background: var(--panel-2);
    }}
    .poly-col .poly-label {{ font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); font-weight: 600; margin-bottom: 4px; }}
    .poly-col .poly-pct {{ font-size: 20px; font-weight: 800; }}
    .poly-col .poly-team {{ font-size: 11px; color: var(--text-2); margin-top: 2px; }}
    .poly-model {{ color: var(--text); }}
    .poly-poly {{ color: var(--amber); }}
    .poly-edge {{ }}

    /* ---- EMPTY STATE ---- */
    .empty {{
      text-align: center; padding: 48px 20px; color: var(--muted);
    }}
    .empty .icon {{ font-size: 36px; margin-bottom: 10px; opacity: 0.4; }}
    .empty h3 {{ color: var(--text-2); margin-bottom: 6px; font-size: 14px; }}
    .empty p {{ font-size: 12px; }}

    /* ---- LOADING OVERLAY ---- */
    .loading-overlay {{
      display: none; position: fixed; inset: 0; z-index: 900;
      background: rgba(10,14,26,0.8); backdrop-filter: blur(4px);
      justify-content: center; align-items: center; flex-direction: column;
    }}
    .loading-overlay.active {{ display: flex; }}
    .loading-spinner {{
      width: 36px; height: 36px; border: 3px solid var(--border-2);
      border-top-color: var(--accent); border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }}
    .loading-text {{
      color: var(--text-2); font-size: 13px; font-weight: 600; margin-top: 12px;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

    /* ---- FOOTER ---- */
    .footer {{
      text-align: center; padding: 20px; color: var(--muted);
      font-size: 11px; border-top: 1px solid var(--border); margin-top: 12px;
    }}
    .footer code {{
      background: var(--panel-2); padding: 2px 5px;
      border-radius: 4px; border: 1px solid var(--border); font-size: 11px;
    }}

    /* ---- THEME TOGGLE ---- */
    .theme-toggle {{
      background: var(--panel-solid); border: 1px solid var(--border-2);
      border-radius: 20px; padding: 5px 12px; font-size: 13px;
      cursor: pointer; transition: all 0.2s; color: var(--text-2);
      display: inline-flex; align-items: center; gap: 5px;
      font-family: inherit; font-weight: 600;
    }}
    .theme-toggle:hover {{ border-color: var(--accent); color: var(--accent); }}
    [data-theme="light"] .loading-overlay {{ background: rgba(248,250,252,0.85); }}
    [data-theme="light"] .modal-backdrop {{ background: rgba(0,0,0,0.3); }}
    [data-theme="light"] .logo {{ color: #fff; }}
    [data-theme="light"] .btn {{ color: #fff; }}
    [data-theme="light"] .play-action {{ color: #fff; }}
    [data-theme="light"] .top-bet-row .rank {{ color: #fff; }}
    [data-theme="light"] .value-table tr:nth-child(even) td {{ background: rgba(241,245,249,0.5); }}
    [data-theme="light"] .value-table tr:hover td {{ background: rgba(8,145,178,0.06); }}

    /* ---- RESPONSIVE ---- */
    @media (max-width: 768px) {{
      .app {{ padding: 0 12px 24px; }}
      .header {{ flex-direction: column; align-items: flex-start; }}
      .kpi-strip {{ flex-wrap: wrap; }}
      .kpi {{ min-width: 120px; }}
      .kpi .kpi-value {{ font-size: 20px; }}
      .games-grid {{ grid-template-columns: 1fr; }}
      .plays-grid {{ grid-template-columns: 1fr; }}
      .arb-grid {{ grid-template-columns: 1fr; }}
      .controls {{ flex-direction: column; }}
      .modal-backdrop {{ padding: 0; }}
      .modal-content {{ border-radius: 0; min-height: 100vh; }}
    }}
    @media (max-width: 480px) {{
      .kpi-strip {{ gap: 1px; border-radius: var(--radius-sm); }}
      .kpi {{ padding: 10px 8px; }}
      .kpi .kpi-value {{ font-size: 18px; }}
      .prob-btn .prob-pct {{ font-size: 18px; }}
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
        <div class="sub">Multi-book NHL betting edge detection</div>
      </div>
    </div>
    <div class="header-actions">
      <div class="badge" id="mode-badge">DEMO</div>
      <button class="theme-toggle" id="theme-toggle" onclick="toggleTheme()" title="Toggle light/dark mode">Light</button>
      <button class="btn btn-ghost" onclick="refreshDashboard(true)">Demo</button>
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
      <input id="ctl-season" type="number" value="">
    </div>
  </div>

  <!-- BOOK FILTER -->
  <div class="books-bar" id="books-bar">
    <span class="label">Books</span>
  </div>

  <!-- KPI STRIP -->
  <div class="kpi-strip">
    <div class="kpi"><div class="kpi-label">Books</div><div class="kpi-value" id="kpi-books">0</div></div>
    <div class="kpi"><div class="kpi-label">Games</div><div class="kpi-value" id="kpi-games">0</div></div>
    <div class="kpi green"><div class="kpi-label">Value Bets</div><div class="kpi-value" id="kpi-bets">0</div></div>
    <div class="kpi green"><div class="kpi-label">Avg Edge</div><div class="kpi-value" id="kpi-edge">0pp</div></div>
    <div class="kpi"><div class="kpi-label">Best Edge</div><div class="kpi-value" id="kpi-best">0pp</div></div>
    <div class="kpi"><div class="kpi-label">Total Stake</div><div class="kpi-value" id="kpi-stake">$0</div></div>
    <div class="kpi amber"><div class="kpi-label">Polymarket</div><div class="kpi-value" id="kpi-poly">&mdash;</div><div class="kpi-sub" id="kpi-poly-sub">games matched</div></div>
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

  <!-- TODAY'S PLAYS -->
  <div class="section-title" id="plays-title">Today's Plays <span class="count" id="plays-count">0</span></div>
  <div class="plays-grid" id="plays-grid"></div>

  <!-- ARB ALERTS -->
  <div class="section-title">Arb Alerts <span class="count" id="arb-count">0</span></div>
  <div class="arb-grid" id="arb-grid"></div>

  <!-- GAMES -->
  <div class="section-title">Tonight's Games <span class="count" id="games-count">0</span></div>
  <div class="games-grid" id="games-grid"></div>

  <!-- VALUE BETS TABLE -->
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
  <div class="loading-text">Loading live data...</div>
</div>

<!-- GAME DETAIL MODAL -->
<div class="modal-backdrop" id="game-modal" onclick="if(event.target===this)closeGameModal()" role="dialog" aria-modal="true" aria-label="Game detail">
  <div class="modal-content" id="modal-body"></div>
</div>

<script type="application/json" id="app-data">{data_json}</script>
<script>
const D = JSON.parse(document.getElementById('app-data').textContent);
function esc(s){{const d=document.createElement('div');d.textContent=String(s);return d.innerHTML;}}
function bookLink(name, url){{if(url)return '<a href="'+esc(url)+'" target="_blank" rel="noopener">'+esc(name)+'</a>';return esc(name);}}
function toggleTheme() {{
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  const btn = document.getElementById('theme-toggle');
  btn.textContent = next === 'dark' ? 'Light' : 'Dark';
  try {{ localStorage.setItem('mp_theme', next); }} catch(e) {{}}
}}
(function() {{
  try {{
    const saved = localStorage.getItem('mp_theme');
    if (saved === 'light') {{
      document.documentElement.setAttribute('data-theme', 'light');
    }}
  }} catch(e) {{}}
}})();
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

function currentNhlSeason() {{
  const now = new Date();
  return now.getMonth() >= 9 ? now.getFullYear() : now.getFullYear() - 1;
}}

function init() {{
  const seasonEl = document.getElementById('ctl-season');
  if (!seasonEl.value) seasonEl.value = currentNhlSeason();
  const theme = document.documentElement.getAttribute('data-theme') || 'dark';
  document.getElementById('theme-toggle').textContent = theme === 'dark' ? 'Light' : 'Dark';
  restorePrefs();
  renderBooks(D.books || []);
  render(D);
  document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closeGameModal(); }});
  ['ctl-region','ctl-bankroll','ctl-min-edge','ctl-min-ev'].forEach(id => {{
    document.getElementById(id).addEventListener('change', savePrefs);
  }});
  if (D.mode !== 'live') {{
    refreshDashboard(false);
  }}
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

  // Polymarket KPI
  const polyGames = games.filter(g => g.poly_home_prob);
  const polyCount = polyGames.length;
  document.getElementById('kpi-poly').textContent = polyCount > 0 ? polyCount + '/' + games.length : '\u2014';
  if (polyCount > 0) {{
    const avgPolyEdge = polyGames.reduce((a, g) => a + Math.abs(g.home_prob - g.poly_home_prob) * 100, 0) / polyCount;
    document.getElementById('kpi-poly-sub').textContent = 'avg ' + n(avgPolyEdge, 1) + 'pp diff';
  }} else {{
    document.getElementById('kpi-poly-sub').textContent = 'no data';
  }}

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

  document.getElementById('plays-count').textContent = bets.length;
  renderPlays(bets);
  document.getElementById('arb-count').textContent = arbs.length;
  renderArbs(arbs);
  document.getElementById('games-count').textContent = currentFilteredGames.length;
  const grid = document.getElementById('games-grid');
  if (!currentFilteredGames.length) {{
    grid.innerHTML = '<div class="empty" style="grid-column:1/-1"><div class="icon">&#127954;</div><h3>No games loaded</h3><p>Click Refresh to load live data</p></div>';
  }} else {{
    grid.innerHTML = currentFilteredGames.map((g, i) => renderGameCard(g, bets, i)).join('');
  }}
  document.getElementById('bets-count').textContent = bets.length;
  renderBets(bets);
}}

/* ---- TODAY'S PLAYS ---- */
function renderPlays(bets) {{
  const grid = document.getElementById('plays-grid');
  if (!bets.length) {{
    grid.innerHTML = '<div class="empty" style="grid-column:1/-1;padding:24px"><h3>No plays found</h3><p>Adjust thresholds or check back later</p></div>';
    return;
  }}
  grid.innerHTML = bets.slice(0, 8).map((b, i) => {{
    const game = esc(b.away_team) + ' @ ' + esc(b.home_team);
    const odds = b.decimal_odds || dec(b.american_odds);
    return `
      <div class="play-card">
        <div class="play-rank">#${{i+1}}</div>
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
    grid.innerHTML = '<div class="empty" style="grid-column:1/-1;padding:16px"><p>No arbitrage opportunities found</p></div>';
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

/* ---- GAME CARD (Polymarket-inspired) ---- */
function renderGameCard(g, bets, idx) {{
  const hasValue = bets.some(b => (b.home_team === g.home && b.away_team === g.away) || (b.home_team === g.away && b.away_team === g.home));
  const hp = (g.home_prob * 100).toFixed(1);
  const ap = (g.away_prob * 100).toFixed(1);
  const homeFav = g.home_prob >= g.away_prob;
  const time = g.commence ? new Date(g.commence).toLocaleTimeString('en-US', {{hour:'numeric', minute:'2-digit', timeZone:'America/New_York'}}) + ' ET' : '';

  // Best odds + Polymarket footer
  let footer = '';
  if (g.books && g.books.length) {{
    const bestH = Math.max(...g.books.map(b => b.home_odds || -9999));
    const bestA = Math.max(...g.books.map(b => b.away_odds || -9999));
    const bestHBook = g.books.find(b => b.home_odds === bestH);
    const bestABook = g.books.find(b => b.away_odds === bestA);
    let lines = `<div class="best-line">
      <span>Best: <strong>${{esc(g.home)}} ${{dec(bestH)}}</strong></span>
      <span><strong>${{esc(g.away)}} ${{dec(bestA)}}</strong> &middot; ${{g.books.length}} books</span>
    </div>`;
    let polyLine = '';
    if (g.poly_home_prob) {{
      const polyDiff = ((g.home_prob - g.poly_home_prob) * 100).toFixed(1);
      const absDiff = Math.abs(polyDiff);
      const edgeClass = polyDiff > 0 ? 'positive' : polyDiff < 0 ? 'negative' : 'neutral';
      const sign = polyDiff > 0 ? '+' : '';
      polyLine = `<div class="poly-strip">
        <span>Poly: ${{esc(g.home)}} ${{(g.poly_home_prob*100).toFixed(0)}}% / ${{esc(g.away)}} ${{(g.poly_away_prob*100).toFixed(0)}}%</span>
        <span class="edge-badge ${{edgeClass}}">${{sign}}${{polyDiff}}pp</span>
      </div>`;
    }}
    footer = `<div class="card-footer">${{lines}}${{polyLine}}</div>`;
  }}

  return `
    <div class="game-card ${{hasValue ? 'has-value' : ''}}" onclick="openGameModal(${{idx}})" tabindex="0" onkeydown="if(event.key==='Enter'||event.key===' '){{event.preventDefault();openGameModal(${{idx}})}}">
      <div class="game-header">
        <div class="game-matchup">
          <span class="team-badge">${{esc(g.away)}}</span>
          <span class="vs">@</span>
          <span class="team-badge">${{esc(g.home)}}</span>
        </div>
        <div style="display:flex;gap:6px;align-items:center;">
          ${{hasValue ? '<span class="game-value-tag">VALUE</span>' : ''}}
          <span class="game-time">${{time}}</span>
        </div>
      </div>
      <div class="prob-buttons">
        <div class="prob-btn ${{!homeFav ? 'fav' : ''}}">
          <span class="prob-team">${{esc(g.away)}}</span>
          <span class="prob-pct">${{ap}}%</span>
        </div>
        <div class="prob-btn ${{homeFav ? 'fav' : ''}}">
          <span class="prob-team">${{esc(g.home)}}</span>
          <span class="prob-pct">${{hp}}%</span>
        </div>
      </div>
      ${{footer}}
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

  // Top 3 bets
  let allBets = [];
  if (g.books) {{
    g.books.forEach(b => {{
      const hDec = parseFloat(dec(b.home_odds));
      const aDec = parseFloat(dec(b.away_odds));
      const hEv = g.home_prob * (hDec - 1) - (1 - g.home_prob);
      const aEv = g.away_prob * (aDec - 1) - (1 - g.away_prob);
      if (hEv > 0) allBets.push({{ side: g.home, market: 'ML', book: b.name, url: b.url, odds: hDec, ev: hEv, edge: b.home_edge || 0 }});
      if (aEv > 0) allBets.push({{ side: g.away, market: 'ML', book: b.name, url: b.url, odds: aDec, ev: aEv, edge: b.away_edge || 0 }});
      if (b.home_spread_odds) {{
        const sDec = parseFloat(dec(b.home_spread_odds));
        allBets.push({{ side: g.home + ' ' + (b.home_spread || -1.5), market: 'Spread', book: b.name, url: b.url, odds: sDec, ev: 0, edge: 0 }});
      }}
      if (b.away_spread_odds) {{
        const sDec = parseFloat(dec(b.away_spread_odds));
        allBets.push({{ side: g.away + ' ' + (b.away_spread || 1.5), market: 'Spread', book: b.name, url: b.url, odds: sDec, ev: 0, edge: 0 }});
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
        <span class="bet-desc">${{esc(b.side)}} ${{esc(b.market)}} @ ${{bookLink(b.book, b.url)}}</span>
        <span class="bet-meta">${{n(b.odds)}} &middot; EV +${{n(b.ev, 3)}} &middot; +${{n(b.edge)}}pp</span>
      </div>`).join('')}}
    </div>`;
  }} else {{
    top3Html = '<div class="no-arb">No positive EV bets found for this game</div>';
  }}

  // ML table
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
          <td>${{bookLink(b.name, b.url)}}</td>
          <td>${{b.home_odds === bestH ? '<strong class="best-star">' : ''}}${{dec(b.home_odds)}}${{b.home_odds === bestH ? '</strong>' : ''}}</td>
          <td>${{b.away_odds === bestA ? '<strong class="best-star">' : ''}}${{dec(b.away_odds)}}${{b.away_odds === bestA ? '</strong>' : ''}}</td>
          <td>
            ${{best > 0 ? '<span class="edge-badge positive">+' + n(best) + 'pp</span>' : '<span class="muted">&mdash;</span>'}}
          </td>
        </tr>`;
      }}).join('')}}</table>`;
  }}

  // Spread table
  let spreadHtml = '';
  const sb = (g.books || []).filter(b => b.home_spread_odds);
  if (sb.length) {{
    const spread = sb[0].home_spread || -1.5;
    const bestHS = Math.max(...sb.map(b => b.home_spread_odds || -9999));
    const bestAS = Math.max(...sb.map(b => b.away_spread_odds || -9999));
    spreadHtml = `<table>
      <tr><th>Book</th><th>${{esc(g.home)}} ${{spread}}</th><th>${{esc(g.away)}} ${{-spread}}</th></tr>
      ${{sb.map(b => `<tr>
        <td>${{bookLink(b.name, b.url)}}</td>
        <td>${{b.home_spread_odds === bestHS ? '<strong class="best-star">' : ''}}${{dec(b.home_spread_odds)}}${{b.home_spread_odds === bestHS ? '</strong>' : ''}}</td>
        <td>${{b.away_spread_odds === bestAS ? '<strong class="best-star">' : ''}}${{dec(b.away_spread_odds)}}${{b.away_spread_odds === bestAS ? '</strong>' : ''}}</td>
      </tr>`).join('')}}</table>`;
  }}

  // Totals table
  let totalHtml = '';
  const tb = (g.books || []).filter(b => b.over_odds);
  if (tb.length) {{
    const line = tb[0].total_line || 5.5;
    const bestO = Math.max(...tb.map(b => b.over_odds || -9999));
    const bestU = Math.max(...tb.map(b => b.under_odds || -9999));
    totalHtml = `<table>
      <tr><th>Book</th><th>Over ${{line}}</th><th>Under ${{line}}</th></tr>
      ${{tb.map(b => `<tr>
        <td>${{bookLink(b.name, b.url)}}</td>
        <td>${{b.over_odds === bestO ? '<strong class="best-star">' : ''}}${{dec(b.over_odds)}}${{b.over_odds === bestO ? '</strong>' : ''}}</td>
        <td>${{b.under_odds === bestU ? '<strong class="best-star">' : ''}}${{dec(b.under_odds)}}${{b.under_odds === bestU ? '</strong>' : ''}}</td>
      </tr>`).join('')}}</table>`;
  }}

  // Arb check
  let arbHtml = '';
  if (arbs.length) {{
    arbHtml = arbs.map(a => `<div class="arb-badge">ARB: ${{esc(a.market)}} &mdash; ${{esc(a.side_a)}} @ ${{esc(a.side_a_book)}} (${{n(a.side_a_odds)}}) vs ${{esc(a.side_b)}} @ ${{esc(a.side_b_book)}} (${{n(a.side_b_odds)}}) &mdash; +${{n(a.profit_pct)}}%</div>`).join('');
  }} else {{
    let closest = 999;
    if (g.books && g.books.length > 1) {{
      const homeDecAll = g.books.map(b => parseFloat(dec(b.home_odds)));
      const awayDecAll = g.books.map(b => parseFloat(dec(b.away_odds)));
      closest = 1/Math.max(...homeDecAll) + 1/Math.max(...awayDecAll);
    }}
    arbHtml = `<div class="no-arb">No arb on this game${{closest < 999 ? ' (margin: ' + n(closest, 3) + ')' : ''}}</div>`;
  }}

  // Polymarket comparison
  let polyHtml = '';
  if (g.poly_home_prob) {{
    const pHP = (g.poly_home_prob * 100).toFixed(1);
    const pAP = (g.poly_away_prob * 100).toFixed(1);
    const modelDiffH = ((g.home_prob - g.poly_home_prob) * 100).toFixed(1);
    const modelDiffA = ((g.away_prob - g.poly_away_prob) * 100).toFixed(1);
    const diffColor = v => parseFloat(v) > 0 ? 'var(--green)' : parseFloat(v) < 0 ? 'var(--red)' : 'var(--muted)';
    polyHtml = `<div class="modal-section">
      <h3>Polymarket vs Model</h3>
      <div class="poly-compare">
        <div class="poly-col">
          <div class="poly-label">Our Model</div>
          <div class="poly-pct poly-model">${{hp}}%</div>
          <div class="poly-team">${{esc(g.home)}}</div>
        </div>
        <div class="poly-col" style="background:var(--amber-bg)">
          <div class="poly-label" style="color:var(--amber)">Polymarket</div>
          <div class="poly-pct poly-poly">${{pHP}}%</div>
          <div class="poly-team">${{esc(g.home)}}</div>
        </div>
        <div class="poly-col">
          <div class="poly-label">Edge</div>
          <div class="poly-pct" style="color:${{diffColor(modelDiffH)}}">${{modelDiffH > 0 ? '+' : ''}}${{modelDiffH}}pp</div>
          <div class="poly-team">${{esc(g.home)}}</div>
        </div>
      </div>
    </div>`;
  }}

  // Build modal
  const modal = document.getElementById('game-modal');
  document.getElementById('modal-body').innerHTML = `
    <button class="modal-close" onclick="closeGameModal()">&times;</button>
    <div class="modal-header">
      <div class="modal-matchup">
        <span class="team-badge">${{esc(g.away)}}</span>
        <span class="vs">@</span>
        <span class="team-badge">${{esc(g.home)}}</span>
        <span style="margin-left:auto;color:var(--muted);font-size:12px">${{time}}</span>
      </div>
      <div class="prob-buttons" style="padding:0;margin-top:8px">
        <div class="prob-btn ${{g.away_prob >= g.home_prob ? 'fav' : ''}}">
          <span class="prob-team">${{esc(g.away)}}</span>
          <span class="prob-pct">${{ap}}%</span>
        </div>
        <div class="prob-btn ${{g.home_prob >= g.away_prob ? 'fav' : ''}}">
          <span class="prob-team">${{esc(g.home)}}</span>
          <span class="prob-pct">${{hp}}%</span>
        </div>
      </div>
    </div>
    ${{polyHtml}}
    <div class="modal-section">
      <h3>Best Bets</h3>
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

/* ---- VALUE BETS TABLE ---- */
function renderBets(bets) {{
  const body = document.getElementById('bets-body');
  const sorted = [...bets].sort((a,b) => {{
    let av = a[sortKey], bv = b[sortKey];
    if (sortKey === 'game') {{ av = a.away_team + a.home_team; bv = b.away_team + b.home_team; }}
    if (typeof av === 'string') return sortDesc ? bv.localeCompare(av) : av.localeCompare(bv);
    return sortDesc ? bv - av : av - bv;
  }});
  if (!sorted.length) {{
    body.innerHTML = '<tr><td colspan="11" style="text-align:center;padding:24px;color:var(--muted);">No value bets found at current thresholds</td></tr>';
    return;
  }}
  body.innerHTML = sorted.map((b, i) => {{
    const game = esc(b.away_team) + ' @ ' + esc(b.home_team);
    const conf = b.confidence || 0;
    const confPct = (conf * 100).toFixed(0);
    const confColor = conf >= 0.7 ? 'var(--green)' : conf >= 0.4 ? 'var(--amber)' : 'var(--red)';
    const odds = b.decimal_odds || dec(b.american_odds);
    return `<tr>
      <td>${{i+1}}</td>
      <td>${{game}}</td>
      <td style="font-weight:700">${{esc(b.side)}} ${{esc(b.market || 'ML')}}</td>
      <td>${{bookLink(b.sportsbook, b.sportsbook_url)}}</td>
      <td class="odds-col">${{odds}}</td>
      <td>${{pct(b.implied_probability)}}</td>
      <td style="font-weight:600">${{pct(b.model_probability)}}</td>
      <td class="edge-col"><span class="edge-badge positive">+${{n(b.edge_probability_points)}}pp</span></td>
      <td class="ev-col">${{n(b.expected_value_per_dollar, 3)}}</td>
      <td><span style="color:${{confColor}};font-weight:600">${{confPct}}%</span></td>
      <td class="stake-col">$${{n(b.recommended_stake)}}</td>
    </tr>`;
  }}).join('');
}}

function sortBets(key) {{
  if (sortKey === key) sortDesc = !sortDesc;
  else {{ sortKey = key; sortDesc = true; }}
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
