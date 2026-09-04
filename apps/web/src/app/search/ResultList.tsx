"use client";

import type { SearchResponse } from "@/lib/types";
import { searchDocuments } from "@/lib/api";
import { useState } from "react";

interface ResultListProps {
  results: SearchResponse;
  query: string;
}

const HOST_NAME_REGEX = /^https?:\/\/([^/]+)/;

function hostOf(url: string): string {
  const match = HOST_NAME_REGEX.exec(url);
  return match ? match[1] : url;
}

function safeHighlight(html: string): string {
  return html.replace(/<(?!\/?mark\b)[^>]*>/g, "");
}

function faviconLetter(host: string): string {
  return host.charAt(0).toUpperCase() || "•";
}

export default function ResultList({ results, query }: ResultListProps) {
  const [page, setPage] = useState(results.page);
  const [data, setData] = useState(results);

  if (page !== results.page) {
    setData(results);
    setPage(results.page);
  }

  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  const onPageChange = async (nextPage: number) => {
    try {
      const updated = await searchDocuments({ query, page: nextPage, limit: data.page_size });
      setData(updated);
      setPage(nextPage);
    } catch {
      // ignore pagination errors for now
    }
  };

  if (data.results.length === 0) {
    const quick = ["youtube", "machine learning", "cooking", "python", "vector search", "example"];
    return (
      <div className="empty-state">
        <h2>No results for “{data.query}”</h2>
        <p>
          PrivateSearch only searches pages you stored — your index has {data.total} matches for this query.
        </p>
        <p>Try one of these:</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center", marginTop: 8 }}>
          {quick.map((q) => (
            <button
              key={q}
              type="button"
              className="suggestion"
              onClick={() => searchDocuments({ query: q, page: 1, limit: data.page_size }).then(setData).catch(() => {})}
            >
              {q}
            </button>
          ))}
        </div>
        <p style={{ marginTop: 14 }}>
          Still empty? Run <code>python scripts/seed_demo.py</code> then{" "}
          <code>curl http://localhost:8000/api/v1/index/rebuild</code>
        </p>
      </div>
    );
  }

  return (
    <section className="results">
      <p className="results-summary">
        {data.total.toLocaleString()} result{data.total === 1 ? "" : "s"} for “{data.query}” · page {data.page} of {totalPages}
      </p>
      <ol className="result-list">
        {data.results.map((hit) => {
          const host = hostOf(hit.url);
          return (
            <li key={hit.doc_id} className="result">
              <div className="result-top">
                <span className="result-favicon" aria-hidden>
                  {faviconLetter(host)}
                </span>
                <p className="result-url">{host} · score {hit.score.toFixed(2)}</p>
              </div>
              <a href={hit.url} className="result-title" target="_blank" rel="noopener">
                {hit.title || hit.url}
              </a>
              <p
                className="result-snippet"
                dangerouslySetInnerHTML={{ __html: safeHighlight(hit.highlighted || hit.snippet) }}
              />
              {hit.explanation && (
                <details className="result-explanation">
                  <summary>Why this result?</summary>
                  <ul>
                    {Object.entries(hit.explanation).map(([key, value]) => (
                      <li key={key}>
                        <span>{key}</span>: <strong>{Number(value).toFixed(3)}</strong>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          );
        })}
      </ol>
      <nav className="pagination" aria-label="Search pagination">
        <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          ← Previous
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>
          Next →
        </button>
      </nav>
    </section>
  );
}