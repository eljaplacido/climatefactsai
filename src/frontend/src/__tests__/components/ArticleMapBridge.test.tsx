import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ArticleMapBridge from '@/components/ArticleMapBridge'

vi.mock('next/link', () => ({
  default: ({ children, href, ...rest }: any) =>
    React.createElement('a', { href, ...rest }, children),
}))

describe('ArticleMapBridge — Phase 4A §3.6', () => {
  it('renders nothing when article has no country AND no tags', () => {
    const { container } = render(
      <ArticleMapBridge articleId="a-1" articleTitle="x" />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the bridge when only country is present', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="German renewables hit milestone"
        countryCode="DE"
        countryName="Germany"
      />,
    )
    expect(screen.getByTestId('article-map-bridge')).toBeInTheDocument()
    expect(screen.getByText('This story on the world')).toBeInTheDocument()
  })

  it('renders all three CTAs when country is provided', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="German renewables"
        countryCode="DE"
        countryName="Germany"
      />,
    )
    expect(screen.getByTestId('article-map-bridge-map-link')).toBeInTheDocument()
    expect(screen.getByTestId('article-map-bridge-passport-link')).toBeInTheDocument()
    expect(screen.getByTestId('article-map-bridge-deep-search-link')).toBeInTheDocument()
  })

  it('country-deeplinks include fromArticle for analytics', () => {
    render(
      <ArticleMapBridge
        articleId="a-42"
        articleTitle="t"
        countryCode="DE"
        countryName="Germany"
      />,
    )
    expect(screen.getByTestId('article-map-bridge-map-link')).toHaveAttribute(
      'href',
      '/map?country=DE&fromArticle=a-42',
    )
    expect(screen.getByTestId('article-map-bridge-passport-link')).toHaveAttribute(
      'href',
      '/country/DE?fromArticle=a-42',
    )
  })

  it('country code is uppercased in the deeplink', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        countryCode="de"
        countryName="Germany"
      />,
    )
    expect(screen.getByTestId('article-map-bridge-map-link')).toHaveAttribute(
      'href',
      expect.stringContaining('country=DE'),
    )
  })

  it('deep-search link is pre-seeded with the article title + country', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="Arctic ice melt acceleration"
        countryCode="DE"
        countryName="Germany"
      />,
    )
    const link = screen.getByTestId('article-map-bridge-deep-search-link')
    const href = link.getAttribute('href')!
    expect(href).toContain('/deep-search?q=Arctic')
    expect(href).toContain('country=DE')
    expect(href).toContain('fromArticle=a-1')
  })

  it('deep-search link works without country', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="Global heat"
        tags={['heat']}
      />,
    )
    const link = screen.getByTestId('article-map-bridge-deep-search-link')
    const href = link.getAttribute('href')!
    expect(href).toContain('/deep-search?q=Global')
    expect(href).not.toContain('country=')
  })

  it('truncates article title in deep-search query at 120 chars', () => {
    const longTitle = 'A'.repeat(200)
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle={longTitle}
        tags={['x']}
      />,
    )
    const href = screen.getByTestId('article-map-bridge-deep-search-link').getAttribute('href')!
    // encoded "A" is "A" itself — 120 of them
    expect(href).toContain('q=' + 'A'.repeat(120))
    expect(href).not.toContain('A'.repeat(121))
  })

  it('renders topic chips when tags are provided (capped at 5)', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        countryCode="DE"
        tags={['heatwave', 'drought', 'wildfire', 'flood', 'storm', 'cyclone', 'extra']}
      />,
    )
    const chips = screen.getAllByTestId('article-map-bridge-topic-chip')
    expect(chips).toHaveLength(5)
    expect(screen.getByText('heatwave')).toBeInTheDocument()
    expect(screen.queryByText('extra')).not.toBeInTheDocument()
  })

  it('topic chips link to /search with the tag + country', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        countryCode="DE"
        tags={['heatwave']}
      />,
    )
    const chip = screen.getByTestId('article-map-bridge-topic-chip')
    expect(chip).toHaveAttribute('href', '/search?q=heatwave&country=DE')
  })

  it('topic chips work without country', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        tags={['heatwave']}
      />,
    )
    const chip = screen.getByTestId('article-map-bridge-topic-chip')
    expect(chip).toHaveAttribute('href', '/search?q=heatwave')
  })

  it('passport + map links are omitted when only tags present', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        tags={['heatwave']}
      />,
    )
    expect(screen.getByTestId('article-map-bridge')).toBeInTheDocument()
    expect(screen.queryByTestId('article-map-bridge-map-link')).not.toBeInTheDocument()
    expect(screen.queryByTestId('article-map-bridge-passport-link')).not.toBeInTheDocument()
    // Deep-search link still renders
    expect(screen.getByTestId('article-map-bridge-deep-search-link')).toBeInTheDocument()
  })

  it('falls back to country code when countryName is missing', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        countryCode="DE"
      />,
    )
    // Map-link copy says "Open DE on the map" (not "Open Germany")
    expect(screen.getByTestId('article-map-bridge-map-link')).toHaveTextContent(/Open DE/)
  })

  it('exposes a labelled landmark for screen readers', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        countryCode="DE"
      />,
    )
    const section = screen.getByRole('region', { name: /This story on the world/i })
    expect(section).toBeInTheDocument()
  })

  it('rejects non-ISO2 country codes (treats as no-country)', () => {
    render(
      <ArticleMapBridge
        articleId="a-1"
        articleTitle="t"
        countryCode="DEU"
        tags={['x']}
      />,
    )
    // Non-2-char code → falls back to tags-only mode
    expect(screen.queryByTestId('article-map-bridge-map-link')).not.toBeInTheDocument()
    expect(screen.queryByTestId('article-map-bridge-passport-link')).not.toBeInTheDocument()
  })
})
