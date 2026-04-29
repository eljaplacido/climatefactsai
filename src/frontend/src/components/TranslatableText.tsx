"use client";

import { useState, useEffect, useRef } from "react";
import { useI18n } from "@/lib/i18n-context";

interface TranslatableTextProps {
  text: string;
  as?: keyof JSX.IntrinsicElements;
  className?: string;
  maxLength?: number;
}

/**
 * Wraps text content and auto-translates it when the user switches language.
 * Caches translations in memory to avoid redundant API calls.
 */
const translationCache: Record<string, string> = {};

export default function TranslatableText({
  text,
  as: Tag = "span",
  className,
  maxLength = 2000,
}: TranslatableTextProps) {
  const { locale, translateText } = useI18n();
  const [translated, setTranslated] = useState(text);
  const [loading, setLoading] = useState(false);
  const prevLocale = useRef(locale);

  useEffect(() => {
    if (locale === "en" || !text || text.length < 3) {
      setTranslated(text);
      return;
    }

    const cacheKey = `${locale}:${text.slice(0, 100)}`;
    if (translationCache[cacheKey]) {
      setTranslated(translationCache[cacheKey]);
      return;
    }

    let cancelled = false;
    setLoading(true);

    const truncated = text.slice(0, maxLength);
    translateText(truncated, locale).then((result) => {
      if (!cancelled) {
        setTranslated(result);
        translationCache[cacheKey] = result;
        setLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, [locale, text, translateText, maxLength]);

  // Reset when text changes
  useEffect(() => {
    if (locale === "en") setTranslated(text);
  }, [text, locale]);

  return (
    <Tag className={className} style={loading ? { opacity: 0.7 } : undefined}>
      {translated}
    </Tag>
  );
}

/**
 * Hook for translating text in components.
 * Returns [translatedText, isLoading].
 */
export function useAutoTranslate(text: string): [string, boolean] {
  const { locale, translateText } = useI18n();
  const [translated, setTranslated] = useState(text);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (locale === "en" || !text || text.length < 3) {
      setTranslated(text);
      return;
    }

    const cacheKey = `${locale}:${text.slice(0, 100)}`;
    if (translationCache[cacheKey]) {
      setTranslated(translationCache[cacheKey]);
      return;
    }

    let cancelled = false;
    setLoading(true);

    translateText(text.slice(0, 2000), locale).then((result) => {
      if (!cancelled) {
        setTranslated(result);
        translationCache[cacheKey] = result;
        setLoading(false);
      }
    });

    return () => { cancelled = true; };
  }, [locale, text, translateText]);

  return [translated, loading];
}
