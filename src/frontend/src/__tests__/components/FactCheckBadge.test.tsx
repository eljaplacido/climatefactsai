import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import FactCheckBadge from '@/components/FactCheckBadge'
import type { FactCheck } from '@/types'

const makeFactCheck = (status: string, confidence: number): FactCheck => ({
  verification_status: status,
  confidence_score: confidence,
})

describe('FactCheckBadge', () => {
  it('renders Verified status', () => {
    render(<FactCheckBadge factCheck={makeFactCheck('VERIFIED', 0.95)} />)
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(screen.getByText('(95%)')).toBeInTheDocument()
  })

  it('renders Unverified status', () => {
    render(<FactCheckBadge factCheck={makeFactCheck('UNVERIFIED', 0.2)} />)
    expect(screen.getByText('Unverified')).toBeInTheDocument()
    expect(screen.getByText('(20%)')).toBeInTheDocument()
  })

  it('renders Disputed status', () => {
    render(<FactCheckBadge factCheck={makeFactCheck('DISPUTED', 0.55)} />)
    expect(screen.getByText('Disputed')).toBeInTheDocument()
  })

  it('renders Partially verified status', () => {
    render(<FactCheckBadge factCheck={makeFactCheck('PARTIALLY_VERIFIED', 0.7)} />)
    expect(screen.getByText('Partially verified')).toBeInTheDocument()
  })

  it('renders unknown status for unexpected values', () => {
    render(<FactCheckBadge factCheck={makeFactCheck('SOMETHING_ELSE', 0.5)} />)
    expect(screen.getByText('Status unknown')).toBeInTheDocument()
  })

  it('rounds confidence percentage', () => {
    render(<FactCheckBadge factCheck={makeFactCheck('VERIFIED', 0.876)} />)
    expect(screen.getByText('(88%)')).toBeInTheDocument()
  })
})
