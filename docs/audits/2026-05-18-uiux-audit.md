# Climatefacts.ai - UI/UX Audit (2026-05-18)

Frontend is in solid shape: rebrand to Climatefacts.ai is complete in user-facing copy (the only stale "CliLens.AI" reference lives in `src/frontend/src/__tests__/pages/HomePage.test.tsx`, not a shipping surface), `MethodologyDrawer` and `/methodology` both render live API data with graceful per-section degradation, and the article detail page surfaces verification status, provenance, and "re-analyze" controls thoughtfully. The main weaknesses are (a) the contextual chat assistant is a Q&A tool rather than an agent that can *act* on the platform - users cannot trigger URL analysis, save items, log in, or apply map filters from chat; (b) several loading states fall back to bare spinners instead of skeletons (`/search`, `/feed`, `/dashboard/saved`); (c) the home page has hardcoded `text-clilens-teal-*` color tokens that survive a dark-mode toggle as light-on-light; (d) the `/feed` page advertises 198-country coverage at platform level but only exposes 33 hard-coded countries, which contradicts the map; (e) accessibility gaps in icon-only buttons (theme toggle, remove-bookmark, view-mode toggles) and the article detail page has no `<main>` landmark wrap. No P0 page-blanking issues found - error boundaries and try/catches are present on every fetch path I reviewed.

## Top issues

| # | Page | Sev | Issue | Fix shape |
|---|------|-----|-------|-----------|
| 1 | global / chat | P1 | Chat is read-only: cannot trigger URL analysis, bookmark, login, apply map filters, run deep search, or open methodology. Users have to context-switch to every other surface. | Add an `actions` payload from `/api/chat` (e.g., `{type:"analyze_url", url}`) and wire client-side handlers in `AgenticAssistant` (router.push, openMethodology, callApi). See chat gap section. |
| 2 | `/feed` | P1 | Hardcoded list of 33 countries (`AVAILABLE_COUNTRIES`) contradicts platform's advertised 198-country coverage. | Replace with `api.getCountries()` like `/map` and `/search` already use via `CountrySelector`. |
| 3 | `/search` | P1 | Loading state is a plain text "Loading results..." (no skeletons), while `/` uses `SkeletonCard`. Inconsistent across the two most-used pages. | Replace line 424 with `<div className={gridClass}>{Array.from({length:4}).map(...<SkeletonCard/>)}</div>`. |
| 4 | `/dashboard/saved` | P1 | Loading is a centered spinner with no layout placeholder; remove-bookmark button only visible on hover (`opacity-0 group-hover:opacity-100`) -> untouchable on mobile/touch. | Use SkeletonCard grid for loading; make trash icon always visible at reduced opacity on touch (`md:opacity-0 md:group-hover:opacity-100`). |
| 5 | `/feed` | P1 | Loading is a bare centered spinner; no empty state when user has zero countries selected (Save button just disables silently). | Add skeleton sections + empty-state CTA "Select at least one country to start". |
| 6 | `/` home | P1 | Body uses `bg-gray-50` and brand `text-clilens-teal-*`; layout enables `dark:bg-gray-900` on body but the home page does not provide dark variants. Toggling theme produces unreadable light-on-light. | Either gate dark mode behind pages that opt in, or add `dark:bg-gray-900 dark:text-gray-100` variants to home/search/feed root divs. |
| 7 | `/analyze` | P2 | Page has no `<h1>` styled hero or stepper for the 30s wait; relies entirely on `UrlAnalysisForm` for status. No empty state guidance if the user hasn't pasted a URL. | Mirror `/deep-search` progress stepper (queued -> fetched -> claims -> verified). |
| 8 | `/articles/[id]` | P2 | No `<main>` landmark; the page renders inside the layout `<main>` but its own root is a `<div>`. Screen readers get "article" only. Also missing alt text on infographic `<img>` is generic `${tpl} infographic`. | Wrap content in `<main id="main-content">` (or rely on layout's), set `alt={'Visual: ' + article.title + ' - ' + tpl}`. |
| 9 | `/map` | P2 | "No data yet" only shown via the legend ("No data" swatch); empty-data countries are colored `bg-slate-700` on the map but `MapCountryPanel` (clicked) will fetch and likely show zeros. Misleading. | In `MapCountryPanel` when `article_count===0`, render an explicit "No coverage yet for {country}" empty state with CTA "Suggest a source". |
| 10 | global chat | P2 | Collapsed bar has a `Mic` icon (line 513 of AgenticAssistant) that is decorative - it has no onClick. Users will click expecting voice input. | Either implement Web Speech API or remove the icon. |
| 11 | global chat | P2 | Click-outside-to-collapse only fires when there are zero messages (`messages.length === 0`); after first message, user must hit the chevron. Discoverability issue. | Document via tooltip on the chevron "Close (history preserved)" or allow Esc to collapse. |
| 12 | global / icon buttons | P2 | Missing `aria-label`s: theme toggle (uses `title=` only), home-page view-mode buttons (`title=` only), trash-can in saved (uses `title=` only). | Replace/augment with `aria-label={...}`. |
| 13 | `/login`, `/signup` | P2 | OAuth buttons silently disable if `NEXT_PUBLIC_GOOGLE_CLIENT_ID` env is unset (40% opacity, no tooltip). Confusing if backend supports it but frontend env is missing. | Render a tooltip `title="OAuth not configured on this deployment"` when disabled, or hide entirely. |
| 14 | `/signup` | P2 | Selecting a paid tier routes to `/dashboard/subscription` after registration but the tier choice is not validated against the user's actual subscription state; if Stripe fails the user is silently on freemium. | Show a banner on subscription page if `tier !== user.subscription_tier`. |
| 15 | `/deep-search` | P2 | "Sources" header (line 372) shows raw counts but citations list has no pagination - very long external lists overflow card. Also no toast/banner when partial result (`clarification_needed` present) - it appears below the answer with no priority cue. | Cap citations to 8 with "Show more"; render clarification chips above the answer, not after. |
| 16 | `/research` | P2 | Status string `result.status === "completed"` is the only render guard; pending/failed states are not handled. If the API returns `processing` user sees a blank form again. | Mirror article detail's `claims_status` pattern. |
| 17 | `/articles/[id]/transparency` | P2 | Long page (read first 120 lines, structured) - missing in-page table of contents; jumping between Methodology / Reliability / Claims / Evidence requires scroll. | Add sticky right-rail anchor list. |
| 18 | `MethodologyDrawer` | P3 | Uses `<details>` element (lines 42-45) but state is mirrored into React `useState` via `onToggle`. Works, but cannot be opened programmatically (e.g., from chat). | Convert to controlled component so chat assistant can `setOpen(true)` deep-linked. |
| 19 | `GlobalNav` | P3 | Hides itself on `/map`, `/articles/*`, `/dashboard/*`, `/login`, `/signup` (line 96). Article detail pages then have no navigation back - the only "Back" is a small text link top of article. | Render a slim sticky breadcrumb on standalone pages, or stop hiding nav on `/articles/*`. |
| 20 | mobile | P3 | `/` home hero "Stats summary" row (`flex space-x-8`) wraps awkwardly on <380px because each item is `flex items-center` with no `flex-wrap` on container. | Add `flex-wrap gap-3` to the container at line 81. |

## Chat panel gap analysis

`ContextualAssistant` + `AgenticAssistant` is well-instrumented for *context* (route, article id, country, compare countries, analysis id, deep-search query all flow into `view_context`) but the response surface is limited to: text answer, `highlighted_countries` (map only), `cited_articles` (deep-link to article pages, open in new tab), `clarification_needed` chips. The chat cannot drive the platform.

Actions available in the UI but **not** triggerable via chat:

- **Analyze a URL** - no path from chat to `/api/analyze`. User must navigate to `/analyze`.
- **Search/filter articles** - cannot apply credibility/tag/date filters on `/search` or `/`.
- **Apply map filters** - `MapAgenticChat` only highlights countries via `country_highlights`; cannot set source, date range, layer, or category filters.
- **Open a country / compare countries** - on the map page `selectedCountry` is local state; chat cannot programmatically open the right panel for a country.
- **Run a deep search** - chat cannot kick off `/api/deep-search` and route the user to the result.
- **View methodology / open the drawer** - `MethodologyDrawer` is uncontrolled; chat cannot deep-link to "show the prompts" or "show calibration".
- **View saved items / bookmark this article** - no bookmark or unbookmark action.
- **Log in / sign up** - chat cannot detect "I want to subscribe" and route to `/signup?tier=...`.
- **View fact-checks for a claim** - claims are addressable by `#claim-N` anchors but chat does not link to them.
- **Reanalyze / re-run analysis** - `ReanalyzeButton` exists but is not exposed.
- **Suggest a source / submit URL** - `/suggest-source` and `/submit` not reachable from chat.

Suggested minimal action protocol: backend returns an optional `actions: [{type, params, label}]` array; client renders them as clickable chips above the message input. Types to implement first: `navigate`, `analyze_url`, `apply_search_filters`, `apply_map_filters`, `open_methodology_section`, `open_country`, `start_deep_search`, `bookmark_article`.

## Files reviewed

- `src/frontend/src/app/{page,search/page,map/page,deep-search/page,analyze/page,research/page,about/page,methodology/page,login/page,signup/page,feed/page,error,layout}.tsx`
- `src/frontend/src/app/articles/[id]/{page,transparency/page}.tsx`
- `src/frontend/src/app/dashboard/saved/page.tsx`
- `src/frontend/src/components/{ContextualAssistant,AgenticAssistant,MethodologyDrawer,ArticleDetailTabs,GlobalNav,SkeletonCard,UrlAnalysisForm,map/MapCountryPanel}.tsx`
