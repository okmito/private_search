import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PrivateSearch",
  description:
    "Privacy-first search engine. No tracking, no third-party APIs.",
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
            <a href="/" className="logo">
              <span aria-hidden>🛡️</span> PrivateSearch
            </a>
            <nav>
              <a href="https://github.com/privatesearch/privatesearch">
                About
              </a>
            </nav>
          </header>
          <main className="app-main">{children}</main>
          <footer className="app-footer">
            <span>
              No telemetry. No third-party APIs. Run it yourself.
            </span>
          </footer>
        </div>
      </body>
    </html>
  );
}