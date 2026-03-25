import { useState, useEffect } from "react";
import { Globe } from "lucide-react";
import { api } from "../services/api";

interface Country {
  country_code: string;
  country_name: string;
  country_name_native: string;
  flag_emoji: string;
  articles_count: number;
  is_eu_member: boolean;
  language_code: string;
}

interface CountrySelectorProps {
  value: string | null;
  onChange: (country: string | null) => void;
}

function CountrySelector({ value, onChange }: CountrySelectorProps) {
  const [countries, setCountries] = useState<Country[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCountries();
  }, []);

  const loadCountries = async () => {
    try {
      const data = await api.getCountries();
      setCountries(data);
    } catch (error) {
      console.error("Error loading countries:", error);
    } finally {
      setLoading(false);
    }
  };

  const euCountries = countries.filter((country) => country.is_eu_member);
  const nonEuCountries = countries.filter((country) => !country.is_eu_member);
  const selectedCountry = countries.find((country) => country.country_code === value);

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        <Globe className="inline h-4 w-4 mr-1" />
        Country
      </label>

      <select
        value={value || ""}
        onChange={(e) => onChange(e.target.value || null)}
        disabled={loading}
        className="w-full border border-gray-300 rounded-lg px-4 py-2.5 bg-white focus:ring-2 focus:ring-climate-green-500 focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <option value="">All EU countries</option>

        {euCountries.length > 0 && (
          <optgroup label="EU countries">
            {euCountries.map((country) => (
              <option key={country.country_code} value={country.country_code}>
                {country.flag_emoji} {country.country_name}
                {country.articles_count > 0 && ` (${country.articles_count})`}
              </option>
            ))}
          </optgroup>
        )}

        {nonEuCountries.length > 0 && (
          <optgroup label="Other European countries">
            {nonEuCountries.map((country) => (
              <option key={country.country_code} value={country.country_code}>
                {country.flag_emoji} {country.country_name}
                {country.articles_count > 0 && ` (${country.articles_count})`}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      {value && selectedCountry && (
        <div className="mt-2">
          <span className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
            {selectedCountry.flag_emoji} {selectedCountry.country_name}
            <button
              onClick={() => onChange(null)}
              className="ml-2 text-blue-600 hover:text-blue-800 font-bold"
              aria-label="Clear country filter"
            >
              ×
            </button>
          </span>
        </div>
      )}
    </div>
  );
}

export default CountrySelector;
