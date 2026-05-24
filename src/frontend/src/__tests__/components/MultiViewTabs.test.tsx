import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import MultiViewTabs from '@/components/MultiViewTabs'

describe('MultiViewTabs — Phase 2G MH2', () => {
  it('defaults to chart view and renders only the chart slot', () => {
    render(
      <MultiViewTabs
        chart={<div data-testid="chart-content">CHART_OK</div>}
        table={<div data-testid="table-content">TABLE_OK</div>}
      />,
    )
    expect(screen.getByTestId('multiview-panel-chart')).toBeInTheDocument()
    expect(screen.getByTestId('chart-content')).toBeInTheDocument()
    // Other view's content is not in the DOM
    expect(screen.queryByTestId('table-content')).not.toBeInTheDocument()
  })

  it('switching to table renders the table slot and unmounts the chart', async () => {
    const user = userEvent.setup()
    render(
      <MultiViewTabs
        chart={<div data-testid="chart-content">CHART_OK</div>}
        table={<div data-testid="table-content">TABLE_OK</div>}
      />,
    )
    await user.click(screen.getByTestId('multiview-tab-table'))
    expect(screen.getByTestId('multiview-panel-table')).toBeInTheDocument()
    expect(screen.getByTestId('table-content')).toBeInTheDocument()
    expect(screen.queryByTestId('chart-content')).not.toBeInTheDocument()
  })

  it('omits tabs for views that were not provided', () => {
    render(<MultiViewTabs chart={<div>just-chart</div>} />)
    expect(screen.getByTestId('multiview-tab-chart')).toBeInTheDocument()
    expect(screen.queryByTestId('multiview-tab-map')).not.toBeInTheDocument()
    expect(screen.queryByTestId('multiview-tab-table')).not.toBeInTheDocument()
  })

  it('renders all three when chart + map + table provided', () => {
    render(
      <MultiViewTabs
        chart={<div>c</div>}
        map={<div>m</div>}
        table={<div>t</div>}
      />,
    )
    expect(screen.getByTestId('multiview-tab-chart')).toBeInTheDocument()
    expect(screen.getByTestId('multiview-tab-map')).toBeInTheDocument()
    expect(screen.getByTestId('multiview-tab-table')).toBeInTheDocument()
  })

  it('uses role=tablist + role=tab + aria-selected for a11y', () => {
    render(
      <MultiViewTabs
        chart={<div>c</div>}
        table={<div>t</div>}
      />,
    )
    expect(screen.getByRole('tablist')).toHaveAttribute('aria-label', 'Data view')
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(2)
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(tabs[1]).toHaveAttribute('aria-selected', 'false')
  })

  it('honors defaultView when the requested view is available', () => {
    render(
      <MultiViewTabs
        chart={<div data-testid="chart-content">c</div>}
        table={<div data-testid="table-content">t</div>}
        defaultView="table"
      />,
    )
    expect(screen.getByTestId('multiview-panel-table')).toBeInTheDocument()
    expect(screen.getByTestId('table-content')).toBeInTheDocument()
  })

  it('falls back to chart when defaultView refers to a non-provided view', () => {
    render(
      <MultiViewTabs
        chart={<div data-testid="chart-content">c</div>}
        // no map / no table
        defaultView="map"
      />,
    )
    expect(screen.getByTestId('multiview-panel-chart')).toBeInTheDocument()
    expect(screen.getByTestId('chart-content')).toBeInTheDocument()
  })

  it('custom ariaLabel propagates to the tablist', () => {
    render(
      <MultiViewTabs
        chart={<div>c</div>}
        table={<div>t</div>}
        ariaLabel="Climate data view"
      />,
    )
    expect(screen.getByRole('tablist')).toHaveAttribute(
      'aria-label',
      'Climate data view',
    )
  })

  it('aria-controls on tab matches id on panel (a11y wiring)', async () => {
    const user = userEvent.setup()
    render(
      <MultiViewTabs
        chart={<div>c</div>}
        table={<div>t</div>}
      />,
    )
    const tableTab = screen.getByTestId('multiview-tab-table')
    expect(tableTab).toHaveAttribute('aria-controls', 'multiview-panel-table')
    await user.click(tableTab)
    expect(screen.getByTestId('multiview-panel-table')).toHaveAttribute(
      'id',
      'multiview-panel-table',
    )
  })
})
