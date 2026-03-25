'use client'

import Link from 'next/link'
import { CheckCircle, AlertTriangle, XCircle, HelpCircle } from 'lucide-react'

export default function MethodologyPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <Link href="/" className="text-2xl font-bold text-clilens-primary">
            CliLens
          </Link>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-gray-900 mb-4">
              Our Methodology
            </h1>
            <p className="text-xl text-gray-600">
              How we fact-check climate news with transparency and scientific rigor
            </p>
          </div>

          {/* Overview */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Overview</h2>
            <p className="text-gray-700 leading-relaxed">
              CliLens uses a combination of <strong>AI-powered analysis</strong> and <strong>scientific databases</strong> to
              verify climate news. Every step is transparent, and you can always see our sources and confidence levels.
            </p>
          </section>

          {/* The Process */}
          <section className="space-y-6">
            <h2 className="text-2xl font-bold text-gray-900">The Verification Process</h2>

            {/* Step 1 */}
            <div className="border-l-4 border-clilens-primary pl-6 py-2">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                1. Article Ingestion &amp; Extraction
              </h3>
              <p className="text-gray-700 mb-3">
                When an article is submitted (by curators or users), we:
              </p>
              <ul className="list-disc list-inside space-y-1 text-gray-600 ml-4">
                <li>Scrape the full article content</li>
                <li>Extract title, author, publication date, source</li>
                <li>Identify the article geographic focus (if applicable)</li>
                <li>Store metadata for transparency</li>
              </ul>
            </div>

            {/* Step 2 */}
            <div className="border-l-4 border-blue-500 pl-6 py-2">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                2. AI-Powered Claim Extraction
              </h3>
              <p className="text-gray-700 mb-3">
                Using <strong>large language models</strong>, we identify specific, verifiable claims:
              </p>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-3">
                <p className="text-sm text-blue-900 font-medium mb-2">What Makes a Good Claim?</p>
                <ul className="list-disc list-inside space-y-1 text-sm text-blue-800 ml-2">
                  <li><strong>Specific</strong>: &quot;Arctic sea ice declined 13% per decade since 1979&quot;</li>
                  <li><strong>Verifiable</strong>: Can be checked against data</li>
                  <li><strong>Factual</strong>: Not opinions or predictions (unless explicitly stated)</li>
                  <li><strong>Self-contained</strong>: Understandable without full article context</li>
                </ul>
              </div>
            </div>

            {/* Step 3 */}
            <div className="border-l-4 border-purple-500 pl-6 py-2">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                3. Evidence Retrieval
              </h3>
              <p className="text-gray-700 mb-3">
                For each claim, we search trusted scientific sources:
              </p>
              <div className="grid md:grid-cols-2 gap-3 mb-3">
                <div className="bg-purple-50 border border-purple-200 rounded p-3">
                  <h4 className="font-semibold text-purple-900 text-sm mb-1">Primary Sources</h4>
                  <ul className="text-xs text-purple-800 space-y-1">
                    <li>NASA Climate Data</li>
                    <li>NOAA (National Oceanic &amp; Atmospheric Admin)</li>
                    <li>IPCC Reports</li>
                    <li>Peer-reviewed journals (Nature, Science)</li>
                  </ul>
                </div>
                <div className="bg-purple-50 border border-purple-200 rounded p-3">
                  <h4 className="font-semibold text-purple-900 text-sm mb-1">Secondary Sources</h4>
                  <ul className="text-xs text-purple-800 space-y-1">
                    <li>Google Fact Check API</li>
                    <li>Climate Feedback</li>
                    <li>FactCheck.org</li>
                    <li>Scientific American</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Step 4 */}
            <div className="border-l-4 border-green-500 pl-6 py-2">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                4. Verdict Adjudication
              </h3>
              <p className="text-gray-700 mb-3">
                The AI analyzes the evidence and assigns a verdict:
              </p>
              <div className="space-y-2">
                <div className="flex items-start space-x-3 p-3 bg-green-50 border border-green-200 rounded">
                  <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-green-900 text-sm">Verified</h4>
                    <p className="text-xs text-green-800">
                      Multiple credible sources confirm the claim with high confidence
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3 p-3 bg-yellow-50 border border-yellow-200 rounded">
                  <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-yellow-900 text-sm">Partially True</h4>
                    <p className="text-xs text-yellow-800">
                      Some evidence supports, some contradicts, or context is needed
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3 p-3 bg-red-50 border border-red-200 rounded">
                  <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-red-900 text-sm">Disputed / False</h4>
                    <p className="text-xs text-red-800">
                      Scientific consensus contradicts the claim
                    </p>
                  </div>
                </div>
                <div className="flex items-start space-x-3 p-3 bg-gray-50 border border-gray-200 rounded">
                  <HelpCircle className="w-5 h-5 text-gray-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="font-semibold text-gray-900 text-sm">Unverified</h4>
                    <p className="text-xs text-gray-800">
                      Insufficient evidence to make a determination
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Step 5 */}
            <div className="border-l-4 border-orange-500 pl-6 py-2">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                5. Confidence Scoring
              </h3>
              <p className="text-gray-700 mb-3">
                Every verdict includes a confidence score (0-100%) based on:
              </p>
              <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
                <ul className="space-y-2 text-sm text-orange-900">
                  <li><strong>Source Quality</strong>: Peer-reviewed papers score higher than news articles</li>
                  <li><strong>Evidence Quantity</strong>: More sources = higher confidence</li>
                  <li><strong>Consensus</strong>: Do all sources agree?</li>
                  <li><strong>Recency</strong>: Newer data weighted more heavily</li>
                  <li><strong>Specificity</strong>: Precise claims easier to verify</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Transparency */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Transparency &amp; Limitations</h2>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h3 className="font-semibold text-blue-900 mb-3">What We Show You:</h3>
              <ul className="list-disc list-inside space-y-2 text-blue-800">
                <li>Every source we consulted</li>
                <li>The AI model used for analysis</li>
                <li>Confidence scores with explanations</li>
                <li>Full justifications for verdicts</li>
                <li>Links to original sources</li>
              </ul>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
              <h3 className="font-semibold text-yellow-900 mb-3">Current Limitations:</h3>
              <ul className="list-disc list-inside space-y-2 text-yellow-800">
                <li>AI may occasionally misinterpret complex scientific nuance</li>
                <li>Evidence retrieval depends on publicly available data</li>
                <li>Some claims are too recent to verify against scientific literature</li>
                <li>We cannot verify predictions (only past/present facts)</li>
                <li>Paywalled sources may be inaccessible</li>
              </ul>
              <p className="text-sm text-yellow-900 mt-3">
                <strong>Always use your judgment</strong> and consult multiple sources for critical decisions.
              </p>
            </div>
          </section>

          {/* Data Sources */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Trusted Data Sources</h2>
            <p className="text-gray-700">
              We prioritize scientific consensus and peer-reviewed research. See our full list on the{' '}
              <Link href="/sources" className="text-clilens-primary underline">Data Sources page</Link>.
            </p>
          </section>

          {/* Updates */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Continuous Improvement</h2>
            <p className="text-gray-700">
              Our methodology evolves as AI and climate science advance. We regularly:
            </p>
            <ul className="list-disc list-inside space-y-1 text-gray-700 ml-4">
              <li>Add new scientific data sources</li>
              <li>Improve AI prompts for better accuracy</li>
              <li>Refine confidence scoring algorithms</li>
              <li>Incorporate user feedback</li>
            </ul>
          </section>

          {/* Call to Action */}
          <section className="bg-gray-100 rounded-lg p-6 text-center">
            <p className="text-gray-700 mb-4">
              Have questions about our methodology?
            </p>
            <Link
              href="/about"
              className="inline-flex px-6 py-3 bg-clilens-primary text-white rounded-lg font-medium hover:bg-clilens-teal-600 transition-colors"
            >
              Learn More About CliLens
            </Link>
          </section>
        </div>
      </main>
    </div>
  )
}
