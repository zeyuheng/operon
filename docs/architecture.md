# Operon Architecture

## v1 Flow

```text
Market Scout
  -> Event Normalizer
  -> Model Router
  -> Evidence Ledger
  -> Probability Engine
  -> Market Comparison Dashboard
```

## Event Model Priority

1. FinancialBarrierEventModel
2. ProductReleaseEventModel
3. MacroPolicyEventModel
4. GeneralEventModel

## Non-Goals for v1

- No automatic trading.
- No private-key handling.
- No claim that model divergence is guaranteed edge.
- No LLM-only forecasts.
