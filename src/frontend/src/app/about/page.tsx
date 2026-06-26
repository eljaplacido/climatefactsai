'use client'

import Link from 'next/link'

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-900">
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-gray-200 dark:border-slate-700">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex items-center justify-between">
          <Link href="/" className="text-2xl font-bold text-clilens-primary dark:text-teal-400">
            Climatefacts.ai
          </Link>
          <nav className="text-sm text-gray-500 dark:text-slate-400 flex gap-4">
            <Link href="/about" className="text-gray-900 dark:text-slate-100 font-medium">About</Link>
            <Link href="/methodology" className="hover:text-gray-800 dark:hover:text-slate-200">Methodology</Link>
            <Link href="/sources" className="hover:text-gray-800 dark:hover:text-slate-200">Sources</Link>
          </nav>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-gray-200 dark:border-slate-700 p-8 space-y-8">

          {/* Hero */}
          <div>
            <h1 className="text-4xl font-bold text-gray-900 dark:text-slate-100 mb-4">
              About Climatefacts.ai
            </h1>
            <p className="text-xl text-gray-600 dark:text-slate-400">
              The truth machine for climate, green transition, and sustainability information.
            </p>
          </div>

          {/* Mission */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Our Mission</h2>
            <p className="text-gray-700 dark:text-slate-300 leading-relaxed">
              Climate, sustainability, and green-transition discourse is the
              most consequential public conversation of our time — and the
              most contested. Climatefacts.ai exists to give every reader,
              policymaker, business leader, researcher, and citizen a
              trustworthy lens on this discourse: <strong>evidence-backed,
              source-traceable, and openly accountable.</strong>
            </p>
            <p className="text-gray-700 dark:text-slate-300 leading-relaxed">
              We don't tell you what to believe. We show you{' '}
              <strong>how each claim was verified</strong>, which
              authoritative datasets it was checked against, and the
              confidence we have in the result — so you can decide.
            </p>
          </section>

          {/* Vision */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Our Vision</h2>
            <p className="text-gray-700 dark:text-slate-300 leading-relaxed">
              A world where climate decisions — from individual purchases
              to national policy — are grounded in transparent, verifiable
              facts rather than narrative or noise. Climatefacts.ai aims
              to be the reference layer that journalists, NGOs, public
              institutions, and citizens reach for when they need the
              ground truth on emissions, energy transition, policy
              ambition, vulnerability, and adaptation across every country
              on Earth.
            </p>
          </section>

          {/* Solution */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Our Solution</h2>
            <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg p-6 space-y-4">
              <p className="text-blue-900 dark:text-blue-200">
                Climatefacts.ai combines authoritative primary-source
                indicators with evidence-grounded retrieval, calibrated
                confidence scoring, and per-claim provenance to deliver a
                continuously updated picture of climate truth.
              </p>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-1">Primary-source indicators</h3>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Climate TRACE, Our World in Data, Climate Action
                    Tracker, UNFCCC NDC Registry, IRENA, ND-GAIN — six
                    authoritative datasets feed every country score.
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-1">Multi-LLM verification</h3>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Every claim is cross-checked across independent
                    large language models; disagreements downgrade
                    confidence rather than being hidden.
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-1">Calibrated confidence</h3>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Scores are calibrated against reviewer-graded ground
                    truth using Brier scores, ECE, and Platt scaling.
                    Refit nightly.
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold text-blue-900 dark:text-blue-200 mb-1">Full provenance</h3>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Every displayed number traces back to its source
                    article, the prompt that produced it, and the
                    retrieval strategy used. Auditors can pin a
                    methodology snapshot to a git commit.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Ownership: CISU Regen */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Who We Are</h2>
            <div className="bg-emerald-50 dark:bg-emerald-900/30 border border-emerald-200 dark:border-emerald-800 rounded-lg p-6 space-y-3">
              <p className="text-emerald-900 dark:text-emerald-200">
                Climatefacts.ai is built and operated by{' '}
                <a
                  href="https://cisuregen.com/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-semibold underline hover:text-emerald-700 dark:text-emerald-400"
                >
                  CISU Regen
                </a>{' '}— an organisation whose mission is to{' '}
                <em>develop regenerative and resilient economies,
                organisations, and communities of the future</em>.
              </p>
              <p className="text-sm text-emerald-800 dark:text-emerald-300">
                We believe public-interest climate intelligence has to be
                open, accountable, and built on the same standards of
                rigour we'd want for any other critical public utility.
                Climatefacts.ai is one of CISU Regen's contributions to
                that goal.
              </p>
            </div>
          </section>

          {/* Values */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Our Values</h2>
            <div className="grid md:grid-cols-3 gap-4">
              <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-2">Scientific Rigor</h3>
                <p className="text-sm text-gray-600 dark:text-slate-400">
                  We anchor every analysis to peer-reviewed research,
                  satellite-verified observations, and authoritative
                  inter-governmental data.
                </p>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-2">Radical Transparency</h3>
                <p className="text-sm text-gray-600 dark:text-slate-400">
                  Every prompt, formula, indicator, and confidence figure
                  is published. If we won't show our work, we don't trust
                  the work either.
                </p>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-slate-800 rounded-lg">
                <h3 className="font-semibold text-gray-900 dark:text-slate-100 mb-2">Public Interest</h3>
                <p className="text-sm text-gray-600 dark:text-slate-400">
                  The platform is built first for civic accountability,
                  not engagement. We optimise for trust, not clicks.
                </p>
              </div>
            </div>
          </section>

          {/* Technology */}
          <section className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Technology</h2>
            <p className="text-gray-700 dark:text-slate-300">
              Climatefacts.ai is powered by a transparent, audit-ready stack:
            </p>
            <ul className="list-disc list-inside space-y-2 text-gray-700 dark:text-slate-300 ml-4">
              <li><strong>Six primary data adapters</strong> — Climate TRACE, OWID, Climate Action Tracker, UNFCCC NDC Registry (via Climate Watch), IRENA, ND-GAIN</li>
              <li><strong>Multi-LLM verification</strong> — Anthropic Claude + DeepSeek with Jaccard-similarity cross-checking</li>
              <li><strong>Hallucination detection</strong> — entity overlap + statistic verification + LLM grounding on every output</li>
              <li><strong>Hybrid retrieval</strong> — PostgreSQL full-text + HNSW vector search + knowledge graph + (optional) Perplexity for external evidence</li>
              <li><strong>Drift monitoring</strong> — KL-divergence on article source mix and prompt-fingerprint distribution</li>
              <li><strong>Calibrated confidence</strong> — Brier score, ECE, Platt scaling against reviewer ground truth</li>
            </ul>
            <p className="text-sm text-gray-600 dark:text-slate-400 mt-4">
              The full audit surface is live at the{' '}
              <Link href="/methodology" className="text-clilens-primary dark:text-teal-400 underline">Methodology page</Link>.
            </p>
          </section>

          {/* Call to Action */}
          <section className="bg-clilens-primary bg-opacity-10 rounded-lg p-6 text-center">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100 mb-3">
              Ready to see through climate misinformation?
            </h2>
            <p className="text-gray-700 dark:text-slate-300 mb-6">
              Start exploring verified climate news, or submit any URL,
              article, or research paper for a transparent breakdown.
            </p>
            <div className="flex justify-center space-x-4">
              <Link
                href="/"
                className="px-6 py-3 bg-clilens-primary text-white rounded-lg font-medium hover:bg-clilens-teal-600 transition-colors"
              >
                Browse News
              </Link>
              <Link
                href="/analyze"
                className="px-6 py-3 bg-white dark:bg-slate-800 text-clilens-primary dark:text-teal-400 border-2 border-clilens-primary rounded-lg font-medium hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
              >
                Analyze a URL
              </Link>
            </div>
          </section>

          {/* Contact */}
          <section className="text-center text-sm text-gray-600 dark:text-slate-400 border-t pt-6 space-y-1">
            <p>
              Questions, feedback, or methodology suggestions? Reach out at{' '}
              <a href="mailto:contact@cisuregen.com" className="text-clilens-primary dark:text-teal-400 underline">
                contact@cisuregen.com
              </a>
            </p>
            <p>
              Operated by{' '}
              <a
                href="https://cisuregen.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-clilens-primary dark:text-teal-400 underline"
              >
                CISU Regen
              </a>
              {' '}— regenerative & resilient economies, organisations, and communities.
            </p>
          </section>
        </div>
      </main>
    </div>
  )
}
