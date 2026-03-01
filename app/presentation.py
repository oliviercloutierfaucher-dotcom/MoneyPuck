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
                "recommended_stake": item["recommended_stake"],
                "stake_fraction": item["stake_fraction"],
            }
        )
    return rows


def render_html_preview(recommendations: list[dict[str, Any]]) -> str:
    rows = to_serializable(recommendations)
    avg_edge = sum(row["edge_probability_points"] for row in rows) / len(rows) if rows else 0.0
    avg_ev = sum(row["expected_value_per_dollar"] for row in rows) / len(rows) if rows else 0.0
    initial_rows_json = json.dumps(rows)

    # Quiver Quant inspired: dense dashboard feel, dark cards, sortable/filterable table.
    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width,initial-scale=1' />
  <title>MoneyPuck Edge Intelligence</title>
  <style>
    :root {{
      --bg: #0b1220;
      --panel: #121b2d;
      --panel-2: #17223a;
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #22d3ee;
      --good: #34d399;
      --border: #22314e;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Inter, Segoe UI, Roboto, sans-serif; background: linear-gradient(180deg, #081022, var(--bg)); color: var(--text); }}
    .wrap {{ max-width: 1280px; margin: 0 auto; padding: 24px; }}
    .header {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-end; flex-wrap:wrap; margin-bottom:18px; }}
    h1 {{ margin:0; font-size: 28px; letter-spacing: 0.3px; }}
    .sub {{ color: var(--muted); margin-top: 6px; font-size: 14px; }}
    .grid {{ display:grid; grid-template-columns: repeat(4, minmax(180px,1fr)); gap:12px; margin-bottom:14px; }}
    .card {{ background: var(--panel); border:1px solid var(--border); border-radius: 12px; padding: 12px; }}
    .card .label {{ color: var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }}
    .card .value {{ margin-top: 4px; font-size:24px; font-weight:700; }}
    .controls {{ display:grid; grid-template-columns: repeat(6,minmax(120px,1fr)); gap:10px; margin-bottom:14px; }}
    .control {{ background: var(--panel); border:1px solid var(--border); border-radius: 10px; padding: 10px; }}
    .control label {{ color: var(--muted); font-size:12px; display:block; margin-bottom:6px; }}
    .control input, .control select {{ width:100%; background: var(--panel-2); border:1px solid var(--border); border-radius:8px; padding:8px; color: var(--text); }}
    .btns {{ display:flex; gap:8px; align-items:end; }}
    button {{ background: var(--accent); color:#041019; font-weight:700; border: none; border-radius: 10px; padding: 10px 14px; cursor: pointer; }}
    button.secondary {{ background: transparent; border:1px solid var(--border); color: var(--text); }}
    .table-wrap {{ background: var(--panel); border:1px solid var(--border); border-radius: 12px; overflow: auto; }}
    table {{ border-collapse: collapse; width:100%; min-width: 1060px; }}
    th, td {{ padding: 10px; border-bottom: 1px solid var(--border); font-size: 13px; text-align:left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; }}
    .good {{ color: var(--good); font-weight: 600; }}
    .muted {{ color: var(--muted); }}
    code {{ background:#0b152a; padding:2px 5px; border-radius:6px; border:1px solid var(--border); }}
    @media (max-width: 980px) {{ .grid {{ grid-template-columns: repeat(2,1fr); }} .controls {{ grid-template-columns: repeat(2,1fr); }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <div>
        <h1>MoneyPuck Edge Intelligence</h1>
        <div class="sub">Quiver-style signal dashboard for NHL opportunities • API endpoint <code>/api/opportunities</code></div>
      </div>
      <div class="muted">Tip: add <code>?demo=1</code> for instant sample data</div>
    </div>

    <div class="grid">
      <div class="card"><div class="label">Opportunities</div><div class="value" id="stat-count">{len(rows)}</div></div>
      <div class="card"><div class="label">Avg Edge (pp)</div><div class="value" id="stat-edge">{avg_edge:.2f}</div></div>
      <div class="card"><div class="label">Avg EV / $1</div><div class="value" id="stat-ev">{avg_ev:.3f}</div></div>
      <div class="card"><div class="label">Suggested Stake Total</div><div class="value" id="stat-stake">${sum(row['recommended_stake'] for row in rows):.2f}</div></div>
    </div>

    <div class="controls">
      <div class="control"><label>Region</label><select id="region"><option value="ca">CA</option><option value="us">US</option></select></div>
      <div class="control"><label>Min Edge (pp)</label><input id="min_edge" type="number" step="0.1" value="2.0"></div>
      <div class="control"><label>Min EV</label><input id="min_ev" type="number" step="0.01" value="0.02"></div>
      <div class="control"><label>Bankroll</label><input id="bankroll" type="number" step="100" value="1000"></div>
      <div class="control"><label>Season</label><input id="season" type="number" value="2024"></div>
      <div class="btns"><button id="refresh">Refresh</button><button class="secondary" id="demo">Demo Data</button></div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Commence (UTC)</th><th>Matchup</th><th>Side</th><th>Book</th><th>Odds</th>
            <th>Implied</th><th>Model</th><th>Edge (pp)</th><th>EV/$</th><th>Kelly</th><th>Stake</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </div>

  <script>
    const initialRows = {initial_rows_json};

    function pct(v) {{ return `${{(Number(v) * 100).toFixed(1)}}%`; }}
    function n(v, d=2) {{ return Number(v).toFixed(d); }}

    function renderRows(rows) {{
      const body = document.getElementById('rows');
      if (!rows.length) {{
        body.innerHTML = `<tr><td colspan="11" class="muted">No opportunities found for current filters.</td></tr>`;
      }} else {{
        body.innerHTML = rows.map((r) => `
          <tr>
            <td>${{r.commence_time_utc}}</td>
            <td>${{r.away_team}} @ ${{r.home_team}}</td>
            <td>${{r.side}}</td>
            <td>${{r.sportsbook}}</td>
            <td>${{r.american_odds > 0 ? '+' : ''}}${{r.american_odds}}</td>
            <td>${{pct(r.implied_probability)}}</td>
            <td>${{pct(r.model_probability)}}</td>
            <td class="good">${{n(r.edge_probability_points,2)}}</td>
            <td class="good">${{n(r.expected_value_per_dollar,3)}}</td>
            <td>${{n(r.kelly_fraction,3)}}</td>
            <td>${{n(r.recommended_stake,2)}}</td>
          </tr>
        `).join('');
      }}

      const avgEdge = rows.length ? rows.reduce((a, r) => a + Number(r.edge_probability_points), 0) / rows.length : 0;
      const avgEv = rows.length ? rows.reduce((a, r) => a + Number(r.expected_value_per_dollar), 0) / rows.length : 0;
      const totalStake = rows.reduce((a, r) => a + Number(r.recommended_stake), 0);
      document.getElementById('stat-count').innerText = rows.length;
      document.getElementById('stat-edge').innerText = n(avgEdge, 2);
      document.getElementById('stat-ev').innerText = n(avgEv, 3);
      document.getElementById('stat-stake').innerText = `$${{n(totalStake, 2)}}`;
    }}

    async function refresh(useDemo=false) {{
      const query = new URLSearchParams({{
        region: document.getElementById('region').value,
        min_edge: document.getElementById('min_edge').value,
        min_ev: document.getElementById('min_ev').value,
        bankroll: document.getElementById('bankroll').value,
        season: document.getElementById('season').value,
      }});
      if (useDemo) query.set('demo', '1');
      const res = await fetch(`/api/opportunities?${{query.toString()}}`);
      const payload = await res.json();
      if (!res.ok) {{
        alert(payload.error || 'Request failed');
        return;
      }}
      renderRows(payload);
    }}

    document.getElementById('refresh').addEventListener('click', () => refresh(false));
    document.getElementById('demo').addEventListener('click', () => refresh(true));
    renderRows(initialRows);
  </script>
</body>
</html>
"""
