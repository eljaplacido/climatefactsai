"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Globe, Home, Info, Settings, Search, Sparkles, BookOpen, User, Languages, MapPin, BarChart3, FileText, Menu, X } from "lucide-react";
import { SUPPORTED_LANGUAGES, detectBrowserLanguage, setLanguage, loadTranslations, getCurrentLanguage, type LanguageCode } from "@/lib/i18n";

interface SiteLayoutProps {
  children: React.ReactNode;
}

function SiteLayout({ children }: SiteLayoutProps) {
  const pathname = usePathname();
  const [langOpen, setLangOpen] = useState(false);
  const [currentLang, setCurrentLang] = useState<LanguageCode>("en");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const detected = detectBrowserLanguage();
    setCurrentLang(detected);
    setLanguage(detected);
    loadTranslations(detected);
  }, []);

  function handleLanguageChange(code: LanguageCode) {
    setCurrentLang(code);
    setLanguage(code);
    loadTranslations(code);
    setLangOpen(false);
  }

  const isActive = (path: string) => pathname === path;

  return (
    <div className="min-h-screen bg-gray-50">
      <header role="banner" className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link href="/" className="flex items-center space-x-2 group">
              <div className="bg-gradient-to-br from-clilens-primary to-clilens-secondary p-2 rounded-lg group-hover:scale-105 transition-transform">
                <Globe className="h-6 w-6 text-white" />
              </div>
              <div>
                <p className="text-xl font-bold text-gray-900">CliLens.AI</p>
                <p className="text-xs text-gray-500">Trusted climate intelligence</p>
              </div>
            </Link>

            <nav className="hidden md:flex space-x-1" role="navigation" aria-label="Main navigation">
              <Link
                href="/"
                aria-current={isActive("/") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/") ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Home className="h-5 w-5" />
                <span className="font-medium">News</span>
              </Link>

              <Link
                href="/map"
                aria-current={isActive("/map") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/map") ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Globe className="h-5 w-5" />
                <span className="font-medium">Map</span>
              </Link>

              <Link
                href="/search"
                aria-current={isActive("/search") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/search") ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Search className="h-5 w-5" />
                <span className="font-medium">Search</span>
              </Link>

              <Link
                href="/deep-search"
                aria-current={isActive("/deep-search") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/deep-search") ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Sparkles className="h-5 w-5" />
                <span className="font-medium">Deep Search</span>
              </Link>

              <Link
                href="/research"
                aria-current={isActive("/research") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/research") ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <BookOpen className="h-5 w-5" />
                <span className="font-medium">Research</span>
              </Link>

              <Link
                href="/about"
                aria-current={isActive("/about") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/about") ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Info className="h-5 w-5" />
                <span className="font-medium">About</span>
              </Link>

              <Link
                href="/admin"
                aria-current={isActive("/admin") ? "page" : undefined}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive("/admin") ? "bg-blue-50 text-blue-700" : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                <Settings className="h-5 w-5" />
                <span className="font-medium">Operations</span>
              </Link>
            </nav>

            {/* Right side: Language selector + User menu */}
            <div className="hidden md:flex items-center space-x-2">
              {/* Language selector */}
              <div className="relative">
                <button
                  onClick={() => setLangOpen(!langOpen)}
                  className="flex items-center space-x-1.5 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                  aria-label="Select language"
                >
                  <Languages className="h-4 w-4" />
                  <span className="uppercase font-medium">{currentLang}</span>
                </button>
                {langOpen && (
                  <div className="absolute right-0 top-full mt-1 w-48 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-80 overflow-y-auto">
                    {SUPPORTED_LANGUAGES.map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => handleLanguageChange(lang.code)}
                        className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center justify-between ${
                          currentLang === lang.code ? "bg-clilens-teal-50 text-clilens-teal-700 font-medium" : "text-gray-700"
                        }`}
                      >
                        <span>{lang.name}</span>
                        <span className="text-xs text-gray-400 uppercase">{lang.code}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* User profile */}
              <Link
                href="/admin"
                className="flex items-center space-x-1.5 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <User className="h-4 w-4" />
              </Link>
            </div>

            {/* Mobile menu toggle */}
            <button
              className="md:hidden p-2 text-gray-600 hover:bg-gray-100 rounded-lg"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label="Toggle menu"
              aria-expanded={mobileMenuOpen}
            >
              {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>

          {/* Mobile navigation */}
          {mobileMenuOpen && (
            <nav className="md:hidden border-t border-gray-100 py-3 space-y-1" role="navigation" aria-label="Mobile navigation">
              {[
                { href: "/", label: "News", icon: Home },
                { href: "/map", label: "Map", icon: Globe },
                { href: "/search", label: "Search", icon: Search },
                { href: "/deep-search", label: "Deep Search", icon: Sparkles },
                { href: "/research", label: "Research", icon: BookOpen },
                { href: "/analyze", label: "Analyze", icon: FileText },
                { href: "/about", label: "About", icon: Info },
              ].map(({ href, label, icon: Icon }) => (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileMenuOpen(false)}
                  aria-current={isActive(href) ? "page" : undefined}
                  className={`flex items-center space-x-3 px-4 py-2.5 rounded-lg ${
                    isActive(href) ? "bg-clilens-teal-50 text-clilens-teal-700" : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span className="font-medium">{label}</span>
                </Link>
              ))}
            </nav>
          )}
        </div>
      </header>

      <main id="main-content" role="main" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>

      <footer role="contentinfo" className="bg-white border-t border-gray-200 mt-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">CliLens.AI</h3>
              <p className="text-sm text-gray-600">
                Independent climate intelligence with transparent fact-checking, powered by a multi-agent news pipeline.
              </p>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Learn more</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>
                  <Link href="/about" className="hover:text-clilens-primary">How it works</Link>
                </li>
                <li>
                  <a href="#" className="hover:text-clilens-primary">Source catalogue</a>
                </li>
                <li>
                  <a href="#" className="hover:text-clilens-primary">Contact</a>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Technology</h3>
              <ul className="space-y-2 text-sm text-gray-600">
                <li>Multi-agent automation</li>
                <li>ClimateCheck, NOAA, NASA data</li>
                <li>DeepSeek AI</li>
                <li>Open source tooling</li>
              </ul>
            </div>
          </div>

          <div className="mt-8 pt-8 border-t border-gray-200 text-center text-sm text-gray-500">
            <p>&copy; {new Date().getFullYear()} CliLens.AI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default SiteLayout;
