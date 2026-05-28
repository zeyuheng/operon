from app.core.resolution_adapters import expected_contract_value
from app.core.rule_parser import ParsedRule, RuleType


def test_fallback_50_50_value_prices_invalid_path() -> None:
    value, fallback_probability, _formula = expected_contract_value(
        hit_probability=0.0,
        parsed_rule=ParsedRule(
            rule_type=RuleType.FALLBACK_50_50_BEFORE_EVENT,
            summary="test",
            has_fallback_50_50=True,
            has_before_event=True,
        ),
    )

    assert value == 0.5
    assert fallback_probability == 1.0


def test_simple_binary_value_equals_hit_probability() -> None:
    value, fallback_probability, _formula = expected_contract_value(
        hit_probability=0.25,
        parsed_rule=ParsedRule(
            rule_type=RuleType.SIMPLE_BINARY_BARRIER,
            summary="test",
            has_fallback_50_50=False,
            has_before_event=False,
        ),
    )

    assert value == 0.25
    assert fallback_probability == 0.0
