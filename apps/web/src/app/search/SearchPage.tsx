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
        d="M13.2 13.2L17 17M14.5 9.2a5.2 5.2 0 11-10.4 0 5.2 5.2 0 0110.4 0z"
        stroke="currentColor"
        strokeWidth="1.5"
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
          <p className="hero-kicker">EST. 2024 · PRIVATE INDEX</p>
          <h1>
            Search without <em>being followed.</em>
          </h1>
          <p>
            Your queries stay on <strong>your machine</strong>. No ads, no profile, no third party. Just the web you
            chose to keep.
          </p>
        </div>
      )}

      {stats !== null && stats.documents < 5 && !hasResults && (
        <p className="status">
          Index has {stats.documents} pages · run <code>python scripts/seed_demo.py</code> then try{" "}
          <strong>youtube</strong>
        </p>
      )}

      <form className="search-form" onSubmit={onSubmit} role="search">
        <SearchIcon />
        <input
          type="search"
          name="q"
          autoComplete="off"
          spellCheck={false}
          placeholder="Ask your index anything — try “youtube music”"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search query"
        />
        <button type="submit" disabled={isPending || !query.trim()}>
          {isPending ? "Searching…" : "Search"}
        </button>
      </form>

      <div className="search-meta">
        <span>{stats ? `${stats.documents} pages · ${stats.terms} terms` : "index ready"}</span>
        <span className="sep">—</span>
        <span>BM25 + hybrid</span>
        <span className="sep">—</span>
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
        <p className="status" style={{ marginTop: 4 }}>
          Try: youtube · youtube music · machine learning · vector search
        </p>
      )}
    </div>
  );
}