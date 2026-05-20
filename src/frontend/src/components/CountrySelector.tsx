"use client";

import { useEffect, useMemo, useState } from "react";
import { Globe, Search } from "lucide-react";
import { api } from "../lib/api";
import type { Country } from "../types";

interface CountrySelectorProps {
  value: string | null;
  onChange: (country: string | null) => void;
  label?: string;
  allOptionLabel?: string;
  showAllOption?: boolean;
  searchable?: boolean;
  showSelectedChip?: boolean;
  theme?: "light" | "dark";
  className?: string;
}

function CountrySelector({
  value,
  onChange,
  label = "Country",
  allOptionLabel = "All EU countries",
  showAllOption = true,
  searchable = false,
  showSelectedChip = true,
  theme = "light",
  className,
}: CountrySelectorProps) {
  const [countries, setCountries] = useState<Country[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const loadCountries = async () => {
      try {
        const data = await api.getCountries();
        setCountries(data);
      } catch (error) {
        console.error("Error loading countries", error);
      } finally {
        setLoading(false);
      }
    };

    loadCountries();
  }, []);

  const selectedCountry = countries.find((country) => country.country_code === value);

  const filteredCountries = useMemo(() => {
    if (!searchQuery.trim()) return countries;
    const q = searchQuery.trim().toLowerCase();
    return countries.filter((country) => {
      const countryName = country.country_name.toLowerCase();
      const countryCode = country.country_code.toLowerCase();
      return countryName.includes(q) || countryCode.includes(q);
    });
  }, [countries, searchQuery]);

  const euCountries = filteredCountries.filter((country) => country.is_eu_member);
  const nonEuCountries = filteredCountries.filter((country) => !country.is_eu_member);

  const isDark = theme === "dark";

  const labelClass = isDark
    ? "block text-sm font-medium text-slate-300 mb-2"
    : "block text-sm font-medium text-gray-700 mb-2";

  const inputClass = isDark
    ? "w-full border border-slate-600 rounded-lg px-3 py-2 bg-slate-700 text-slate-100 placeholder-slate-400 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all"
    : "w-full border border-gray-300 rounded-lg px-3 py-2 bg-white text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-clilens-primary focus:border-transparent transition-all";

  const selectClass = isDark
    ? "w-full border border-slate-600 rounded-lg px-4 py-2.5 bg-slate-700 text-slate-100 focus:ring-2 focus:ring-teal-500 focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
    : "w-full border border-gray-300 rounded-lg px-4 py-2.5 bg-white text-gray-900 focus:ring-2 focus:ring-clilens-primary focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed";

  const chipClass = isDark
    ? "inline-flex items-center px-3 py-1 bg-teal-900/30 text-teal-200 rounded-full text-sm border border-teal-700/40"
    : "inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm";

  const clearClass = isDark
    ? "ml-2 text-teal-300 hover:text-teal-100 font-bold"
    : "ml-2 text-blue-600 hover:text-blue-800 font-bold";

  return (
    <div className={`relative ${className || ""}`}>
      <label className={labelClass}>
        <Globe className="inline h-4 w-4 mr-1" />
        {label}
      </label>

      {searchable && (
        <div className="relative mb-2">
          <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="Search country or code..."
            className={`${inputClass} pl-8`}
          />
        </div>
      )}

      <select
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value || null)}
        disabled={loading}
        className={selectClass}
      >
        {showAllOption ? (
          <option value="">{allOptionLabel}</option>
        ) : (
          <option value="">{allOptionLabel || "Select country"}</option>
        )}

        {!loading && filteredCountries.length === 0 && (
          <option value="" disabled>
            No matching countries
          </option>
        )}

        {euCountries.length > 0 && (
          <optgroup label="EU countries">
            {euCountries.map((country) => (
              <option key={country.country_code} value={country.country_code}>
                {country.flag_emoji} {country.country_name}
                {country.articles_count > 0 ? ` (${country.articles_count})` : ""}
              </option>
            ))}
          </optgroup>
        )}

        {nonEuCountries.length > 0 && (
          <optgroup label="Other European countries">
            {nonEuCountries.map((country) => (
              <option key={country.country_code} value={country.country_code}>
                {country.flag_emoji} {country.country_name}
                {country.articles_count > 0 ? ` (${country.articles_count})` : ""}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      {value && selectedCountry && showSelectedChip && (
        <div className="mt-2">
          <span className={chipClass}>
            {selectedCountry.flag_emoji} {selectedCountry.country_name}
            <button
              onClick={() => onChange(null)}
              className={clearClass}
              aria-label="Clear country filter"
              type="button"
            >
              x
            </button>
          </span>
        </div>
      )}
    </div>
  );
}

export default CountrySelector;
