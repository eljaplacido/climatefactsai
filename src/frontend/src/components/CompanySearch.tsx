"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Search, ChevronDown, Loader2, Building2 } from "lucide-react";

interface Company {
  company_id: string;
  name: string;
  ticker: string;
  country_code?: string;
  sector_nace?: string;
}

interface CompanySearchProps {
  onSelect: (company: Company) => void;
  placeholder?: string;
  excludeTicker?: string;
  className?: string;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5400";

export default function CompanySearch({
  onSelect,
  placeholder = "Search companies...",
  excludeTicker,
  className = "",
}: CompanySearchProps) {
  const [query, setQuery] = useState("");
  const [companies, setCompanies] = useState<Company[]>([]);
  const [filtered, setFiltered] = useState<Company[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  // Fetch full company list on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE_URL}/api/companies?limit=200&has_climate_data=true`, {
          headers: { Accept: "application/json" },
        });
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled && Array.isArray(data.companies)) {
          const mapped: Company[] = data.companies
            .filter((c: Company) => c.ticker && c.name)
            .filter((c: Company) => !excludeTicker || c.ticker !== excludeTicker);
          setCompanies(mapped);
        }
      } catch {
        // Degrade silently — user can type ticker manually
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [excludeTicker]);

  // Filter as user types
  useEffect(() => {
    if (!query.trim()) {
      setFiltered(companies.slice(0, 20));
      return;
    }
    const q = query.toLowerCase();
    const results = companies
      .filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.ticker.toLowerCase().includes(q) ||
          (c.sector_nace && c.sector_nace.toLowerCase().includes(q))
      )
      .slice(0, 30);
    setFiltered(results);
  }, [query, companies]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, -1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (selectedIndex >= 0 && selectedIndex < filtered.length) {
          handleSelect(filtered[selectedIndex]);
        }
      } else if (e.key === "Escape") {
        setIsOpen(false);
        inputRef.current?.blur();
      }
    },
    [selectedIndex, filtered]
  );

  const handleSelect = (company: Company) => {
    setQuery(company.ticker);
    setIsOpen(false);
    setSelectedIndex(-1);
    onSelect(company);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    setIsOpen(true);
    setSelectedIndex(-1);
  };

  return (
    <div className={`relative ${className}`}>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => query.trim() && setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-400"
          aria-autocomplete="list"
          role="combobox"
          aria-expanded={isOpen}
        />
        {loading && (
          <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 animate-spin" />
        )}
      </div>

      {isOpen && filtered.length > 0 && (
        <ul
          ref={listRef}
          className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-y-auto"
          role="listbox"
        >
          {filtered.map((company, idx) => (
            <li
              key={company.company_id || company.ticker}
              role="option"
              aria-selected={idx === selectedIndex}
              onClick={() => handleSelect(company)}
              className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer text-sm border-b border-gray-100 last:border-b-0 ${
                idx === selectedIndex
                  ? "bg-teal-50 text-teal-900"
                  : "hover:bg-gray-50 text-gray-700"
              }`}
            >
              <Building2 className="h-4 w-4 text-gray-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{company.name}</div>
                {company.sector_nace && (
                  <div className="text-xs text-gray-400 truncate">{company.sector_nace}</div>
                )}
              </div>
              <span className="text-xs font-mono font-semibold text-teal-600 bg-teal-50 px-2 py-0.5 rounded shrink-0">
                {company.ticker}
              </span>
            </li>
          ))}
        </ul>
      )}

      {isOpen && query.trim() && filtered.length === 0 && !loading && (
        <div className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-lg shadow-lg p-4 text-sm text-gray-500 text-center">
          No companies found matching &ldquo;{query}&rdquo;
        </div>
      )}

      {/* Click outside to close */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
      )}
    </div>
  );
}
