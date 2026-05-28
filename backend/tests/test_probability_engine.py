from app.core.probability_engine import update_log_odds


def test_positive_evidence_increases_probability() -> None:
    assert update_log_odds(0.5, 0.4) > 0.5


def test_negative_evidence_decreases_probability() -> None:
    assert update_log_odds(0.5, -0.4) < 0.5
