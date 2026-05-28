from app.core.rule_parser import ParsedRule, RuleType


def expected_contract_value(
    hit_probability: float,
    parsed_rule: ParsedRule,
) -> tuple[float, float, str]:
    if parsed_rule.rule_type == RuleType.FALLBACK_50_50_BEFORE_EVENT:
        fallback_probability = 1.0 - hit_probability
        value = hit_probability + 0.5 * fallback_probability
        formula = "P(hit first) * 1.0 + P(fallback) * 0.5"
        return value, fallback_probability, formula

    return hit_probability, 0.0, "P(hit by deadline) * 1.0 + P(no hit) * 0.0"
