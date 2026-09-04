# Indexing

## Inverted Index

`indexing/inverted_index.py` implements the classic `term → [Posting(doc_id, tf, positions)]` map.

- Tokenization via `EnglishTokenizer` (lowercase, NFKC, html.unescape, `\w+`, stop words, length bounds).
- Per-document `DocumentField` stores `doc_length`, `title_length`, `url`, `title`.
- `IndexStats` tracks `num_documents`, `num_terms`, `avg_document_length`.

## Persistence

`IndexSnapshot` serializes stats + postings + documents to JSON. `InvertedIndex.save_snapshot(path)` / `load_snapshot(path)` round-trip in tests.

`IndexingPipeline` is the bridge to storage:

- `index_pages(pages)` — for each `CrawledPage`, compute `content_hash`, upsert the `Document` row (hash dedup), then sync the in-memory index.
- `load_from_storage()` — rebuilds the index from all `Document` rows.
- Snapshot path is `data/index` by convention; API calls `holder.rebuild()` (`GET /api/v1/index/rebuild`).

## Retriever

`retrieval/retriever.py` wraps `BM25` + `build_snippet` (window around first match, `<mark>` highlighting). `retriever.count(query)` exposes total hits for pagination.