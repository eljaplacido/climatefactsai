"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  History,
  Bookmark,
  CreditCard,
  Settings,
  Globe,
  LogOut,
  Menu,
  X,
  Crown,
} from "lucide-react";
import { useState } from "react";
import { useAuth, ProtectedRoute } from "@/lib/auth";

const SIDEBAR_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/dashboard/history", label: "History", icon: History, exact: false },
  { href: "/saves", label: "Saved", icon: Bookmark, exact: false },
  {
    href: "/dashboard/subscription",
    label: "Subscription",
    icon: CreditCard,
    exact: false,
  },
  { href: "/dashboard/settings", label: "Settings", icon: Settings, exact: false },
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

function DashboardSidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const tier = user?.subscription_tier || "freemium";

  function isActive(href: string, exact: boolean) {
    if (exact) return pathname === href;
    return pathname?.startsWith(href);
  }

  const navContent = (
    <>
      {/* User info */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-teal-500 to-emerald-500 flex items-center justify-center text-white font-bold text-sm">
            {user?.full_name?.charAt(0)?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 truncate">
              {user?.full_name || "User"}
            </p>
            <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          </div>
        </div>
        <div className="mt-2">
          <span
            className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${TIER_COLORS[tier]}`}
          >
            <Crown className="h-3 w-3" />
            {TIER_LABELS[tier] || tier}
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-0.5">
        {SIDEBAR_ITEMS.map(({ href, label, icon: Icon, exact }) => (
          <Link
            key={href}
            href={href}
            onClick={() => setMobileOpen(false)}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              isActive(href, exact)
                ? "bg-teal-50 text-teal-700 font-semibold"
                : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Bottom links */}
      <div className="p-3 border-t border-gray-200 space-y-0.5">
        <Link
          href="/"
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-50 hover:text-gray-900 transition-colors"
        >
          <Globe className="h-4 w-4" />
          Back to News
        </Link>
        <button
          onClick={() => {
            logout();
            window.location.href = "/";
          }}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-red-600 hover:bg-red-50 transition-colors"
        >
          <LogOut className="h-4 w-4" />
          Sign Out
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Mobile toggle */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <Link href="/dashboard" className="flex items-center gap-2">
          <div className="bg-gradient-to-br from-teal-600 to-emerald-600 p-1.5 rounded-lg">
            <Globe className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-gray-900">Dashboard</span>
        </Link>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-2 text-gray-500 hover:bg-gray-50 rounded-lg"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-30 bg-black/30"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 z-30 h-full w-64 bg-white border-r border-gray-200 flex flex-col transition-transform lg:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } lg:static lg:flex`}
      >
        {/* Desktop logo */}
        <div className="hidden lg:flex items-center gap-2 p-4 border-b border-gray-100">
          <div className="bg-gradient-to-br from-teal-600 to-emerald-600 p-1.5 rounded-lg">
            <Globe className="h-5 w-5 text-white" />
          </div>
          <div>
            <p className="text-base font-bold text-gray-900 leading-tight">
              Climatefacts.ai
            </p>
            <p className="text-[10px] text-gray-400 leading-tight -mt-0.5">
              Dashboard
            </p>
          </div>
        </div>
        {navContent}
      </aside>
    </>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <div className="flex min-h-screen bg-gray-50">
        <DashboardSidebar />
        <main className="flex-1 lg:ml-0 pt-14 lg:pt-0">
          <div className="max-w-6xl mx-auto p-4 sm:p-6 lg:p-8">{children}</div>
        </main>
      </div>
    </ProtectedRoute>
  );
}
