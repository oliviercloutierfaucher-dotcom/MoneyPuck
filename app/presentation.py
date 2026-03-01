from __future__ import annotations

import html
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
    if not rows:
        table_body = "<tr><td colspan='9'>No opportunities found with current thresholds.</td></tr>"
    else:
        parts: list[str] = []
        for row in rows:
            matchup = f"{row['away_team']} @ {row['home_team']}"
            parts.append(
                "<tr>"
                f"<td>{html.escape(row['commence_time_utc'])}</td>"
                f"<td>{html.escape(matchup)}</td>"
                f"<td>{html.escape(row['side'])}</td>"
                f"<td>{html.escape(row['sportsbook'])}</td>"
                f"<td>{row['american_odds']:+}</td>"
                f"<td>{row['edge_probability_points']:.2f}</td>"
                f"<td>{row['expected_value_per_dollar']:.3f}</td>"
                f"<td>{row['kelly_fraction']:.3f}</td>"
                f"<td>${row['recommended_stake']:.2f}</td>"
                "</tr>"
            )
        table_body = "".join(parts)

    return f"""<!doctype html>
<html>
<head>
  <meta charset='utf-8' />
  <meta name='viewport' content='width=device-width,initial-scale=1' />
  <title>MoneyPuck Edge Preview</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    .hint {{ color: #4b5563; margin-bottom: 16px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
    th {{ background: #f9fafb; }}
    code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>MoneyPuck Edge Preview</h1>
  <div class='hint'>Live preview from model + market odds. JSON endpoint: <code>/api/opportunities</code></div>
  <table>
    <thead>
      <tr>
        <th>Commence (UTC)</th>
        <th>Matchup</th>
        <th>Bet Side</th>
        <th>Sportsbook</th>
        <th>Odds</th>
        <th>Edge (pp)</th>
        <th>EV/$</th>
        <th>Kelly</th>
        <th>Stake</th>
      </tr>
    </thead>
    <tbody>{table_body}</tbody>
  </table>
</body>
</html>
"""
