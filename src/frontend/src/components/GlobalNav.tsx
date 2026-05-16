"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Globe, Home, Search, Sparkles, BookOpen,
  MapPin, FileText, Menu, X, BarChart3,
  Shield, Info, LogOut, LayoutDashboard, Rss, Settings,
  LogIn, UserPlus, Lightbulb, Loader2, Sun, Moon, Monitor,
} from "lucide-react";
import {
  SUPPORTED_LANGUAGES,
  getFlagEmoji,
  type LanguageCode,
} from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-context";
import { useAuth } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/", labelKey: "nav.news", fallback: "News", icon: Home },
  { href: "/map", labelKey: "nav.map", fallback: "Map", icon: Globe },
  { href: "/search", labelKey: "nav.search", fallback: "Search", icon: Search },
  { href: "/deep-search", labelKey: "nav.deep_search", fallback: "Deep Search", icon: Sparkles },
  { href: "/analyze", labelKey: "nav.analyze", fallback: "Analyze", icon: FileText },
  { href: "/research", labelKey: "nav.research", fallback: "Research", icon: BookOpen },
  { href: "/sources", labelKey: "nav.sources", fallback: "Sources", icon: Shield },
  { href: "/suggest-source", labelKey: "nav.suggest", fallback: "Suggest", icon: Lightbulb },
];

const TIER_COLORS: Record<string, string> = {
  freemium: "bg-gray-100 text-gray-600",
  basic: "bg-blue-100 text-blue-700",
  professional: "bg-teal-100 text-teal-700",
  enterprise: "bg-purple-100 text-purple-700",
};

const TIER_LABELS: Record<string, string> = {
  freemium: "Free",
  basic: "Basic",
  professional: "Pro",
  enterprise: "Enterprise",
};

export default function GlobalNav() {
  const pathname = usePathname();
  const [langOpen, setLangOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const langRef = useRef<HTMLDivElement>(null);
  const { user, isLoggedIn, loading: authLoading, logout } = useAuth();
  const { locale, setLocale, t, isTranslating } = useI18n();
  const [theme, setTheme] = useState<"light" | "dark" | "auto">("light");

  // Initialize theme from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("clilens_theme") as "light" | "dark" | "auto" | null;
    if (saved) {
      setTheme(saved);
      applyTheme(saved);
    }
  }, []);

  function applyTheme(t: "light" | "dark" | "auto") {
    const root = document.documentElement;
    if (t === "dark" || (t === "auto" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  }

  function cycleTheme() {
    const next = theme === "light" ? "dark" : theme === "dark" ? "auto" : "light";
    setTheme(next);
    localStorage.setItem("clilens_theme", next);
    applyTheme(next);
  }

  // Close menus on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
      if (langRef.current && !langRef.current.contains(e.target as Node)) {
        setLangOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Pages that handle their own full layout
  const standalone = ["/map", "/articles", "/dashboard", "/login", "/signup"];
  const isStandalone = standalone.some((p) => pathname?.startsWith(p));

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function handleLangChange(code: LanguageCode) {
    setLocale(code);
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
            {NAV_ITEMS.map(({ href, labelKey, fallback, icon: Icon }) => (
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
                <span>{t(labelKey) !== labelKey.split(".").pop() ? t(labelKey) : fallback}</span>
              </Link>
            ))}
          </nav>

          {/* Right controls */}
          <div className="flex items-center space-x-1">
            {/* Theme toggle */}
            <button
              onClick={cycleTheme}
              className="flex items-center px-2 py-1.5 text-gray-500 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-md transition-colors"
              title={`Theme: ${theme}`}
            >
              {theme === "light" ? <Sun className="h-4 w-4" /> : theme === "dark" ? <Moon className="h-4 w-4" /> : <Monitor className="h-4 w-4" />}
            </button>

            {/* Language selector with globe icon and flag emoji */}
            <div className="relative" ref={langRef}>
              <button
                onClick={() => setLangOpen(!langOpen)}
                className="flex items-center space-x-1.5 px-2 py-1.5 text-xs text-gray-500 hover:bg-gray-50 rounded-md transition-colors"
                aria-label={t("label.language")}
              >
                {isTranslating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Globe className="h-3.5 w-3.5" />
                )}
                <span className="uppercase font-semibold">{locale}</span>
              </button>
              {langOpen && (
                <div className="absolute right-0 top-full mt-1 w-52 bg-white border border-gray-200 rounded-lg shadow-xl z-50 max-h-80 overflow-y-auto py-1">
                  {SUPPORTED_LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      onClick={() => handleLangChange(lang.code)}
                      className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2.5 transition-colors ${
                        locale === lang.code
                          ? "bg-teal-50 text-teal-700 font-medium"
                          : "text-gray-700"
                      }`}
                    >
                      <span className="text-base w-6 text-center">{getFlagEmoji(lang.flag)}</span>
                      <span className="flex-1">{lang.name}</span>
                      <span className="text-[10px] text-gray-400 uppercase font-mono">{lang.code}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Analytics link — gated to authenticated users; backend enforces admin role */}
            {isLoggedIn && (
              <Link
                href="/admin/analytics"
                className="hidden md:flex items-center px-2 py-1.5 text-gray-500 hover:bg-gray-50 rounded-md transition-colors"
                title={t("nav.analytics")}
              >
                <BarChart3 className="h-4 w-4" />
              </Link>
            )}

            {/* About */}
            <Link
              href="/about"
              className="hidden md:flex items-center px-2 py-1.5 text-gray-500 hover:bg-gray-50 rounded-md transition-colors"
              title={t("nav.about")}
            >
              <Info className="h-4 w-4" />
            </Link>

            {/* Auth: Sign In / User Menu */}
            {!authLoading && (
              <>
                {isLoggedIn && user ? (
                  <div className="relative hidden md:block" ref={userMenuRef}>
                    <button
                      onClick={() => setUserMenuOpen(!userMenuOpen)}
                      className="flex items-center space-x-2 px-2 py-1 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      <div className="w-7 h-7 rounded-full bg-gradient-to-br from-teal-500 to-emerald-500 flex items-center justify-center text-white text-xs font-bold">
                        {user.full_name?.charAt(0)?.toUpperCase() || "U"}
                      </div>
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${TIER_COLORS[user.subscription_tier] || TIER_COLORS.freemium}`}>
                        {TIER_LABELS[user.subscription_tier] || "Free"}
                      </span>
                    </button>
                    {userMenuOpen && (
                      <div className="absolute right-0 top-full mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-xl z-50 py-1">
                        <div className="px-4 py-2.5 border-b border-gray-100">
                          <p className="text-sm font-semibold text-gray-900 truncate">{user.full_name}</p>
                          <p className="text-xs text-gray-500 truncate">{user.email}</p>
                        </div>
                        <Link href="/dashboard" onClick={() => setUserMenuOpen(false)} className="flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                          <LayoutDashboard className="h-4 w-4 text-gray-400" />
                          {t("nav.dashboard")}
                        </Link>
                        <Link href="/feed" onClick={() => setUserMenuOpen(false)} className="flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                          <Rss className="h-4 w-4 text-gray-400" />
                          {t("nav.my_feed")}
                        </Link>
                        <Link href="/dashboard/settings" onClick={() => setUserMenuOpen(false)} className="flex items-center gap-2.5 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                          <Settings className="h-4 w-4 text-gray-400" />
                          {t("nav.settings")}
                        </Link>
                        <div className="border-t border-gray-100 mt-1 pt-1">
                          <button
                            onClick={() => { setUserMenuOpen(false); logout(); }}
                            className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                          >
                            <LogOut className="h-4 w-4" />
                            {t("nav.sign_out")}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="hidden md:flex items-center space-x-1.5">
                    <Link
                      href="/login"
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-md transition-colors font-medium"
                    >
                      <LogIn className="h-4 w-4" />
                      {t("nav.sign_in")}
                    </Link>
                    <Link
                      href="/signup"
                      className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white bg-teal-600 hover:bg-teal-700 rounded-md transition-colors font-medium"
                    >
                      <UserPlus className="h-4 w-4" />
                      {t("nav.sign_up")}
                    </Link>
                  </div>
                )}
              </>
            )}

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
            {NAV_ITEMS.map(({ href, labelKey, fallback, icon: Icon }) => (
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
                <span>{t(labelKey) !== labelKey.split(".").pop() ? t(labelKey) : fallback}</span>
              </Link>
            ))}
            <div className="border-t border-gray-100 mt-2 pt-2">
              {isLoggedIn && (
                <Link href="/admin/analytics" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                  <BarChart3 className="h-5 w-5" />
                  <span>{t("nav.analytics")}</span>
                </Link>
              )}
              <Link href="/about" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                <Info className="h-5 w-5" />
                <span>{t("nav.about")}</span>
              </Link>
            </div>
            {/* Mobile auth section */}
            {!authLoading && (
              <div className="border-t border-gray-100 mt-2 pt-2">
                {isLoggedIn && user ? (
                  <>
                    <div className="px-3 py-2 mb-1">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-teal-500 to-emerald-500 flex items-center justify-center text-white text-xs font-bold">
                          {user.full_name?.charAt(0)?.toUpperCase() || "U"}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-gray-900 truncate">{user.full_name}</p>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${TIER_COLORS[user.subscription_tier] || TIER_COLORS.freemium}`}>
                            {TIER_LABELS[user.subscription_tier] || "Free"}
                          </span>
                        </div>
                      </div>
                    </div>
                    <Link href="/dashboard" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                      <LayoutDashboard className="h-5 w-5" />
                      <span>{t("nav.dashboard")}</span>
                    </Link>
                    <Link href="/feed" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                      <Rss className="h-5 w-5" />
                      <span>{t("nav.my_feed")}</span>
                    </Link>
                    <button
                      onClick={logout}
                      className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-red-600 hover:bg-red-50"
                    >
                      <LogOut className="h-5 w-5" />
                      <span>{t("nav.sign_out")}</span>
                    </button>
                  </>
                ) : (
                  <>
                    <Link href="/login" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50">
                      <LogIn className="h-5 w-5" />
                      <span>{t("nav.sign_in")}</span>
                    </Link>
                    <Link href="/signup" className="flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-white bg-teal-600 hover:bg-teal-700 mt-1">
                      <UserPlus className="h-5 w-5" />
                      <span>{t("nav.sign_up")}</span>
                    </Link>
                  </>
                )}
              </div>
            )}
          </nav>
        )}
      </div>
    </header>
  );
}
