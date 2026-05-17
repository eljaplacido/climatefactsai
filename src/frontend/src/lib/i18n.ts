/**
 * Lightweight i18n system for Climatefacts.ai
 *
 * Supports 10+ languages with server-side translation loading.
 * Falls back to English for missing keys.
 * Detects browser language preference on first load.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English", flag: "GB" },
  { code: "fi", name: "Suomi", flag: "FI" },
  { code: "de", name: "Deutsch", flag: "DE" },
  { code: "fr", name: "Francais", flag: "FR" },
  { code: "es", name: "Espanol", flag: "ES" },
  { code: "sv", name: "Svenska", flag: "SE" },
  { code: "no", name: "Norsk", flag: "NO" },
  { code: "da", name: "Dansk", flag: "DK" },
  { code: "nl", name: "Nederlands", flag: "NL" },
  { code: "it", name: "Italiano", flag: "IT" },
  { code: "pt", name: "Portugues", flag: "BR" },
  { code: "pl", name: "Polski", flag: "PL" },
  { code: "zh", name: "中文", flag: "CN" },
  { code: "hi", name: "हिन्दी", flag: "IN" },
  { code: "ar", name: "العربية", flag: "SA", rtl: true },
  { code: "ru", name: "Русский", flag: "RU" },
  { code: "ja", name: "日本語", flag: "JP" },
] as const;

export type LanguageCode = (typeof SUPPORTED_LANGUAGES)[number]["code"];

// Flag emoji lookup for language codes
const FLAG_EMOJIS: Record<string, string> = {
  GB: "🇬🇧", FI: "🇫🇮", DE: "🇩🇪", FR: "🇫🇷", ES: "🇪🇸",
  SE: "🇸🇪", NO: "🇳🇴", DK: "🇩🇰", NL: "🇳🇱", IT: "🇮🇹",
  BR: "🇧🇷", PL: "🇵🇱", CN: "🇨🇳", IN: "🇮🇳", SA: "🇸🇦",
  RU: "🇷🇺", JP: "🇯🇵",
};

export function getFlagEmoji(flagCode: string): string {
  return FLAG_EMOJIS[flagCode] || "";
}

// Translation cache
let translationCache: Record<string, Record<string, string>> = {};
let currentLanguage: LanguageCode = "en";

export function detectBrowserLanguage(): LanguageCode {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem("clilens_language");
  if (stored && SUPPORTED_LANGUAGES.some((l) => l.code === stored)) {
    return stored as LanguageCode;
  }
  const browserLang = navigator.language?.slice(0, 2).toLowerCase();
  const match = SUPPORTED_LANGUAGES.find((l) => l.code === browserLang);
  return match ? match.code : "en";
}

export async function loadTranslations(lang: LanguageCode): Promise<Record<string, string>> {
  if (translationCache[lang]) return translationCache[lang];

  try {
    const res = await fetch(`${API_BASE}/api/translations/ui/${lang}`);
    if (res.ok) {
      const data = await res.json();
      translationCache[lang] = data.translations || {};
      return translationCache[lang];
    }
  } catch {
    // Fall back to empty (English keys used as-is)
  }
  return {};
}

export function setLanguage(lang: LanguageCode) {
  currentLanguage = lang;
  if (typeof window !== "undefined") {
    localStorage.setItem("clilens_language", lang);
    document.documentElement.lang = lang;
    const isRtl = SUPPORTED_LANGUAGES.find((l) => l.code === lang && "rtl" in l);
    document.documentElement.dir = isRtl ? "rtl" : "ltr";
  }
}

export function t(key: string, fallback?: string): string {
  const translations = translationCache[currentLanguage];
  if (translations && translations[key]) return translations[key];
  // Fall back to English cache
  const enTranslations = translationCache["en"];
  if (enTranslations && enTranslations[key]) return enTranslations[key];
  // Fall back to provided default or key itself
  return fallback || key.split(".").pop() || key;
}

export function getCurrentLanguage(): LanguageCode {
  return currentLanguage;
}

export function isRtl(): boolean {
  return currentLanguage === "ar";
}
