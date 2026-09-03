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
  // Strip any non-whitelisted HTML to avoid XSS from the backend.
  return html.replace(/<(?!\/?mark\b)[^>]*>/g, "");
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
    return (
      <div className="empty-state">
        <h2>No results for “{data.query}”</h2>
        <p>
          Try different keywords, check your spelling or expand your index by
          crawling more pages.
        </p>
      </div>
    );
  }

  return (
    <section className="results">
      <p className="results-summary">
        About {data.total.toLocaleString()} result{data.total === 1 ? "" : "s"}
      </p>
      <ol className="result-list">
        {data.results.map((hit) => (
          <li key={hit.doc_id} className="result">
            <a href={hit.url} className="result-title" target="_blank" rel="noopener">
              {hit.title || hit.url}
            </a>
            <p className="result-url">{hostOf(hit.url)}</p>
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
        ))}
      </ol>
      <nav className="pagination" aria-label="Search pagination">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          ← Previous
        </button>
        <span>
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next →
        </button>
      </nav>
    </section>
  );
}