import { Globe, Zap, Shield, Brain, Database, Code } from "lucide-react";

function AboutPage() {
  const features = [
    { icon: Zap, title: "Automatic refresh", desc: "New articles are ingested and fact-checked on a rolling schedule." },
    { icon: Shield, title: "Verified claims", desc: "Every claim is cross-checked against trusted data sources." },
    { icon: Brain, title: "AI-assisted newsroom", desc: "Claude and GPT-4 accelerate analysis while humans stay in control." },
    { icon: Globe, title: "European focus", desc: "Tailored coverage of climate developments across the continent." },
  ];

  return (
    <div className="space-y-12">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-climate-green-500 to-climate-blue-500 rounded-2xl mb-6">
          <Globe className="h-8 w-8 text-white" />
        </div>
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          About Climate News
        </h1>
        <p className="text-xl text-gray-600 max-w-3xl mx-auto">
          Climate News is an automated climate intelligence portal that discovers, verifies, and presents
          trusted stories with transparent sourcing. Multi-agent workflows combine AI speed with editorial oversight.
        </p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">How the pipeline works</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-climate-blue-100 rounded-lg mb-4">
              <Database className="h-6 w-6 text-climate-blue-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">1. Discovery</h3>
            <p className="text-sm text-gray-600">
              The content discovery agent scans European news feeds and APIs to capture climate-related coverage in real time.
            </p>
          </div>

          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-climate-green-100 rounded-lg mb-4">
              <Shield className="h-6 w-6 text-climate-green-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">2. Verification</h3>
            <p className="text-sm text-gray-600">
              Claims are validated against ClimateCheck, NOAA, NASA, and other reference datasets with LLM reasoning guardrails.
            </p>
          </div>

          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-climate-green-100 rounded-lg mb-4">
              <Brain className="h-6 w-6 text-climate-green-600" />
            </div>
            <h3 className="font-semibold text-gray-900 mb-2">3. Publishing</h3>
            <p className="text-sm text-gray-600">
              The content creation agent produces summaries, dashboards, and scripts ready for web, API, and video formats.
            </p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Technology stack</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
              <Code className="h-5 w-5 text-climate-blue-600" />
              <span>Platform</span>
            </h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>- Multi-agent architecture with orchestrator and specialist workers</li>
              <li>- Python, FastAPI, Pydantic</li>
              <li>- Apache Kafka for event-driven pipelines</li>
              <li>- PostgreSQL + pgvector for structured and semantic storage</li>
              <li>- Redis for coordination and caching</li>
            </ul>
          </div>

          <div>
            <h3 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
              <Brain className="h-5 w-5 text-climate-green-600" />
              <span>AI and data</span>
            </h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>- Claude 3.5 Sonnet for orchestration and narrative generation</li>
              <li>- GPT-4o for analytical cross-checks and summarisation</li>
              <li>- ClimateCheck, NOAA, NASA, and EU data sources for ground truth</li>
              <li>- Custom NLP pipelines for claim detection and tagging</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Key features</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {features.map((feature, idx) => (
            <div key={idx} className="flex items-start space-x-3">
              <div className="flex-shrink-0 w-10 h-10 bg-climate-green-100 rounded-lg flex items-center justify-center">
                <feature.icon className="h-5 w-5 text-climate-green-600" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900">{feature.title}</h4>
                <p className="text-sm text-gray-600">{feature.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">News sources</h2>
        <p className="text-gray-600 mb-4">
          The ingestion layer prioritises well-established European outlets with transparent editorial standards.
        </p>
        <ul className="space-y-2 text-sm text-gray-700">
          <li>- Yle (Finland)</li>
          <li>- Helsingin Sanomat (Finland)
          </li>
          <li>- Additional European climate desks are being onboarded continuously</li>
        </ul>
      </div>

      <div className="bg-gradient-to-r from-climate-green-600 to-climate-blue-600 rounded-xl p-8 text-white text-center">
        <h2 className="text-2xl font-bold mb-4">Open source</h2>
        <p className="mb-6 text-white/90">
          Climate News is built in the open so that others can contribute workflows, datasets, and new distribution surfaces.
        </p>
        <a
          href="https://github.com/yourusername/climatenews"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center space-x-2 px-6 py-3 bg-white text-climate-green-700 rounded-lg font-medium hover:bg-gray-100 transition-colors"
        >
          <Code className="h-5 w-5" />
          <span>View on GitHub</span>
        </a>
      </div>
    </div>
  );
}

export default AboutPage;
