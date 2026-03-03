from __future__ import annotations

import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .logging_config import get_logger, setup_logging
from .models import TrackerConfig, ValueCandidate
from .presentation import render_html_preview, to_serializable
from .service import run_tracker

log = get_logger("web_preview")

SUPPORTED_REGIONS = {"ca", "us"}


def _float_param(params: dict[str, list[str]], name: str, default: float) -> float:
    try:
        value = params.get(name, [str(default)])[0]
        result = float(value)
        if not math.isfinite(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _int_param(params: dict[str, list[str]], name: str, default: int) -> int:
    try:
        value = params.get(name, [str(default)])[0]
        return int(value)
    except (ValueError, TypeError):
        return default


def _build_config(params: dict[str, list[str]]) -> TrackerConfig:
    """Build a TrackerConfig from query parameters.

    API key is read ONLY from the environment variable for security.
    """
    api_key = os.getenv("ODDS_API_KEY", "")
    if not api_key:
        raise ValueError(
            "Missing Odds API key. Set the ODDS_API_KEY environment variable."
        )

    region = params.get("region", ["ca"])[0]
    if region not in SUPPORTED_REGIONS:
        raise ValueError(f"Unsupported region '{region}'. Must be one of: {sorted(SUPPORTED_REGIONS)}")

    bankroll = _float_param(params, "bankroll", 1000.0)
    if bankroll <= 0:
        raise ValueError("Bankroll must be positive")

    return TrackerConfig(
        odds_api_key=api_key,
        region=region,
        bookmakers=params.get("bookmakers", [""])[0],
        season=_int_param(params, "season", 2024),
        min_edge=max(0.0, _float_param(params, "min_edge", 2.0)),
        min_ev=max(0.0, _float_param(params, "min_ev", 0.02)),
        bankroll=bankroll,
        max_fraction_per_bet=min(1.0, max(0.0, _float_param(params, "max_fraction_per_bet", 0.03))),
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
        except ValueError as exc:
            log.warning("Bad request: %s", exc)
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            return
        except (OSError, TimeoutError) as exc:
            log.error("Network error during tracker run: %s", exc)
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Upstream data source unavailable"}).encode("utf-8"))
            return
        except Exception:
            log.exception("Unexpected error during tracker run")
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Internal server error"}).encode("utf-8"))
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

    def log_message(self, format: str, *args: object) -> None:
        """Route BaseHTTPRequestHandler logs through our logger."""
        log.info(format, *args)


def main() -> None:
    setup_logging()
    host = os.getenv("PREVIEW_HOST", "0.0.0.0")
    port = int(os.getenv("PREVIEW_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), PreviewHandler)
    log.info("Preview server starting on http://%s:%d", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()
