from app.core.specialized_models import (
    build_election_polling_model,
    build_general_event_model,
    build_macro_policy_model,
    build_product_release_model,
)
from app.schemas.market import Market


def assert_diagnostics_are_bounded(posterior: float, interval: list[float]) -> None:
    assert 0 <= posterior <= 1
    assert len(interval) == 2
    assert 0 <= interval[0] <= interval[1] <= 1


def test_product_release_model_outputs_diagnostics() -> None:
    diagnostics = build_product_release_model(
        Market(id="1", question="Will OpenAI release GPT-5 before July?", market_probability=0.4)
    )

    assert diagnostics.model_name == "Product Release Model"
    assert "technical_readiness" in diagnostics.state_scores
    assert_diagnostics_are_bounded(
        diagnostics.posterior_probability,
        diagnostics.uncertainty_interval,
    )


def test_macro_policy_model_outputs_diagnostics() -> None:
    diagnostics = build_macro_policy_model(
        Market(id="1", question="Will Fed cut rates in June?", market_probability=0.3)
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
