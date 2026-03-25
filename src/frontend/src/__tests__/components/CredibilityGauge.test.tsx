import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CredibilityGauge from '@/components/CredibilityGauge'

describe('CredibilityGauge', () => {
  it('renders the numeric score', () => {
    render(<CredibilityGauge score={85} level="HIGH" />)
    expect(screen.getByText('85')).toBeInTheDocument()
  })

  it('renders level label for medium size', () => {
    render(<CredibilityGauge score={60} level="MEDIUM" size="md" />)
    expect(screen.getByText('Moderate')).toBeInTheDocument()
  })

  it('renders level label for HIGH', () => {
    render(<CredibilityGauge score={90} level="HIGH" size="lg" />)
    expect(screen.getByText('High')).toBeInTheDocument()
  })

  it('renders level label for LOW', () => {
    render(<CredibilityGauge score={30} level="LOW" size="md" />)
    expect(screen.getByText('Low')).toBeInTheDocument()
  })

  it('does not render level label at small size', () => {
    render(<CredibilityGauge score={75} level="HIGH" size="sm" />)
    expect(screen.getByText('75')).toBeInTheDocument()
    expect(screen.queryByText('High')).not.toBeInTheDocument()
  })

  it('clamps score to 0-100 range', () => {
    render(<CredibilityGauge score={150} level="HIGH" size="md" />)
    expect(screen.getByText('100')).toBeInTheDocument()
  })

  it('renders SVG circle elements', () => {
    const { container } = render(<CredibilityGauge score={50} level="MEDIUM" />)
    const circles = container.querySelectorAll('circle')
    expect(circles.length).toBe(2) // background + score arc
  })
})
