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
    return (
      <div className="model-viz viz-financial">
        <div className="viz-header">
          <div>
            <span className="metric-label">Model Run</span>
            <h2>Barrier Simulation</h2>
          </div>
          <strong>{percent(barrier.expected_contract_value)} expected value</strong>
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
      </div>
    );
  }

  if (!diagnostics) {
    return null;
  }

  const configs: Record<string, { title: string; subtitle: string; stages: string[]; accent: string }> = {
    product_release: {
      title: "Latent Readiness Update",
      subtitle: "Evidence activates readiness, intent, timeline, and official-source states.",
      stages: ["Read market", "Plan sources", "Extract evidence", "Update latent state", "Posterior"],
      accent: "viz-product",
    },
    macro_policy: {
      title: "Macro Nowcast Factor Stack",
      subtitle: "Market prior is adjusted by inflation, labor, yield curve, and policy factors.",
      stages: ["Market prior", "FRED indicators", "Z-scores", "Policy reaction", "Posterior"],
      accent: "viz-macro",
    },
    election_polling: {
      title: "Polling Aggregation Pipeline",
      subtitle: "Poll-like samples are weighted by source quality, sample size, and recency decay.",
      stages: ["Market prior", "Poll samples", "Recency decay", "Field adjustment", "Posterior"],
      accent: "viz-election",
    },
    sports_outright: {
      title: "Outright Title Simulation",
      subtitle: "Market-implied team strength is tested against a noisy field of contenders.",
      stages: ["Team prior", "Field ratings", "Path clarity", "Monte Carlo", "Title odds"],
      accent: "viz-sports",
    },
    logic_consistency: {
      title: "Probability Constraint Graph",
      subtitle: "Related markets are checked for monotonicity, exclusivity, and bound breaks.",
      stages: ["Parse claims", "Link markets", "Check bounds", "Project graph", "Flag breaks"],
      accent: "viz-logic",
    },
    general_event: {
      title: "General Evidence Update",
      subtitle: "Weak evidence is source-weighted and conservatively shrunk toward uncertainty.",
      stages: ["Collect evidence", "Score sources", "Penalty", "Shrink prior", "Posterior"],
      accent: "viz-general",
    },
  };
  const config = configs[event.model_type] ?? configs.general_event;
  return <GenericModelViz diagnostics={diagnostics} {...config} />;
}

function GenericModelViz({
  title,
  subtitle,
  diagnostics,
  stages,
  accent,
}: {
  title: string;
  subtitle: string;
  diagnostics: ModelDiagnostics;
  stages: string[];
  accent: string;
}) {
  const states = topStates(diagnostics, 5);
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
      <div className="viz-flow">
        {stages.map((stage) => (
          <div key={stage}>{stage}</div>
        ))}
      </div>
      <div className="viz-state-map">
        {states.map(([name, value], index) => (
          <div className="viz-node" key={name} style={{ ["--node-index" as string]: index }}>
            <span>{name}</span>
            <strong>{percent(value)}</strong>
            <div className="node-ring" style={{ ["--node-value" as string]: value }} />
          </div>
        ))}
      </div>
      <div className="viz-columns">
        <VizGauge label="Confidence" value={diagnostics.confidence} />
        <VizGauge label="Lower bound" value={diagnostics.uncertainty_interval[0]} />
        <VizGauge label="Upper bound" value={diagnostics.uncertainty_interval[1]} />
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
