"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Code, Key, Terminal, Copy, Check, ExternalLink, ArrowRight,
  Zap, Crown, Building2, User, Sparkles, Server, ShieldCheck,
  BookOpen, Globe,
} from "lucide-react";

const SNIPPETS = {
  curl: `curl -H "Authorization: Bearer YOUR_API_KEY" \\
  "https://api.climatefacts.ai/v1/articles"`,
  python: `import requests

url = "https://api.climatefacts.ai/v1/articles"
headers = {"Authorization": "Bearer YOUR_API_KEY"}
resp = requests.get(url, headers=headers)
print(resp.json())`,
  js: `const res = await fetch(
  "https://api.climatefacts.ai/v1/articles",
  {
    headers: {
      Authorization: "Bearer YOUR_API_KEY",
    },
  }
);
const data = await res.json();
console.log(data);`,
};

const TIERS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    calls: "1,000 / day",
    icon: User,
    color: "border-slate-700 bg-slate-800/50",
    iconBg: "bg-slate-700 text-slate-300",
    highlighted: false,
    features: ["Public data only", "Rate-limited", "Community support"],
  },
  {
    name: "Basic",
    price: "$9.99",
    period: "/month",
    calls: "10,000 / day",
    icon: Zap,
    color: "border-blue-800 bg-blue-900/20",
    iconBg: "bg-blue-700 text-blue-200",
    highlighted: false,
    features: ["Research data access", "Email support", "Standard rate limits"],
  },
  {
    name: "Pro",
    price: "$29.99",
    period: "/month",
    calls: "10,000 / day",
    icon: Crown,
    color: "border-teal-800 bg-teal-900/20 ring-1 ring-teal-700/40",
    iconBg: "bg-teal-700 text-teal-200",
    highlighted: true,
    features: ["All data + priority queue", "Priority support", "Webhook notifications"],
  },
  {
    name: "Enterprise",
    price: "$99.99",
    period: "/month",
    calls: "Custom volume",
    icon: Building2,
    color: "border-purple-800 bg-purple-900/20",
    iconBg: "bg-purple-700 text-purple-200",
    highlighted: false,
    features: ["Dedicated support", "SLA guarantee", "On-premise option"],
  },
];

export default function ApiAccessPage() {
  const [copied, setCopied] = useState<string | null>(null);

  function copySnippet(lang: string, code: string) {
    navigator.clipboard.writeText(code);
    setCopied(lang);
    setTimeout(() => setCopied(null), 2000);
  }

  return (
    <div className="min-h-screen bg-slate-900">
      <div className="border-b border-slate-800">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-5 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-teal-400">
            Climatefacts.ai
          </Link>
          <nav className="text-sm text-slate-400 flex gap-4">
            <Link href="/about" className="hover:text-slate-200">About</Link>
            <Link href="/api-access" className="text-teal-400 font-medium">API</Link>
            <Link href="/methodology" className="hover:text-slate-200">Methodology</Link>
          </nav>
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-12">
        <header>
          <div className="flex items-center gap-3 mb-3">
            <div className="p-2.5 rounded-xl bg-teal-600/20">
              <Code className="w-6 h-6 text-teal-400" />
            </div>
            <h1 className="text-4xl font-bold text-slate-100">API Access</h1>
          </div>
          <p className="text-lg text-slate-400 max-w-3xl">
            Integrate verified climate intelligence into your applications,
            models, or dashboards. Authenticate once, query with confidence.
          </p>
        </header>

        {/* Authentication */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 space-y-4">
          <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <Key className="w-5 h-5 text-teal-400" />
            Authentication
          </h2>
          <p className="text-sm text-slate-400">
            All API requests require a Bearer token. Get your key from{" "}
            <Link href="/dashboard/settings" className="text-teal-400 hover:underline">
              Dashboard → Settings
            </Link>{" "}
            after creating an account.
          </p>
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-sm text-slate-300">
            <span className="text-slate-500">Authorization:</span>{" "}
            <span className="text-teal-400">Bearer</span>{" "}
            <span className="text-slate-500">&lt;api_key&gt;</span>
          </div>
        </section>

        {/* Tiers */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <Sparkles className="w-5 h-5 text-teal-400" />
            Plans & limits
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {TIERS.map((tier) => {
              const Icon = tier.icon;
              return (
                <div
                  key={tier.name}
                  className={`rounded-xl border p-5 ${tier.color} ${tier.highlighted ? "scale-[1.02]" : ""}`}
                >
                  <div className={`inline-flex p-2 rounded-lg ${tier.iconBg} mb-3`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex items-baseline gap-1 mb-1">
                    <span className="text-2xl font-bold text-slate-100">{tier.price}</span>
                    {tier.period && <span className="text-xs text-slate-500">{tier.period}</span>}
                  </div>
                  <div className="text-sm font-semibold text-slate-200 mb-1">{tier.name}</div>
                  <div className="text-xs text-teal-400 font-mono mb-3">{tier.calls}</div>
                  <ul className="space-y-1">
                    {tier.features.map((f) => (
                      <li key={f} className="text-xs text-slate-400 flex items-center gap-1.5">
                        <span className="w-1 h-1 rounded-full bg-slate-600 flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-amber-300 bg-amber-950/30 border border-amber-800/40 rounded-lg px-3 py-2.5">
            API keys require Professional tier or higher.
          </p>
        </section>

        {/* Quick-start code examples */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <Terminal className="w-5 h-5 text-teal-400" />
            Quick start
          </h2>
          <p className="text-sm text-slate-400">
            Replace <code className="bg-slate-800 px-1.5 py-0.5 rounded text-teal-400 font-mono text-xs">YOUR_API_KEY</code>{" "}
            with the key from your dashboard.
          </p>
          <div className="space-y-3">
            {([
              { lang: "curl", label: "cURL" },
              { lang: "python", label: "Python" },
              { lang: "js", label: "JavaScript" },
            ] as const).map(({ lang, label }) => (
              <div key={lang} className="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-900">
                  <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
                  <button
                    onClick={() => copySnippet(lang, SNIPPETS[lang])}
                    className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                  >
                    {copied === lang ? (
                      <Check className="w-3.5 h-3.5 text-teal-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                    {copied === lang ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre className="p-4 text-sm text-slate-300 font-mono overflow-x-auto leading-relaxed">
                  {SNIPPETS[lang]}
                </pre>
              </div>
            ))}
          </div>
        </section>

        {/* Endpoints + Docs */}
        <section className="space-y-4">
          <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <BookOpen className="w-5 h-5 text-teal-400" />
            Endpoint catalog
          </h2>
          <div className="grid sm:grid-cols-2 gap-3">
            <Link
              href="/api/methodology/endpoints"
              className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 hover:border-teal-700/50 transition-colors group"
            >
              <div className="flex items-center gap-2 mb-2">
                <Server className="w-4 h-4 text-teal-400" />
                <h3 className="font-semibold text-slate-200">REST Endpoint Catalog</h3>
              </div>
              <p className="text-sm text-slate-400 mb-3">
                Every endpoint with request/response schemas, query parameters, and
                live examples from the methodology bundle.
              </p>
              <span className="text-xs text-teal-400 flex items-center gap-1 group-hover:gap-2 transition-all">
                Browse endpoints <ArrowRight className="w-3 h-3" />
              </span>
            </Link>

            <a
              href="https://climatenews-495412.lm.r.appspot.com/docs"
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 hover:border-teal-700/50 transition-colors group"
            >
              <div className="flex items-center gap-2 mb-2">
                <Globe className="w-4 h-4 text-teal-400" />
                <h3 className="font-semibold text-slate-200">
                  Interactive Swagger Docs{" "}
                  <ExternalLink className="inline w-3 h-3 text-slate-500" />
                </h3>
              </div>
              <p className="text-sm text-slate-400 mb-3">
                Full OpenAPI spec with live &ldquo;Try it out&rdquo; — test endpoints
                directly from the browser with your API key.
              </p>
              <span className="text-xs text-teal-400 flex items-center gap-1 group-hover:gap-2 transition-all">
                Open Swagger UI <ArrowRight className="w-3 h-3" />
              </span>
            </a>
          </div>
        </section>

        {/* API Key Management */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 space-y-4">
          <h2 className="text-2xl font-bold text-slate-100 flex items-center gap-2.5">
            <ShieldCheck className="w-5 h-5 text-teal-400" />
            API key management
          </h2>
          <div className="space-y-3 text-sm text-slate-400">
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-teal-700/30 text-teal-400 font-semibold text-xs flex items-center justify-center mt-0.5">1</span>
              <div>
                <span className="font-medium text-slate-200">Create your account</span>{" "}
                <Link href="/signup" className="text-teal-400 hover:underline">at the signup page</Link>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-teal-700/30 text-teal-400 font-semibold text-xs flex items-center justify-center mt-0.5">2</span>
              <div>
                <span className="font-medium text-slate-200">Navigate to Dashboard → Settings</span>{" "}
                — your API key is displayed at the top of the settings page
              </div>
            </div>
            <div className="flex items-start gap-3">
              <span className="flex-shrink-0 w-6 h-6 rounded-full bg-teal-700/30 text-teal-400 font-semibold text-xs flex items-center justify-center mt-0.5">3</span>
              <div>
                <span className="font-medium text-slate-200">Use the key in all requests</span>{" "}
                via the <code className="bg-slate-800 px-1.5 py-0.5 rounded text-teal-400 font-mono text-xs">Authorization: Bearer</code> header.
                Rotate it anytime from Settings.
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="rounded-xl border border-teal-800 bg-gradient-to-br from-teal-950 to-slate-900 p-8 text-center">
          <h2 className="text-2xl font-bold text-slate-100 mb-2">
            Ready to integrate?
          </h2>
          <p className="text-slate-400 mb-5 max-w-lg mx-auto">
            Create a free account, grab your API key, and start building with
            verified climate intelligence.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/signup"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 transition-colors"
            >
              Get started <ArrowRight className="w-4 h-4" />
            </Link>
            <a
              href="https://climatenews-495412.lm.r.appspot.com/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-2 px-5 py-2.5 border border-slate-700 text-slate-300 rounded-lg font-medium text-sm hover:border-slate-500 transition-colors"
            >
              Swagger Docs <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}
