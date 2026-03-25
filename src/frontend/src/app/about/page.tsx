'use client'

import Link from 'next/link'

export default function AboutPage() {
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
              About CliLens
            </h1>
            <p className="text-xl text-gray-600">
              Your trusted lens to understand climate news truthfulness
            </p>
          </div>

          {/* Mission */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Our Mission</h2>
            <p className="text-gray-700 leading-relaxed">
              Climate misinformation is everywhere. From exaggerated headlines to outright denial,
              it's hard to know what to trust. CliLens provides a <strong>transparent, AI-powered lens</strong> to
              help you understand the truthfulness of climate news.
            </p>
            <p className="text-gray-700 leading-relaxed">
              We don't just tell you what to believe—we show you <strong>how we verified each claim</strong>,
              what <strong>evidence we found</strong>, and where you can <strong>dig deeper</strong>.
            </p>
          </section>

          {/* The Problem */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">The Problem We Solve</h2>
            <div className="bg-red-50 border border-red-200 rounded-lg p-6 space-y-3">
              <h3 className="font-semibold text-red-900">Climate News Challenges:</h3>
              <ul className="list-disc list-inside space-y-2 text-red-800">
                <li>Misinformation spreads faster than corrections</li>
                <li>Technical jargon makes articles hard to understand</li>
                <li>Hard to verify claims without scientific background</li>
                <li>Difficult to find trusted sources</li>
                <li>Local climate impacts often misreported</li>
              </ul>
            </div>
          </section>

          {/* Our Solution */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Our Solution</h2>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <h3 className="font-semibold text-blue-900 mb-2">🔍 Claim Extraction</h3>
                  <p className="text-sm text-blue-800">
                    AI identifies factual claims in every article
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 mb-2">✅ Fact-Checking</h3>
                  <p className="text-sm text-blue-800">
                    Automatic verification against scientific sources
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 mb-2">📊 Visual Indicators</h3>
                  <p className="text-sm text-blue-800">
                    See trustworthiness at a glance with confidence scores
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 mb-2">🌍 Geographic Context</h3>
                  <p className="text-sm text-blue-800">
                    Explore news by region and see local impacts
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 mb-2">💬 Interactive Analysis</h3>
                  <p className="text-sm text-blue-800">
                    Ask questions and get AI-powered explanations
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 mb-2">📚 Education</h3>
                  <p className="text-sm text-blue-800">
                    Learn climate concepts as you read
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* How It Works */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">How It Works</h2>
            <div className="space-y-3">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 bg-clilens-primary text-white rounded-full flex items-center justify-center font-bold">
                  1
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Article Ingestion</h3>
                  <p className="text-sm text-gray-600">
                    We ingest climate news from trusted sources or user submissions
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 bg-clilens-primary text-white rounded-full flex items-center justify-center font-bold">
                  2
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">AI Claim Extraction</h3>
                  <p className="text-sm text-gray-600">
                    Claude 3.5 Sonnet identifies specific, verifiable claims in the text
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 bg-clilens-primary text-white rounded-full flex items-center justify-center font-bold">
                  3
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Evidence Retrieval</h3>
                  <p className="text-sm text-gray-600">
                    We search scientific databases (NASA, NOAA, etc.) for supporting or contradicting evidence
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 bg-clilens-primary text-white rounded-full flex items-center justify-center font-bold">
                  4
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Verdict Adjudication</h3>
                  <p className="text-sm text-gray-600">
                    AI analyzes evidence and assigns a verdict with confidence score
                  </p>
                </div>
              </div>
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0 w-8 h-8 bg-clilens-primary text-white rounded-full flex items-center justify-center font-bold">
                  5
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900">Results Display</h3>
                  <p className="text-sm text-gray-600">
                    You see visual trust indicators, evidence sources, and can dig deeper
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Team & Values */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Our Values</h2>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold text-gray-900 mb-2">🔬 Scientific Rigor</h3>
                <p className="text-sm text-gray-600">
                  We only trust peer-reviewed sources and scientific data
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold text-gray-900 mb-2">🌐 Transparency</h3>
                <p className="text-sm text-gray-600">
                  We show our sources, methods, and confidence levels
                </p>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <h3 className="font-semibold text-gray-900 mb-2">📖 Education</h3>
                <p className="text-sm text-gray-600">
                  We explain concepts so everyone can understand climate science
                </p>
              </div>
            </div>
          </section>

          {/* Technology */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Technology</h2>
            <p className="text-gray-700">
              CliLens is powered by:
            </p>
            <ul className="list-disc list-inside space-y-2 text-gray-700 ml-4">
              <li><strong>Anthropic Claude 3.5 Sonnet</strong> - For claim extraction and analysis</li>
              <li><strong>Scientific Databases</strong> - NASA, NOAA, Google Scholar</li>
              <li><strong>PostgreSQL</strong> - For reliable data storage</li>
              <li><strong>Next.js & React</strong> - For modern, responsive UI</li>
            </ul>
            <p className="text-sm text-gray-600 mt-4">
              Learn more about our methodology on the <Link href="/methodology" className="text-clilens-primary underline">Methodology page</Link>.
            </p>
          </section>

          {/* Call to Action */}
          <section className="bg-clilens-primary bg-opacity-10 rounded-lg p-6 text-center">
            <h2 className="text-2xl font-bold text-gray-900 mb-3">
              Ready to See Through Climate Misinformation?
            </h2>
            <p className="text-gray-700 mb-6">
              Start exploring verified climate news or submit an article for analysis
            </p>
            <div className="flex justify-center space-x-4">
              <Link
                href="/"
                className="px-6 py-3 bg-clilens-primary text-white rounded-lg font-medium hover:bg-clilens-teal-600 transition-colors"
              >
                Browse News
              </Link>
              <Link
                href="/submit"
                className="px-6 py-3 bg-white text-clilens-primary border-2 border-clilens-primary rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Submit Article
              </Link>
            </div>
          </section>

          {/* Contact */}
          <section className="text-center text-sm text-gray-600 border-t pt-6">
            <p>
              Questions or feedback? Reach out at{' '}
              <a href="mailto:info@clilens.ai" className="text-clilens-primary underline">
                info@clilens.ai
              </a>
            </p>
          </section>
        </div>
      </main>
    </div>
  )
}
