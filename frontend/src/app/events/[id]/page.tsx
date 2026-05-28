"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { EventDraft, getEvent } from "@/lib/api";

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

        <div className="panel">
          <h2>Evidence Ledger</h2>
          <div className="evidence-list">
            {event.evidence_items.map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
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
      </section>
    </>
  );
}
