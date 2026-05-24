import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SentenceGroundedAnswer from '@/components/SentenceGroundedAnswer'
import type { SentenceGrounding } from '@/types'

const FIXTURE: SentenceGrounding[] = [
  { text: 'Arctic sea-ice extent has declined since 1979.', level: 'HIGH', reason: 'NSIDC time series' },
  { text: 'Antarctic ice shelves show variable mass balance.', level: 'MEDIUM' },
  { text: 'This trend may accelerate by 2050.', level: 'LOW', reason: 'projection' },
  { text: 'The future is hard to predict precisely.', level: 'NONE' },
]

describe('SentenceGroundedAnswer — Day 3-B per-sentence grounding', () => {
  it('renders every sentence with a calibration pill', () => {
    render(<SentenceGroundedAnswer sentences={FIXTURE} />)
    // Each sentence renders
    expect(screen.getByText(/Arctic sea-ice extent/)).toBeInTheDocument()
    expect(screen.getByText(/Antarctic ice shelves/)).toBeInTheDocument()
    expect(screen.getByText(/This trend may accelerate/)).toBeInTheDocument()
    expect(screen.getByText(/The future is hard to predict/)).toBeInTheDocument()

    // Each level pill renders with its testid
    expect(screen.getByTestId('sentence-pill-HIGH')).toBeInTheDocument()
    expect(screen.getByTestId('sentence-pill-MEDIUM')).toBeInTheDocument()
    expect(screen.getByTestId('sentence-pill-LOW')).toBeInTheDocument()
    expect(screen.getByTestId('sentence-pill-NONE')).toBeInTheDocument()
  })

  it('uses readable labels (not the raw level codes) on pills', () => {
    render(<SentenceGroundedAnswer sentences={FIXTURE} />)
    expect(screen.getByTestId('sentence-pill-HIGH')).toHaveTextContent('Grounded')
    expect(screen.getByTestId('sentence-pill-MEDIUM')).toHaveTextContent('Consensus')
    expect(screen.getByTestId('sentence-pill-LOW')).toHaveTextContent('Inference')
    expect(screen.getByTestId('sentence-pill-NONE')).toHaveTextContent('Speculation')
  })

  it('renders the confidence banner when confidence envelope is provided', () => {
    render(
      <SentenceGroundedAnswer
        sentences={FIXTURE}
        confidence={{ confidence: 'low', reason: 'no_internal_sources' }}
      />,
    )
    const banner = screen.getByTestId('sentence-grounded-confidence-banner')
    expect(banner).toBeInTheDocument()
    expect(banner).toHaveTextContent(/low/i)
    expect(banner).toHaveTextContent('no_internal_sources')
  })

  it('omits the confidence banner when no envelope provided', () => {
    render(<SentenceGroundedAnswer sentences={FIXTURE} />)
    expect(screen.queryByTestId('sentence-grounded-confidence-banner')).not.toBeInTheDocument()
  })

  it('renders the grounding distribution summary', () => {
    render(<SentenceGroundedAnswer sentences={FIXTURE} />)
    const summary = screen.getByTestId('sentence-grounded-summary')
    expect(summary).toBeInTheDocument()
    // Shows count distribution across all 4 levels
    expect(summary).toHaveTextContent('Grounded: 1/4')
    expect(summary).toHaveTextContent('Consensus: 1/4')
    expect(summary).toHaveTextContent('Inference: 1/4')
    expect(summary).toHaveTextContent('Speculation: 1/4')
  })

  it('drops malformed sentences without crashing', () => {
    const malformed: any[] = [
      { text: 'good one', level: 'HIGH' },
      { text: '', level: 'HIGH' },          // empty text — should be dropped
      { text: null, level: 'HIGH' },        // null text — should be dropped
      { text: 'another good one', level: 'LOW' },
    ]
    render(<SentenceGroundedAnswer sentences={malformed} />)
    expect(screen.getByText('good one')).toBeInTheDocument()
    expect(screen.getByText('another good one')).toBeInTheDocument()
    // Only the two valid sentences should have pills
    expect(screen.getAllByTestId(/^sentence-pill-/)).toHaveLength(2)
  })

  it('hides distribution levels that have zero sentences', () => {
    render(
      <SentenceGroundedAnswer
        sentences={[
          { text: 'all high a', level: 'HIGH' },
          { text: 'all high b', level: 'HIGH' },
        ]}
      />,
    )
    const summary = screen.getByTestId('sentence-grounded-summary')
    expect(summary).toHaveTextContent('Grounded: 2/2')
    // MEDIUM/LOW/NONE should not appear
    expect(summary).not.toHaveTextContent('Consensus:')
    expect(summary).not.toHaveTextContent('Inference:')
    expect(summary).not.toHaveTextContent('Speculation:')
  })

  it('exposes pill tooltip via title attribute that explains the level', () => {
    render(<SentenceGroundedAnswer sentences={FIXTURE} />)
    const highPill = screen.getByTestId('sentence-pill-HIGH')
    const title = highPill.getAttribute('title')
    expect(title).toMatch(/Grounded/)
    expect(title).toMatch(/NSIDC time series/) // the reason from fixture
  })
})
