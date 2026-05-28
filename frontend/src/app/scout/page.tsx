"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { MarketCandidate, promoteToEvent, runMarketScout } from "@/lib/api";

function percent(value?: number | null) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function compactNumber(value?: number | null) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return new Intl.NumberFormat("en", { notation: "compact" }).format(value);
}

export default function ScoutPage() {
  const router = useRouter();
  const [limit, setLimit] = useState(100);
  const [topN, setTopN] = useState(20);
  const [candidates, setCandidates] = useState<MarketCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function scanMarkets() {
    setLoading(true);
    setError(null);
    try {
      setCandidates(await runMarketScout(limit, topN));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to scan markets.");
    } finally {
      setLoading(false);
    }
  }

  async function analyze(candidate: MarketCandidate) {
    setAnalyzingId(candidate.market.id);
    setError(null);
    try {
      const event = await promoteToEvent(candidate);
      router.push(`/events/${event.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to promote candidate.");
      setAnalyzingId(null);
    }
  }

  return (
    <>
      <section className="toolbar">
        <div>
          <h1 className="title">Market Scout</h1>
          <p className="subtitle">
            Scan active Polymarket markets and rank the best candidates for Operon event
            modeling.
          </p>
        </div>
        <div className="controls">
          <div className="field">
            <label htmlFor="limit">Scan</label>
            <input
              id="limit"
              min={1}
              max={500}
              type="number"
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
            />
          </div>
          <div className="field">
            <label htmlFor="topN">Return</label>
            <input
              id="topN"
              min={1}
              max={100}
              type="number"
              value={topN}
              onChange={(event) => setTopN(Number(event.target.value))}
            />
          </div>
          <button className="button" disabled={loading} onClick={scanMarkets}>
            {loading ? "Scanning..." : "Scan Markets"}
          </button>
        </div>
      </section>

      {error ? <div className="error">{error}</div> : null}

      <section className="grid">
        {candidates.length === 0 ? (
          <div className="empty">Run Market Scout to find the first Operon candidates.</div>
        ) : (
          candidates.map((candidate) => (
            <article className="candidate" key={candidate.market.id}>
              <div className="candidate-header">
                <div>
                  <h2 className="question">{candidate.market.question}</h2>
                  <div className="meta">
                    {candidate.category_guess} / {candidate.model_type}
                    {candidate.market.end_date ? ` / closes ${candidate.market.end_date}` : ""}
                  </div>
                  <p className="reason">{candidate.selected_reason}</p>
                  <div className="badge-row">
                    {candidate.risk_flags.length === 0 ? (
                      <span className="badge">no scout risk flags</span>
                    ) : (
                      candidate.risk_flags.map((flag) => (
                        <span className="badge warning" key={flag}>
                          {flag}
                        </span>
                      ))
                    )}
                  </div>
                </div>
                <button
                  className="button secondary"
                  disabled={analyzingId === candidate.market.id}
                  onClick={() => analyze(candidate)}
                >
                  {analyzingId === candidate.market.id ? "Analyzing..." : "Analyze"}
                </button>
              </div>

              <div className="metrics">
                <div className="metric">
                  <span className="metric-label">Operon Score</span>
                  <span className="metric-value">{percent(candidate.operon_score)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Market Price</span>
                  <span className="metric-value">{percent(candidate.market.market_probability)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Volume</span>
                  <span className="metric-value">{compactNumber(candidate.market.volume)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Liquidity</span>
                  <span className="metric-value">{compactNumber(candidate.market.liquidity)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Evidence</span>
                  <span className="metric-value">{percent(candidate.evidence_score)}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Resolution</span>
                  <span className="metric-value">{percent(candidate.resolution_score)}</span>
                </div>
              </div>
            </article>
          ))
        )}
      </section>
    </>
  );
}
