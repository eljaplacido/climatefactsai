import { describe, it, expect } from 'vitest'
import {
  CREDIBILITY_COLORS,
  TEMPERATURE_ANOMALY_DIVERGING,
  ARTICLE_DENSITY_SEQUENTIAL,
  CLIMATE_RISK_SEQUENTIAL,
  CATEGORICAL_8,
  TREND_LINE_COLORS,
  TONE_COLORS,
  VARIABLE_COLORS,
  ALL_PALETTES,
  getCredibilityColor,
  getTemperatureAnomalyColor,
  assertNotRainbow,
} from '@/lib/climateColors'

const HEX_RE = /^#[0-9a-fA-F]{6}$/

function hueDistance(a: string, b: string): number {
  // Cheap luminance proxy for "are these visually distinguishable".
  const ah = parseInt(a.slice(1), 16)
  const bh = parseInt(b.slice(1), 16)
  return Math.abs(ah - bh)
}

/** ITU-R BT.601 perceptual luminance — 0 (black) to 255 (white). */
function luminance(hex: string): number {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return 0.299 * r + 0.587 * g + 0.114 * b
}

describe('climateColors — Phase 2F central palette', () => {
  describe('shape invariants', () => {
    it('every color is a 6-digit hex string', () => {
      const all = [
        ...Object.values(CREDIBILITY_COLORS),
        ...Object.values(TEMPERATURE_ANOMALY_DIVERGING),
        ...Object.values(ARTICLE_DENSITY_SEQUENTIAL),
        ...Object.values(CLIMATE_RISK_SEQUENTIAL),
        ...Object.values(TREND_LINE_COLORS),
        ...Object.values(TONE_COLORS),
        ...Object.values(VARIABLE_COLORS),
        ...CATEGORICAL_8,
      ]
      for (const c of all) {
        expect(c, `${c} is not a 6-digit hex`).toMatch(HEX_RE)
      }
    })

    it('ALL_PALETTES exposes every named palette for downstream consumers', () => {
      expect(Object.keys(ALL_PALETTES).sort()).toEqual([
        'articleDensity',
        'categorical',
        'climateRisk',
        'credibility',
        'temperatureAnomaly',
        'tone',
        'trendLine',
      ])
    })
  })

  describe('credibility palette', () => {
    it('exposes the three canonical levels + UNVERIFIED fallback', () => {
      expect(CREDIBILITY_COLORS.HIGH).toBeTruthy()
      expect(CREDIBILITY_COLORS.MEDIUM).toBeTruthy()
      expect(CREDIBILITY_COLORS.LOW).toBeTruthy()
      expect(CREDIBILITY_COLORS.UNVERIFIED).toBeTruthy()
    })

    it('getCredibilityColor uppercases input', () => {
      expect(getCredibilityColor('high')).toBe(CREDIBILITY_COLORS.HIGH)
      expect(getCredibilityColor('High')).toBe(CREDIBILITY_COLORS.HIGH)
    })

    it('getCredibilityColor returns UNVERIFIED for unknown / null / undefined', () => {
      expect(getCredibilityColor(null)).toBe(CREDIBILITY_COLORS.UNVERIFIED)
      expect(getCredibilityColor(undefined)).toBe(CREDIBILITY_COLORS.UNVERIFIED)
      expect(getCredibilityColor('bogus')).toBe(CREDIBILITY_COLORS.UNVERIFIED)
    })
  })

  describe('temperature anomaly — DIVERGING palette per audit rule', () => {
    it('cool side colours are visually distinct from warm side', () => {
      const cool = TEMPERATURE_ANOMALY_DIVERGING.veryCool
      const warm = TEMPERATURE_ANOMALY_DIVERGING.veryWarm
      // Diverging palette: opposite ends must be far apart visually.
      // veryCool is deep blue (~#2166ac), veryWarm is deep red (~#b2182b)
      expect(hueDistance(cool, warm)).toBeGreaterThan(500_000)
    })

    it('getTemperatureAnomalyColor returns no-data tone for null/NaN', () => {
      expect(getTemperatureAnomalyColor(null)).toBe('#cbd5e1')
      expect(getTemperatureAnomalyColor(undefined)).toBe('#cbd5e1')
      expect(getTemperatureAnomalyColor(NaN)).toBe('#cbd5e1')
    })

    it('cold extremes get veryCool, hot extremes get veryWarm', () => {
      expect(getTemperatureAnomalyColor(-3)).toBe(TEMPERATURE_ANOMALY_DIVERGING.veryCool)
      expect(getTemperatureAnomalyColor(5)).toBe(TEMPERATURE_ANOMALY_DIVERGING.veryWarm)
    })

    it('zero anomaly returns the neutral midpoint', () => {
      expect(getTemperatureAnomalyColor(0)).toBe(TEMPERATURE_ANOMALY_DIVERGING.neutral)
    })

    it('bucket boundaries are stable', () => {
      // Boundary check — pinning the rubric so refactors don't shift it
      expect(getTemperatureAnomalyColor(-1.5)).toBe(TEMPERATURE_ANOMALY_DIVERGING.cool)
      expect(getTemperatureAnomalyColor(-0.5)).toBe(TEMPERATURE_ANOMALY_DIVERGING.slightlyCool)
      expect(getTemperatureAnomalyColor(0.5)).toBe(TEMPERATURE_ANOMALY_DIVERGING.slightlyWarm)
      expect(getTemperatureAnomalyColor(1.5)).toBe(TEMPERATURE_ANOMALY_DIVERGING.warm)
    })
  })

  describe('sequential palettes — audit rule: light → dark = low → high', () => {
    it('article density: low value is perceptually lighter than high value', () => {
      // Use perceptual luminance (BT.601) — comparing raw hex is wrong
      // across hues. light teal #ccfbf1 reads brighter than dark teal #0f766e.
      expect(luminance(ARTICLE_DENSITY_SEQUENTIAL.low)).toBeGreaterThan(
        luminance(ARTICLE_DENSITY_SEQUENTIAL.high),
      )
    })

    it('climate risk: low (green) is perceptually lighter than veryHigh (red)', () => {
      expect(luminance(CLIMATE_RISK_SEQUENTIAL.low)).toBeGreaterThan(
        luminance(CLIMATE_RISK_SEQUENTIAL.veryHigh),
      )
    })
  })

  describe('categorical palette', () => {
    it('has exactly 8 entries (ColorBrewer Set2 size)', () => {
      expect(CATEGORICAL_8).toHaveLength(8)
    })

    it('all entries are unique', () => {
      const set = new Set(CATEGORICAL_8)
      expect(set.size).toBe(CATEGORICAL_8.length)
    })
  })

  describe('VARIABLE_COLORS — same-variable-same-color rule', () => {
    it('temperature is warm-toned (orange family), not blue', () => {
      // Crude red-channel test: orange has high R, low B.
      const tempHex = VARIABLE_COLORS.temperature
      const r = parseInt(tempHex.slice(1, 3), 16)
      const b = parseInt(tempHex.slice(5, 7), 16)
      expect(r).toBeGreaterThan(b + 50)
    })

    it('precipitation is blue-toned, not red', () => {
      const precHex = VARIABLE_COLORS.precipitation
      const r = parseInt(precHex.slice(1, 3), 16)
      const b = parseInt(precHex.slice(5, 7), 16)
      expect(b).toBeGreaterThan(r + 50)
    })
  })

  describe('assertNotRainbow — defends against future rainbow-scale PRs', () => {
    it('throws when a palette contains pure red+green+blue', () => {
      expect(() => assertNotRainbow(['#ff0000', '#00ff00', '#0000ff'])).toThrow(/rainbow/i)
    })

    it('accepts a sequential single-hue palette', () => {
      expect(() =>
        assertNotRainbow([
          ARTICLE_DENSITY_SEQUENTIAL.low,
          ARTICLE_DENSITY_SEQUENTIAL.medium,
          ARTICLE_DENSITY_SEQUENTIAL.high,
        ]),
      ).not.toThrow()
    })

    it('accepts a diverging palette (no pure RGB primaries)', () => {
      expect(() =>
        assertNotRainbow(Object.values(TEMPERATURE_ANOMALY_DIVERGING)),
      ).not.toThrow()
    })

    it('accepts the categorical Set2 palette', () => {
      expect(() => assertNotRainbow(CATEGORICAL_8)).not.toThrow()
    })
  })

  describe('tone tokens match plain-language layer', () => {
    it('TONE_COLORS keys match the plainLanguage tone enum', () => {
      // plainLanguage.ts exports PlainLanguageTone = 'ok'|'warn'|'alert'|'neutral'.
      // The two modules must stay aligned so a tone string from one is renderable
      // by the other without translation.
      expect(Object.keys(TONE_COLORS).sort()).toEqual(['alert', 'neutral', 'ok', 'warn'])
    })
  })
})
