# Analytical Robustness Audit — 2026-05-18

Scope: every module under `src/backend/app/domains/intelligence/` plus the six indicator adapters under `src/backend/app/domains/content/indicators/`. Method: source read + cross-check against the claimed composite grade of 4.78/5.

---

## 1. Claim extraction quality

**Verdict: 3.5/5.** The shared prompt (`prompts.py:158-179`, `_CLAIM_EXTRACTION_TEMPLATE`) asks for `claim_type ∈ {factual, opinion, prediction}` AND `claim_category ∈ {scientific_causal, statistical, policy, anecdotal, predictive}`. These two taxonomies overlap (a "prediction" type can also be a "predictive" category) which weakens discrimination — the LLM has to make two correlated choices on the same sentence.

**Gap:** the prompt has no instruction for hedged language. A claim like "emissions *could* rise 30% by 2040" is both predictive and hedged, but nothing in the template asks the model to preserve the hedge or downgrade `importance_score`. The downstream verifier treats "will rise 30%" and "could rise 30%" as identical Jaccard-wise (`multi_llm_verifier.py:165-175` strips punctuation only — modal verbs survive but are not separately weighted). Wording is also not required to be a verbatim quote, so paraphrase drift is unmeasured.

## 2. Multi-LLM agreement

**Verdict: 3.5/5.** Jaccard ≥ 0.5 on token sets is a defensible default for short factual claims sharing technical vocabulary (`multi_llm_verifier.py:251`), and the "agreement = corroboration" framing is honest.

**Gap:** the documented failure mode in the prompt — "DeepSeek and Anthropic agree on a hallucinated claim" — is real and unaddressed. The module's own docstring at `multi_llm_verifier.py:14-35` says "two independent models running the same extraction give a much harder signal", but with `claim_extraction` v1.0 sent to BOTH (the very design choice that lets agreement_score be measured), shared training-corpus biases collapse independence. `agreement_score=1.0` means "both models extracted the same string", not "the claim is true". No ground-truth check (e.g., against `country_indicators`) ever runs at the multi-LLM stage.

## 3. Hallucination detection

**Verdict: 3.0/5.** Three-channel composite (`hallucination_detector.py:60-70`): entity overlap (0.3) + statistic accuracy (0.3) + LLM grounding (0.4). The LLM-grounding piece is the heaviest weight and it's a self-graded LLM call — that bakes in the same model bias the multi-LLM step tried to mitigate.

**Gap:** entity extraction is regex on capitalised n-grams (`hallucination_detector.py:128-142`). It will flag "European Union" if the source only said "EU", and pass "Saudi Aramco invented solar power" if both tokens appear anywhere across the source corpus (set intersection, no context). Multi-source synthesis where the claim spans the union of sources but is in none individually is correctly handled at the entity layer (sets are unioned at `:104-106`) but fails the statistic check, which requires the exact number string in any single source (`:213-227`). Net effect: numeric synthesis is over-flagged; entity hallucination is under-flagged.

## 4. Calibration

**Verdict: 2.5/5.** The math is correct (hand-rolled Brier/ECE/Platt verified at `calibration.py:116-306`). Graceful degradation works: `refit_and_persist` returns `insufficient_data` when N < 5 (`calibration_store.py:249-254`), and the `/api/methodology/calibration` endpoint returns "awaiting first labels" when zero rows exist (`api/methodology_routes.py:369-380`).

**Gap:** label population is unknown but almost certainly < 50. The `min_labels=5` floor is far below what produces a stable Platt fit on real-world climate-news distributions (literature suggests N ≥ 50 for reliable two-parameter logistic regression in calibration). At N = 5–15 the fit will swing wildly between weekly refits. There is no warning surfaced to users when the active fit was learned on too few labels.

## 5. Sustainability score formula

**Verdict: 3.5/5.** Re-weighting on missing components is transparent (`sustainability_score.py:276-285`), confidence bands widen with fewer indicators (`:170-177`), and per-component provenance is preserved.

**Gap (and this is the big one):** the formula at `sustainability_score.py:131-162` is **0.40 emissions-inverse + 0.40 renewable share + 0.20 CAT rating**. The prompt asserts the formula uses "0.5 × inverse-emissions + 0.5 × renewable + 3rd component when CAT/UNFCCC/IRENA present" — the actual weights differ (0.40/0.40/0.20). More importantly, **ND-GAIN adaptation index is fetched but never enters the score** (`nd_gain.py` writes `nd_gain_index` rows, but `COMPONENTS` in `sustainability_score.py` doesn't reference it). This biases the composite toward rich, decarbonising countries and gives zero credit to vulnerable low-emitter nations that score highly on adaptation readiness. UNFCCC NDC + IRENA adapters write data that is also not consumed by the composite.

## 6. Drift detection

**Verdict: 4.0/5.** Cleanly implemented (`drift_detection.py`). KL on Laplace-smoothed source mix + prompt-fingerprint with thresholds 0.10 / 0.25 / 0.50 nats is defensible. Non-overlapping baseline/recent windows (`:222-228`) prevent leakage.

**Gap:** thresholds are documented as "tuned per-deployment" but no per-deployment calibration job exists — they are hard-coded constants (`verdict_for` at `:134-142`). The baseline window default (30 days) is too short to be stable for a platform that's been operational only since 2026-04 — the "baseline" is itself drifting.

## 7. Indicator adapters

**Verdict: 3.5/5.** All six implement the same base contract (`indicators/base.py`), upsert is idempotent, schema drift is debug-logged and skipped rather than crashing the sync.

**Gap:** there is **no last-fetched-at SLA**. The `country_indicators` table has a `fetched_at` column, but nothing in the API surface refuses to render a sustainability score when its inputs are >18 months old. The `compute_sustainability_score` function happily blends a 2022 OWID emissions number with a 2024 IRENA renewable share and a 2025 CAT rating into one composite — without exposing the year-range mismatch in the confidence band. OWID's documented 1–2-year lag (`owid.py:17-18`) is acknowledged in comments but not in the score's uncertainty.

## 8. Reliability against research papers

**Verdict: 3.0/5.** `BayesianCredibilityService.compute_research_prior` (`bayesian_credibility.py:23-67`) tiers content correctly: news_article = 50, preprint = 40, research_report = 60, policy_document = 55, with +20 for DOI and +30 for known venue (Nature, Science, Elsevier, Springer, Wiley, PLOS, Frontiers, Copernicus).

**Gap:** the `KNOWN_VENUES` set is 8 publishers, hard-coded, alphabetic. There is no concept of journal impact factor, retraction history, or NGO-vs-academic distinction. A peer-reviewed Nature article scores 50 + 20 (DOI) + 30 (venue) = 100, but an Elsevier predatory-journal paper hits the same ceiling. An NGO blog post that happens to have a DOI (some do) reaches 70. The credibility tier is essentially binary: "known publisher? +30 : 0".

## 9. Transparency / audit trail

**Verdict: 4.5/5.** Provenance is well-wired. `claim_provenance` schema records model + prompt name + version + fingerprint + retrieval strategy + source article IDs + hallucination score + raw metadata, and four read endpoints (`/api/methodology/audit-trail/url-analysis|article|claim` at `api/methodology_routes.py:279-322`, plus `/audit-trail/deep-search` referenced from `provenance.py:240-262`) surface them.

**Gap:** the audit trail is best-effort (any DB error returns None at `provenance.py:149-154`), and there's no metric for "what fraction of analyses have at least one provenance row". A silent collapse of writes wouldn't be visible. Spot-check: tracing one URL analysis would walk `url_analyses → claim_provenance` and read prompt_fingerprint, but `claim_provenance.source_article_ids` is a JSONB array of UUIDs only — no titles/URLs joined in the audit-trail endpoint response, so an external auditor sees opaque IDs.

## 10. Per-axis grade reality check

The composite of 4.78/5 in the memory document is optimistic. Concrete instances where actual robustness is below the claimed grade:

- **Calibration claimed at "Phase 5 wave 5 complete":** label table exists, math is right, but if the deployed DB has <50 calibration_labels rows, the calibrated reliability is statistical noise — and there's no SQL count of labels exposed at `/api/methodology/calibration`.
- **Sustainability axis:** the formula in code (0.40/0.40/0.20) doesn't match the formula described in the audit prompt (0.5/0.5/+3rd), and ND-GAIN is fetched but unused — that's a >0.5-point honesty gap on its own.
- **Reliability axis:** known-venues whitelist of 8 publishers is the entire source-tiering apparatus.

---

## Honest re-grading

| Axis              | Claimed | Assessed | Gap                                                                 |
|-------------------|---------|----------|---------------------------------------------------------------------|
| Reliability       | 4.8     | 3.5      | 8-publisher venue whitelist; no impact-factor or retraction signal  |
| Transparency      | 4.8     | 4.5      | Audit trail returns UUIDs without joined titles                     |
| Traceability      | 4.8     | 4.3      | source_article_ids array not denormalised in endpoint response      |
| Calibration       | 4.7     | 2.8      | Likely <50 labels; min_labels=5 floor too low for stable Platt      |
| Hallucination     | 4.8     | 3.2      | Entity check is set-intersect; statistic check rejects synthesis    |
| Drift detection   | 4.8     | 4.0      | Thresholds hard-coded; baseline window too short for new platform   |
| Sustainability    | 4.8     | 3.3      | ND-GAIN unused; weights don't match docs; mixed-year inputs unfla­gged |
| Multi-LLM         | 4.8     | 3.5      | Shared prompt collapses independence; shared-bias hallucinations score 1.0 |
| Claim extraction  | 4.7     | 3.5      | Overlapping type/category; no hedge handling; paraphrase tolerated  |
| **Composite**     | **4.78**| **3.6**  | ~1.18 points of optimism                                            |

---

## Top 5 changes to push composite to true 4.8

1. **Wire ND-GAIN into the sustainability composite.** Edit `src/backend/app/domains/intelligence/sustainability_score.py:131-162` to add a fourth `ComponentDefinition(indicator_id="nd_gain_index", weight=0.15, normalizer=lambda x: x)` and rebalance to (0.35 emissions, 0.35 renewable, 0.15 CAT, 0.15 ND-GAIN). Bump `METHODOLOGY_VERSION` to `sustainability_v2_2026_05`.

2. **Add a `min_labels_for_inference` floor of 50.** In `src/backend/app/domains/intelligence/calibration_store.py:231-254`, refuse to write a `calibration_fits` row when `n_labels < 50`, OR write it but tag `status='preview'`. In `apply_latest_to_reliability` (`:353-372`), skip preview fits — fall back to raw. Surface `n_labels` and `is_preview` at `/api/methodology/calibration`.

3. **Replace 8-publisher venue whitelist with a tiered credibility table.** Move `KNOWN_VENUES` out of `src/backend/app/domains/intelligence/bayesian_credibility.py:48-51` into a DB-backed `source_credibility_tiers` table seeded with Scimago Journal Rank quartiles + retracted-paper flags. Tier 1 = +30, Tier 2 = +15, Tier 3 = +5, unknown = 0. Joins on DOI prefix or domain.

4. **Stop the multi-LLM-shared-hallucination scenario.** In `src/backend/app/domains/intelligence/multi_llm_verifier.py:354-376`, before returning a corroborated claim, cross-check any numeric content in the claim against `country_indicators` (for emissions/renewable claims). Add a `numeric_grounded: bool` field to `CorroboratedClaim`; downgrade `confidence` by 0.5 when corroborated=True but numeric_grounded=False.

5. **Flag mixed-year input vintages in sustainability output.** In `src/backend/app/domains/intelligence/sustainability_score.py:281-297`, compute `year_spread = max(year) - min(year)` across contributing components and widen `confidence_band` by `2 * year_spread` (so a 2022+2024+2025 mix adds ±6 to the existing ±10/15/25 band). Expose `year_spread` in the API response next to `indicators_used`.
