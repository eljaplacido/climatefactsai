"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface ViewContextValue {
  route?: string;
  articleId?: string;
  countryCode?: string;
  analysisId?: string;
  deepSearchQuery?: string;
  deepSearchCompare?: { query_a: string; query_b: string };
  compareCountries?: [string, string];
  sourceId?: string;
  label?: string;
}

type ViewContextType = {
  view: ViewContextValue;
  setView: (partial: Partial<ViewContextValue>) => void;
  clearKey: (key: keyof ViewContextValue) => void;
};

const ViewContext = createContext<ViewContextType>({
  view: {},
  setView: () => {},
  clearKey: () => {},
});

export function ViewContextProvider({ children }: { children: ReactNode }) {
  const [view, setViewState] = useState<ViewContextValue>({});

  const setView = useCallback((partial: Partial<ViewContextValue>) => {
    setViewState((prev) => ({ ...prev, ...partial }));
  }, []);

  const clearKey = useCallback((key: keyof ViewContextValue) => {
    setViewState((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  return (
    <ViewContext.Provider value={{ view, setView, clearKey }}>
      {children}
    </ViewContext.Provider>
  );
}

export function useViewContext() {
  return useContext(ViewContext);
}
