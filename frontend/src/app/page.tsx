import Link from "next/link";

const modelCards = [
  ["Financial Barrier", "Price paths, volatility, payoff adapters"],
  ["Product Release", "Official signals, launch readiness, deadline pressure"],
  ["Macro Policy", "FRED indicators, yield curve, policy reaction"],
  ["Election Polling", "Poll aggregation, recency decay, candidate field risk"],
  ["Sports Outright", "Team strength, standings, path simulation roadmap"],
];

export default function HomePage() {
  return (
    <>
      <section className="public-hero">
        <div className="hero-visual" aria-hidden="true">
          <div className="radar-grid">
            <span />
            <span />
            <span />
            <span />
          </div>
          <div className="market-orbit orbit-a" />
          <div className="market-orbit orbit-b" />
          <div className="market-orbit orbit-c" />
          <div className="terminal-strip strip-a">market prior 57% / model posterior 51%</div>
          <div className="terminal-strip strip-b">source: FRED connected / odds key required</div>
          <div className="terminal-strip strip-c">resolution risk: low / evidence gap: visible</div>
        </div>
        <div className="hero-copy">
          <p className="eyebrow">Prediction-market intelligence</p>
          <h1>Operon turns market prices into explainable event models.</h1>
          <p>
            Scan live Polymarket markets, identify which ones are worth modeling, promote them
            into events, and inspect every probability through sources, inputs, uncertainty, and
            model logic.
          </p>
          <div className="hero-actions">
            <Link className="button" href="/scout">
              Launch Scout
            </Link>
            <a className="button secondary" href="http://127.0.0.1:8000/docs">
              API Docs
            </a>
          </div>
        </div>
      </section>

      <section className="public-section">
        <div>
          <p className="eyebrow">What it does</p>
          <h2>Not just a score. A probability audit trail.</h2>
        </div>
        <div className="feature-grid">
          <div>
            <strong>Market Scout</strong>
            <p>Ranks markets by liquidity, resolution clarity, evidence availability, and model fit.</p>
          </div>
          <div>
            <strong>Model Routing</strong>
            <p>Routes each market into the right modeling family instead of using one generic model.</p>
          </div>
          <div>
            <strong>Data Provenance</strong>
            <p>Labels every source as connected, proxy, failed, planned, fallback, or key required.</p>
          </div>
          <div>
            <strong>Consensus Guardrail</strong>
            <p>Compares Operon output against liquid market prices and flags suspicious divergence.</p>
          </div>
        </div>
      </section>

      <section className="public-section model-band">
        <div>
          <p className="eyebrow">Model families</p>
          <h2>Built for different event physics.</h2>
        </div>
        <div className="model-card-grid">
          {modelCards.map(([name, description]) => (
            <div className="model-card" key={name}>
              <span>{name}</span>
              <p>{description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="public-section proof-panel">
        <div>
          <p className="eyebrow">Transparency first</p>
          <h2>Every event page exposes what the model actually used.</h2>
          <p>
            Operon distinguishes real integrations from proxies. If a model needs injuries, odds,
            delegates, or paid feeds, the interface says so directly instead of hiding it in a
            black box.
          </p>
        </div>
        <Link className="button" href="/scout">
          Scan Markets
        </Link>
      </section>
    </>
  );
}
