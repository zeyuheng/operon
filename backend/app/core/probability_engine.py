import math


def logit(probability: float) -> float:
    clipped = min(max(probability, 1e-6), 1 - 1e-6)
    return math.log(clipped / (1 - clipped))


def sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-value))


def update_log_odds(prior_probability: float, evidence_weight: float) -> float:
    return sigmoid(logit(prior_probability) + evidence_weight)
