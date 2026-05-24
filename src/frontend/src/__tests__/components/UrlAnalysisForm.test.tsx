import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UrlAnalysisForm from '@/components/UrlAnalysisForm'

// Mock the api module: we want full control over what analyzeUrl /
// getAnalysisStatus return so we can pin the structured-failure render
// branches added in the §3.4 fix on 2026-05-23.
const mockAnalyzeUrl = vi.fn()
const mockGetAnalysisStatus = vi.fn()

vi.mock('@/lib/api', () => ({
  api: {
    analyzeUrl: (...args: any[]) => mockAnalyzeUrl(...args),
    getAnalysisStatus: (...args: any[]) => mockGetAnalysisStatus(...args),
  },
}))

// Minimal stub for the view-context provider hook. Real implementation
// lives in @/lib/view-context but the component only uses setView/clearKey
// for side-effects; no need to test that here.
vi.mock('@/lib/view-context', () => ({
  useViewContext: () => ({
    setView: vi.fn(),
    clearKey: vi.fn(),
  }),
}))

// CredibilityGauge has its own test suite — stub to keep this test fast.
vi.mock('@/components/CredibilityGauge', () => ({
  default: () => <div data-testid="credibility-gauge-stub" />,
}))
vi.mock('@/components/Markdown', () => ({
  default: ({ content }: { content: string }) => <div>{content}</div>,
}))

const VALID_URL = 'https://example.com/some-climate-article'

async function submitAndWaitForFailureBlock(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/article url/i), VALID_URL)
  await user.click(screen.getByRole('button', { name: /^Analyze$/i }))
  // Polling kicks in 3s after the submit; the GET mock resolves
  // synchronously so waitFor with a generous budget is plenty.
  await waitFor(
    () => {
      expect(screen.getByTestId('url-analysis-failure')).toBeInTheDocument()
    },
    { timeout: 8000 },
  )
}

describe('UrlAnalysisForm — structured failure surface (§3.4 fix)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Default: POST returns processing + access token; tests override the
    // GET response per scenario.
    mockAnalyzeUrl.mockResolvedValue({
      job_id: 'job-123',
      status: 'processing',
      access_token: 'tok-abc',
      estimated_time: 5,
    })
  })

  it('renders the structured failure block for paywall_suspected', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'Paywall message',
      failure_reason: 'paywall_suspected',
      failure_detail: {
        reason: 'paywall_suspected',
        title: 'Paywall detected',
        message:
          'The page loaded but only returned a short stub with subscription / premium-content keywords.',
        remediation: 'Paste the text into /research.',
      },
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    expect(screen.getByTestId('url-analysis-failure-title')).toHaveTextContent(
      'Paywall detected',
    )
    expect(screen.getByTestId('url-analysis-failure-reason')).toHaveTextContent(
      'paywall_suspected',
    )
    expect(screen.getByText(/subscription/i)).toBeInTheDocument()
    expect(screen.getByText(/Paste the text into \/research\./i)).toBeInTheDocument()

    // Paywall is on the deeplink whitelist — link should be visible
    const deeplink = screen.getByTestId('url-analysis-failure-paste-deeplink')
    expect(deeplink).toBeInTheDocument()
    expect(deeplink).toHaveAttribute('href', '/research')
  })

  it('renders the structured failure block for js_rendered_spa with the /research deeplink', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'JS-rendered',
      failure_reason: 'js_rendered_spa',
      failure_detail: {
        reason: 'js_rendered_spa',
        title: 'JavaScript-rendered page',
        message: 'The site renders its article body via JavaScript.',
        remediation: 'Paste the article text into /research.',
      },
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    expect(screen.getByTestId('url-analysis-failure-title')).toHaveTextContent(
      'JavaScript-rendered page',
    )
    expect(screen.getByTestId('url-analysis-failure-paste-deeplink')).toBeInTheDocument()
  })

  it('hides the /research deeplink for http_forbidden (not in whitelist)', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'Forbidden',
      failure_reason: 'http_forbidden',
      failure_detail: {
        reason: 'http_forbidden',
        title: 'Source blocked our reader',
        message: 'HTTP 403 — automated access blocked.',
        remediation: 'Use browser + copy text.',
        status_code: 403,
      },
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    expect(screen.getByTestId('url-analysis-failure-title')).toHaveTextContent(
      'Source blocked our reader',
    )
    // HTTP status chip is rendered when present. The literal text "HTTP 403"
    // appears in both the status-code chip and the inline message, so
    // assert ≥1 match rather than exactly-one.
    expect(screen.getAllByText(/HTTP 403/).length).toBeGreaterThanOrEqual(1)
    // No deeplink for http_forbidden
    expect(
      screen.queryByTestId('url-analysis-failure-paste-deeplink'),
    ).not.toBeInTheDocument()
  })

  it('hides the /research deeplink for timeout (not in whitelist)', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'Timeout',
      failure_reason: 'timeout',
      failure_detail: {
        reason: 'timeout',
        title: 'Source took too long to respond',
        message: 'Waited 45 seconds.',
        remediation: 'Retry the URL.',
      },
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    expect(
      screen.queryByTestId('url-analysis-failure-paste-deeplink'),
    ).not.toBeInTheDocument()
  })

  it('renders the legacy fallback block when only `error` is present (no failure_detail)', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'Legacy error from an old backend',
      // No failure_reason / failure_detail — simulates pre-migration-031 backend
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    // The legacy block renders the literal "Analysis Failed" heading
    expect(screen.getByText('Analysis Failed')).toBeInTheDocument()
    expect(screen.getByText('Legacy error from an old backend')).toBeInTheDocument()

    // None of the structured-only elements appear
    expect(screen.queryByTestId('url-analysis-failure-title')).not.toBeInTheDocument()
    expect(screen.queryByTestId('url-analysis-failure-reason')).not.toBeInTheDocument()
  })

  it('shows extraction_too_short with the paste deeplink (it IS in the whitelist)', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'extraction failed',
      failure_reason: 'extraction_too_short',
      failure_detail: {
        reason: 'extraction_too_short',
        title: "Couldn't find article body",
        message: 'Less than 50 characters extracted.',
        remediation: 'Use /research → Paste text mode.',
      },
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    expect(screen.getByTestId('url-analysis-failure-paste-deeplink')).toBeInTheDocument()
  })

  it('reset clears failure state when Try-a-different-URL is clicked', async () => {
    mockGetAnalysisStatus.mockResolvedValue({
      job_id: 'job-123',
      status: 'failed',
      error: 'oops',
      failure_reason: 'http_5xx',
      failure_detail: {
        reason: 'http_5xx',
        title: 'Source server failed',
        message: '5xx error.',
        remediation: 'Retry.',
      },
    })

    const user = userEvent.setup()
    render(<UrlAnalysisForm />)
    await submitAndWaitForFailureBlock(user)

    expect(screen.getByTestId('url-analysis-failure')).toBeInTheDocument()

    const resetButton = screen.getByRole('button', { name: /Try a different URL/i })
    await user.click(resetButton)

    expect(screen.queryByTestId('url-analysis-failure')).not.toBeInTheDocument()
    // URL input cleared
    expect((screen.getByLabelText(/article url/i) as HTMLInputElement).value).toBe('')
  })
})
