"use client";

import { useEffect, useState, useTransition } from "react";
import { searchDocuments, fetchSuggestions } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import ResultList from "./ResultList";

interface SearchPageProps {
  initialQuery?: string;
}

function SearchIcon() {
  return (
    <svg className="search-icon" viewBox="0 0 20 20" fill="none" aria-hidden>
      <path
        d="M14.5 14.5L17 17M15.5 9.5A6 6 0 113.5 9.5a6 6 0 0112 0z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

export default function SearchPage({ initialQuery }: SearchPageProps) {
  const [query, setQuery] = useState<string>(initialQuery ?? "");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isPending, startTransition] = useTransition();
  const [stats, setStats] = useState<{ documents: number; terms: number } | null>(null);
  const hasResults = results !== null;

  useEffect(() => {
    fetch("/api/v1/stats")
      .then((r) => (r.ok ? r.json() : null))
      .then((j) => j && setStats({ documents: j.documents, terms: j.terms }))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!query) {
      setResults(null);
      setSuggestions([]);
      return;
    }
    const handler = setTimeout(() => {
      fetchSuggestions(query)
        .then((payload) => setSuggestions(payload.suggestions))
        .catch(() => setSuggestions([]));
    }, 200);
    return () => clearTimeout(handler);
  }, [query]);

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      return;
    }
    startTransition(async () => {
      try {
        setError(null);
        const response = await searchDocuments({ query: trimmed });
        setResults(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed");
        setResults(null);
      }
    });
  };

  return (
    <div className={`search-page ${hasResults ? "has-results" : ""}`}>
      {!hasResults && (
        <div className="hero">
          <h1>
            Search without <em>being followed.</em>
          </h1>
          <p>
            Your queries stay on your machine. No ads, no tracking.
            <br />
            Self-hosted. Your index, your rules.
          </p>
        </div>
      )}

      {stats !== null && stats.documents < 5 && !hasResults && (
        <p className="status" style={{ maxWidth: 640, margin: "0 auto", width: "100%" }}>
          Index has {stats.documents} pages ({stats.terms} terms) — try <code>python scripts/seed_demo.py</code> then search{" "}
          <strong>youtube</strong> or <strong>machine learning</strong>.
        </p>
      )}

      <form className="search-form" onSubmit={onSubmit} role="search">
        <SearchIcon />
        <input
          type="search"
          name="q"
          autoComplete="off"
          spellCheck={false}
          placeholder="Ask your index anything"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search query"
        />
        <button type="submit" disabled={isPending || !query.trim()}>
          {isPending ? "Searching…" : "Search →"}
        </button>
      </form>

      <div className="search-meta">
        <span>{stats ? `${stats.documents} pages indexed` : "index ready"}</span>
        <span className="sep">·</span>
        <span>BM25 + hybrid</span>
        <span className="sep">·</span>
        <span>no tracking</span>
      </div>

      {suggestions.length > 0 && (
        <div className="suggestions" aria-label="Suggestions">
          {suggestions.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="suggestion"
              onClick={() => setQuery(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
      {error && <p className="error">Error: {error}</p>}
      {isPending && <p className="status">Searching…</p>}
      {results && !isPending && <ResultList results={results} query={query} />}
      {!hasResults && !isPending && (
        <p className="status" style={{ marginTop: 8 }}>
          Try: youtube · machine learning · vector search · cooking
        </p>
      )}
    </div>
  );
}