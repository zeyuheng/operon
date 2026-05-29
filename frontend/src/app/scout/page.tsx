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

function uniqueValues(candidates: MarketCandidate[], key: keyof MarketCandidate) {
  return Array.from(new Set(candidates.map((candidate) => String(candidate[key])))).sort();
}

export default function ScoutPage() {
  const router = useRouter();
  const [limit, setLimit] = useState(100);
  const [topN, setTopN] = useState(20);
  const [candidates, setCandidates] = useState<MarketCandidate[]>([]);
  const [query, setQuery] = useState("");
  const [modelFilter, setModelFilter] = useState("all");
  const [structureFilter, setStructureFilter] = useState("all");
  const [minLiquidity, setMinLiquidity] = useState(0);
  const [sortBy, setSortBy] = useState("operon_score");
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

  const modelOptions = uniqueValues(candidates, "model_type");
  const structureOptions = uniqueValues(candidates, "market_structure_type");
  const filteredCandidates = candidates
    .filter((candidate) => {
      const text = `${candidate.market.question} ${candidate.category_guess} ${candidate.model_type}`.toLowerCase();
      const matchesQuery = !query || text.includes(query.toLowerCase());
      const matchesModel = modelFilter === "all" || candidate.model_type === modelFilter;
      const matchesStructure =
        structureFilter === "all" || candidate.market_structure_type === structureFilter;
      const matchesLiquidity = candidate.liquidity_score >= minLiquidity / 100;
      return matchesQuery && matchesModel && matchesStructure && matchesLiquidity;
    })
    .sort((a, b) => {
      if (sortBy === "market_probability") {
        return (b.market.market_probability ?? 0) - (a.market.market_probability ?? 0);
      }
      if (sortBy === "liquidity_score") {
        return b.liquidity_score - a.liquidity_score;
      }
      if (sortBy === "resolution_score") {
        return b.resolution_score - a.resolution_score;
      }
      if (sortBy === "evidence_score") {
        return b.evidence_score - a.evidence_score;
      }
      return b.operon_score - a.operon_score;
    });

  const averageScore =
    candidates.length > 0
      ? candidates.reduce((total, candidate) => total + candidate.operon_score, 0) /
        candidates.length
      : null;
  const connectedReady = candidates.filter(
    (candidate) => candidate.market_structure_type === "forecasting_market",
  ).length;
  const fallbackDominated = candidates.filter((candidate) =>
    candidate.risk_flags.includes("fallback_dominated"),
  ).length;

  return (
    <>
      <section className="scout-hero">
        <div>
          <p className="eyebrow">Market Scout</p>
          <h1 className="title">Market Scout</h1>
          <p className="subtitle">
            Scan active Polymarket markets, remove noisy mechanics, and promote the best
            candidates into transparent Operon event dashboards.
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

      <section className="scout-summary">
        <div>
          <span>Markets returned</span>
          <strong>{candidates.length}</strong>
        </div>
        <div>
          <span>Average Operon score</span>
          <strong>{percent(averageScore)}</strong>
        </div>
        <div>
          <span>Forecasting markets</span>
          <strong>{connectedReady}</strong>
        </div>
        <div>
          <span>Resolution mechanics</span>
          <strong>{fallbackDominated}</strong>
        </div>
      </section>

      <section className="scout-workbench">
        <div className="search-field">
          <label htmlFor="query">Search markets</label>
          <input
            id="query"
            placeholder="bitcoin, Fed, NBA, nomination..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="modelFilter">Model</label>
          <select
            id="modelFilter"
            value={modelFilter}
            onChange={(event) => setModelFilter(event.target.value)}
          >
            <option value="all">All models</option>
            {modelOptions.map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="structureFilter">Structure</label>
          <select
            id="structureFilter"
            value={structureFilter}
            onChange={(event) => setStructureFilter(event.target.value)}
          >
            <option value="all">All structures</option>
            {structureOptions.map((structure) => (
              <option key={structure} value={structure}>
                {structure}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="sortBy">Sort</label>
          <select id="sortBy" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
            <option value="operon_score">Operon score</option>
            <option value="liquidity_score">Liquidity</option>
            <option value="evidence_score">Evidence</option>
            <option value="resolution_score">Resolution</option>
            <option value="market_probability">Market price</option>
          </select>
        </div>
        <div className="field range-field">
          <label htmlFor="minLiquidity">Min liquidity score: {minLiquidity}%</label>
          <input
            id="minLiquidity"
            max={100}
            min={0}
            type="range"
            value={minLiquidity}
            onChange={(event) => setMinLiquidity(Number(event.target.value))}
          />
        </div>
      </section>

      <section className="grid">
        {candidates.length === 0 ? (
          <div className="empty">Run Market Scout to find the first Operon candidates.</div>
        ) : filteredCandidates.length === 0 ? (
          <div className="empty">No markets match the current filters.</div>
        ) : (
          filteredCandidates.map((candidate) => (
            <article className="candidate" key={candidate.market.id}>
              <div className="candidate-header">
                <div>
                  <h2 className="question">{candidate.market.question}</h2>
                  <div className="meta">
                    {candidate.category_guess} / {candidate.model_type} /{" "}
                    {candidate.market_structure_type}
                    {candidate.market.end_date ? ` / closes ${candidate.market.end_date}` : ""}
                  </div>
                  <p className="reason">{candidate.selected_reason}</p>
                  <div className="score-strip">
                    <span style={{ width: `${Math.round(candidate.operon_score * 100)}%` }} />
                  </div>
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
                <div className="metric">
                  <span className="metric-label">Edge Source</span>
                  <span className="metric-value">{candidate.primary_edge_source}</span>
                </div>
                <div className="metric">
                  <span className="metric-label">Scout Penalty</span>
                  <span className="metric-value">{percent(candidate.scout_penalty)}</span>
                </div>
              </div>
              <div className="candidate-footer">
                <span>Why selected: {candidate.reason}</span>
                <span>Primary edge: {candidate.primary_edge_source}</span>
              </div>
            </article>
          ))
        )}
      </section>
    </>
  );
}
