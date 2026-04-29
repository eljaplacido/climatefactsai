"use client";

import { useEffect, useRef, useCallback } from "react";
import { useI18n } from "@/lib/i18n-context";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

// Global translation cache persisted in sessionStorage
const cache: Record<string, string> = {};
const pendingTexts: Map<string, ((v: string) => void)[]> = new Map();
let batchTimer: ReturnType<typeof setTimeout> | null = null;

function getCacheKey(text: string, lang: string) {
  return `${lang}:${text.slice(0, 120)}`;
}

// Batch translate: collects texts for 200ms then sends one request
async function batchTranslate(texts: string[], targetLang: string): Promise<Record<string, string>> {
  if (!texts.length || targetLang === "en") return {};

  // Dedupe
  const unique = Array.from(new Set(texts));
  const results: Record<string, string> = {};

  // Check cache first
  const uncached: string[] = [];
  for (const t of unique) {
    const ck = getCacheKey(t, targetLang);
    if (cache[ck]) {
      results[t] = cache[ck];
    } else {
      uncached.push(t);
    }
  }

  if (!uncached.length) return results;

  // Send as one concatenated request (separator: \n---\n)
  const combined = uncached.join("\n---SPLIT---\n");
  try {
    const res = await fetch(`${API_BASE}/api/translate/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: combined.slice(0, 8000), target_language: targetLang }),
    });
    if (!res.ok) return results;
    const data = await res.json();
    const translated = (data.translated_text || "").split("\n---SPLIT---\n");

    uncached.forEach((orig, i) => {
      const tr = (translated[i] || orig).trim();
      results[orig] = tr;
      cache[getCacheKey(orig, targetLang)] = tr;
    });
  } catch {
    // On failure, return originals
    uncached.forEach((t) => { results[t] = t; });
  }

  return results;
}

function isTranslatable(node: Node): boolean {
  const el = node.parentElement;
  if (!el) return false;
  // Skip script, style, SVG, input, code, pre, textarea
  const tag = el.tagName;
  if (["SCRIPT", "STYLE", "SVG", "INPUT", "TEXTAREA", "CODE", "PRE", "NOSCRIPT"].includes(tag)) return false;
  // Skip already-translated nodes
  if (el.closest("[data-notranslate]")) return false;
  // Skip very short text (likely icons/symbols)
  const text = (node.textContent || "").trim();
  if (text.length < 4 || /^[\d\s.,;:!?%$#@&*+\-=/<>(){}\[\]|\\]+$/.test(text)) return false;
  return true;
}

/**
 * Whole-page translator component. Placed in layout.tsx.
 * When locale changes from 'en', walks the DOM and translates all visible text nodes.
 * Uses MutationObserver to catch dynamically added content.
 */
export default function PageTranslator() {
  const { locale } = useI18n();
  const prevLocale = useRef("en");
  const originals = useRef<Map<Node, string>>(new Map());
  const observerRef = useRef<MutationObserver | null>(null);

  const translateNode = useCallback(async (node: Text, lang: string) => {
    const text = (node.textContent || "").trim();
    if (!text || text.length < 4) return;

    const ck = getCacheKey(text, lang);
    if (cache[ck]) {
      if (!originals.current.has(node)) originals.current.set(node, text);
      node.textContent = cache[ck];
      return;
    }

    // Queue for batch
    if (!pendingTexts.has(text)) {
      pendingTexts.set(text, []);
    }
    pendingTexts.get(text)!.push((translated) => {
      if (!originals.current.has(node)) originals.current.set(node, text);
      node.textContent = translated;
    });

    // Debounce batch send
    if (batchTimer) clearTimeout(batchTimer);
    batchTimer = setTimeout(async () => {
      const texts = [...pendingTexts.keys()];
      const callbacks = new Map(pendingTexts);
      pendingTexts.clear();
      const results = await batchTranslate(texts, lang);
      for (const [orig, cbs] of callbacks) {
        const translated = results[orig] || orig;
        cbs.forEach((cb) => cb(translated));
      }
    }, 300);
  }, []);

  const translatePage = useCallback((lang: string) => {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode: (node) =>
          isTranslatable(node) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT,
      }
    );

    const nodes: Text[] = [];
    while (walker.nextNode()) {
      nodes.push(walker.currentNode as Text);
    }

    // Translate in chunks to avoid blocking UI
    let i = 0;
    function translateChunk() {
      const end = Math.min(i + 30, nodes.length);
      for (; i < end; i++) {
        translateNode(nodes[i], lang);
      }
      if (i < nodes.length) {
        requestAnimationFrame(translateChunk);
      }
    }
    translateChunk();
  }, [translateNode]);

  const restoreOriginals = useCallback(() => {
    originals.current.forEach((original, node) => {
      if (node.textContent !== original) {
        node.textContent = original;
      }
    });
    originals.current.clear();
  }, []);

  useEffect(() => {
    if (locale === "en") {
      // Restore to English
      restoreOriginals();
      prevLocale.current = "en";
      return;
    }

    if (locale !== prevLocale.current) {
      // First restore originals if switching between non-en languages
      if (prevLocale.current !== "en") {
        restoreOriginals();
      }
      prevLocale.current = locale;

      // Wait for DOM to settle then translate
      setTimeout(() => translatePage(locale), 500);
    }
  }, [locale, translatePage, restoreOriginals]);

  // MutationObserver for dynamically added content
  useEffect(() => {
    if (locale === "en") return;

    observerRef.current = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
          if (node.nodeType === Node.TEXT_NODE && isTranslatable(node)) {
            translateNode(node as Text, locale);
          } else if (node.nodeType === Node.ELEMENT_NODE) {
            const walker = document.createTreeWalker(
              node, NodeFilter.SHOW_TEXT,
              { acceptNode: (n) => isTranslatable(n) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT }
            );
            while (walker.nextNode()) {
              translateNode(walker.currentNode as Text, locale);
            }
          }
        }
      }
    });

    observerRef.current.observe(document.body, {
      childList: true,
      subtree: true,
    });

    return () => {
      observerRef.current?.disconnect();
    };
  }, [locale, translateNode]);

  return null; // Invisible component
}
