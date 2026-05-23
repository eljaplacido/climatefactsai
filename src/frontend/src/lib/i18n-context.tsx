"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import {
  SUPPORTED_LANGUAGES,
  detectBrowserLanguage,
  setLanguage as setLanguageUtil,
  loadTranslations,
  t as tUtil,
  getCurrentLanguage,
  type LanguageCode,
} from "./i18n";

export { SUPPORTED_LANGUAGES, type LanguageCode };

/* ---------- static UI translations dictionary ---------- */

const UI_TRANSLATIONS: Record<string, Record<string, string>> = {
  en: {
    "nav.news": "News",
    "nav.map": "Map",
    "nav.search": "Search",
    "nav.deep_search": "Deep Search",
    "nav.analyze": "Analyze",
    "nav.research": "Research",
    "nav.sources": "Sources",
    "nav.analytics": "Analytics",
    "nav.about": "About",
    "nav.sign_in": "Sign In",
    "nav.sign_up": "Sign Up",
    "nav.sign_out": "Sign Out",
    "nav.dashboard": "Dashboard",
    "nav.my_feed": "My Feed",
    "nav.settings": "Settings",
    "nav.suggest": "Suggest Source",
    "btn.send": "Send",
    "btn.cancel": "Cancel",
    "btn.close": "Close",
    "btn.save": "Save",
    "btn.load_more": "Load More",
    "btn.read_more": "Read More",
    "btn.back": "Back",
    "btn.translate": "Translate",
    "label.language": "Language",
    "label.search_placeholder": "Search articles...",
    "label.loading": "Loading...",
    "label.no_results": "No results found",
    "label.error": "An error occurred",
    "section.latest_news": "Latest News",
    "section.trending": "Trending",
    "section.fact_checks": "Fact Checks",
    "section.climate_data": "Climate Data",
    "section.transparency": "Transparency Report",
    "section.methodology": "Methodology",
    "section.reliability": "Reliability Breakdown",
    "section.confidence": "Confidence Intervals",
    "section.evidence": "Evidence Chains",
    "section.source_profile": "Source Profile",
    "chat.placeholder": "Ask about climate news, data, or trends...",
    "chat.analyzing": "Analyzing...",
    "chat.try_questions": "Try one of these questions",
    "transparency.not_analyzed": "Not yet analyzed",
    "transparency.data_unavailable": "Data not available",
    "transparency.partial": "This article has been partially analyzed",
    "transparency.scoring_legend": "Scoring: Green (>70%) = Strong, Amber (40-70%) = Moderate, Red (<40%) = Weak",
  },
  fi: {
    "nav.news": "Uutiset",
    "nav.map": "Kartta",
    "nav.search": "Haku",
    "nav.deep_search": "Syva haku",
    "nav.analyze": "Analysoi",
    "nav.research": "Tutkimus",
    "nav.sources": "Lahteet",
    "nav.analytics": "Analytiikka",
    "nav.about": "Tietoa",
    "nav.sign_in": "Kirjaudu",
    "nav.sign_up": "Rekisteroidy",
    "nav.sign_out": "Kirjaudu ulos",
    "nav.dashboard": "Hallintapaneeli",
    "nav.my_feed": "Oma syote",
    "nav.settings": "Asetukset",
    "nav.suggest": "Ehdota lahdetta",
    "btn.send": "Laheta",
    "btn.cancel": "Peruuta",
    "btn.close": "Sulje",
    "btn.save": "Tallenna",
    "btn.load_more": "Lataa lisaa",
    "btn.read_more": "Lue lisaa",
    "btn.back": "Takaisin",
    "btn.translate": "Kaanna",
    "label.language": "Kieli",
    "label.search_placeholder": "Hae artikkeleita...",
    "label.loading": "Ladataan...",
    "label.no_results": "Tuloksia ei loytynyt",
    "label.error": "Tapahtui virhe",
    "section.latest_news": "Viimeisimmat uutiset",
    "section.trending": "Suositut",
    "section.fact_checks": "Faktatarkistukset",
    "section.climate_data": "Ilmastotiedot",
    "section.transparency": "Avoimuusraportti",
    "chat.placeholder": "Kysy ilmastouutisista, datasta tai trendeista...",
    "chat.analyzing": "Analysoidaan...",
  },
  de: {
    "nav.news": "Nachrichten",
    "nav.map": "Karte",
    "nav.search": "Suche",
    "nav.deep_search": "Tiefensuche",
    "nav.analyze": "Analysieren",
    "nav.research": "Forschung",
    "nav.sources": "Quellen",
    "nav.analytics": "Analytik",
    "nav.about": "Info",
    "nav.sign_in": "Anmelden",
    "nav.sign_up": "Registrieren",
    "nav.sign_out": "Abmelden",
    "nav.dashboard": "Dashboard",
    "nav.settings": "Einstellungen",
    "nav.suggest": "Quelle vorschlagen",
    "btn.send": "Senden",
    "btn.cancel": "Abbrechen",
    "btn.close": "Schliessen",
    "btn.save": "Speichern",
    "btn.load_more": "Mehr laden",
    "btn.read_more": "Weiterlesen",
    "btn.back": "Zuruck",
    "btn.translate": "Ubersetzen",
    "label.language": "Sprache",
    "label.loading": "Laden...",
    "label.no_results": "Keine Ergebnisse gefunden",
    "chat.placeholder": "Fragen zu Klimanachrichten, Daten oder Trends...",
  },
  fr: {
    "nav.news": "Actualites",
    "nav.map": "Carte",
    "nav.search": "Recherche",
    "nav.deep_search": "Recherche approfondie",
    "nav.analyze": "Analyser",
    "nav.research": "Recherche",
    "nav.sources": "Sources",
    "nav.analytics": "Analytique",
    "nav.about": "A propos",
    "nav.sign_in": "Connexion",
    "nav.sign_up": "Inscription",
    "nav.sign_out": "Deconnexion",
    "nav.dashboard": "Tableau de bord",
    "nav.settings": "Parametres",
    "nav.suggest": "Suggerer une source",
    "btn.send": "Envoyer",
    "btn.cancel": "Annuler",
    "btn.close": "Fermer",
    "btn.save": "Sauvegarder",
    "btn.load_more": "Charger plus",
    "btn.read_more": "Lire la suite",
    "btn.back": "Retour",
    "btn.translate": "Traduire",
    "label.language": "Langue",
    "label.loading": "Chargement...",
    "label.no_results": "Aucun resultat",
    "chat.placeholder": "Questions sur le climat, les donnees ou les tendances...",
  },
  es: {
    "nav.news": "Noticias",
    "nav.map": "Mapa",
    "nav.search": "Buscar",
    "nav.deep_search": "Busqueda profunda",
    "nav.analyze": "Analizar",
    "nav.research": "Investigacion",
    "nav.sources": "Fuentes",
    "nav.analytics": "Analitica",
    "nav.about": "Acerca de",
    "nav.sign_in": "Iniciar sesion",
    "nav.sign_up": "Registrarse",
    "nav.sign_out": "Cerrar sesion",
    "nav.dashboard": "Panel",
    "nav.settings": "Configuracion",
    "nav.suggest": "Sugerir fuente",
    "btn.send": "Enviar",
    "btn.cancel": "Cancelar",
    "btn.close": "Cerrar",
    "btn.save": "Guardar",
    "btn.load_more": "Cargar mas",
    "btn.read_more": "Leer mas",
    "btn.back": "Volver",
    "btn.translate": "Traducir",
    "label.language": "Idioma",
    "label.loading": "Cargando...",
    "label.no_results": "Sin resultados",
    "chat.placeholder": "Preguntas sobre noticias climaticas, datos o tendencias...",
  },
  sv: {
    "nav.news": "Nyheter",
    "nav.map": "Karta",
    "nav.search": "Sok",
    "nav.analyze": "Analysera",
    "nav.research": "Forskning",
    "nav.sources": "Kallor",
    "nav.sign_in": "Logga in",
    "nav.sign_up": "Registrera",
    "nav.sign_out": "Logga ut",
    "nav.suggest": "Foreslå kalla",
    "label.language": "Sprak",
    "label.loading": "Laddar...",
  },
  no: {
    "nav.news": "Nyheter",
    "nav.map": "Kart",
    "nav.search": "Sok",
    "nav.analyze": "Analyser",
    "nav.research": "Forskning",
    "nav.sources": "Kilder",
    "nav.sign_in": "Logg inn",
    "nav.sign_up": "Registrer",
    "nav.sign_out": "Logg ut",
    "nav.suggest": "Foreslå kilde",
    "label.language": "Sprak",
    "label.loading": "Laster...",
  },
  da: {
    "nav.news": "Nyheder",
    "nav.map": "Kort",
    "nav.search": "Sog",
    "nav.analyze": "Analyser",
    "nav.research": "Forskning",
    "nav.sources": "Kilder",
    "nav.sign_in": "Log ind",
    "nav.sign_up": "Registrer",
    "nav.sign_out": "Log ud",
    "nav.suggest": "Foreslå kilde",
    "label.language": "Sprog",
    "label.loading": "Indlaeser...",
  },
  nl: {
    "nav.news": "Nieuws",
    "nav.map": "Kaart",
    "nav.search": "Zoeken",
    "nav.analyze": "Analyseren",
    "nav.research": "Onderzoek",
    "nav.sources": "Bronnen",
    "nav.sign_in": "Inloggen",
    "nav.sign_up": "Registreren",
    "nav.sign_out": "Uitloggen",
    "nav.suggest": "Bron voorstellen",
    "label.language": "Taal",
    "label.loading": "Laden...",
  },
  it: {
    "nav.news": "Notizie",
    "nav.map": "Mappa",
    "nav.search": "Cerca",
    "nav.analyze": "Analizza",
    "nav.research": "Ricerca",
    "nav.sources": "Fonti",
    "nav.sign_in": "Accedi",
    "nav.sign_up": "Registrati",
    "nav.sign_out": "Esci",
    "nav.suggest": "Suggerisci fonte",
    "label.language": "Lingua",
    "label.loading": "Caricamento...",
  },
  pt: {
    "nav.news": "Noticias",
    "nav.map": "Mapa",
    "nav.search": "Pesquisar",
    "nav.analyze": "Analisar",
    "nav.research": "Pesquisa",
    "nav.sources": "Fontes",
    "nav.sign_in": "Entrar",
    "nav.sign_up": "Cadastrar",
    "nav.sign_out": "Sair",
    "nav.suggest": "Sugerir fonte",
    "label.language": "Idioma",
    "label.loading": "Carregando...",
  },
  pl: {
    "nav.news": "Wiadomosci",
    "nav.map": "Mapa",
    "nav.search": "Szukaj",
    "nav.analyze": "Analizuj",
    "nav.research": "Badania",
    "nav.sources": "Zrodla",
    "nav.sign_in": "Zaloguj sie",
    "nav.sign_up": "Zarejestruj sie",
    "nav.sign_out": "Wyloguj sie",
    "nav.suggest": "Zaproponuj zrodlo",
    "label.language": "Jezyk",
    "label.loading": "Ladowanie...",
  },
};

/* ---------- API base ---------- */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

/* ---------- Context ---------- */

interface I18nContextValue {
  locale: string;
  setLocale: (locale: string) => void;
  t: (key: string) => string;
  translateText: (text: string, targetLang: string) => Promise<string>;
  isTranslating: boolean;
}

const I18nContext = createContext<I18nContextValue | null>(null);

/* ---------- Provider ---------- */

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<string>("en");
  const [isTranslating, setIsTranslating] = useState(false);

  // Initialize from localStorage / browser detection
  useEffect(() => {
    const detected = detectBrowserLanguage();
    setLocaleState(detected);
    setLanguageUtil(detected);
    loadTranslations(detected);
  }, []);

  const setLocale = useCallback((newLocale: string) => {
    setLocaleState(newLocale);
    setLanguageUtil(newLocale as LanguageCode);
    loadTranslations(newLocale as LanguageCode);
  }, []);

  const t = useCallback(
    (key: string): string => {
      // First check our static dictionary
      const langDict = UI_TRANSLATIONS[locale];
      if (langDict && langDict[key]) return langDict[key];
      // Fall back to English static dict
      const enDict = UI_TRANSLATIONS["en"];
      if (enDict && enDict[key]) return enDict[key];
      // Fall back to the existing i18n.ts utility (server translations)
      const fromServer = tUtil(key);
      if (fromServer !== key.split(".").pop()) return fromServer;
      // Final fallback: return the last segment of the key
      return key.split(".").pop() || key;
    },
    [locale]
  );

  const translateText = useCallback(
    async (text: string, targetLang: string): Promise<string> => {
      if (targetLang === "en") return text;
      setIsTranslating(true);
      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("clilens_token")
            : null;
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const res = await fetch(`${API_BASE}/api/translate/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ text, target_language: targetLang }),
        });

        if (!res.ok) {
          throw new Error(`Translation API error: ${res.status}`);
        }

        const data = await res.json();
        return data.translated_text || data.translation || text;
      } catch {
        // Return original text on failure
        return text;
      } finally {
        setIsTranslating(false);
      }
    },
    []
  );

  return (
    <I18nContext.Provider
      value={{ locale, setLocale, t, translateText, isTranslating }}
    >
      {children}
    </I18nContext.Provider>
  );
}

/* ---------- Hook ---------- */

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    // Provide a safe fallback for components outside the provider
    return {
      locale: "en",
      setLocale: () => {},
      t: (key: string) => {
        const enDict = UI_TRANSLATIONS["en"];
        if (enDict && enDict[key]) return enDict[key];
        return key.split(".").pop() || key;
      },
      translateText: async (text: string) => text,
      isTranslating: false,
    };
  }
  return ctx;
}
