from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .models import TrackerConfig, ValueCandidate
from .presentation import render_html_preview, to_serializable
from .service import run_tracker


def _float_param(params: dict[str, list[str]], name: str, default: float) -> float:
    value = params.get(name, [str(default)])[0]
    return float(value)


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    value = params.get(name, [str(default)])[0]
    return int(value)


def _build_config(params: dict[str, list[str]]) -> TrackerConfig:
    api_key = params.get("odds_api_key", [os.getenv("ODDS_API_KEY", "")])[0]
    if not api_key:
        raise ValueError("Missing Odds API key. Set ODDS_API_KEY or pass odds_api_key query param.")

    return TrackerConfig(
        odds_api_key=api_key,
        region=params.get("region", ["ca"])[0],
        bookmakers=params.get("bookmakers", [""])[0],
        season=_int_param(params, "season", 2024),
        min_edge=_float_param(params, "min_edge", 2.0),
        min_ev=_float_param(params, "min_ev", 0.02),
        bankroll=_float_param(params, "bankroll", 1000.0),
        max_fraction_per_bet=_float_param(params, "max_fraction_per_bet", 0.03),
    )




def _demo_recommendations() -> list[dict[str, object]]:
    candidate = ValueCandidate(
        commence_time_utc="2026-01-01T00:00:00Z",
        home_team="MTL",
        away_team="TOR",
        side="MTL",
        sportsbook="DemoBook",
        american_odds=115,
        decimal_odds=2.15,
        implied_probability=0.4651,
        model_probability=0.54,
        edge_probability_points=7.49,
        expected_value_per_dollar=0.161,
        kelly_fraction=0.12,
        confidence=0.82,
    )
    return [{"candidate": candidate, "recommended_stake": 30.0, "stake_fraction": 0.03}]


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        use_demo = params.get("demo", ["0"])[0] in {"1", "true", "yes"}

        try:
            if use_demo:
                recommendations = _demo_recommendations()
            else:
                config = _build_config(params)
                recommendations = run_tracker(config)
        except Exception as exc:
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            return

        if parsed.path == "/api/opportunities":
            body = json.dumps(to_serializable(recommendations), indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path in {"/", "/index.html"}:
            body = render_html_preview(recommendations).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not found"}).encode("utf-8"))


def main() -> None:
    host = os.getenv("PREVIEW_HOST", "0.0.0.0")
    port = int(os.getenv("PREVIEW_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PreviewHandler)
    print(f"Preview running on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
