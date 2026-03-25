"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Globe, Home, Search, Sparkles, BookOpen, User,
  Languages, MapPin, FileText, Menu, X, BarChart3,
  Shield, Info,
} from "lucide-react";
import {
  SUPPORTED_LANGUAGES,
  detectBrowserLanguage,
  setLanguage,
  loadTranslations,
  type LanguageCode,
} from "@/lib/i18n";

const NAV_ITEMS = [
  { href: "/", label: "News", icon: Home },
  { href: "/map", label: "Map", icon: Globe },
  { href: "/search", label: "Search", icon: Search },
  { href: "/deep-search", label: "Deep Search", icon: Sparkles },
  { href: "/analyze", label: "Analyze", icon: FileText },
  { href: "/research", label: "Research", icon: BookOpen },
  { href: "/sources", label: "Sources", icon: Shield },
];

export default function GlobalNav() {
  const pathname = usePathname();
  const [langOpen, setLangOpen] = useState(false);
  const [currentLang, setCurrentLang] = useState<LanguageCode>("en");
  const [mobileOpen, setMobileOpen] = useState(false);

  // Pages that handle their own full layout
  const standalone = ["/map", "/articles"];
  const isStandalone = standalone.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    const detected = detectBrowserLanguage();
    setCurrentLang(detected);
    setLanguage(detected);
    loadTranslations(detected);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function handleLangChange(code: LanguageCode) {
    setCurrentLang(code);
    setLanguage(code);
    loadTranslations(code);
    setLangOpen(false);
  }

  const isActive = (path: string) =>
    path === "/" ? pathname === "/" : pathname?.startsWith(path);

  // Don't render nav on pages with their own layout
  if (isStandalone) return null;

  return (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-14">
          {/* Logo */}
          <Link href="/" className="flex items-center space-x-2 group flex-shrink-0">
            <div className="bg-gradient-to-br from-teal-600 to-emerald-600 p-1.5 rounded-lg group-hover:scale-105 transition-transform">
              <Globe className="h-5 w-5 text-white" />
            </div>
            <div className="hidden sm:block">
              <p className="text-lg font-bold text-gray-900 leading-tight">CliLens.AI</p>
              <p className="text-[10px] text-gray-400 leading-tight -mt-0.5">Climate Intelligence</p>
            </div>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden lg:flex items-center space-x-0.5">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-sm transition-colors ${
                  isActive(href)
                    ? "bg-teal-50 text-teal-700 font-semibold"
                    : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          {/* Right controls */}
          <div className="flex items-center space-x-1">
            {/* Language selector */}
            <div className="relative">
              <button
                onClick={() => setLangOpen(!langOpen)}
                className="flex items-center space-x-1 px-2 py-1.5 text-xs text-gray-500 hover:bg-gray-50 rounded-md transition-colors"
                aria-label="Select language"
              >
                <Languages className="h-3.5 w-3.5" />
                <span className="uppercase font-semibold">{currentLang}</span>
              </button>
              {langOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setLangOpen(false)} />
                  <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-h-72 overflow-y-auto">
                    {SUPPORTED_LANGUAGES.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => handleLangChange(lang.code)}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between transition-colors ${
                          currentLang === lang.code
                            ? "bg-teal-50 text-teal-700 font-medium"
                            : "text-gray-700"
                        }`}
                      >
                        <span>{lang.name}</span>
                        <span className="text-[10px] text-gray-400 uppercase">{lang.code}</span>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Analytics link */}
            <Link
              href="/admin/analytics"
              className="hidden md:flex items-center px-2 py-1.5 text-gray-500 hover:bg-gray-50 rounded-md transition-colors"
              title="Analytics"
            >
              <BarChart3 className="h-4 w-4" />
            </Link>

            {/* About */}
            <Link
              href="/about"
              className="hidden md:flex items-center px-2 py-1.5 text-gray-500 hover:bg-gray-50 rounded-md transition-colors"
              title="About"
            >
              <Info className="h-4 w-4" />
            </Link>

            {/* Mobile menu button */}
            <button
              className="lg:hidden p-2 text-gray-500 hover:bg-gray-50 rounded-md"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle menu"
            >
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <nav className="lg:hidden border-t border-gray-100 py-2 space-y-0.5 pb-3">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm ${
                  isActive(href)
                    ? "bg-teal-50 text-teal-700 font-semibold"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <Icon className="h-5 w-5" />
                <span>{label}</span>
              </Link>
            ))}
            <div className="border-t border-gray-100 mt-2 pt-2">
              <Link href="/admin/analytics" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                <BarChart3 className="h-5 w-5" />
                <span>Analytics</span>
              </Link>
              <Link href="/about" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                <Info className="h-5 w-5" />
                <span>About</span>
              </Link>
            </div>
          </nav>
        )}
      </div>
    </header>
  );
}
