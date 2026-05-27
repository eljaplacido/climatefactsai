import { describe, it, expect } from 'vitest'
import {
  BUSINESS_PLAIN_LANGUAGE_FORMATTERS,
  formatArticleCountBusiness,
  formatClimateRiskBusiness,
  formatCredibilityBusiness,
  formatTemperatureAnomalyBusiness,
  getComplianceFrameworks,
} from '@/lib/plainLanguage'

describe('Business-decision-maker persona helpers — Phase 6', () => {
  describe('formatTemperatureAnomalyBusiness', () => {
    it('returns empty for null/undefined/NaN', () => {
      expect(formatTemperatureAnomalyBusiness(null).sentence).toBe('')
      expect(formatTemperatureAnomalyBusiness(undefined).sentence).toBe('')
      expect(formatTemperatureAnomalyBusiness(NaN).sentence).toBe('')
    })

    it('small deviation → ok tone with no-action copy', () => {
      const r = formatTemperatureAnomalyBusiness(0.3)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toMatch(/no near-term physical-risk action/i)
    })

    it('moderate deviation → warn tone referencing CSRD', () => {
      const r = formatTemperatureAnomalyBusiness(1.0)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toMatch(/CSRD/)
    })

    it('large deviation → alert tone referencing IFRS S2 disclosure trigger', () => {
      const r = formatTemperatureAnomalyBusiness(2.5)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toMatch(/IFRS S2/)
      expect(r.sentence).toMatch(/disclosure trigger/i)
    })
  })

  describe('formatCredibilityBusiness', () => {
    it('returns empty for null', () => {
      expect(formatCredibilityBusiness(null).sentence).toBe('')
    })

    it('≥80 → "audit-grade" copy', () => {
      const r = formatCredibilityBusiness(85)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toMatch(/audit-grade/i)
      expect(r.sentence).toMatch(/CSRD/)
    })

    it('60-79 → "corroboration-grade" with disclosure warning', () => {
      const r = formatCredibilityBusiness(70)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toMatch(/corroboration-grade/i)
      expect(r.sentence).toMatch(/disclosure filings/i)
    })

    it('40-59 → reputational risk warn', () => {
      const r = formatCredibilityBusiness(50)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toMatch(/reputational risk/i)
    })

    it('<40 → greenwashing-exposure alert', () => {
      const r = formatCredibilityBusiness(30)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toMatch(/greenwashing/i)
    })
  })

  describe('formatClimateRiskBusiness', () => {
    it('returns empty for null', () => {
      expect(formatClimateRiskBusiness(null).sentence).toBe('')
    })

    it('≥70 → severe-exposure alert referencing TCFD + asset valuation', () => {
      const r = formatClimateRiskBusiness(80)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toMatch(/TCFD/)
      expect(r.sentence).toMatch(/asset valuation|board risk/i)
    })

    it('50-69 → high-exposure alert + scenario model recommendation', () => {
      const r = formatClimateRiskBusiness(60)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toMatch(/scenario-model|1\.5°C|2°C/i)
    })

    it('30-49 → moderate-exposure warn + insurance/continuity hint', () => {
      const r = formatClimateRiskBusiness(40)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toMatch(/insurance|continuity/i)
    })

    it('<30 → low-exposure ok with planning horizon note', () => {
      const r = formatClimateRiskBusiness(15)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toMatch(/planning horizon|2030\+/i)
    })
  })

  describe('formatArticleCountBusiness', () => {
    it('zero → diligence-constrained alert', () => {
      const r = formatArticleCountBusiness(0)
      expect(r.tone).toBe('alert')
      expect(r.sentence).toMatch(/diligence is constrained/i)
    })

    it('<10 → thin coverage warn for due-diligence', () => {
      const r = formatArticleCountBusiness(5)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toMatch(/due-diligence/i)
    })

    it('10-49 → adequate-for-trend-reading warn', () => {
      const r = formatArticleCountBusiness(25)
      expect(r.tone).toBe('warn')
      expect(r.sentence).toMatch(/trend reading/i)
    })

    it('≥50 → robust-coverage ok with fiduciary framing', () => {
      const r = formatArticleCountBusiness(120)
      expect(r.tone).toBe('ok')
      expect(r.sentence).toMatch(/fiduciary/i)
    })
  })

  describe('getComplianceFrameworks', () => {
    it('climate_risk maps to all three physical-risk regimes', () => {
      const fws = getComplianceFrameworks('climate_risk')
      expect(fws).toContain('CSRD')
      expect(fws).toContain('IFRS S2')
      expect(fws).toContain('TCFD')
    })

    it('temperature_anomaly maps to physical-risk regimes', () => {
      const fws = getComplianceFrameworks('temperature_anomaly')
      expect(fws).toContain('CSRD')
      expect(fws).toContain('IFRS S2')
    })

    it('credibility maps to CSRD assurance regimes', () => {
      const fws = getComplianceFrameworks('credibility')
      expect(fws).toContain('CSRD')
    })

    it('article_count returns at minimum CSRD', () => {
      const fws = getComplianceFrameworks('article_count')
      expect(fws.length).toBeGreaterThan(0)
      expect(fws).toContain('CSRD')
    })

    it('returned arrays are non-empty for every supported metric', () => {
      for (const m of [
        'temperature_anomaly',
        'credibility',
        'climate_risk',
        'article_count',
      ] as const) {
        const fws = getComplianceFrameworks(m)
        expect(fws.length).toBeGreaterThan(0)
      }
    })
  })

  describe('Registry shape', () => {
    it('BUSINESS_PLAIN_LANGUAGE_FORMATTERS exposes all four metrics', () => {
      expect(Object.keys(BUSINESS_PLAIN_LANGUAGE_FORMATTERS).sort()).toEqual([
        'article_count',
        'climate_risk',
        'credibility',
        'temperature_anomaly',
      ])
    })

    it('every business sentence ends with terminal punctuation', () => {
      const cases = [
        formatTemperatureAnomalyBusiness(2.0).sentence,
        formatCredibilityBusiness(85).sentence,
        formatClimateRiskBusiness(80).sentence,
        formatArticleCountBusiness(5).sentence,
      ]
      for (const s of cases) {
        expect(s).toMatch(/[.!?]$/)
      }
    })

    it('every business sentence references at least one regulatory regime OR fiduciary frame', () => {
      const regimeOrFrame = /CSRD|IFRS S2|TCFD|TNFD|fiduciary|disclosure|board|asset|greenwashing|due-diligence|capex|risk|insurance|reputational|continuity|substantiation|filings/i
      const cases = [
        formatTemperatureAnomalyBusiness(2.0).sentence,
        formatTemperatureAnomalyBusiness(1.0).sentence,
        formatCredibilityBusiness(85).sentence,
        formatCredibilityBusiness(50).sentence,
        formatCredibilityBusiness(30).sentence,
        formatClimateRiskBusiness(80).sentence,
        formatClimateRiskBusiness(60).sentence,
        formatClimateRiskBusiness(40).sentence,
        formatArticleCountBusiness(0).sentence,
        formatArticleCountBusiness(5).sentence,
      ]
      for (const s of cases) {
        expect(s, `Business sentence lacks fiduciary/regulatory framing: ${s}`).toMatch(regimeOrFrame)
      }
    })
  })
})
