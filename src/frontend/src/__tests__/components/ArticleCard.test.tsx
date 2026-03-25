import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ArticleCard from '@/components/ArticleCard'
import type { Article } from '@/types'

const mockArticle: Article = {
  article_id: 'test-123',
  title: 'Climate Change Impact on Nordic Countries',
  url: 'https://reuters.com/article/123',
  source_name: 'Reuters',
  source_credibility_score: 85,
  published_date: '2026-03-01T12:00:00Z',
  overall_credibility: 'HIGH',
  reliability_score: 85,
  tags: ['climate', 'nordic'],
  excerpt: 'A detailed analysis of climate impacts in the Nordic region.',
  claim_count: 3,
  verified_claim_count: 2,
  created_at: '2026-03-01T12:00:00Z',
}

describe('ArticleCard', () => {
  it('renders article title', () => {
    render(<ArticleCard article={mockArticle} />)
    expect(screen.getByText(mockArticle.title)).toBeInTheDocument()
  })

  it('renders source name', () => {
    render(<ArticleCard article={mockArticle} />)
    expect(screen.getByText(/Reuters/)).toBeInTheDocument()
  })

  it('renders credibility score', () => {
    render(<ArticleCard article={mockArticle} />)
    // CredibilityGauge renders the numeric score
    expect(screen.getByText('85')).toBeInTheDocument()
  })

  it('links to article detail page', () => {
    render(<ArticleCard article={mockArticle} />)
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', `/articles/${mockArticle.article_id}`)
  })
})
