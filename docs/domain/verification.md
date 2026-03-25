# Verification Domain (Intelligence)

## Overview

The Verification (Intelligence) domain is the core intellectual property of CliLens.AI. It implements a multi-stage fact-checking pipeline that decomposes articles into atomic claims, retrieves evidence from trusted sources, and assigns confidence-scored verdicts.

## Responsibilities

### 1. Claim Decomposition
- Break down article text into atomic, verifiable claims
- Classify claim types (factual, opinion, prediction)
- Extract claim context and supporting quotes
- Generate unique claim identifiers

### 2. Evidence Retrieval
- Query multiple trusted data sources for evidence
- Rank evidence by relevance and authority
- Extract supporting and contradicting evidence
- Build evidence chains with provenance

### 3. Verification & Adjudication
- Compare claims against retrieved evidence
- Assign verdicts: verified, disputed, partially true, unverified
- Calculate confidence scores (0-1 scale)
- Generate human-readable justifications

### 4. Credibility Scoring
- Aggregate claim-level verdicts into article credibility
- Weight by claim importance and confidence
- Factor in source reliability
- Produce final credibility level (high/medium/low)

## Data Flow

```
[Article (from Ingestion)]
         ↓
[Claim Extraction (Claude 3.5)]
         ↓
[Atomic Claims List]
         ↓
[Evidence Retrieval]
    ├─→ Google Fact Check API
    ├─→ Climate Watch API
    ├─→ NASA Earthdata
    └─→ Scientific Papers DB
         ↓
[Evidence Collection]
         ↓
[Adjudication (Claude 3.5)]
         ↓
[Verdict + Confidence]
         ↓
[Credibility Aggregation]
         ↓
[PostgreSQL: claims, fact_checks]
         ↓
[Celery Task: create_summary triggered with workflow_state]
```

## Key Components

### ClaimExtractor
**Purpose**: Decompose articles into atomic claims  
**Model**: Claude 3.5 Sonnet (structured output)  
**Input**: Article full text  
**Output**: List of `AtomicClaim` objects

```python
class AtomicClaim(BaseModel):
    claim_text: str  # "Arctic ice extent decreased by 13% per decade since 1979"
    claim_type: str  # 'factual', 'opinion', 'prediction'
    claim_context: str  # Surrounding sentences
    importance_score: float  # 0-1, how central to article
    extracted_from: str  # Source sentence/paragraph
```

### EvidenceRetriever
**Purpose**: Fetch supporting/contradicting evidence  
**Sources**:
- **Google Fact Check Tools API**: Check existing fact-checks
- **Climate Watch API**: Historical climate data
- **NASA Earthdata**: Satellite/sensor data
- **Semantic Scholar API**: Peer-reviewed papers

```python
class Evidence(BaseModel):
    source: str  # 'NASA Earthdata'
    source_url: str
    source_reliability: str  # 'high', 'medium', 'low'
    content_excerpt: str  # Relevant quote
    relevance_score: float  # 0-1
    supports_claim: bool | None  # True, False, None (neutral)
    retrieved_at: datetime
```

### VerdictAdjudicator
**Purpose**: Compare claim against evidence and assign verdict  
**Model**: Claude 3.5 Sonnet (chain-of-thought reasoning)  
**Logic**:
1. Analyze all evidence (supporting, contradicting, neutral)
2. Weight by source reliability and relevance
3. Generate reasoning chain
4. Assign verdict and confidence score

```python
class Verdict(BaseModel):
    verdict: str  # 'verified', 'disputed', 'partially_true', 'unverified'
    confidence_score: float  # 0-1
    justification: str  # Human-readable explanation
    evidence_summary: str  # Key evidence cited
    model_used: str  # 'claude-3-5-sonnet-20240620'
    verified_at: datetime
```

## Atomic Claim Quality Standards

### Definition
An atomic claim is:
- **Self-contained**: Understandable without external context
- **Verifiable**: Can be fact-checked against evidence
- **Singular**: Contains one factual assertion (not compound)
- **Specific**: Includes concrete details (numbers, dates, entities)

### Examples

✅ **Good Atomic Claims**
- "Global average temperature increased by 1.1°C between 1850 and 2020"
- "The Arctic sea ice extent in September 2024 was 4.7 million square kilometers"
- "The Paris Agreement aims to limit warming to 1.5°C above pre-industrial levels"

❌ **Bad (Non-Atomic) Claims**
- "Climate change is bad" (opinion, not verifiable)
- "Temperatures rose and ice melted" (compound claim, split into 2)
- "Many experts agree" (vague, no specifics)

## Verification Methods

### Method 1: Automated (Default)
- LLM-powered claim extraction + evidence retrieval + adjudication
- Confidence threshold: 0.6
- Processing time: ~30 seconds per article
- **When to use**: Standard news articles, high-volume processing

### Method 2: Human-Reviewed
- Automated pipeline + manual expert review for low-confidence claims
- Triggered when confidence < 0.6
- Routing to fact-checker dashboard
- **When to use**: Controversial topics, policy decisions, breaking news

### Method 3: Rapid (Simplified)
- Single-step LLM verification (no evidence retrieval)
- Faster but lower confidence
- Used for time-sensitive content
- **When to use**: Breaking news alerts, real-time monitoring

## Data Models

### Claim
```python
class Claim(BaseModel):
    id: UUID
    article_id: int
    claim_text: str
    claim_type: str  # 'factual', 'opinion', 'prediction'
    claim_context: str | None
    importance_score: float
    
    # Timestamps
    extracted_at: datetime
    extraction_model: str
```

### FactCheck
```python
class FactCheck(BaseModel):
    id: UUID
    claim_id: UUID
    
    # Verdict
    verdict: str  # 'verified', 'disputed', 'partially_true', 'unverified'
    confidence_score: float
    justification: str
    
    # Evidence
    evidence: list[Evidence]
    sources: list[str]  # Source URLs
    
    # Metadata
    verified_at: datetime
    verification_model: str
    verification_method: str  # 'automated', 'human_reviewed'
```

## Celery Tasks

### verify_claims
**Trigger**: Called after `discover_articles` completes, receives `workflow_state` containing `article_ids`
**Queue**: `celery` (default)
**Return payload** (merged into `workflow_state`):
```json
{
  "article_ids": ["..."],
  "verification_results": [
    {
      "article_id": "...",
      "claims": [],
      "verdicts": [],
      "credibility_score": 0.78,
      "credibility_level": "high"
    }
  ]
}
```

### create_summary
**Trigger**: Called after `verify_claims` completes, receives the same `workflow_state`
**Queue**: `celery` (default)
**Return payload** (merged into `workflow_state`):
```json
{
  "summary_task": {
    "updated": 3
  }
}
```

## Credibility Calculation

### Formula
```
Article Credibility Score = (
    Σ (claim_importance × confidence_score × verdict_weight)
) / Σ (claim_importance)

verdict_weights = {
    'verified': 1.0,
    'partially_true': 0.6,
    'unverified': 0.3,
    'disputed': 0.0
}
```

### Credibility Levels
- **High**: Score ≥ 0.75
- **Medium**: Score 0.45 - 0.74
- **Low**: Score < 0.45

### Example
```
Article with 3 claims:
1. "1.1°C warming" → verified (conf: 0.95, importance: 0.9)
2. "Arctic ice -13%" → verified (conf: 0.88, importance: 0.8)
3. "Policy prediction" → unverified (conf: 0.40, importance: 0.3)

Score = (0.9×0.95×1.0 + 0.8×0.88×1.0 + 0.3×0.40×0.3) / (0.9+0.8+0.3)
      = (0.855 + 0.704 + 0.036) / 2.0
      = 1.595 / 2.0
      = 0.798
      → Credibility Level: HIGH
```

## Quality Controls

### Evidence Source Reliability
```python
SOURCE_RELIABILITY = {
    'nasa.gov': 0.95,
    'noaa.gov': 0.95,
    'nature.com': 0.90,
    'ipcc.ch': 0.95,
    'bbc.com': 0.80,
    'climatewatchdata.org': 0.85,
    # ...
}
```

### Confidence Thresholds
- **High confidence**: ≥ 0.80
- **Medium confidence**: 0.60 - 0.79
- **Low confidence**: < 0.60 (route to human review)

### Monitoring
- Track average verification time per claim
- Monitor confidence score distribution
- Alert on sudden drops in verification success rate
- Track evidence retrieval failures by source

## Configuration

### Environment Variables
```
ANTHROPIC_API_KEY=sk-ant-xxx
GOOGLE_FACTCHECK_API_KEY=xxx
CLIMATE_WATCH_API_KEY=xxx
NASA_API_KEY=xxx

VERIFICATION_MODEL=claude-3-5-sonnet-20240620
VERIFICATION_TEMPERATURE=0.1
MAX_CLAIMS_PER_ARTICLE=20
CONFIDENCE_THRESHOLD=0.6
```

## Future Enhancements

- [ ] Multi-lingual claim verification
- [ ] Image/chart fact-checking via vision models
- [ ] Temporal fact decay (update old verdicts with new data)
- [ ] Contradiction detection across articles
- [ ] Expert review marketplace integration
- [ ] Blockchain-based provenance tracking

