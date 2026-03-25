# Code Review Report: Mock Data and Error Handling Audit

**Date**: 2025-12-21
**Reviewer**: Claude Code Review Agent
**Scope**: Backend codebase error handling and mock data fallback verification
**Reference**: `.claude/skills/clilens-development/SKILL.md` lines 73-97

---

## Executive Summary

✅ **PASSED**: Primary verification pipeline (intelligence services) has proper explicit error handling
⚠️ **WARNINGS**: Multiple areas with silent failures and placeholder code remain
❌ **CRITICAL**: Video production service contains extensive placeholder implementations

**Overall Status**: Partially compliant with "Fail Explicitly, Never Mock Silently" principle

---

## 1. Critical Issues (Must Fix)

### 1.1 Video Production Service - Extensive Placeholder Code
**Location**: `src/backend/services/video_production_service/src/main.py`

**Issues Found**:
- Line 255: `# Tämä on placeholder - todellinen toteutus käyttäisi OpenAI API:a`
- Line 273: `"TTS audio generated (placeholder)"`
- Line 310: `"url": "https://placeholder.com/climate-news.jpg"`
- Line 360: `# Luo placeholder-tiedosto`
- Line 364: `"Video rendered (placeholder)"`

**Risk**: Service appears functional but returns fake data without warning users

**Recommendation**:
```python
# IMPLEMENT THIS PATTERN:
if not self.openai_api_key:
    raise HTTPException(
        status_code=503,
        detail="Video production unavailable: OpenAI API key not configured"
    )
```

**Action Required**: Either implement actual OpenAI integration OR remove the service entirely to reduce confusion

---

### 1.2 Climate API Placeholder Fallbacks
**Location**: `src/backend/services/verification_service/src/climate_api.py`

**Issues Found**:
- Line 513: `"""Yksinkertainen placeholder-vastaus"""`
- Line 520: `# Palauta placeholder joka ilmaisee että data ei ole saatavilla`

**Current Behavior**: Returns a "No nearby weather stations found" message in data structure

**Assessment**: ⚠️ **ACCEPTABLE** - This is actually explicit about unavailability, not a silent mock

**Code**:
```python
return {
    "source": "NOAA",
    "location": location,
    "dataType": "global_summary",
    "data": {
        "status": "No nearby weather stations found",
        "note": "NOAA GHCND data is primarily available for US locations..."
    }
}
```

**Recommendation**: This pattern is fine, but consider returning `None` instead to make the failure more explicit at the API level.

---

### 1.3 Scraper Site-Specific Parsing Placeholder
**Location**: `src/backend/services/ingestion_service/src/scraper.py`

**Issues Found**:
- Lines 202-204: TODO comment indicating placeholder for site-specific parsing
```python
# TODO: Implementoi sivukohtainen parsinta
# Tämä on placeholder - tuotannossa käytettäisiin
# sivukohtaisia selektoreja
```

**Current Behavior**: Uses generic selectors that may fail silently on different sites

**Recommendation**:
1. Document supported sites explicitly
2. Raise errors for unsupported sites
3. Remove TODO comments if not planning to implement

---

## 2. Major Issues (Should Fix)

### 2.1 Bare Exception Handlers Swallowing Errors
**Location**: Multiple files in `src/backend/services/ingestion_service/src/`

**Files Affected**:
- `perplexity_news_discovery.py`: Lines 231, 238, 306
- `scraper.py`: Lines 327, 349, 404, 414, 440, 457

**Example from scraper.py:327**:
```python
try:
    return parsedate_to_datetime(date_string)
except:  # ❌ BARE EXCEPT
    return None
```

**Risk**: Swallows all exceptions including system errors (KeyboardInterrupt, SystemExit)

**Recommendation**: Replace with specific exception handling:
```python
try:
    return parsedate_to_datetime(date_string)
except (ValueError, TypeError, AttributeError) as e:
    logger.debug(f"Failed to parse date '{date_string}': {e}")
    return None
```

**Count**: 9 bare `except:` blocks found across ingestion service

---

### 2.2 Silent Empty List Returns
**Location**: Multiple services

**Pattern Found**: 11 instances of `return []` that may hide errors

**Examples**:
- `intelligence/services.py:313` - Google Fact Check API failure returns `[]`
- `scraper.py:166` - RSS feed scraping failure returns `[]`
- `perplexity_news_discovery.py:162` - API error returns `[]`

**Current Pattern**:
```python
except requests.exceptions.RequestException as e:
    print(f"❌ Perplexity API error: {e}")
    return []  # ❌ Silent failure
```

**Recommendation**:
```python
except requests.exceptions.RequestException as e:
    logger.error(f"Perplexity API error: {e}")
    raise HTTPException(
        status_code=503,
        detail="News discovery service temporarily unavailable"
    )
```

---

### 2.3 Print Statements Instead of Logging
**Location**: `perplexity_news_discovery.py`

**Issues**: Lines 158, 159, 161, 206 use `print()` instead of structured logging

**Example**:
```python
print(f"❌ Perplexity API error: {e}")  # ❌ Should use logger
print(f"Warning: Failed to normalize article: {e}")  # ❌ Should use logger
```

**Recommendation**: Use structured logging consistently
```python
logger.error("Perplexity API error", error=str(e), status_code=e.response.status_code)
logger.warning("Failed to normalize article", error=str(e), article_data=article)
```

---

## 3. Positive Findings ✅

### 3.1 Intelligence Service - Excellent Error Handling
**Location**: `src/backend/app/domains/intelligence/services.py`

**Strengths**:
1. **Explicit API key checks** (lines 64-69):
```python
if not self.client or not self.api_key:
    raise HTTPException(
        status_code=503,
        detail="Claim extraction unavailable: Anthropic API key not configured"
    )
```

2. **Specific exception handling** (lines 85-104):
```python
except anthropic.RateLimitError as e:
    raise HTTPException(status_code=429, detail="Rate limit exceeded...")
except anthropic.APIError as e:
    raise HTTPException(status_code=503, detail="Service temporarily unavailable...")
```

3. **Model fallback with logging** (lines 156-182): Tries multiple models but logs failures

4. **No mock data generation**: Removed `_generate_mock_claims()` as confirmed

**HTTPException Usage**: 12 instances of explicit `raise HTTPException` found - excellent!

---

## 4. Compliance Summary

### ✅ Compliant Areas:
1. **Claim Extraction Service**: Explicit failures, no mock data
2. **Evidence Retrieval**: Returns empty lists but logs warnings
3. **Verdict Adjudication**: Returns "unverified" verdict when data unavailable (acceptable pattern)

### ⚠️ Partially Compliant:
1. **Climate APIs**: Some placeholder returns but documented
2. **Scraper Service**: Generic parsing may fail silently
3. **URL Analyzer**: Returns empty lists on errors

### ❌ Non-Compliant:
1. **Video Production Service**: Extensive placeholder implementations
2. **Bare Exception Handlers**: 9 instances swallow all errors
3. **Print vs Logging**: Inconsistent error reporting
4. **Silent Empty Returns**: 11 instances hide failures from callers

---

## 5. Recommendations by Priority

### Priority 1 (Critical - Fix Immediately):
1. **Remove or implement video production service** - Lines 255-364 in `video_production_service/src/main.py`
2. **Fix bare exception handlers** - Replace all 9 `except:` with specific exceptions
3. **Replace print() with logger** - In `perplexity_news_discovery.py`

### Priority 2 (Major - Fix This Sprint):
4. **Audit empty list returns** - Consider raising exceptions instead of returning `[]`
5. **Document scraper limitations** - Clarify which sites are supported
6. **Add API key validation startup checks** - Fail fast on missing credentials

### Priority 3 (Minor - Technical Debt):
7. **Remove TODO comments** - Either implement or document as known limitations
8. **Standardize error response format** - Consistent HTTPException detail messages
9. **Add error recovery documentation** - User guidance for 503 errors

---

## 6. Code Quality Metrics

| Metric | Count | Status |
|--------|-------|--------|
| HTTPException (explicit) | 12 | ✅ Good |
| Bare except: blocks | 9 | ❌ Bad |
| TODO/Placeholder comments | 6 | ⚠️ Needs cleanup |
| Silent return [] | 11 | ⚠️ Review needed |
| Print vs Logger | 4 | ❌ Fix needed |
| Mock data generators | 0 | ✅ Excellent |

---

## 7. Testing Recommendations

1. **Integration Tests**: Verify HTTPException raised when APIs unavailable
2. **Unit Tests**: Test exception handling paths explicitly
3. **Error Scenarios**: Test with missing API keys, rate limits, timeouts
4. **Monitoring**: Add alerts for 503 errors (indicates missing configuration)

---

## 8. Action Items

- [ ] **Video Service**: Remove placeholder implementations or implement OpenAI integration
- [ ] **Ingestion Service**: Replace 9 bare `except:` with specific exception types
- [ ] **Perplexity Client**: Replace `print()` with structured logging
- [ ] **All Services**: Audit `return []` patterns - consider raising exceptions
- [ ] **Documentation**: Update API docs with error codes and retry guidance
- [ ] **Monitoring**: Add metrics for 503 errors by service

---

## Conclusion

The **intelligence/verification pipeline** demonstrates excellent adherence to the "Fail Explicitly, Never Mock Silently" principle. However, **video production service** and **ingestion utilities** contain significant violations that should be addressed.

**Estimated Effort**:
- Critical fixes: 4-6 hours
- Major fixes: 8-12 hours
- Minor cleanup: 2-4 hours

**Next Steps**:
1. Review this report with team
2. Create GitHub issues for Priority 1 items
3. Schedule fixes for current sprint
4. Update CI/CD to fail on bare `except:` blocks (linting rule)

---

**Reviewed by**: Claude Code Review Agent
**Methodology**: Static analysis + pattern matching + project standards review
**Standards Reference**: `.claude/skills/clilens-development/SKILL.md`
