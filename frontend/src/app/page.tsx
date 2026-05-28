import Link from "next/link";

export default function HomePage() {
  return (
    <section className="toolbar">
      <div>
        <h1 className="title">Operon</h1>
        <p className="subtitle">
          Scan prediction markets, select high-quality modeling targets, and turn noisy
          public information into living event probabilities.
        </p>
      </div>
      <Link className="button" href="/scout">
        Open Market Scout
      </Link>
    </section>
  );
}
