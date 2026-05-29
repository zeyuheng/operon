import Link from "next/link";
import type { Metadata } from "next";

import "./globals.css";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export const metadata: Metadata = {
  title: "Operon",
  description: "Market-aware event intelligence for prediction markets.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <Link className="brand" href="/">
              Operon
            </Link>
            <nav className="nav">
              <Link href="/scout">Scout</Link>
              <a href={`${apiBaseUrl}/docs`}>API Docs</a>
            </nav>
          </header>
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
