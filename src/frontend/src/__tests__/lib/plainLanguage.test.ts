import { describe, it, expect } from 'vitest'
import {
  formatTemperatureAnomalyPlain,
  formatCredibilityPlain,
  formatClimateRiskPlain,
  formatArticleCountPlain,
  formatEvidenceStrengthPlain,
  PLAIN_LANGUAGE_FORMATTERS,
} from '@/lib/plainLanguage'

describe('plainLanguage — Phase 2C templated interpretation layer', () => {
  describe('formatTemperatureAnomalyPlain', () => {
    it('returns empty result for null/undefined/NaN', () => {
      expect(formatTemperatureAnomalyPlain(null).sentence).toBe('')
      expect(formatTemperatureAnomalyPlain(undefined).sentence).toBe('')
      expect(formatTemperatureAnomalyPlain(NaN).sentence).toBe('')
    })

    it('uses provided location and baseline in copy', () => {
      const r = formatTemperatureAnomalyPlain(1.4, {
        locationName: 'Germany',
        baselineLabel: 'the 1981-2010 baseline',
      })
      expect(r.sentence).toContain('Germany')
      expect(r.sentence).toContain('the 1981-2010 baseline')
      expect(r.sentence).toContain('1.4°C warmer')
    })

    it('classifies <0.5°C as OK tone (within typical variation)', () => {
      expect(formatTemperatureAnomalyPlain(0.3).tone).toBe('ok')
    })

    it('classifies 0.5-1.5°C as warning tone', () => {
      expect(formatTemperatureAnomalyPlain(1.0).tone).toBe('warn')
    })

    it('classifies ≥1.5°C as alert tone with severity narrative', () => {
      const r = formatTemperatureAnomalyPlain(2.5)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toContain('unusually large')
    })

    it('cooler-than-baseline uses "cooler" wording', () => {
      const r = formatTemperatureAnomalyPlain(-1.8)
      expect(r.sentence).toContain('1.8°C cooler')
      expect(r.tone).toBe('alert')
    })

    it('zero anomaly uses "same temperature" phrasing', () => {
      const r = formatTemperatureAnomalyPlain(0)
      expect(r.sentence).toContain('same temperature')
      expect(r.tone).toBe('ok')
    })
  })

  describe('formatCredibilityPlain', () => {
    it('returns empty for null', () => {
      expect(formatCredibilityPlain(null).sentence).toBe('')
    })

    it('classifies ≥80 as highly-trusted (ok)', () => {
      const r = formatCredibilityPlain(85)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toContain('highly-trusted')
    })

    it('classifies 60-79 as generally reliable (ok)', () => {
      const r = formatCredibilityPlain(72)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toContain('generally reliable')
    })

    it('classifies 40-59 as mixed (warn)', () => {
      const r = formatCredibilityPlain(50)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toContain('mixed reliability')
    })

    it('classifies <40 as below threshold (alert)', () => {
      const r = formatCredibilityPlain(30)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toContain('below the platform')
    })

    it('includes sample size hint when provided', () => {
      const r = formatCredibilityPlain(80, { sampleSize: 142 })
      expect(r.sentence).toContain('based on 142 articles')
    })

    it('singularises "1 article" correctly', () => {
      const r = formatCredibilityPlain(80, { sampleSize: 1 })
      expect(r.sentence).toContain('1 article)')
      expect(r.sentence).not.toContain('1 articles')
    })
  })

  describe('formatClimateRiskPlain', () => {
    it('returns empty for null', () => {
      expect(formatClimateRiskPlain(null).sentence).toBe('')
    })

    it('≥70 surfaces severe-exposure copy (alert)', () => {
      const r = formatClimateRiskPlain(80)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toMatch(/severe/i)
    })

    it('50-69 surfaces high-exposure copy (alert)', () => {
      const r = formatClimateRiskPlain(55)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toContain('high climate exposure')
    })

    it('30-49 surfaces moderate-exposure copy (warn)', () => {
      const r = formatClimateRiskPlain(40)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toContain('moderate')
    })

    it('<30 surfaces low-immediate-exposure copy (ok)', () => {
      const r = formatClimateRiskPlain(15)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toContain('low immediate')
    })
  })

  describe('formatArticleCountPlain', () => {
    it('returns empty for null', () => {
      expect(formatArticleCountPlain(null).sentence).toBe('')
    })

    it('zero count surfaces "coverage signal" copy (alert)', () => {
      const r = formatArticleCountPlain(0, { entity: 'Tuvalu' })
      expect(r.tone).toBe('alert')
      expect(r.sentence).toContain('Tuvalu has no articles')
      expect(r.sentence).toContain('coverage signal')
    })

    it('<10 articles → thin coverage warn', () => {
      const r = formatArticleCountPlain(5)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toContain('thin coverage')
    })

    it('singularises "1 article" in thin-coverage copy', () => {
      const r = formatArticleCountPlain(1)
      expect(r.sentence).toContain('(1 article')
      expect(r.sentence).not.toContain('1 articles')
    })

    it('10-49 → modest coverage warn', () => {
      const r = formatArticleCountPlain(25)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toContain('modest coverage')
    })

    it('50-199 → good coverage ok', () => {
      const r = formatArticleCountPlain(120)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toContain('good coverage')
    })

    it('≥200 → extensive coverage ok, uses toLocaleString', () => {
      const r = formatArticleCountPlain(1234)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toContain('extensive coverage')
      // toLocaleString formatting (commas in en-US; whatever locale runs)
      expect(r.sentence).toMatch(/1,234|1\.234|1 234/)
    })
  })

  describe('formatEvidenceStrengthPlain', () => {
    it('zero total → alert + deterministic-explainer copy', () => {
      const r = formatEvidenceStrengthPlain(0, 0)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toContain('deterministic explainer')
    })

    it('null+null treated as zero', () => {
      const r = formatEvidenceStrengthPlain(null, null)
      expect(r.tone).toBe('alert')
    })

    it('1-2 total → warn + thin-evidence copy', () => {
      const r = formatEvidenceStrengthPlain(1, 1)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toContain('Evidence is thin')
      expect(r.sentence).toContain('1 internal + 1 external')
    })

    it('3-7 total → warn + moderate copy', () => {
      const r = formatEvidenceStrengthPlain(4, 2)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toContain('moderate')
    })

    it('≥8 total → ok + strong copy', () => {
      const r = formatEvidenceStrengthPlain(6, 4)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toContain('strong')
      expect(r.sentence).toContain('cross-source corroboration')
    })
  })

  describe('PLAIN_LANGUAGE_FORMATTERS registry', () => {
    it('exposes every formatter under a stable key', () => {
      expect(Object.keys(PLAIN_LANGUAGE_FORMATTERS).sort()).toEqual([
        'article_count',
        'climate_risk',
        'credibility',
        'evidence_strength',
        'temperature_anomaly',
      ])
    })
  })

  describe('a11y / output safety', () => {
    it('always returns a string for `sentence` (never undefined)', () => {
      expect(typeof formatTemperatureAnomalyPlain(undefined).sentence).toBe('string')
      expect(typeof formatCredibilityPlain(null).sentence).toBe('string')
      expect(typeof formatClimateRiskPlain(null).sentence).toBe('string')
      expect(typeof formatArticleCountPlain(null).sentence).toBe('string')
    })

    it('non-empty sentences end with terminal punctuation', () => {
      const cases = [
        formatTemperatureAnomalyPlain(2.0).sentence,
        formatCredibilityPlain(85).sentence,
        formatClimateRiskPlain(80).sentence,
        formatArticleCountPlain(5).sentence,
        formatEvidenceStrengthPlain(0, 0).sentence,
      ]
      for (const s of cases) {
        expect(s).toMatch(/[.!?]$/)
      }
    })
  })
})
