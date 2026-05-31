# Climatefacts.ai — Full-Fix Deploy Status (2026-05-31)

User directive: ship the whole `fixes.md` punch-list and deploy live. Full
autonomy granted. This is the honest record of what is on production `main`
(Cloud Build auto-deploys: migrations → API → frontend, ~10-20 min) vs what
is committed-but-not-yet-merged vs what genuinely remains.

> **Mid-session note:** the Windows Git Bash shell hit a fork/heap exhaustion
> after a long run of commands. State below is reconstructed from the last
> confirmed pushes; the F1 merge + F13/F8a commit were interrupted and must be
> completed once the shell recovers (a fresh terminal/session fixes it).

## ✅ LIVE on production (`main` @ `269fc34`, pushed → Cloud Build)

8 items deployed:

| Item | What shipped |
|---|---|
| **F12a** (P0 security) | `/api/analytics/*` admin-gated (anon→401, non-admin→403). `ADMIN_EMAILS=eljailari.suhonen@gmail.com` in deploy env so the owner keeps access. |
| **F5e** | CountrySelector grouped by world region; "Other European countries" gone. |
| **F7** (partial) | KG entity boilerplate filter — "cookies"/nav/legal no longer extracted. |
| **F5b** | Free-tier deep_research cap 2 → 3. |
| **F9a** (partial) | Verify-a-claim fires a toast with the verdict (was silent). |
| **F10a** | Share control on every saved item. |
| **F6b** | "Open country on map" deep-link focuses the country. |
| **F5a** | Deep-search "Platform sources only" toggle. |

## ⏸ COMMITTED but NOT yet deployed (finish when shell recovers)

- **F1** content-scope relevance gate — committed on branch `polish/wave-5`
  (`c56b79a`, 13 tests + 86 regression green). **Pending:** merge `wave-5`
  → `main` + push.
- **F13** i18n missing-key humanize + **F8a** research provenance relabel —
  edits written to `src/frontend/src/lib/i18n.ts` and
  `src/frontend/src/components/RecentResearchAnalyses.tsx`, tsc clean, but the
  commit was interrupted. **Pending:** commit on `wave-5`, then it rides the
  same merge.

### Recovery steps (run in a FRESH terminal)
```
cd C:\Users\35845\Desktop\DIGICISU\climatenews
git checkout polish/wave-5
git add src/frontend/src/lib/i18n.ts src/frontend/src/components/RecentResearchAnalyses.tsx
git commit -m "fix(ux): humanize missing i18n keys (F13) + clarify research provenance link (F8a)"
git checkout main
git merge --no-ff polish/wave-5 -m "Merge wave-5: F1 ingest gate, F13 i18n, F8a research relabel"
git push origin main          # triggers Cloud Build deploy
# optional hygiene: untrack build artifacts
git rm -r --cached $(git ls-files | grep -E "__pycache__|\.pyc$")
git commit -m "chore: untrack __pycache__/*.pyc"; git push origin main
```

## ⏳ NOT shipped — large features / backend-data (honest scope)

Deliberately not force-deployed: each is a multi-file feature whose UIX can't
be verified from this environment (no live render, no prod DB). Shipping a
half-built version would break the production UI.

| Item | Why it's not a quick fix |
|---|---|
| **F3 dark theme** | `layout.tsx` hard-pins `className="light"` on purpose (most components lack `dark:` partners; a prior half-toggle caused "light text on white"). Needs a real ThemeProvider + full `dark:` token audit + live contrast checks. |
| **F7 KG visual graph** | Relationships still render as text rows; needs an inline SVG/canvas node-link graph + live layout testing. (Cookies sub-item IS shipped.) |
| **F9b/c/d/e companies** | Compliance-lens switcher, Planet/People/Profit lens, auto drill-down questions, compare-two-companies — 4 substantial new features. |
| **F8b** academic-only scope | `rss_feed_registry` tier curation + ingest filter + corpus pass. |
| **F8c** research SDG/theme tags | `/api/research/analyses` payload lacks `summary`/`key_findings`/`sdgs`; backend must emit them first. |
| **F8a-full** readable report | Same backend gap as F8c (relabel shipped as the interim step). |
| **F11** unrated sources | Data backfill across `source_credibility_tiers` + source expansion per persona. |
| **F5c** evidence-strength reasoning | Low-evidence path already returns `confidence_envelope`; surfacing "why weak" prominently remains. |
| **F12b** geo balance / **F12c** verdict yield | Not code one-liners — ingestion rebalancing + a verification-pipeline run over the corpus. |
| **F2 / F4 / F6a** | `VERIFY-ON-LIVE` — code reads correct; reproduce on the live deploy (hard-refresh) and report if still broken. |

## What to test on live (after Cloud Build finishes — hard-refresh / clear SW cache)

- **Analytics** admin-only — log in as `eljailari.suhonen@gmail.com`; signed-out → 401/403.
- **Deep search**: region-grouped country dropdown; "Platform sources only" checkbox; 3 free deep searches/month.
- **Companies**: verifying a claim pops a toast with the verdict.
- **My Saves**: each item has a Share button.
- **Article → "Open country on map"**: map flies to the country.
- **Ingestion (after F1 deploys)**: off-topic stories (bus accident class) rejected at ingest; existing off-topic rows still need a backfill.
- **i18n (after F13 deploys)**: no raw `key.like.this` strings in any locale.

## Recommended next session (priority order)

1. Finish the F1/F13/F8a deploy (recovery steps above).
2. F8c + F8a-full: backend emits research summary/findings/SDG → real readable report.
3. F9b–e company suite (one slice each).
4. F3 dark theme (proper system + token audit) — needs live contrast checks.
5. F7 KG graph viz.
6. F12b/c: ingestion rebalance + verification backfill run.
