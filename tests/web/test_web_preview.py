from app.web.web_preview import _build_demo_dashboard


def test_demo_dashboard_shape():
    data = _build_demo_dashboard({"region": ["qc"]})
    assert data["games"]
    assert data["books"]
    assert data["value_bets"]
    assert data["mode"] == "demo"
    # Check game structure
    game = data["games"][0]
    assert "home" in game
    assert "away" in game
    assert "books" in game
    assert game["books"]  # should have Quebec book odds
    # Check value bet structure
    bet = data["value_bets"][0]
    assert bet["recommended_stake"] > 0
    assert bet["edge_probability_points"] > 0


def test_demo_dashboard_has_quebec_books():
    data = _build_demo_dashboard({"region": ["qc"]})
    book_names = data["books"]
    assert "Bet365" in book_names
    assert "Betway" in book_names
    assert "Bet99" in book_names
    assert "FanDuel" in book_names
    assert "Mise-o-jeu" in book_names
