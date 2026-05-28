from app.core.specialized_models import (
    build_election_polling_model,
    build_general_event_model,
    build_macro_policy_model,
    build_product_release_model,
    build_sports_outright_model,
    macro_z_score,
    product_evidence_weight,
    simulate_outright_probability,
    weighted_polling_average,
)
from app.schemas.evidence import EvidenceDirection, EvidenceObservation, PollSample
from app.schemas.market import Market
from app.services.evidence_collector import is_blocked_search_text
from app.services.macro_data_service import MacroSnapshot
from app.services.research_planner_service import infer_entity


def assert_diagnostics_are_bounded(posterior: float, interval: list[float]) -> None:
    assert 0 <= posterior <= 1
    assert len(interval) == 2
    assert 0 <= interval[0] <= interval[1] <= 1


def test_product_release_model_outputs_diagnostics() -> None:
    diagnostics = build_product_release_model(
        Market(id="1", question="Will OpenAI release GPT-5 before July?", market_probability=0.4),
        [
            EvidenceObservation(
                claim="Official docs show release preparation.",
                source_type="official",
                direction=EvidenceDirection.POSITIVE,
                relevance=0.8,
                strength=0.4,
                novelty=0.7,
                ambiguity=0.2,
            )
        ],
    )

    assert diagnostics.model_name == "Product Release Model"
    assert "technical_readiness" in diagnostics.state_scores
    assert_diagnostics_are_bounded(
        diagnostics.posterior_probability,
        diagnostics.uncertainty_interval,
    )


def test_macro_policy_model_outputs_diagnostics() -> None:
    diagnostics = build_macro_policy_model(
        Market(id="1", question="Will Fed cut rates in June?", market_probability=0.3),
        MacroSnapshot(cpi_yoy=3.2, unemployment_rate=4.0, fed_funds_rate=5.0),
    )

    assert diagnostics.model_name == "Macro Policy Model"
    assert "policy_reaction_function" in diagnostics.state_scores


def test_election_model_outputs_diagnostics() -> None:
    diagnostics = build_election_polling_model(
        Market(id="1", question="Will candidate X win the election?", market_probability=0.6)
    )

    assert diagnostics.model_name == "Election / Polling Model"
    assert "market_consensus" in diagnostics.state_scores


def test_general_model_is_conservative() -> None:
    diagnostics = build_general_event_model(
        Market(id="1", question="Will a vague event happen?", market_probability=0.9)
    )

    assert diagnostics.posterior_probability < 0.9


def test_sports_outright_model_outputs_diagnostics() -> None:
    diagnostics = build_sports_outright_model(
        Market(id="1", question="Will the Knicks win the NBA Finals?", market_probability=0.2)
    )

    assert diagnostics.model_name == "Sports Outright Model"
    assert "team_strength_proxy" in diagnostics.state_scores


def test_weighted_polling_average_respects_recency_and_quality() -> None:
    average, weight = weighted_polling_average(
        [
            PollSample(candidate="A", support=0.40, pollster_quality=0.9, age_days=5),
            PollSample(candidate="A", support=0.20, pollster_quality=0.3, age_days=90),
        ]
    )

    assert average > 0.30
    assert weight > 0


def test_sports_monte_carlo_probability_is_bounded() -> None:
    probability = simulate_outright_probability(
        target_rating=0.55,
        field_ratings=[0.55, 0.45, 0.40, 0.35],
        path_clarity=0.6,
        simulations=200,
    )

    assert 0 <= probability <= 1


def test_product_evidence_weight_uses_reliability() -> None:
    weight = product_evidence_weight(
        [
            EvidenceObservation(
                claim="Official launch signal.",
                source_type="official",
                direction=EvidenceDirection.POSITIVE,
                relevance=1.0,
                strength=0.5,
                novelty=1.0,
                ambiguity=0.0,
            )
        ]
    )

    assert weight > 0


def test_macro_z_score_is_bounded() -> None:
    assert 0 <= macro_z_score(10, center=2, scale=1) <= 1


def test_search_challenge_text_is_not_treated_as_evidence() -> None:
    assert is_blocked_search_text(
        "DuckDuckGo Unfortunately, bots use DuckDuckGo too. "
        "Please complete the following challenge to confirm this search was made by a human."
    )


def test_election_entity_extraction_keeps_full_name() -> None:
    entity = infer_entity(
        "Will Gavin Newsom win the 2028 Democratic presidential nomination?",
        "election_polling",
    )

    assert entity == "Gavin Newsom"
