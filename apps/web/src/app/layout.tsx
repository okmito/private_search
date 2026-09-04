import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PrivateSearch — Search without being followed.",
  description:
    "Privacy-first search. Your queries stay on your machine. No tracking, no ads, no third-party APIs. Self-hostable.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="grain" aria-hidden />
        <div className="app-shell">
          <header className="app-header">
            <a href="/" className="logo" aria-label="PrivateSearch home">
              <span className="logo-mark" aria-hidden>
                <span className="logo-dot" />
                <span className="logo-ring" />
              </span>
              <span className="logo-word">
                <span className="logo-private">Private</span>
                <span className="logo-search">Search</span>
              </span>
              <span className="logo-tag"> / self-hosted</span>
            </a>
            <nav className="header-nav">
              <a href="https://github.com/privatesearch/privatesearch" target="_blank" rel="noopener">
                GitHub
              </a>
              <a href="/api/v1/health" className="nav-muted">
                API
              </a>
            </nav>
          </header>
          <main className="app-main">{children}</main>
          <footer className="app-footer">
            <div className="footer-inner">
              <span className="footer-left">
                No telemetry <span className="dot">·</span> no ads <span className="dot">·</span> your index, your rules
              </span>
              <span className="footer-right">
                <a href="https://github.com/privatesearch/privatesearch">Source</a> · Apache-2.0 · hand-made with care
              </span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}