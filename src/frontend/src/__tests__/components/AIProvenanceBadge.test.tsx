import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import AIProvenanceBadge, {
  AIProvenanceJsonLd,
  buildAiJsonLd,
  type AIProvenancePayload,
} from '@/components/AIProvenanceBadge'

const FULL_PAYLOAD: AIProvenancePayload = {
  model: 'claude-sonnet-4-6',
  prompt_name: 'deep_search_synthesis',
  prompt_version: 'v1.0',
  prompt_fingerprint: 'abc123def456',
  retrieval_strategy: 'internal_corpus(fts+semantic) + perplexity_external',
  timestamp: '2026-05-23T10:00:00Z',
  methodology_version: '2026.05',
  surface: 'deep_search',
  surface_url: 'https://climatefacts.ai/deep-search?q=arctic+ice',
  content_summary: 'Synthesis for Arctic ice query',
}

describe('AIProvenanceBadge — Day 3-A EU AI Act Art. 50 disclosure', () => {
  describe('buildAiJsonLd', () => {
    it('emits a schema.org CreativeWork with AI authorship', () => {
      const ld = buildAiJsonLd(FULL_PAYLOAD)
      expect(ld['@context']).toBe('https://schema.org')
      expect(ld['@type']).toBe('CreativeWork')
      // AI authorship is what the AI Act requires
      expect(ld.creator).toBeDefined()
      expect(ld.creator['@type']).toBe('SoftwareApplication')
      expect(ld.creator.applicationCategory).toBe('AIApplication')
      // additionalType varies by surface so downstream crawlers can route
      expect(ld.creator.additionalType).toBe('ResearchAnalysis')
    })

    it('uses ScholarlyAnalysis for research_analysis surface', () => {
      const ld = buildAiJsonLd({ ...FULL_PAYLOAD, surface: 'research_analysis' })
      expect(ld.creator.additionalType).toBe('ScholarlyAnalysis')
    })

    it('uses ComparativeAnalysis for deep_search_compare surface', () => {
      const ld = buildAiJsonLd({ ...FULL_PAYLOAD, surface: 'deep_search_compare' })
      expect(ld.creator.additionalType).toBe('ComparativeAnalysis')
    })

    it('embeds the prompt SHA-256 fingerprint as a PropertyValue identifier', () => {
      const ld = buildAiJsonLd(FULL_PAYLOAD)
      expect(ld.creator.identifier).toBeDefined()
      expect(ld.creator.identifier['@type']).toBe('PropertyValue')
      expect(ld.creator.identifier.propertyID).toBe('prompt_sha256')
      expect(ld.creator.identifier.value).toBe('abc123def456')
    })

    it('omits the fingerprint identifier when prompt_fingerprint is missing', () => {
      const ld = buildAiJsonLd({ ...FULL_PAYLOAD, prompt_fingerprint: undefined })
      expect(ld.creator.identifier).toBeUndefined()
    })

    it('strips undefined fields so the rendered JSON is clean', () => {
      const minimal: AIProvenancePayload = {
        model: 'deepseek-chat',
        timestamp: '2026-05-23T10:00:00Z',
      }
      const ld = buildAiJsonLd(minimal)
      // None of these optional fields should appear
      expect(ld.url).toBeUndefined()
      expect(ld.description).toBeUndefined()
      expect(ld['https://climatefacts.ai/schema/v1#retrieval_strategy']).toBeUndefined()
      expect(ld['https://climatefacts.ai/schema/v1#methodology_version']).toBeUndefined()
      // Required fields still present
      expect(ld['@type']).toBe('CreativeWork')
      expect(ld.creator.name).toBe('deepseek-chat')
    })

    it('preserves the platform-namespaced extension fields when present', () => {
      const ld = buildAiJsonLd(FULL_PAYLOAD)
      expect(ld['https://climatefacts.ai/schema/v1#retrieval_strategy']).toBe(
        'internal_corpus(fts+semantic) + perplexity_external',
      )
      expect(ld['https://climatefacts.ai/schema/v1#methodology_version']).toBe('2026.05')
      expect(ld['https://climatefacts.ai/schema/v1#surface']).toBe('deep_search')
    })

    it('strips the date suffix from dated model names for display', () => {
      const ld = buildAiJsonLd({
        ...FULL_PAYLOAD,
        model: 'claude-sonnet-2026-05-15',
      })
      expect(ld.creator.name).toBe('claude-sonnet')
    })
  })

  describe('AIProvenanceJsonLd', () => {
    it('renders a script tag with type=application/ld+json containing the payload', () => {
      const { container } = render(<AIProvenanceJsonLd provenance={FULL_PAYLOAD} />)
      const script = container.querySelector('script[type="application/ld+json"]')
      expect(script).not.toBeNull()
      expect(script).toHaveAttribute('data-testid', 'ai-provenance-jsonld')

      const parsed = JSON.parse(script!.textContent || '{}')
      expect(parsed['@type']).toBe('CreativeWork')
      expect(parsed.creator['@type']).toBe('SoftwareApplication')
      expect(parsed.datePublished).toBe('2026-05-23T10:00:00Z')
    })

    it('produces valid JSON (no syntax errors)', () => {
      const { container } = render(<AIProvenanceJsonLd provenance={FULL_PAYLOAD} />)
      const script = container.querySelector('script[type="application/ld+json"]')
      expect(() => JSON.parse(script!.textContent || '')).not.toThrow()
    })
  })

  describe('AIProvenanceBadge component', () => {
    it('renders the visible badge with data-ai-generated=true (AI Act discoverability)', () => {
      render(<AIProvenanceBadge provenance={FULL_PAYLOAD} />)
      const badge = screen.getByTestId('ai-provenance-badge')
      expect(badge).toBeInTheDocument()
      expect(badge).toHaveAttribute('data-ai-generated', 'true')
      // role="note" for assistive tech
      expect(badge).toHaveAttribute('role', 'note')
      // aria-label MUST mention AI + the model name
      const label = badge.getAttribute('aria-label')
      expect(label).toMatch(/AI-generated/i)
      expect(label).toMatch(/claude/i)
    })

    it('emits the JSON-LD script alongside the badge by default', () => {
      const { container } = render(<AIProvenanceBadge provenance={FULL_PAYLOAD} />)
      expect(container.querySelector('script[type="application/ld+json"]')).not.toBeNull()
    })

    it('skips the JSON-LD script when emitJsonLd=false', () => {
      const { container } = render(
        <AIProvenanceBadge provenance={FULL_PAYLOAD} emitJsonLd={false} />,
      )
      expect(container.querySelector('script[type="application/ld+json"]')).toBeNull()
      // Badge still renders
      expect(screen.getByTestId('ai-provenance-badge')).toBeInTheDocument()
    })

    it('renders block variant with prompt, retrieval, timestamp, and methodology link', () => {
      render(<AIProvenanceBadge provenance={FULL_PAYLOAD} variant="block" />)
      const badge = screen.getByTestId('ai-provenance-badge')
      expect(badge).toHaveTextContent('deep_search_synthesis')
      expect(badge).toHaveTextContent('internal_corpus')
      const link = screen.getByRole('link', { name: /Reproduce via methodology/i })
      expect(link).toHaveAttribute('href', '/methodology')
    })

    it('shows the short model name on the badge (strips dated suffix)', () => {
      render(
        <AIProvenanceBadge
          provenance={{ ...FULL_PAYLOAD, model: 'claude-sonnet-2026-05-15' }}
        />,
      )
      const badge = screen.getByTestId('ai-provenance-badge')
      expect(badge).toHaveTextContent(/claude-sonnet/)
      expect(badge).not.toHaveTextContent('2026-05-15')
    })
  })
})
