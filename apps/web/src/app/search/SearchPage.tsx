"use client";

import { useEffect, useState, useTransition } from "react";
import { searchDocuments, fetchSuggestions } from "@/lib/api";
import type { SearchResponse } from "@/lib/types";
import ResultList from "./ResultList";

interface SearchPageProps {
  initialQuery?: string;
}

export default function SearchPage({ initialQuery }: SearchPageProps) {
  const [query, setQuery] = useState<string>(initialQuery ?? "");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isPending, startTransition] = useTransition();

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
    <div className="search-page">
      <form className="search-form" onSubmit={onSubmit} role="search">
        <input
          type="search"
          name="q"
          autoComplete="off"
          spellCheck={false}
          placeholder="Search the web without being tracked"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search query"
        />
        <button type="submit" disabled={isPending || !query.trim()}>
          {isPending ? "Searching…" : "Search"}
        </button>
      </form>
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
      {results && !isPending && (
        <ResultList results={results} query={query} />
      )}
    </div>
  );
}