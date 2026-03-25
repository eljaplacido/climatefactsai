import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import LoadingSpinner from '@/components/LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders without text', () => {
    const { container } = render(<LoadingSpinner />)
    expect(container.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders with text', () => {
    render(<LoadingSpinner text="Loading articles..." />)
    expect(screen.getByText('Loading articles...')).toBeInTheDocument()
  })

  it('does not render text paragraph when text is undefined', () => {
    const { container } = render(<LoadingSpinner />)
    expect(container.querySelector('p')).not.toBeInTheDocument()
  })
})
