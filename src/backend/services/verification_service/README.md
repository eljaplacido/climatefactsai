# Verification Service (Fact Checking)

## Purpose
The Verification Service is the critical fact-checking engine of CliLens.AI. It validates claims extracted from news articles using authoritative climate data sources and APIs, ensuring the accuracy and trustworthiness of published content.

## Core Responsibilities
1. **Claim Verification**: Validate factual claims against authoritative data sources
2. **Multi-Source Validation**: Cross-reference claims across multiple APIs (ClimateCheck, NOAA, NASA)
3. **Confidence Scoring**: Assign confidence scores to verified claims
4. **Source Attribution**: Track and attribute verification sources for transparency
5. **Data Handoff**: Send verified content to Content Creation Service

## Architecture

### Components
- `main.py`: Main fact-checking agent and entry point
- `verifier.py`: Core claim verification logic
- `climate_api.py`: API clients for ClimateCheck, NOAA, and NASA
- `perplexity_client.py`: Perplexity AI integration for additional verification

### Dependencies
- **Shared Modules**: `shared.config`, `shared.logger`, `shared.kafka_client`, `shared.database`
- **External APIs**:
  - ClimateCheck API: Risk scores and climate hazard data
  - NOAA API: Historical climate data
  - NASA Earth API: Satellite data and temperature measurements
  - Perplexity API: AI-powered fact verification
- **Database**: PostgreSQL for claim storage and verification history

## Data Flow

```
Kafka (factcheck_queue)
  → Claim Extraction
  → Multi-Source Verification
    ├→ ClimateCheck API
    ├→ NOAA API
    ├→ NASA API
    └→ Perplexity API
  → Confidence Scoring
  → Kafka (content_creation_queue)
  → Content Creation Service
```

## Verification Process

### 1. Claim Parsing
Extract structured claims from article text:
- Numeric claims (e.g., "Temperature increased by 1.5°C")
- Temporal claims (e.g., "Since 2020...")
- Geospatial claims (e.g., "In Helsinki...")

### 2. Source Selection
Determine appropriate data sources based on claim type:
- **Temperature claims** → NASA, NOAA
- **Risk assessments** → ClimateCheck
- **General facts** → Perplexity AI

### 3. API Queries
Query selected sources with claim parameters:
- Location coordinates
- Date ranges
- Data types (temperature, precipitation, etc.)

### 4. Verification Logic
Compare claim against source data:
- Exact match: Confidence = 0.95+
- Close match (within tolerance): Confidence = 0.70-0.95
- No match or conflicting: Confidence < 0.50

### 5. Consensus Building
Aggregate results from multiple sources:
- Weight by source credibility
- Identify conflicting information
- Generate final confidence score

## Kafka Integration

### Consumes From
- `factcheck_queue`: Articles with extracted claims from Ingestion Service
  - Schema: `schemas/discovery_to_factcheck.json`

### Produces To
- `content_creation_queue`: Verified claims ready for content generation
  - Schema: `schemas/factcheck_to_creation.json`

## Configuration
- `climate_data.climatecheck_api_key`: ClimateCheck API key
- `climate_data.climatecheck_api_url`: ClimateCheck API endpoint
- `climate_data.noaa_api_token`: NOAA API token
- `climate_data.nasa_api_key`: NASA API key
- `verification.min_confidence_threshold`: Minimum confidence for publication (default: 0.70)
- `verification.require_multi_source`: Require verification from multiple sources

## Database Schema

### Tables Used
- `claims`: Stores individual claims with verification results
- `verification_results`: Detailed verification outcomes per source
- `api_call_logs`: API usage tracking for rate limiting

## API Contract

### Input (Kafka Message)
From `discovery_to_factcheck.json` schema:
```json
{
  "schemaVersion": "1.0",
  "taskId": "task-20251022-001",
  "articleId": "uuid",
  "sourceArticle": {
    "url": "https://...",
    "title": "Arctic Ice Melting Accelerates"
  },
  "claims": [
    {
      "claimText": "Arctic sea ice decreased by 13% per decade since 1979",
      "confidence": 0.85,
      "claimType": "factual",
      "location": {
        "name": "Arctic",
        "coordinates": [90.0, 0.0]
      }
    }
  ]
}
```

### Output (Kafka Message)
To `factcheck_to_creation.json` schema:
```json
{
  "schemaVersion": "1.0",
  "taskId": "task-20251022-001",
  "articleId": "uuid",
  "verificationResults": [
    {
      "claimId": "uuid",
      "claimText": "Arctic sea ice decreased by 13% per decade since 1979",
      "verificationStatus": "VERIFIED",
      "confidenceScore": 0.92,
      "sources": [
        {
          "sourceName": "NASA",
          "sourceUrl": "https://climate.nasa.gov/...",
          "verificationTimestamp": "2025-10-22T12:30:00Z",
          "matchQuality": "exact"
        },
        {
          "sourceName": "NOAA",
          "sourceUrl": "https://www.noaa.gov/...",
          "verificationTimestamp": "2025-10-22T12:30:15Z",
          "matchQuality": "close"
        }
      ],
      "verdict": "Claim is accurate based on NASA and NOAA data.",
      "evidenceSummary": "Multiple authoritative sources confirm Arctic sea ice decline rate."
    }
  ],
  "metadata": {
    "verificationTimestamp": "2025-10-22T12:30:20Z",
    "totalClaimsProcessed": 1,
    "verifiedCount": 1,
    "unverifiedCount": 0,
    "averageConfidence": 0.92
  }
}
```

## Running the Service

### Development
```bash
cd src/backend/services/verification_service
export CLIMATECHECK_API_KEY=your_key
export NOAA_API_TOKEN=your_token
export NASA_API_KEY=your_key
python src/main.py
```

### Docker
```bash
docker build -t clilens-verification-service .
docker run \
  -e CLIMATECHECK_API_KEY=your_key \
  -e NOAA_API_TOKEN=your_token \
  -e NASA_API_KEY=your_key \
  clilens-verification-service
```

## Testing
```bash
pytest tests/test_fact_checking.py
pytest tests/test_climate_api.py
```

## Logging
Structured logging with verification context:
- `task_id`: Task identifier
- `claim_id`: Individual claim ID
- `api_source`: Which API is being queried
- `confidence_score`: Verification confidence

## Error Handling
- **API Failures**: Graceful degradation if one source is unavailable
- **Rate Limiting**: Respect API rate limits with exponential backoff
- **Invalid Data**: Log and skip malformed claims
- **Timeout Handling**: 30-second timeout per API call

## Verification Confidence Levels
- **0.95-1.00**: Exact match with multiple authoritative sources
- **0.70-0.94**: Close match or single authoritative source
- **0.50-0.69**: Partial match, conflicting sources, or low confidence
- **< 0.50**: Unverified or conflicting information

## Future Enhancements
- Machine learning model for claim-data matching
- Automated source discovery (find relevant APIs for new claim types)
- Real-time data stream integration
- Scientific paper verification via arXiv/PubMed APIs
- Blockchain-based verification audit trail
