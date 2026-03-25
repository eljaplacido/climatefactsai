# Content Creation Service

## Purpose
The Content Creation Service transforms verified claims and raw article data into polished, reader-friendly content. It generates article summaries, creates narrative structures, and prepares content for publication on the CliLens.AI platform.

## Core Responsibilities
1. **Article Synthesis**: Create coherent narratives from verified claims
2. **Summarization**: Generate concise summaries of complex climate topics
3. **Fact Highlighting**: Integrate verification badges and source attribution
4. **Multi-Format Output**: Prepare content for web, mobile, and future video formats
5. **Localization**: Adapt content for different languages and regions (future)

## Architecture

### Components
- `content_creator.py`: Core content generation logic using LLMs
- `__init__.py`: Service initialization and exports

### Dependencies
- **Shared Modules**: `shared.config`, `shared.logger`, `shared.kafka_client`, `shared.database`
- **LLM Integration**: Anthropic Claude 3.5 Sonnet for text generation
- **Templates**: Markdown/HTML templates for article formatting

## Data Flow

```
Kafka (content_creation_queue)
  → Verified Claims + Article Data
  → LLM Prompt Construction
  → Claude 3.5 Sonnet API
  → Content Generation
  → Formatting & Structuring
  → Database Storage
  → Kafka (publication_queue)
  → Publication
```

## Content Generation Process

### 1. Input Processing
Receive verified claims and source article:
- Extract high-confidence claims (≥0.70)
- Gather source metadata
- Identify key themes and topics

### 2. Prompt Engineering
Construct structured prompt for Claude:
```
You are a climate journalist writing for CliLens.AI. Create a concise,
fact-based summary of the following verified information:

Verified Claims:
- [Claim 1] (Confidence: 0.95, Sources: NASA, NOAA)
- [Claim 2] (Confidence: 0.88, Sources: ClimateCheck)

Source Article:
Title: "Arctic Ice Melting Accelerates"
URL: https://...

Requirements:
- 3-5 paragraphs, ~300 words
- Lead with most important fact
- Include verification badges for each claim
- Maintain neutral, journalistic tone
- Target audience: General public (Z-Gen)
```

### 3. LLM Generation
Call Claude 3.5 Sonnet API:
- Temperature: 0.3 (for consistency)
- Max tokens: 1500
- System prompt: Climate journalism guidelines

### 4. Post-Processing
- Inject interactive fact-check elements
- Add source attribution links
- Format for responsive web display
- Generate metadata (tags, categories)

### 5. Quality Checks
- Verify all claims are sourced
- Check tone and readability
- Validate formatting
- Ensure mobile-friendly structure

## Kafka Integration

### Consumes From
- `content_creation_queue`: Verified claims from Verification Service
  - Schema: `schemas/factcheck_to_creation.json`

### Produces To
- `publication_queue`: Finalized articles ready for publication
  - Schema: `schemas/creation_to_publication.json`

## Configuration
- `llm.provider`: LLM provider (default: "anthropic")
- `llm.model`: Model name (default: "claude-3-5-sonnet-20241022")
- `llm.temperature`: Generation temperature (default: 0.3)
- `llm.max_tokens`: Maximum output tokens (default: 1500)
- `content.target_word_count`: Target article length (default: 300)
- `content.reading_level`: Target reading level (default: "general")

## Database Schema

### Tables Used
- `generated_articles`: Stores finalized article content
- `article_metadata`: Tags, categories, and metadata
- `content_versions`: Version history for HITL edits

## API Contract

### Input (Kafka Message)
From `factcheck_to_creation.json` schema:
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
      "sources": [...]
    }
  ],
  "sourceArticle": {
    "title": "Arctic Ice Melting Accelerates",
    "url": "https://...",
    "extractedText": "Full article text..."
  }
}
```

### Output (Kafka Message)
To `creation_to_publication.json` schema:
```json
{
  "schemaVersion": "1.0",
  "taskId": "task-20251022-001",
  "articleId": "uuid",
  "generatedContent": {
    "title": "Arctic Sea Ice Decline Accelerates: What the Data Shows",
    "summary": "Short 1-2 sentence summary...",
    "body": "Full article HTML with fact-check markers...",
    "wordCount": 287,
    "readingTimeMinutes": 2
  },
  "factCheckElements": [
    {
      "claimId": "uuid",
      "displayText": "Arctic sea ice decreased by 13% per decade",
      "verificationBadge": "CliLens.AI Verified",
      "sources": ["NASA", "NOAA"],
      "confidenceScore": 0.92
    }
  ],
  "metadata": {
    "tags": ["arctic", "sea-ice", "climate-change"],
    "category": "polar-regions",
    "publishedDate": "2025-10-22T14:00:00Z",
    "language": "en",
    "targetAudience": "general"
  }
}
```

## Running the Service

### Development
```bash
cd src/backend/services/content_creation_service
export ANTHROPIC_API_KEY=your_key
python src/content_creator.py
```

### Docker
```bash
docker build -t clilens-content-creation-service .
docker run -e ANTHROPIC_API_KEY=your_key clilens-content-creation-service
```

## Testing
```bash
pytest tests/test_content_creation.py
```

## Logging
Structured logging with content generation context:
- `task_id`: Task identifier
- `article_id`: Article UUID
- `llm_model`: Which model was used
- `generation_time_ms`: Time to generate content
- `word_count`: Final article word count

## Error Handling
- **LLM API Failures**: Retry with exponential backoff
- **Rate Limiting**: Queue requests during high load
- **Content Quality**: Flag low-quality outputs for HITL review
- **Timeout**: 60-second timeout for LLM calls

## Content Quality Metrics
- Factual accuracy (all claims sourced)
- Readability score (Flesch reading ease)
- Engagement potential (headline quality)
- Mobile responsiveness
- Load time optimization

## Future Enhancements
- Multi-language content generation
- A/B testing for different content formats
- Personalized content based on user preferences
- Automatic video script generation (integration with Video Production Service)
- SEO optimization and meta tag generation
- Social media snippet generation
