from app.web_preview import _demo_recommendations


def test_demo_recommendations_shape():
    rows = _demo_recommendations()
    assert rows
    assert rows[0]["recommended_stake"] > 0
    candidate = rows[0]["candidate"]
    assert candidate.home_team == "MTL"
