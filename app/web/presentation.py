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
    /* Sparkline strip in card footer */
    .sparkline-strip {{
      display: flex; align-items: center; gap: 8px; padding-top: 4px;
    }}
    .sparkline-strip svg {{ flex-shrink: 0; }}
    .sparkline-label {{
      font-size: 10px; color: var(--muted); white-space: nowrap; flex-shrink: 0;
    }}
    .sparkline-label .spark-open {{ color: var(--text-2); }}
    .sparkline-label .spark-current {{ font-weight: 700; }}
    .sparkline-label .spark-up {{ color: var(--green); }}
    .sparkline-label .spark-down {{ color: var(--red); }}
    .sparkline-label .spark-flat {{ color: var(--muted); }}
    /* Larger sparkline chart in modal */
    .modal-sparkline {{
      width: 100%; overflow: hidden; background: var(--panel-2);
      border-radius: var(--radius-sm); padding: 12px 16px;
      margin-bottom: 12px;
    }}
    .modal-sparkline svg {{ width: 100%; height: 80px; display: block; }}
    .modal-sparkline-labels {{
      display: flex; justify-content: space-between;
      font-size: 10px; color: var(--muted); margin-top: 6px;
    }}
    .modal-sparkline-legend {{
      display: flex; gap: 12px; font-size: 10px; margin-top: 4px;
    }}
    .modal-sparkline-legend .leg-home {{
      display: flex; align-items: center; gap: 4px; color: var(--accent);
    }}
    .modal-sparkline-legend .leg-away {{
      display: flex; align-items: center; gap: 4px; color: var(--amber);
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

    /* ---- CLV TRACKER ---- */
    .clv-panel {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 14px 20px;
      margin-bottom: 20px; display: flex; align-items: center; gap: 0;
    }}
    .clv-panel.clv-positive {{ border-color: var(--green-border); box-shadow: 0 0 16px var(--green-glow); }}
    .clv-panel.clv-negative {{ border-color: rgba(239,68,68,0.2); }}
    .clv-header {{
      display: flex; align-items: center; gap: 10px;
      margin-right: 24px; min-width: 140px;
    }}
    .clv-icon {{
      width: 32px; height: 32px; border-radius: 8px;
      background: linear-gradient(135deg, var(--accent), #8b5cf6);
      display: flex; align-items: center; justify-content: center;
      font-size: 14px; font-weight: 900; color: #fff; flex-shrink: 0;
    }}
    .clv-title {{ font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
    .clv-subtitle {{ font-size: 11px; color: var(--muted); margin-top: 1px; }}
    .clv-kpis {{
      display: flex; gap: 0; flex: 1; align-items: stretch;
      border-left: 1px solid var(--border); padding-left: 20px;
    }}
    .clv-kpi {{
      flex: 1; padding: 4px 16px; border-right: 1px solid var(--border);
      text-align: center; min-width: 0;
    }}
    .clv-kpi:last-child {{ border-right: none; }}
    .clv-kpi .kpi-label {{ color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600; }}
    .clv-kpi .kpi-value {{ font-size: 22px; font-weight: 800; margin-top: 2px; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }}
    .clv-kpi .kpi-sub {{ color: var(--muted); font-size: 10px; margin-top: 1px; }}
    .clv-kpi.positive .kpi-value {{ color: var(--green); }}
    .clv-kpi.negative .kpi-value {{ color: var(--red); }}
    .clv-kpi.neutral .kpi-value {{ color: var(--text-2); }}
    .clv-empty {{ color: var(--muted); font-size: 12px; padding: 4px 16px; }}

    /* ---- PERFORMANCE TRACKER ---- */
    .perf-section {{ margin-bottom: 28px; }}
    .perf-empty {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 32px 20px; text-align: center;
      color: var(--muted); font-size: 13px;
    }}
    .perf-chart-wrap {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 18px 20px; margin-bottom: 12px;
      overflow-x: auto;
    }}
    .perf-chart-title {{
      font-size: 11px; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted); margin-bottom: 14px;
    }}
    .perf-bar-chart {{
      display: flex; align-items: flex-end; gap: 8px;
      height: 100px; position: relative;
    }}
    .perf-bar-col {{
      display: flex; flex-direction: column; align-items: center;
      flex: 1; min-width: 36px; max-width: 72px; gap: 4px;
    }}
    .perf-bar {{
      width: 100%; border-radius: 4px 4px 0 0;
      transition: opacity 0.15s;
      min-height: 3px;
    }}
    .perf-bar.positive {{ background: var(--green); }}
    .perf-bar.negative {{ background: var(--red); border-radius: 0 0 4px 4px; }}
    .perf-bar-label {{
      font-size: 9px; color: var(--muted); text-align: center;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;
    }}
    .perf-bar-value {{
      font-size: 9px; font-weight: 700; color: var(--text-2); text-align: center;
    }}
    .perf-two-col {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;
    }}
    @media (max-width: 600px) {{ .perf-two-col {{ grid-template-columns: 1fr; }} }}
    .perf-book-table-wrap {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: auto;
    }}
    .perf-book-table {{ border-collapse: collapse; width: 100%; }}
    .perf-book-table th {{
      padding: 9px 12px; text-align: left;
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600;
      background: var(--panel-2); border-bottom: 1px solid var(--border);
    }}
    .perf-book-table td {{
      padding: 7px 12px; border-bottom: 1px solid var(--border);
      font-size: 12px; font-variant-numeric: tabular-nums;
    }}
    .perf-book-table tr:last-child td {{ border-bottom: none; }}
    .perf-book-table tr:hover td {{ background: var(--accent-glow); }}
    .perf-recent-wrap {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); overflow: auto;
    }}
    .perf-recent-list {{ list-style: none; }}
    .perf-recent-item {{
      display: flex; align-items: center; gap: 10px;
      padding: 8px 14px; border-bottom: 1px solid var(--border);
      font-size: 12px; font-variant-numeric: tabular-nums;
    }}
    .perf-recent-item:last-child {{ border-bottom: none; }}
    .perf-result-badge {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 24px; height: 24px; border-radius: 6px;
      font-weight: 800; font-size: 11px; flex-shrink: 0;
    }}
    .perf-result-badge.win {{ background: var(--green-bg); color: var(--green); border: 1px solid var(--green-border); }}
    .perf-result-badge.loss {{ background: rgba(239,68,68,0.08); color: var(--red); border: 1px solid rgba(239,68,68,0.2); }}
    .perf-recent-meta {{ color: var(--muted); font-size: 11px; margin-left: auto; white-space: nowrap; }}
    .perf-profit.pos {{ color: var(--green); font-weight: 700; }}
    .perf-profit.neg {{ color: var(--red); font-weight: 700; }}

    /* ---- FOOTER ---- */
    .footer {{
      text-align: center; padding: 20px; color: var(--muted);
      font-size: 11px; border-top: 1px solid var(--border); margin-top: 12px;
    }}
    .footer code {{
      background: var(--panel-2); padding: 2px 5px;
      border-radius: 4px; border: 1px solid var(--border); font-size: 11px;
    }}

    /* ---- PROPS ---- */
    .props-chip {{
      display: inline-flex; align-items: center; gap: 4px;
      background: rgba(139,92,246,0.10); border: 1px solid rgba(139,92,246,0.25);
      border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 600;
      color: #a78bfa; letter-spacing: 0.02em; cursor: default;
    }}
    .props-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    .props-table th {{
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600; padding: 5px 6px;
      text-align: left; border-bottom: 1px solid var(--border);
    }}
    .props-table td {{
      padding: 5px 6px; border-bottom: 1px solid rgba(30,41,59,0.3);
      font-variant-numeric: tabular-nums;
    }}
    .props-table tr:last-child td {{ border-bottom: none; }}
    .props-table tr.wide-spread td {{ background: rgba(245,158,11,0.06); }}
    .props-table .spread-col {{ font-weight: 700; }}
    .props-table .spread-wide {{ color: var(--amber); }}
    .props-table .spread-tight {{ color: var(--green); }}
    .props-table td a {{ color: var(--accent); text-decoration: none; }}
    .props-table td a:hover {{ text-decoration: underline; }}
    .props-edge-note {{
      margin-top: 8px; padding: 6px 10px; border-radius: 6px;
      background: var(--amber-bg); border: 1px solid rgba(245,158,11,0.2);
      font-size: 11px; color: var(--amber);
    }}
    .props-edge-row {{ margin-bottom: 3px; }}
    .props-edge-row:last-child {{ margin-bottom: 0; }}

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

    /* ---- HEDGE CALCULATOR ---- */
    .hedge-panel {{
      background: var(--panel-solid); border: 1px solid var(--border);
      border-radius: var(--radius); margin-bottom: 16px; overflow: hidden;
    }}
    .hedge-toggle {{
      width: 100%; display: flex; align-items: center; justify-content: space-between;
      padding: 11px 16px; background: none; border: none; cursor: pointer;
      color: var(--text); font-family: inherit; font-size: 12px; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.07em;
    }}
    .hedge-toggle:hover {{ background: var(--panel-2); }}
    .hedge-toggle .hedge-toggle-label {{ display: flex; align-items: center; gap: 8px; color: var(--accent); }}
    .hedge-toggle .hedge-caret {{
      color: var(--muted); font-size: 10px; transition: transform 0.2s;
    }}
    .hedge-toggle.open .hedge-caret {{ transform: rotate(180deg); }}
    .hedge-body {{
      display: none; padding: 16px; border-top: 1px solid var(--border);
    }}
    .hedge-body.open {{ display: block; }}
    .hedge-inputs {{
      display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-end; margin-bottom: 14px;
    }}
    .hedge-field {{
      display: flex; flex-direction: column; gap: 4px;
    }}
    .hedge-field label {{
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600;
    }}
    .hedge-field input {{
      background: var(--panel-2); border: 1px solid var(--border-2);
      border-radius: 6px; padding: 6px 10px; color: var(--text);
      font-size: 13px; width: 110px; font-family: inherit;
    }}
    .hedge-field input:focus {{ outline: none; border-color: var(--accent); }}
    .hedge-mode-toggle {{
      display: flex; gap: 4px;
    }}
    .hedge-mode-btn {{
      padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 700;
      cursor: pointer; border: 1px solid var(--border-2);
      background: var(--panel-2); color: var(--text-2); font-family: inherit;
      transition: all 0.15s;
    }}
    .hedge-mode-btn.active {{
      background: var(--accent-glow); border-color: var(--accent); color: var(--accent);
    }}
    .hedge-results {{
      display: none; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border);
    }}
    .hedge-results.visible {{ display: block; }}
    .hedge-results-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 8px;
      margin-bottom: 12px;
    }}
    .hedge-stat {{
      background: var(--panel-2); border-radius: var(--radius-sm); padding: 10px 12px;
    }}
    .hedge-stat .hs-label {{
      color: var(--muted); font-size: 10px; text-transform: uppercase;
      letter-spacing: 0.06em; font-weight: 600;
    }}
    .hedge-stat .hs-value {{
      font-size: 18px; font-weight: 800; margin-top: 3px;
      font-variant-numeric: tabular-nums;
    }}
    .hedge-stat .hs-value.green {{ color: var(--green); }}
    .hedge-stat .hs-value.red {{ color: var(--red); }}
    .hedge-stat .hs-value.amber {{ color: var(--amber); }}
    .hedge-cashout {{
      background: var(--panel-2); border-radius: var(--radius-sm); padding: 10px 14px;
      display: flex; gap: 20px; flex-wrap: wrap; margin-top: 8px;
    }}
    .hedge-cashout .hc-item {{ display: flex; flex-direction: column; gap: 2px; }}
    .hedge-cashout .hc-label {{ color: var(--muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }}
    .hedge-cashout .hc-value {{ font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }}
    .hedge-error {{
      color: var(--red); font-size: 12px; margin-top: 8px; display: none;
    }}

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

  <!-- HEDGE CALCULATOR -->
  <div class="hedge-panel">
    <button class="hedge-toggle" id="hedge-toggle" onclick="toggleHedge()" aria-expanded="false" aria-controls="hedge-body">
      <span class="hedge-toggle-label">&#9881; Hedge Calculator</span>
      <span class="hedge-caret">&#9660;</span>
    </button>
    <div class="hedge-body" id="hedge-body" role="region" aria-label="Hedge Calculator">
      <div class="hedge-inputs">
        <div class="hedge-field">
          <label for="hc-orig-odds">Original Odds (decimal)</label>
          <input id="hc-orig-odds" type="number" step="0.01" min="1.01" placeholder="e.g. 2.50" oninput="calcHedge()">
        </div>
        <div class="hedge-field">
          <label for="hc-orig-stake">Original Stake ($)</label>
          <input id="hc-orig-stake" type="number" step="1" min="1" placeholder="e.g. 100" oninput="calcHedge()">
        </div>
        <div class="hedge-field">
          <label for="hc-hedge-odds">Hedge Odds (decimal)</label>
          <input id="hc-hedge-odds" type="number" step="0.01" min="1.01" placeholder="e.g. 2.10" oninput="calcHedge()">
        </div>
        <div class="hedge-field">
          <label>Mode</label>
          <div class="hedge-mode-toggle">
            <button class="hedge-mode-btn active" id="hm-lock" onclick="setHedgeMode('lock_profit')">Lock Profit</button>
            <button class="hedge-mode-btn" id="hm-min" onclick="setHedgeMode('minimize_loss')">Min Loss</button>
          </div>
        </div>
      </div>

      <div class="hedge-error" id="hedge-error"></div>

      <div class="hedge-results" id="hedge-results">
        <div class="hedge-results-grid">
          <div class="hedge-stat">
            <div class="hs-label">Hedge Stake</div>
            <div class="hs-value amber" id="hs-stake">$0</div>
          </div>
          <div class="hedge-stat">
            <div class="hs-label">If Original Wins</div>
            <div class="hs-value" id="hs-orig-win">$0</div>
          </div>
          <div class="hedge-stat">
            <div class="hs-label">If Hedge Wins</div>
            <div class="hs-value" id="hs-hedge-win">$0</div>
          </div>
          <div class="hedge-stat">
            <div class="hs-label">Guaranteed Profit</div>
            <div class="hs-value green" id="hs-guaranteed">$0</div>
          </div>
          <div class="hedge-stat">
            <div class="hs-label">ROI</div>
            <div class="hs-value" id="hs-roi">0%</div>
          </div>
        </div>
        <div class="hedge-cashout" id="hedge-cashout-row">
          <div class="hc-item"><div class="hc-label">Fair Cashout Value</div><div class="hc-value" id="hc-fair">$0</div></div>
          <div class="hc-item"><div class="hc-label">Cashout Profit</div><div class="hc-value" id="hc-profit">$0</div></div>
          <div class="hc-item"><div class="hc-label">EV if Hold</div><div class="hc-value" id="hc-ev">$0</div></div>
        </div>
      </div>
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

  <!-- CLV TRACKER -->
  <div class="clv-panel" id="clv-panel">
    <div class="clv-header">
      <div class="clv-icon">CLV</div>
      <div>
        <div class="clv-title">CLV Tracker</div>
        <div class="clv-subtitle">Closing Line Value</div>
      </div>
    </div>
    <div class="clv-kpis" id="clv-kpis">
      <div class="clv-empty">No CLV data yet &mdash; settle predictions to track closing line value</div>
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

  <!-- PERFORMANCE TRACKER (lazy-loaded) -->
  <div class="perf-section" id="perf-section">
    <div class="section-title">Performance Tracker</div>
    <div class="perf-empty" id="perf-placeholder">Loading performance data...</div>
    <div id="perf-content" style="display:none">
      <!-- KPI strip -->
      <div class="kpi-strip" style="margin-bottom:12px" id="perf-kpis"></div>
      <!-- Bar chart -->
      <div class="perf-chart-wrap" id="perf-chart-wrap">
        <div class="perf-chart-title">Monthly P&amp;L ($)</div>
        <div class="perf-bar-chart" id="perf-bar-chart"></div>
      </div>
      <!-- Two-column: book table + recent bets -->
      <div class="perf-two-col">
        <div>
          <div class="section-title" style="margin-bottom:8px">By Sportsbook</div>
          <div class="perf-book-table-wrap">
            <table class="perf-book-table">
              <thead><tr><th>Book</th><th>Bets</th><th>P&amp;L</th><th>ROI%</th></tr></thead>
              <tbody id="perf-book-body"></tbody>
            </table>
          </div>
        </div>
        <div>
          <div class="section-title" style="margin-bottom:8px">Recent Settled Bets</div>
          <div class="perf-recent-wrap">
            <ul class="perf-recent-list" id="perf-recent-list"></ul>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="footer">
    Model: 16-metric composite | Logistic win probability | Confidence-adj Kelly<br>
    API: <code>/api/dashboard</code> | <code>/api/opportunities</code> | <code>/api/performance</code>
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

/* ---- CLV TRACKER ---- */
function renderClv(clv) {{
  const panel = document.getElementById('clv-panel');
  const kpisEl = document.getElementById('clv-kpis');
  if (!clv || !clv.total_bets) {{
    kpisEl.innerHTML = '<div class="clv-empty">No CLV data yet &mdash; settle predictions to track closing line value</div>';
    panel.className = 'clv-panel';
    return;
  }}

  const avgClv = Number(clv.avg_clv_cents);
  const pctBeat = Number(clv.pct_beating_close);
  const total = clv.total_bets;

  const avgClass = avgClv > 0 ? 'positive' : avgClv < 0 ? 'negative' : 'neutral';
  const sign = avgClv > 0 ? '+' : '';
  const beatPct = (pctBeat * 100).toFixed(1);
  const beatClass = pctBeat >= 0.55 ? 'positive' : pctBeat >= 0.45 ? 'neutral' : 'negative';

  // Per-book breakdown (top 4 books by sample size)
  const byBook = clv.clv_by_book || {{}};
  const bookEntries = Object.entries(byBook)
    .sort((a, b) => b[1].total_bets - a[1].total_bets)
    .slice(0, 4);
  const bookHtml = bookEntries.map(([book, stats]) => {{
    const bc = Number(stats.avg_clv_cents);
    const bClass = bc > 0 ? 'positive' : bc < 0 ? 'negative' : 'neutral';
    const bSign = bc > 0 ? '+' : '';
    return `<div class="clv-kpi ${{bClass}}">
      <div class="kpi-label">${{esc(book)}}</div>
      <div class="kpi-value">${{bSign}}${{n(bc, 1)}}¢</div>
      <div class="kpi-sub">${{stats.total_bets}} bets</div>
    </div>`;
  }}).join('');

  panel.className = 'clv-panel' + (avgClv > 0 ? ' clv-positive' : avgClv < 0 ? ' clv-negative' : '');
  kpisEl.innerHTML = `
    <div class="clv-kpi ${{avgClass}}">
      <div class="kpi-label">Avg CLV</div>
      <div class="kpi-value">${{sign}}${{n(avgClv, 1)}}¢</div>
      <div class="kpi-sub">per bet</div>
    </div>
    <div class="clv-kpi ${{beatClass}}">
      <div class="kpi-label">Beat Close</div>
      <div class="kpi-value">${{beatPct}}%</div>
      <div class="kpi-sub">of bets</div>
    </div>
    <div class="clv-kpi neutral">
      <div class="kpi-label">Sample</div>
      <div class="kpi-value">${{total}}</div>
      <div class="kpi-sub">settled bets</div>
    </div>
    ${{bookHtml}}
  `;
}}

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

  renderClv(data.clv || null);

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

/* ---- SPARKLINE RENDERING (pure inline SVG) ---- */

/**
 * Build an SVG polyline sparkline from an array of y-values (0-1 probabilities).
 * @param {{number[]}} pts   - array of probability values in [0,1]
 * @param {{number}} w       - total width in px
 * @param {{number}} h       - total height in px
 * @param {{string}} color   - stroke color (CSS value)
 * @param {{boolean}} dashed - whether to use a dashed stroke
 * @returns {{string}} - SVG <polyline> element string
 */
function buildSparkPolyline(pts, w, h, color, dashed) {{
  if (!pts || pts.length < 2) return '';
  const pad = 3;
  const minV = Math.min(...pts);
  const maxV = Math.max(...pts);
  const range = maxV - minV || 0.01;
  const coords = pts.map((v, i) => {{
    const x = pad + (i / (pts.length - 1)) * (w - 2 * pad);
    const y = (h - pad) - ((v - minV) / range) * (h - 2 * pad);
    return x.toFixed(1) + ',' + y.toFixed(1);
  }}).join(' ');
  const dashAttr = dashed ? ' stroke-dasharray="4 3"' : '';
  return `<polyline points="${{coords}}" fill="none" stroke="${{color}}" stroke-width="1.5"${{dashAttr}} stroke-linecap="round" stroke-linejoin="round"/>`;
}}

/**
 * Render a mini sparkline strip for a game card.
 * Uses g.sparkline if present (demo mode pre-populated) or fetches lazily.
 * @param {{object}} g - game object
 * @returns {{string}} HTML string for the sparkline strip
 */
function renderCardSparkline(g) {{
  const data = g.sparkline || [];
  if (!data.length) return '';

  const pts = data.map(d => d.home_implied);
  const w = 120, h = 24;
  const first = pts[0], last = pts[pts.length - 1];
  const shift = last - first;
  const color = shift > 0.005 ? 'var(--green)' : shift < -0.005 ? 'var(--red)' : 'var(--muted)';
  const dirClass = shift > 0.005 ? 'spark-up' : shift < -0.005 ? 'spark-down' : 'spark-flat';
  const sign = shift > 0 ? '+' : '';
  const shiftPp = (shift * 100).toFixed(1);

  const polyline = buildSparkPolyline(pts, w, h, color, false);
  const openPct = (first * 100).toFixed(0);
  const nowPct = (last * 100).toFixed(0);

  return `<div class="sparkline-strip">
    <svg width="${{w}}" height="${{h}}" viewBox="0 0 ${{w}} ${{h}}" xmlns="http://www.w3.org/2000/svg">
      ${{polyline}}
    </svg>
    <span class="sparkline-label">
      <span class="spark-open">${{openPct}}%</span>
      <span class="spark-flat"> → </span>
      <span class="spark-current ${{dirClass}}">${{nowPct}}%</span>
      <span class="${{dirClass}}"> (${{sign}}${{shiftPp}}pp)</span>
    </span>
  </div>`;
}}

/**
 * Render a full-width dual-line sparkline for the game modal.
 * Shows home (solid accent) and away (dashed amber) implied probability over time.
 * @param {{object}} g - game object
 * @returns {{string}} HTML string for the modal sparkline section
 */
function renderModalSparkline(g) {{
  const data = g.sparkline || [];
  if (data.length < 2) return '';

  const homePts = data.map(d => d.home_implied);
  const awayPts = data.map(d => d.away_implied);
  const times = data.map(d => d.time);

  // Use a fixed viewBox width so SVG scales naturally with CSS width:100%
  const vw = 400, vh = 80;
  const homeLine = buildSparkPolyline(homePts, vw, vh, 'var(--accent)', false);
  const awayLine = buildSparkPolyline(awayPts, vw, vh, 'var(--amber)', true);

  const firstTime = times[0] || '';
  const lastTime = times[times.length - 1] || '';
  const homeOpen = (homePts[0] * 100).toFixed(1);
  const homeNow = (homePts[homePts.length - 1] * 100).toFixed(1);
  const awayOpen = (awayPts[0] * 100).toFixed(1);
  const awayNow = (awayPts[awayPts.length - 1] * 100).toFixed(1);

  return `<div class="modal-sparkline">
    <svg viewBox="0 0 ${{vw}} ${{vh}}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      ${{homeLine}}
      ${{awayLine}}
    </svg>
    <div class="modal-sparkline-labels">
      <span>${{firstTime}}</span>
      <span>${{lastTime}}</span>
    </div>
    <div class="modal-sparkline-legend">
      <span class="leg-home">&#9644; ${{esc(g.home)}} ${{homeOpen}}% → ${{homeNow}}%</span>
      <span class="leg-away">&#9148; ${{esc(g.away)}} ${{awayOpen}}% → ${{awayNow}}%</span>
    </div>
  </div>`;
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
    const sparklineHtml = renderCardSparkline(g);
    footer = `<div class="card-footer">${{lines}}${{polyLine}}${{sparklineHtml}}</div>`;
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
          ${{(g.props && g.props.length) ? '<span class="props-chip">' + g.props.length + ' props</span>' : ''}}
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

  // Line movement sparkline for modal
  const modalSparklineHtml = renderModalSparkline(g);
  const lineMovementSection = modalSparklineHtml
    ? `<div class="modal-section"><h3>Line Movement</h3>${{modalSparklineHtml}}</div>`
    : '';

  // Player Props section
  let propsHtml = '';
  const propsData = g.props || [];
  if (propsData.length) {{
    // Sort by book_spread ascending (tightest first), already pre-sorted
    const SPREAD_WIDE_THRESHOLD = 0.08; // 8pp combined vig = unusually wide
    const rows = propsData.map(p => {{
      const isWide = p.book_spread > SPREAD_WIDE_THRESHOLD;
      const spreadFmt = ((p.book_spread * 100).toFixed(1)) + '%';
      const spreadClass = isWide ? 'spread-wide' : 'spread-tight';
      const overLink = p.best_over_key
        ? bookLink(p.best_over_book, (D.books_urls || {{}})[p.best_over_key] || '')
        : esc(p.best_over_book);
      const underLink = p.best_under_key
        ? bookLink(p.best_under_book, (D.books_urls || {{}})[p.best_under_key] || '')
        : esc(p.best_under_book);
      return `<tr class="${{isWide ? 'wide-spread' : ''}}">
        <td style="font-weight:600">${{esc(p.player_name)}}</td>
        <td style="color:var(--text-2)">${{esc(p.market_label)}}</td>
        <td>${{p.line}}</td>
        <td>${{p.best_over_odds > 0 ? '+' : ''}}${{p.best_over_odds}} <span style="font-size:10px;color:var(--muted)">${{overLink}}</span></td>
        <td>${{p.best_under_odds > 0 ? '+' : ''}}${{p.best_under_odds}} <span style="font-size:10px;color:var(--muted)">${{underLink}}</span></td>
        <td class="spread-col ${{spreadClass}}">${{spreadFmt}}</td>
      </tr>`;
    }}).join('');

    // Prop edge notes
    const edgesData = g.prop_edges || [];
    let edgeNotes = '';
    if (edgesData.length) {{
      const edgeItems = edgesData.slice(0, 3).map(e => {{
        const dir = e.direction === 'over_value' ? 'Over value' : 'Under value';
        return `<div class="props-edge-row"><strong>${{esc(e.sportsbook)}}</strong> &mdash; ${{esc(e.player_name)}} ${{esc(e.market_label)}}: line ${{e.outlier_line}} vs consensus ${{e.consensus_line}} &mdash; ${{dir}}</div>`;
      }}).join('');
      edgeNotes = `<div class="props-edge-note">Line discrepancies: ${{edgeItems}}</div>`;
    }}

    propsHtml = `<div class="modal-section">
      <h3>Player Props <span style="font-weight:400;color:var(--muted);font-size:10px;text-transform:none;letter-spacing:0">(best odds across books &middot; sorted by spread)</span></h3>
      <div style="overflow-x:auto">
        <table class="props-table">
          <thead><tr>
            <th>Player</th><th>Market</th><th>Line</th>
            <th>Best Over</th><th>Best Under</th><th>Book Spread</th>
          </tr></thead>
          <tbody>${{rows}}</tbody>
        </table>
      </div>
      ${{edgeNotes}}
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
    ${{lineMovementSection}}
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
    ${{propsHtml}}
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

/* ---- HEDGE CALCULATOR ---- */
let hedgeMode = 'lock_profit';

function toggleHedge() {{
  const body = document.getElementById('hedge-body');
  const btn = document.getElementById('hedge-toggle');
  const open = body.classList.toggle('open');
  btn.classList.toggle('open', open);
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
}}

function setHedgeMode(mode) {{
  hedgeMode = mode;
  document.getElementById('hm-lock').classList.toggle('active', mode === 'lock_profit');
  document.getElementById('hm-min').classList.toggle('active', mode === 'minimize_loss');
  calcHedge();
}}

function calcHedge() {{
  const errEl = document.getElementById('hedge-error');
  const resEl = document.getElementById('hedge-results');

  const origOdds = parseFloat(document.getElementById('hc-orig-odds').value);
  const origStake = parseFloat(document.getElementById('hc-orig-stake').value);
  const hedgeOdds = parseFloat(document.getElementById('hc-hedge-odds').value);

  errEl.style.display = 'none';
  errEl.textContent = '';

  if (!origOdds || !origStake || !hedgeOdds) {{
    resEl.classList.remove('visible');
    return;
  }}

  if (origOdds <= 1.0 || hedgeOdds <= 1.0) {{
    errEl.textContent = 'Decimal odds must be greater than 1.00.';
    errEl.style.display = 'block';
    resEl.classList.remove('visible');
    return;
  }}
  if (origStake <= 0) {{
    errEl.textContent = 'Original stake must be positive.';
    errEl.style.display = 'block';
    resEl.classList.remove('visible');
    return;
  }}

  // --- Hedge calculation ---
  const origPayout = origOdds * origStake;
  // lock_profit and minimize_loss both use the same hedge sizing formula
  const hedgeStake = Math.round((origPayout / hedgeOdds) * 100) / 100;
  const totalOutlay = origStake + hedgeStake;
  const profitOrigWins = Math.round((origPayout - origStake - hedgeStake) * 100) / 100;
  const profitHedgeWins = Math.round((hedgeStake * hedgeOdds - totalOutlay) * 100) / 100;
  const guaranteed = Math.min(profitOrigWins, profitHedgeWins);
  const roi = totalOutlay > 0 ? Math.round((guaranteed / totalOutlay) * 10000) / 100 : 0;

  // --- Cashout calculation ---
  const currentImpliedProb = 1.0 / hedgeOdds;
  const fairValue = Math.round(currentImpliedProb * origPayout * 100) / 100;
  const cashoutProfit = Math.round((fairValue - origStake) * 100) / 100;
  const evIfHold = Math.round(
    (currentImpliedProb * (origPayout - origStake) - (1 - currentImpliedProb) * origStake) * 100
  ) / 100;

  // --- Render ---
  function fmtMoney(v) {{
    const s = Math.abs(v).toFixed(2);
    return (v < 0 ? '-$' : '$') + s;
  }}
  function colorClass(v) {{
    return v > 0 ? 'green' : v < 0 ? 'red' : '';
  }}

  document.getElementById('hs-stake').textContent = '$' + hedgeStake.toFixed(2);
  const owEl = document.getElementById('hs-orig-win');
  owEl.textContent = fmtMoney(profitOrigWins);
  owEl.className = 'hs-value ' + colorClass(profitOrigWins);
  const hwEl = document.getElementById('hs-hedge-win');
  hwEl.textContent = fmtMoney(profitHedgeWins);
  hwEl.className = 'hs-value ' + colorClass(profitHedgeWins);
  const gpEl = document.getElementById('hs-guaranteed');
  gpEl.textContent = fmtMoney(guaranteed);
  gpEl.className = 'hs-value ' + colorClass(guaranteed);
  const roiEl = document.getElementById('hs-roi');
  roiEl.textContent = (roi >= 0 ? '+' : '') + roi.toFixed(2) + '%';
  roiEl.className = 'hs-value ' + colorClass(roi);

  document.getElementById('hc-fair').textContent = '$' + fairValue.toFixed(2);
  const cpEl = document.getElementById('hc-profit');
  cpEl.textContent = fmtMoney(cashoutProfit);
  cpEl.style.color = cashoutProfit >= 0 ? 'var(--green)' : 'var(--red)';
  const evEl = document.getElementById('hc-ev');
  evEl.textContent = fmtMoney(evIfHold);
  evEl.style.color = evIfHold >= 0 ? 'var(--green)' : 'var(--red)';

  resEl.classList.add('visible');
}}

init();

/* ---- PERFORMANCE TRACKER ---- */
(function() {{
  function fmt$(v) {{ return (v >= 0 ? '+' : '') + '$' + Math.abs(v).toFixed(2); }}
  function roiColor(r) {{ return r >= 0 ? 'var(--green)' : 'var(--red)'; }}

  function renderPerf(d) {{
    // Show content, hide placeholder
    document.getElementById('perf-placeholder').style.display = 'none';
    document.getElementById('perf-content').style.display = '';

    // KPI strip
    const winRatePct = (d.win_rate * 100).toFixed(1);
    const roi = d.roi_pct;
    const netPl = d.net_profit;
    const plSign = netPl >= 0 ? '+' : '';
    document.getElementById('perf-kpis').innerHTML = `
      <div class="kpi ${{d.win_rate >= 0.5 ? 'green' : ''}}">
        <div class="kpi-label">Win Rate</div>
        <div class="kpi-value">${{winRatePct}}%</div>
        <div class="kpi-sub">${{d.wins}}W / ${{d.losses}}L</div>
      </div>
      <div class="kpi ${{roi >= 0 ? 'green' : ''}}">
        <div class="kpi-label">ROI</div>
        <div class="kpi-value" style="color:${{roiColor(roi)}}">${{roi >= 0 ? '+' : ''}}${{roi.toFixed(1)}}%</div>
        <div class="kpi-sub">on ${{d.settled_bets}} settled</div>
      </div>
      <div class="kpi ${{netPl >= 0 ? 'green' : ''}}">
        <div class="kpi-label">Net P&amp;L</div>
        <div class="kpi-value" style="color:${{roiColor(netPl)}}">${{plSign}}$${{Math.abs(netPl).toFixed(2)}}</div>
        <div class="kpi-sub">staked $${{d.total_staked.toFixed(2)}}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">Total Bets</div>
        <div class="kpi-value">${{d.total_bets}}</div>
        <div class="kpi-sub">${{d.pending_bets}} pending</div>
      </div>
    `;

    // Bar chart
    const months = d.by_month || [];
    if (months.length) {{
      const maxAbs = Math.max(1, ...months.map(m => Math.abs(m.profit)));
      const chartHeight = 80; // px available for bars
      const chart = document.getElementById('perf-bar-chart');
      chart.innerHTML = months.map(m => {{
        const h = Math.max(3, (Math.abs(m.profit) / maxAbs) * chartHeight);
        const pos = m.profit >= 0;
        return `<div class="perf-bar-col">
          <div class="perf-bar-value" style="color:${{roiColor(m.profit)}}">${{fmt$(m.profit)}}</div>
          <div class="perf-bar ${{pos ? 'positive' : 'negative'}}" style="height:${{h}}px" title="${{m.month}}: ${{fmt$(m.profit)}} (${{m.roi}}% ROI)"></div>
          <div class="perf-bar-label">${{m.month.slice(5)}}</div>
        </div>`;
      }}).join('');
    }} else {{
      document.getElementById('perf-chart-wrap').style.display = 'none';
    }}

    // By-book table
    const books = d.by_book || [];
    const bookBody = document.getElementById('perf-book-body');
    if (books.length) {{
      bookBody.innerHTML = books.map(b => {{
        const plCls = b.profit >= 0 ? 'pos' : 'neg';
        return `<tr>
          <td style="font-weight:600">${{esc(b.book)}}</td>
          <td>${{b.bets}}</td>
          <td class="perf-profit ${{plCls}}">${{fmt$(b.profit)}}</td>
          <td style="color:${{roiColor(b.roi)}};font-weight:700">${{b.roi >= 0 ? '+' : ''}}${{b.roi.toFixed(1)}}%</td>
        </tr>`;
      }}).join('');
    }} else {{
      bookBody.innerHTML = '<tr><td colspan="4" style="color:var(--muted);padding:12px">No data</td></tr>';
    }}

    // Recent bets
    const recent = d.recent_bets || [];
    const list = document.getElementById('perf-recent-list');
    if (recent.length) {{
      list.innerHTML = recent.map(b => {{
        const isWin = b.result === 'win';
        const resultLabel = isWin ? 'W' : 'L';
        const plCls = b.profit >= 0 ? 'pos' : 'neg';
        return `<li class="perf-recent-item">
          <span class="perf-result-badge ${{isWin ? 'win' : 'loss'}}">${{resultLabel}}</span>
          <span>
            <strong>${{esc(b.side)}}</strong>
            <span style="color:var(--muted);font-size:11px"> &mdash; ${{esc(b.game)}}</span>
          </span>
          <span class="perf-recent-meta">
            <span style="color:var(--text-2)">${{b.odds.toFixed(2)}}</span>
            &nbsp;&middot;&nbsp;$${{b.stake.toFixed(2)}}
            &nbsp;&middot;&nbsp;<span class="perf-profit ${{plCls}}">${{fmt$(b.profit)}}</span>
          </span>
        </li>`;
      }}).join('');
    }} else {{
      list.innerHTML = '<li class="perf-recent-item" style="color:var(--muted)">No settled bets yet</li>';
    }}
  }}

  function showPerfError(msg) {{
    const ph = document.getElementById('perf-placeholder');
    ph.style.display = '';
    ph.textContent = msg || 'No tracking data yet. Bets will appear here once recorded.';
    document.getElementById('perf-content').style.display = 'none';
  }}

  async function loadPerf() {{
    try {{
      const res = await fetch('/api/performance');
      if (!res.ok) {{ showPerfError('Performance data unavailable.'); return; }}
      const d = await res.json();
      if (d.settled_bets === 0 && !d._demo) {{
        showPerfError('No tracking data yet. Bets will appear here once recorded.');
        return;
      }}
      renderPerf(d);
    }} catch(e) {{
      showPerfError('No tracking data yet. Bets will appear here once recorded.');
    }}
  }}

  // Lazy-load after main render completes
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', loadPerf);
  }} else {{
    loadPerf();
  }}
}})();
</script>
</body>
</html>"""
