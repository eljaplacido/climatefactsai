"use client";

import { useState } from "react";
import {
  User,
  Bell,
  Languages,
  Shield,
  Loader2,
  Download,
  Trash2,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

interface NotificationPrefs {
  email_daily_digest: boolean;
  email_breaking_alerts: boolean;
  email_weekly_report: boolean;
  push_new_articles: boolean;
}

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "fi", label: "Suomi (Finnish)" },
  { code: "sv", label: "Svenska (Swedish)" },
  { code: "de", label: "Deutsch (German)" },
  { code: "fr", label: "Francais (French)" },
  { code: "es", label: "Espanol (Spanish)" },
];

export default function SettingsPage() {
  const { user, token } = useAuth();

  const [notifications, setNotifications] = useState<NotificationPrefs>({
    email_daily_digest: true,
    email_breaking_alerts: true,
    email_weekly_report: false,
    push_new_articles: false,
  });
  const [language, setLanguage] = useState("en");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteText, setDeleteText] = useState("");
  const [deleting, setDeleting] = useState(false);

  function toggleNotification(key: keyof NotificationPrefs) {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`${API_BASE}/api/user/preferences`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ notifications, language }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch {
      // Silently handle - preferences are best-effort
    } finally {
      setSaving(false);
    }
  }

  async function handleExportData() {
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE}/api/user/export-data`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "clilens-data-export.json";
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch {
      // Best-effort export
    } finally {
      setExporting(false);
    }
  }

  async function handleDeleteAccount() {
    if (deleteText !== "DELETE") return;
    setDeleting(true);
    try {
      await fetch(`${API_BASE}/api/user/account`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      window.location.href = "/";
    } catch {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage your account preferences and privacy settings.
        </p>
      </div>

      {/* Profile Section */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <User className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Profile</h2>
            <p className="text-xs text-gray-500">
              Your account information
            </p>
          </div>
        </div>

        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              Full name
            </label>
            <input
              type="text"
              readOnly
              value={user?.full_name || ""}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">
              Email
            </label>
            <input
              type="email"
              readOnly
              value={user?.email || ""}
              className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-700 cursor-not-allowed"
            />
          </div>
        </div>
        <p className="text-xs text-gray-400 mt-3">
          Contact support to update your profile information.
        </p>
      </section>

      {/* Notification Preferences */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Bell className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Notifications
            </h2>
            <p className="text-xs text-gray-500">
              Choose what updates you receive
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {([
            {
              key: "email_daily_digest" as const,
              label: "Daily digest",
              desc: "Receive a summary of top climate news every morning",
            },
            {
              key: "email_breaking_alerts" as const,
              label: "Breaking alerts",
              desc: "Get notified about high-impact climate events",
            },
            {
              key: "email_weekly_report" as const,
              label: "Weekly report",
              desc: "A weekly intelligence brief with trends and analysis",
            },
            {
              key: "push_new_articles" as const,
              label: "New article alerts",
              desc: "Notifications when articles match your saved topics",
            },
          ]).map(({ key, label, desc }) => (
            <div
              key={key}
              className="flex items-center justify-between py-2"
            >
              <div>
                <p className="text-sm font-medium text-gray-800">{label}</p>
                <p className="text-xs text-gray-500">{desc}</p>
              </div>
              <button
                type="button"
                onClick={() => toggleNotification(key)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  notifications[key] ? "bg-teal-600" : "bg-gray-300"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform ${
                    notifications[key] ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Language */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Languages className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Language</h2>
            <p className="text-xs text-gray-500">
              Set your preferred display language
            </p>
          </div>
        </div>

        <select
          value={language}
          onChange={(e) => {
            setLanguage(e.target.value);
            setSaved(false);
          }}
          className="w-full sm:w-64 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-teal-500 focus:border-transparent outline-none"
        >
          {LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </section>

      {/* Save button */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="px-6 py-2.5 bg-teal-600 text-white rounded-lg font-medium text-sm hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
        >
          {saving && <Loader2 className="h-4 w-4 animate-spin" />}
          Save Preferences
        </button>
        {saved && (
          <span className="flex items-center gap-1.5 text-sm text-emerald-600">
            <CheckCircle2 className="h-4 w-4" />
            Saved
          </span>
        )}
      </div>

      {/* Data & Privacy */}
      <section className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="p-2 bg-teal-50 rounded-lg">
            <Shield className="h-5 w-5 text-teal-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Data & Privacy
            </h2>
            <p className="text-xs text-gray-500">
              Manage your data and account
            </p>
          </div>
        </div>

        <div className="space-y-4">
          {/* Export */}
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-sm font-medium text-gray-800">
                Export your data
              </p>
              <p className="text-xs text-gray-500">
                Download all your saved articles, search history, and
                preferences
              </p>
            </div>
            <button
              type="button"
              onClick={handleExportData}
              disabled={exporting}
              className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Export
            </button>
          </div>

          {/* Delete */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-red-700">
                  Delete account
                </p>
                <p className="text-xs text-gray-500">
                  Permanently delete your account and all associated data
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(!showDeleteConfirm)}
                className="flex items-center gap-2 px-4 py-2 border border-red-300 rounded-lg text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                <Trash2 className="h-4 w-4" />
                Delete
              </button>
            </div>

            {showDeleteConfirm && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <div className="flex items-start gap-2 mb-3">
                  <AlertTriangle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">
                    This action is <strong>irreversible</strong>. All your
                    data, saved articles, and search history will be
                    permanently deleted. Type <strong>DELETE</strong> to
                    confirm.
                  </p>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={deleteText}
                    onChange={(e) => setDeleteText(e.target.value)}
                    placeholder='Type "DELETE"'
                    className="flex-1 px-3 py-2 border border-red-300 rounded-lg text-sm focus:ring-2 focus:ring-red-500 focus:border-transparent outline-none"
                  />
                  <button
                    type="button"
                    onClick={handleDeleteAccount}
                    disabled={deleteText !== "DELETE" || deleting}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    {deleting && (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    )}
                    Confirm Delete
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
