"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { EventDraft, ModelDiagnostics, getEvent } from "@/lib/api";

function percent(value?: number | null) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function currency(value?: number | null) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en", {
    currency: "USD",
    maximumFractionDigits: 0,
    style: "currency",
  }).format(value);
}

function number(value?: number | null) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(value);
}

function labelize(value: string) {
  return value.replace(/_/g, " ");
}

function signedPercent(value?: number | null) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${value >= 0 ? "+" : ""}${Math.round(value * 100)}%`;
}

function activeDiagnostics(event: EventDraft): ModelDiagnostics | null {
  return (
    event.product_release ??
    event.macro_policy ??
    event.election_polling ??
    event.sports_outright ??
    event.logic_consistency ??
    event.general_event ??
    null
  );
}

function topStates(diagnostics: ModelDiagnostics | null, limit = 5) {
  if (!diagnostics) {
    return [];
  }
  return Object.entries(diagnostics.state_scores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

function stateValue(diagnostics: ModelDiagnostics | null, key: string) {
  return diagnostics?.state_scores[key];
}

function timelineValue(event: EventDraft, label: string) {
  return event.probability_timeline.find((point) => point.label === label)?.probability;
}

function probabilityDelta(event: EventDraft, diagnostics: ModelDiagnostics | null) {
  const model = diagnostics?.posterior_probability ?? event.financial_barrier?.expected_contract_value;
  if (model === undefined || event.market_probability === null || event.market_probability === undefined) {
    return null;
  }
  return model - event.market_probability;
}

function ModelRunVisualization({
  event,
  diagnostics,
}: {
  event: EventDraft;
  diagnostics: ModelDiagnostics | null;
}) {
  if (event.financial_barrier) {
    const barrier = event.financial_barrier;
    const spotRatio = Math.min(100, (barrier.spot_price / barrier.barrier_price) * 100);
    const distance = Math.max(0, barrier.barrier_price / Math.max(barrier.spot_price, 1) - 1);
    return (
      <div className="model-viz viz-financial">
        <div className="viz-header">
          <div>
            <span className="metric-label">Model Run</span>
            <h2>Barrier Simulation Map</h2>
            <p>
              The model asks whether the asset path can touch the target before deadline, then
              applies the market rule payoff.
            </p>
          </div>
          <strong>{percent(barrier.expected_contract_value)} expected value</strong>
        </div>
        <div className="viz-brief">
          <div>
            <span>Input</span>
            <strong>{barrier.asset} spot {currency(barrier.spot_price)}</strong>
            <p>Target is {currency(barrier.barrier_price)}, about {number(distance * 100)}% above spot.</p>
          </div>
          <div>
            <span>Algorithm</span>
            <strong>GBM Monte Carlo</strong>
            <p>{barrier.simulations.toLocaleString()} simulated price paths over {barrier.steps} steps.</p>
          </div>
          <div>
            <span>Payoff adapter</span>
            <strong>{labelize(barrier.rule_type)}</strong>
            <p>{barrier.valuation_formula}</p>
          </div>
        </div>
        <div className="barrier-track">
          <span style={{ left: `${spotRatio}%` }}>spot</span>
          <span style={{ left: "100%" }}>barrier</span>
          <div className="barrier-fill" style={{ width: `${spotRatio}%` }} />
        </div>
        <div className="viz-flow">
          <div>Parse rule</div>
          <div>Fetch price</div>
          <div>Estimate vol</div>
          <div>Simulate paths</div>
          <div>Apply payoff</div>
        </div>
        <div className="viz-columns">
          <VizGauge label="Hit probability" value={barrier.hit_probability} />
          <VizGauge label="Fallback probability" value={barrier.fallback_probability} />
          <VizGauge label="Annual volatility" value={barrier.annualized_volatility} />
        </div>
        <div className="viz-explain">
          <strong>What changes the answer</strong>
          <p>{barrier.notes.join(" ")}</p>
        </div>
      </div>
    );
  }

  if (!diagnostics) {
    return null;
  }

  const configs: Record<
    string,
    {
      title: string;
      subtitle: string;
      stages: Array<{ label: string; detail: string; value?: number }>;
      accent: string;
      formula: string;
    }
  > = {
    product_release: {
      title: "Product Release Readiness",
      subtitle: "Official signals, readiness, intent, and deadline pressure update the market prior.",
      stages: [
        { label: "Market prior", detail: "Start from the traded probability.", value: event.market_probability ?? undefined },
        { label: "Evidence extraction", detail: "LLM or heuristic reads sources into structured claims.", value: stateValue(diagnostics, "structured_evidence_weight") },
        { label: "Latent states", detail: "Readiness, intent, official signal, and timeline confidence are scored.", value: stateValue(diagnostics, "technical_readiness") },
        { label: "Log-odds update", detail: "Weighted evidence moves the prior up or down.", value: diagnostics.posterior_probability },
      ],
      accent: "viz-product",
      formula: "logit(posterior) = logit(market prior) + weighted evidence + deadline pressure",
    },
    macro_policy: {
      title: "Macro Nowcast Stack",
      subtitle: "Inflation, labor, rates, yield curve, and policy guidance push against market consensus.",
      stages: [
        { label: "Market prior", detail: "Use market price as the consensus base.", value: event.market_probability ?? undefined },
        { label: "Macro feeds", detail: "Pull CPI, unemployment, Fed funds, 2Y and 10Y yields.", value: stateValue(diagnostics, "market_expectation") },
        { label: "Z-score factors", detail: "Normalize each macro indicator around an economic baseline.", value: stateValue(diagnostics, "inflation_trend") },
        { label: "Policy reaction", detail: "Map factors into a Fed/policy response probability.", value: diagnostics.posterior_probability },
      ],
      accent: "viz-macro",
      formula: "posterior = market prior + indicator z-scores + policy reaction function",
    },
    election_polling: {
      title: "Polling Aggregation Board",
      subtitle: "Poll-like signals are weighted by pollster quality, sample size, recency, and field risk.",
      stages: [
        { label: "Market prior", detail: "Treat market price as a low-weight consensus poll.", value: event.market_probability ?? undefined },
        { label: "Weighted average", detail: "Aggregate poll samples with quality and sample-size weights.", value: stateValue(diagnostics, "weighted_polling_average") },
        { label: "Recency decay", detail: "Older polls lose influence exponentially.", value: stateValue(diagnostics, "recency_weight") },
        { label: "Field adjustment", detail: "Nomination fields get entry/exit and consolidation uncertainty.", value: diagnostics.posterior_probability },
      ],
      accent: "viz-election",
      formula: "posterior = market prior x polling likelihood + field adjustment",
    },
    sports_outright: {
      title: "Championship Path Simulator",
      subtitle: "Team strength, field strength, path clarity, injury risk, and playoff variance drive the title odds.",
      stages: [
        { label: "Team strength", detail: "Infer the team rating from market consensus until Elo/odds feeds exist.", value: stateValue(diagnostics, "team_strength_proxy") },
        { label: "Field of contenders", detail: "Create a noisy distribution of rival team strengths.", value: stateValue(diagnostics, "playoff_variance") },
        { label: "Path clarity", detail: "Adjust confidence for bracket/schedule certainty.", value: stateValue(diagnostics, "schedule_path_clarity") },
        { label: "Monte Carlo title odds", detail: "Simulate winner draws across the field.", value: stateValue(diagnostics, "monte_carlo_title_probability") },
      ],
      accent: "viz-sports",
      formula: "posterior = 50% market consensus + 50% simulated title probability",
    },
    logic_consistency: {
      title: "Related Market Constraint Graph",
      subtitle: "The model checks whether nearby markets violate monotonicity, exclusivity, or probability bounds.",
      stages: [
        { label: "Parse claim", detail: "Extract threshold, deadline, entity, and relation.", value: stateValue(diagnostics, "related_market_coverage") },
        { label: "Link markets", detail: "Find comparable markets for the same underlying event.", value: stateValue(diagnostics, "monotonicity_check") },
        { label: "Check bounds", detail: "Apply monotonicity, mutual exclusivity, and Frechet bounds.", value: stateValue(diagnostics, "frechet_bound_check") },
        { label: "Flag breaks", detail: "Output inconsistencies rather than a standalone forecast.", value: diagnostics.posterior_probability },
      ],
      accent: "viz-logic",
      formula: "edge = market prices that break logical probability constraints",
    },
    general_event: {
      title: "Conservative Evidence Update",
      subtitle: "When no specialized model fits, the prior is shrunk toward uncertainty and evidence is discounted.",
      stages: [
        { label: "Market prior", detail: "Start from traded probability.", value: event.market_probability ?? undefined },
        { label: "Source quality", detail: "Score reliability and specificity of available evidence.", value: stateValue(diagnostics, "source_reliability") },
        { label: "Uncertainty penalty", detail: "Reduce confidence when evidence is generic or ambiguous.", value: stateValue(diagnostics, "uncertainty_penalty") },
        { label: "Posterior", detail: "Move cautiously, usually toward 50%.", value: diagnostics.posterior_probability },
      ],
      accent: "viz-general",
      formula: "posterior = market prior shrunk toward 50%, adjusted by reliable evidence",
    },
  };
  const config = configs[event.model_type] ?? configs.general_event;
  return <GenericModelViz event={event} diagnostics={diagnostics} {...config} />;
}

function GenericModelViz({
  event,
  title,
  subtitle,
  diagnostics,
  stages,
  accent,
  formula,
}: {
  event: EventDraft;
  title: string;
  subtitle: string;
  diagnostics: ModelDiagnostics;
  stages: Array<{ label: string; detail: string; value?: number }>;
  accent: string;
  formula: string;
}) {
  const states = topStates(diagnostics, 5);
  const delta = probabilityDelta(event, diagnostics);
  const scoutAdjusted = timelineValue(event, "scout_adjusted");
  const missing = event.research_plan?.missing_data ?? [];
  return (
    <div className={`model-viz ${accent}`}>
      <div className="viz-header">
        <div>
          <span className="metric-label">Model Run</span>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <strong>{percent(diagnostics.posterior_probability)} posterior</strong>
      </div>

      <div className="viz-brief">
        <div>
          <span>Market common sense</span>
          <strong>{percent(event.market_probability)}</strong>
          <p>Liquid market price is the anchor unless stronger model evidence appears.</p>
        </div>
        <div>
          <span>Model edge</span>
          <strong>{signedPercent(delta)}</strong>
          <p>Difference between the model run and the traded market probability.</p>
        </div>
        <div>
          <span>Confidence band</span>
          <strong>
            {percent(diagnostics.uncertainty_interval[0])} to{" "}
            {percent(diagnostics.uncertainty_interval[1])}
          </strong>
          <p>Wide bands mean missing data or high event variance.</p>
        </div>
      </div>

      <div className="viz-formula">{formula}</div>

      <div className="viz-flow explain-flow">
        {stages.map((stage) => (
          <div key={stage.label}>
            <strong>{stage.label}</strong>
            <p>{stage.detail}</p>
            {stage.value !== undefined ? <span>{percent(stage.value)}</span> : null}
          </div>
        ))}
      </div>

      <div className="viz-state-map">
        {states.map(([name, value], index) => (
          <div className="viz-node" key={name} style={{ ["--node-index" as string]: index }}>
            <span>{labelize(name)}</span>
            <strong>{percent(value)}</strong>
            <div className="node-ring" style={{ ["--node-value" as string]: value }} />
          </div>
        ))}
      </div>

      <div className="viz-bridge">
        <VizGauge label="Market prior" value={event.market_probability ?? 0.5} />
        <VizGauge label="Scout adjusted" value={scoutAdjusted ?? event.market_probability ?? 0.5} />
        <VizGauge label="Model posterior" value={diagnostics.posterior_probability} />
        <VizGauge label="Final Operon" value={event.operon_probability} />
      </div>

      <div className="viz-columns">
        <VizGauge label="Confidence" value={diagnostics.confidence} />
        <VizGauge label="Lower bound" value={diagnostics.uncertainty_interval[0]} />
        <VizGauge label="Upper bound" value={diagnostics.uncertainty_interval[1]} />
      </div>

      <div className="viz-explain">
        <strong>What the model still needs</strong>
        {missing.length ? (
          <p>{missing.join(", ")}</p>
        ) : (
          <p>{diagnostics.notes.join(" ")}</p>
        )}
      </div>
    </div>
  );
}

function VizGauge({ label, value }: { label: string; value: number }) {
  return (
    <div className="viz-gauge">
      <span>{label}</span>
      <div className="gauge-track">
        <div className="gauge-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </div>
      <strong>{percent(value)}</strong>
    </div>
  );
}

export default function EventPage() {
  const params = useParams<{ id: string }>();
  const [event, setEvent] = useState<EventDraft | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) {
      return;
    }

    getEvent(params.id)
      .then(setEvent)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load event."));
  }, [params.id]);

  if (error) {
    return (
      <section className="panel">
        <p className="error">{error}</p>
        <Link className="button secondary" href="/scout">
          Back to Scout
        </Link>
      </section>
    );
  }

  if (!event) {
    return <div className="empty">Loading event dashboard...</div>;
  }
  const diagnostics = activeDiagnostics(event);

  return (
    <>
      <section className="toolbar">
        <div>
          <h1 className="title">{event.market.question}</h1>
          <p className="subtitle">
            Event draft promoted from Market Scout. This is the first dashboard shell for
            evidence and probability updates.
          </p>
        </div>
        <Link className="button secondary" href="/scout">
          Back to Scout
        </Link>
      </section>

      <section className="dashboard">
        <div className="panel">
          <h2>Probability</h2>
          <div className="metrics">
            <div className="metric">
              <span className="metric-label">Market</span>
              <span className="metric-value">{percent(event.market_probability)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Operon</span>
              <span className="metric-value">{percent(event.operon_probability)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Model</span>
              <span className="metric-value">{event.model_type}</span>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Risk Flags</h2>
          <div className="badge-row">
            {event.risk_flags.length === 0 ? (
              <span className="badge">none</span>
            ) : (
              event.risk_flags.map((flag) => (
                <span className="badge warning" key={flag}>
                  {flag}
                </span>
              ))
            )}
          </div>
        </div>

        {event.consensus_guardrail ? (
          <div className="panel wide">
            <h2>Market Consensus Check</h2>
            <div className="metrics">
              <div className="metric">
                <span className="metric-label">Status</span>
                <span className="metric-value">{event.consensus_guardrail.status}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Gap</span>
                <span className="metric-value">
                  {event.consensus_guardrail.gap >= 0 ? "+" : ""}
                  {percent(event.consensus_guardrail.gap)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Abs Gap</span>
                <span className="metric-value">
                  {percent(event.consensus_guardrail.absolute_gap)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Divergence Risk</span>
                <span className="metric-value">
                  {percent(event.consensus_guardrail.divergence_risk)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Model Confidence</span>
                <span className="metric-value">
                  {percent(event.consensus_guardrail.confidence_used)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Liquidity Weight</span>
                <span className="metric-value">
                  {percent(event.consensus_guardrail.liquidity_weight)}
                </span>
              </div>
            </div>
            <div
              className={
                event.consensus_guardrail.model_review_required
                  ? "rule-box review"
                  : "rule-box"
              }
            >
              <strong>
                {event.consensus_guardrail.model_review_required
                  ? "Model review required"
                  : "Consensus guardrail"}
              </strong>
              <p>{event.consensus_guardrail.warning}</p>
            </div>
          </div>
        ) : null}

        {event.research_plan ? (
          <div className="panel wide">
            <h2>Research Plan</h2>
            <div className="metrics">
              <div className="metric">
                <span className="metric-label">Planner</span>
                <span className="metric-value">{event.research_plan.planner}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Event Type</span>
                <span className="metric-value">
                  {event.research_plan.understanding.event_type}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Entity</span>
                <span className="metric-value">
                  {event.research_plan.understanding.target_entity ?? "n/a"}
                </span>
              </div>
            </div>
            <div className="split-list">
              <div>
                <strong>Required Variables</strong>
                {event.research_plan.requirements.map((item) => (
                  <p key={item.name}>
                    {item.priority}: {item.name} - {item.reason}
                  </p>
                ))}
              </div>
              <div>
                <strong>Source Plan</strong>
                {event.research_plan.source_plan.map((item) => (
                  <p key={`${item.source_type}-${item.variable}-${item.query}`}>
                    {item.source_type}: {item.variable} - {item.query}
                  </p>
                ))}
              </div>
            </div>
            {event.research_plan.missing_data.length ? (
              <div className="rule-box">
                <strong>Still Missing</strong>
                {event.research_plan.missing_data.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="panel">
          <h2>Evidence Ledger</h2>
          <div className="evidence-list">
            {event.evidence_items.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        </div>

        <div className="panel wide">
          <ModelRunVisualization event={event} diagnostics={diagnostics} />
        </div>

        <div className="panel">
          <h2>Probability Timeline</h2>
          <div className="timeline">
            {event.probability_timeline.map((point) => (
              <div className="timeline-row" key={point.label}>
                <span>{point.label}</span>
                <div className="bar">
                  <div
                    className="bar-fill"
                    style={{ width: `${Math.round(point.probability * 100)}%` }}
                  />
                </div>
                <strong>{percent(point.probability)}</strong>
              </div>
            ))}
          </div>
        </div>

        {event.financial_barrier ? (
          <div className="panel wide">
            <h2>Financial Barrier Model</h2>
            <div className="metrics">
              <div className="metric">
                <span className="metric-label">Asset</span>
                <span className="metric-value">{event.financial_barrier.asset}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Spot Price</span>
                <span className="metric-value">{currency(event.financial_barrier.spot_price)}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Barrier</span>
                <span className="metric-value">
                  {currency(event.financial_barrier.barrier_price)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Days Left</span>
                <span className="metric-value">
                  {number(event.financial_barrier.days_remaining)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Annual Vol</span>
                <span className="metric-value">
                  {percent(event.financial_barrier.annualized_volatility)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Hit Probability</span>
                <span className="metric-value">
                  {percent(event.financial_barrier.hit_probability)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Expected Value</span>
                <span className="metric-value">
                  {percent(event.financial_barrier.expected_contract_value)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Fallback</span>
                <span className="metric-value">
                  {percent(event.financial_barrier.fallback_probability)}
                </span>
              </div>
            </div>
            <div className="rule-box">
              <strong>Rule Adapter: {event.financial_barrier.rule_type}</strong>
              <p>{event.financial_barrier.rule_summary}</p>
              <p>Valuation: {event.financial_barrier.valuation_formula}</p>
            </div>
            <p className="reason">
              {event.financial_barrier.simulations.toLocaleString()} simulations over{" "}
              {event.financial_barrier.steps} time steps. Data source:{" "}
              {event.financial_barrier.data_source}.
            </p>
            <div className="evidence-list">
              {event.financial_barrier.notes.map((note) => (
                <p key={note}>{note}</p>
              ))}
            </div>
          </div>
        ) : null}

        {diagnostics ? (
          <div className="panel wide">
            <h2>{diagnostics.model_name}</h2>
            <div className="metrics">
              <div className="metric">
                <span className="metric-label">Posterior</span>
                <span className="metric-value">
                  {percent(diagnostics.posterior_probability)}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Confidence</span>
                <span className="metric-value">{percent(diagnostics.confidence)}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Lower</span>
                <span className="metric-value">
                  {percent(diagnostics.uncertainty_interval[0])}
                </span>
              </div>
              <div className="metric">
                <span className="metric-label">Upper</span>
                <span className="metric-value">
                  {percent(diagnostics.uncertainty_interval[1])}
                </span>
              </div>
            </div>

            <div className="state-grid">
              {Object.entries(diagnostics.state_scores).map(([name, value]) => (
                <div className="state-row" key={name}>
                  <span>{name}</span>
                  <div className="bar">
                    <div className="bar-fill" style={{ width: `${Math.round(value * 100)}%` }} />
                  </div>
                  <strong>{percent(value)}</strong>
                </div>
              ))}
            </div>

            <div className="split-list">
              <div>
                <strong>Key Drivers</strong>
                {diagnostics.key_drivers.map((driver) => (
                  <p key={driver}>{driver}</p>
                ))}
              </div>
              <div>
                <strong>Notes</strong>
                {diagnostics.notes.map((note) => (
                  <p key={note}>{note}</p>
                ))}
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </>
  );
}
