# Chat View-Context Contract

The chat assistant resolves pronouns ("this article", "this country", "compare them", "the analysis") against whatever the user is currently viewing. The frontend publishes a small `view_context` payload alongside every `/api/chat` request; the backend hydrates it into a richer block before building the LLM prompt.

This is the contract between frontend pages, the chat surface, and `api/chat_routes.py`.

## Payload shape

`view_context` is an optional dict on `POST /api/chat`. All keys are optional.

| Key | Type | Meaning |
|---|---|---|
| `route` | string | Frontend route (e.g. `/map`, `/deep-search`) |
| `article_id` | string (UUID) | Article currently open |
| `country` | ISO-2/ISO-3 | Country focus (map selection, filter) |
| `compare_countries` | string[] (max 4) | Countries selected in compare mode |
| `analysis_id` | string (UUID) | URL-analysis row currently displayed |
| `deep_search_query` | string | Active deep-search query |
| `deep_search_compare` | `{ query_a, query_b }` | Active deep-search compare topics |
| `source_id` | string | Source page focus |
| `label` | string | Optional human-readable label |

The same shape is also accepted by `/api/map/query` and `/api/articles/{id}/ask` for parity. For backwards-compat, a top-level `country` on `ChatRequest` is lifted into `view_context.country` if not already present.

## Frontend: `ViewContextProvider` / `useViewContext`

Source: `src/frontend/src/lib/view-context.tsx`.

- `ViewContextProvider` wraps the app in `app/layout.tsx`.
- `useViewContext()` exposes `setView(patch)`, `clearKey(key)`, `reset()`. Empty / nullish values in `setView` patches are dropped automatically so the payload stays minimal.
- `serializeViewContext(view)` converts camelCase React state to the snake_case payload above and returns `undefined` if there's nothing to send.
- Outside a provider (server components, tests) `useViewContext` returns a no-op shim.

`AgenticAssistant.tsx` builds the same payload directly from props (`currentArticleId`, `currentCountry`, `currentCompareCountries`, `currentAnalysisId`, `currentDeepSearchQuery`, `currentSourceId`, `currentRoute`, `contextLabel`).

## Backend: `_hydrate_view_context`

Source: `api/chat_routes.py`. Best-effort lookups; failures degrade silently.

- `article_id` -> `article` block: title, source, country, credibility, category, claims status, insight summary, 1500-char body preview.
- `country` -> `country_stats`: article count, source count, HIGH-credibility count, latest published.
- `compare_countries` -> normalised, deduped, capped at 4.
- `analysis_id` -> `url_analysis`: submitted URL, source, title, status, reliability, credibility, up to 5 claims.
- `deep_search_query` / `deep_search_compare` -> short strings, truncated to 300 / 200 chars.
- `source_id` -> `source_focus`: article count, country count, average reliability.
- `route` and `label` are length-capped and forwarded as-is.

If `view_context.country` is set and the request had no top-level `country`, the hydrated value becomes the corpus filter for retrieval (`effective_country`).

## Backend: `_format_view_context_block`

Renders the hydrated dict as a bulleted block injected near the top of the system prompt with this preamble:

> When the user says "this article", "this country", "these results", "the analysis", "compare them", resolve those pronouns against the CURRENT VIEW above first; otherwise fall back to the article corpus below.

Article excerpts are truncated to 800 chars; URL-analysis claims capped at 3.

## Pages publishing view-context

| Page / component | Source | Keys |
|---|---|---|
| Map | `src/frontend/src/app/map/page.tsx` | `countryCode`, `compareCountries` |
| Deep Search | `src/frontend/src/app/deep-search/page.tsx` | `deepSearchQuery`, `deepSearchCompare`, `countryCode` |
| URL Analysis form | `src/frontend/src/components/UrlAnalysisForm.tsx` | `analysisId` |
| `AgenticAssistant` (global) | `src/frontend/src/components/AgenticAssistant.tsx` | All of the above via props |

The article detail page intentionally does not publish view-context: `/api/articles/{id}/ask` already grounds in the article body, so forwarding would be redundant for that endpoint.

## Failure model

- DB errors in `_hydrate_view_context` are logged at debug; the affected block is omitted.
- Missing/malformed `view_context` falls back to corpus retrieval.
- The view block is injected only when at least one field resolved.

## Adding a new field

1. Add it to `ChatRequest.view_context` description (`api/chat_routes.py`) and `ViewContextState` (`view-context.tsx`).
2. Map the camelCase -> snake_case key in `serializeViewContext`.
3. Resolve it inside `_hydrate_view_context` (best-effort).
4. Render it in `_format_view_context_block` as a bullet.
5. Set it from the relevant page via `useViewContext().setView({ ... })` and clear it on unmount.
