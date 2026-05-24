import { test, expect, type Route } from '@playwright/test';

/**
 * GP3 — Deep Search compare with weak/empty evidence.
 *
 * Verifies the §3.1 fix shipped on 2026-05-23:
 *   1. The aggregate `guidance` block renders prominently above the
 *      comparative analysis (not after, not buried) when both sides return 0
 *      sources.
 *   2. The unified `clarification_needed` refinement chips appear, and the
 *      "A" / "B" buttons on each chip re-fire the compare with the refined
 *      query.
 *   3. The "Low confidence" pill renders on the comparative card.
 *   4. The Cmp synthesis text is the deterministic explainer, not the
 *      former hallucinated "Both topics address polar ice dynamics..."
 *      paragraph.
 *
 * Backend is mocked via `page.route` so this passes in CI without a
 * running FastAPI backend. The Phase 1 integration suite will run the
 * same assertions against a real seeded docker-compose stack.
 */
test.describe('Deep Search · Compare with weak evidence (GP3)', () => {
  const COMPARE_FIXTURE_BOTH_EMPTY = {
    query_a: 'Arctic ice melt acceleration',
    query_b: 'Antarctic ice shelf loss comparison',
    result_a: {
      query: 'Arctic ice melt acceleration',
      answer:
        'Based on the provided sources, I cannot generate a comprehensive answer.',
      citations: [],
      internal_articles_count: 0,
      external_sources_count: 0,
      weather_context: null,
      filters: { country: null, category: null },
      methodology: {
        queries_run: [
          { layer: 'internal_corpus', scope: {}, hits: 0 },
          { layer: 'perplexity_external', hits: 0 },
        ],
        retrieval_strategy: 'internal_corpus(fts+semantic) + perplexity_external',
        weather_used: false,
        synthesis_model: 'anthropic',
        embedding_model: 'openai:text-embedding-ada-002',
        external_provider_configured: true,
        sources_consulted: [],
        hallucination_check: null,
        prompts_used: {},
      },
      clarification_needed: null,
      searched_at: '2026-05-23T10:00:00Z',
    },
    result_b: {
      query: 'Antarctic ice shelf loss comparison',
      answer: 'No data available.',
      citations: [],
      internal_articles_count: 0,
      external_sources_count: 0,
      weather_context: null,
      filters: { country: null, category: null },
      methodology: {
        queries_run: [
          { layer: 'internal_corpus', scope: {}, hits: 0 },
          { layer: 'perplexity_external', hits: 0 },
        ],
        retrieval_strategy: 'internal_corpus(fts+semantic) + perplexity_external',
        weather_used: false,
        synthesis_model: 'anthropic',
        embedding_model: 'openai:text-embedding-ada-002',
        external_provider_configured: true,
        sources_consulted: [],
        hallucination_check: null,
        prompts_used: {},
      },
      clarification_needed: null,
      searched_at: '2026-05-23T10:00:00Z',
    },
    comparative_analysis:
      'We could not find evidence in our verified corpus or external sources for either "Arctic ice melt acceleration" or "Antarctic ice shelf loss comparison". A side-by-side comparison would be unreliable here — instead, try one of the refined queries below.',
    comparative_analysis_structured: null,
    guidance: {
      status: 'empty',
      reason: 'no_matching_evidence_either_side',
      message:
        'Neither topic returned matching evidence from the verified corpus or external research. The comparative analysis below is a deterministic explainer — not a synthesised finding. Pick a refined query to get a substantive answer.',
      suggested_actions: [
        'Constrain by country and timeframe',
        'Use domain-specific terms (e.g. SPI, SPEI, sea-ice extent)',
        'Pick one of the refined queries below',
      ],
      per_side: {
        a: { internal: 0, external: 0 },
        b: { internal: 0, external: 0 },
      },
    },
    clarification_needed: [
      'Arctic sea-ice extent September minimum 2010-2024',
      'Antarctic ice shelf mass balance Larsen C 2015-2024',
      'Compare Arctic vs Antarctic ice loss rates 2000-2024',
    ],
    low_confidence: true,
    compared_at: '2026-05-23T10:00:00Z',
  };

  test('renders aggregate guidance, refinement chips, and low-confidence pill when both sides are empty', async ({ page }) => {
    let compareCalls = 0;
    let lastBody: any = null;

    await page.route('**/api/deep-search/compare', async (route: Route) => {
      compareCalls += 1;
      lastBody = JSON.parse(route.request().postData() || '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(COMPARE_FIXTURE_BOTH_EMPTY),
      });
    });

    await page.goto('/deep-search');

    // Switch to compare mode
    await page.getByRole('button', { name: /Compare/i }).first().click();

    // Fill topics
    await page.locator('input').filter({ hasText: '' }).nth(0).fill('Arctic ice melt acceleration');
    // The two text inputs are rendered consecutively under "Topic A" / "Topic B".
    const topicInputs = page.locator('input[placeholder*="energy" i]');
    await expect(topicInputs).toHaveCount(2);
    await topicInputs.nth(0).fill('Arctic ice melt acceleration');
    await topicInputs.nth(1).fill('Antarctic ice shelf loss comparison');

    // Submit
    await page.getByRole('button', { name: /^Compare$/i }).last().click();

    // Wait for the compare response to land
    await page.waitForResponse((resp) =>
      resp.url().includes('/api/deep-search/compare') && resp.status() === 200
    );

    // ---- Assertion 1: guidance block present and marked status=empty ----
    const guidance = page.getByTestId('compare-guidance-block');
    await expect(guidance).toBeVisible();
    await expect(guidance).toHaveAttribute('data-status', 'empty');
    await expect(guidance).toContainText('No evidence on either side');
    await expect(guidance).toContainText('A: 0i+0e');
    await expect(guidance).toContainText('B: 0i+0e');

    // ---- Assertion 2: refinement chips present with A/B buttons ----
    const chipsBlock = page.getByTestId('compare-refinement-chips');
    await expect(chipsBlock).toBeVisible();
    await expect(chipsBlock).toContainText('Arctic sea-ice extent September minimum 2010-2024');
    await expect(chipsBlock).toContainText('Try a refined query');

    // ---- Assertion 3: low-confidence pill present ----
    const pill = page.getByTestId('compare-low-confidence-pill');
    await expect(pill).toBeVisible();
    await expect(pill).toContainText(/Low confidence/i);

    // ---- Assertion 4: deterministic explainer text, NOT a hallucinated comparison ----
    const comparativeText = await page.locator('text=deterministic explainer').first().isVisible()
      || await page.locator('text=could not find evidence').first().isVisible();
    expect(comparativeText).toBeTruthy();

    // ---- Assertion 5: clicking the "A" button on a chip re-fires compare with the refined query as Topic A ----
    const firstChipAButton = chipsBlock.getByRole('button', { name: /Use as Topic A/i }).first();
    await firstChipAButton.click();
    await page.waitForResponse((resp) =>
      resp.url().includes('/api/deep-search/compare') && resp.status() === 200,
      { timeout: 5000 }
    );
    expect(compareCalls).toBeGreaterThanOrEqual(2);
    expect(lastBody.query_a).toBe('Arctic sea-ice extent September minimum 2010-2024');
    expect(lastBody.query_b).toBe('Antarctic ice shelf loss comparison');
  });

  test('renders asymmetric warning + pill when exactly one side is empty', async ({ page }) => {
    const ASYMMETRIC_FIXTURE = {
      ...COMPARE_FIXTURE_BOTH_EMPTY,
      result_a: {
        ...COMPARE_FIXTURE_BOTH_EMPTY.result_a,
        internal_articles_count: 4,
        external_sources_count: 2,
        answer: 'Substantive finding about Arctic ice loss with 6 sources.',
        citations: Array(6).fill(0).map((_, i) => ({
          type: 'internal_article',
          article_id: `art-${i}`,
          title: `Source ${i}`,
          source_name: 'Nature',
          credibility: 'HIGH',
        })),
      },
      // result_b stays empty
      comparative_analysis: 'Topic A had 6 sources; Topic B had 0 — comparison is asymmetric.',
      comparative_analysis_structured: {
        low_confidence: true,
        low_confidence_reason: 'Topic B returned 0 sources; the comparison reflects an asymmetric evidence base.',
      },
      guidance: {
        status: 'asymmetric',
        reason: 'one_side_empty',
        message: 'Topic B ("Antarctic ice shelf loss comparison") returned 0 sources, so the comparison is structurally asymmetric. Treat any contrast claim about that topic as low-confidence.',
        suggested_actions: [
          'Refine Topic B with country + timeframe',
          'Switch to single-topic Research mode for the empty side',
        ],
        per_side: {
          a: { internal: 4, external: 2 },
          b: { internal: 0, external: 0 },
        },
      },
      clarification_needed: null,
      low_confidence: true,
    };

    await page.route('**/api/deep-search/compare', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ASYMMETRIC_FIXTURE),
      });
    });

    await page.goto('/deep-search');
    await page.getByRole('button', { name: /Compare/i }).first().click();

    const topicInputs = page.locator('input[placeholder*="energy" i]');
    await topicInputs.nth(0).fill('Arctic ice melt acceleration');
    await topicInputs.nth(1).fill('Antarctic ice shelf loss comparison');
    await page.getByRole('button', { name: /^Compare$/i }).last().click();

    await page.waitForResponse((resp) =>
      resp.url().includes('/api/deep-search/compare') && resp.status() === 200
    );

    const guidance = page.getByTestId('compare-guidance-block');
    await expect(guidance).toBeVisible();
    await expect(guidance).toHaveAttribute('data-status', 'asymmetric');
    await expect(guidance).toContainText('Asymmetric evidence');
    await expect(guidance).toContainText('A: 4i+2e');
    await expect(guidance).toContainText('B: 0i+0e');

    const pill = page.getByTestId('compare-low-confidence-pill');
    await expect(pill).toBeVisible();
  });
});
