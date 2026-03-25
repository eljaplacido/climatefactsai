import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatCard from '@/components/StatCard'
import { FileText } from 'lucide-react'

describe('StatCard', () => {
  it('renders title and numeric value', () => {
    render(<StatCard title="Total Articles" value={42} icon={FileText} />)
    expect(screen.getByText('Total Articles')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatCard title="Status" value="Active" icon={FileText} />)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('applies color class', () => {
    const { container } = render(
      <StatCard title="Claims" value={10} icon={FileText} color="green" />
    )
    const iconWrapper = container.querySelector('.bg-emerald-50')
    expect(iconWrapper).toBeInTheDocument()
  })

  it('defaults to blue color', () => {
    const { container } = render(
      <StatCard title="Count" value={5} icon={FileText} />
    )
    const iconWrapper = container.querySelector('.bg-blue-50')
    expect(iconWrapper).toBeInTheDocument()
  })
})
