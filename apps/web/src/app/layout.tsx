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
        <div className="app-shell">
          <header className="app-header">
            <a href="/" className="logo" aria-label="PrivateSearch home">
              <span className="logo-mark">PS — 01</span>
              <span className="logo-word">
                <span className="logo-private">Private</span>
                <span className="logo-search">Search</span>
              </span>
              <span className="logo-tag">self-hosted / no. 008</span>
            </a>
            <nav className="header-nav">
              <a href="https://github.com/privatesearch/privatesearch" target="_blank" rel="noopener">
                GitHub
              </a>
              <a href="/api/v1/health">API</a>
            </nav>
          </header>
          <main className="app-main">{children}</main>
          <footer className="app-footer">
            <div className="footer-inner">
              <span>Set in Fraunces &amp; JetBrains Mono — Printed in the browser</span>
              <span>
                <a href="https://github.com/privatesearch/privatesearch">Source</a> · Apache-2.0 · hand-set with care
              </span>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}