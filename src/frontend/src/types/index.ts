/**
 * TypeScript type definitions shared across the frontend.
 */

// --- Decomposed Confidence (CARF-inspired) ---

export interface DecomposedConfidence {
  model_confidence: number;
  source_quality: number;
  evidence_breadth: number;
  cross_reference_score: number;
  temporal_relevance: number;
  overall: number;
}

export interface EvidenceChainLink {
  step_number: number;
  description: string;
  source: string;
  source_url: string;
  retrieval_method?: string;
  relevance_explanation?: string;
  confidence: number;
  supports_claim: boolean | null;
}

export interface ReliabilityBreakdown {
  [factor: string]: {
    weight: number;
    score: number;
    weighted_score: number;
    label: string;
  };
}

export type ClaimCategory =
  | "scientific_causal"
  | "statistical"
  | "policy"
  | "anecdotal"
  | "predictive";

// --- Core Models ---

export interface Article {
  article_id: string;
  title: string;
  url: string;
  author?: string;
  published_date?: string;
  source_name: string;
  source_credibility_score: number;
  excerpt?: string;
  enriched_excerpt?: string;
  climate_context_summary?: string;
  enrichment_metadata?: {
    weather_match?: boolean;
    source_reliability_assessed?: boolean;
    trend_context?: string;
    temperature_trend?: string;
    enrichment_model?: string;
  };
  claim_count: number;
  verified_claim_count: number;
  claims_status?: "pending" | "processing" | "completed" | "failed";
  claims_error_message?: string;
  claims_processed_at?: string;
  tags: string[];
  content_relevance_score?: number;
  reliability_score?: number;
  overall_credibility: "HIGH" | "MEDIUM" | "LOW";
  created_at: string;
  country_code?: string;
  claims_by_category?: Record<string, number>;
  content_category?: string;
  executive_brief?: string;
  is_synthetic?: boolean;
  provenance?: Record<string, any>;
  source_articles?: Array<{
    article_id: string;
    title: string;
    url: string;
    source_name: string;
    published_at: string;
  }>;
}

export interface FactCheck {
  verification_status: string;
  confidence_score: number;
  justification?: string;
  evidence?: any;
  climatecheck_hazard_type?: string;
  climatecheck_risk_score?: number;
  verified_date?: string;
  decomposed_confidence?: DecomposedConfidence;
  evidence_chain?: EvidenceChainLink[];
}

export interface ClaimDetail {
  claim_id: string;
  claim_text: string;
  claim_context?: string;
  claim_type: string;
  claim_category?: ClaimCategory;
  fact_check?: FactCheck;
}

export type ContentCategory =
  | "climate_science"
  | "sustainability"
  | "circular_economy"
  | "green_transition"
  | "localized_forecast"
  | "policy";

export interface ArticleDetail extends Article {
  full_text?: string;
  language_code: string;
  claims: ClaimDetail[];
  claims_available: boolean;
  decomposed_confidence?: DecomposedConfidence;
  reliability_breakdown?: ReliabilityBreakdown;
  insight_summary?: string;
  analysis_article_html?: string;
  analysis_article_generated_at?: string;
  executive_brief?: string;
  content_category?: ContentCategory;
  enriched_excerpt?: string;
  climate_context_summary?: string;
  enrichment_metadata?: {
    weather_match?: boolean;
    source_reliability_assessed?: boolean;
    trend_context?: string;
    temperature_trend?: string;
    enrichment_model?: string;
  };
}

// --- Dashboard & Workflows ---

export interface DashboardStats {
  total_articles: number;
  articles_today: number;
  total_fact_checks: number;
  verified_claims: number;
  average_confidence: number;
  last_updated?: string;
}

export interface WorkflowStatus {
  task_id: string;
  status: string;
  current_stage?: string;
  started_at?: string;
  completed_at?: string;
  metadata: Record<string, any>;
}

export interface TagStat {
  tag: string;
  article_count: number;
}

// --- Search ---

export interface SearchSuggestion {
  text: string;
  category: "tag" | "country" | "source";
  count: number;
}

export interface SearchHistoryEntry {
  query: string;
  filters?: Record<string, any>;
  result_count?: number;
  timestamp?: string;
}

// --- Feedback ---

export type FeedbackType = "USEFUL" | "NOT_USEFUL" | "FLAGGED";

export interface FeedbackSummary {
  article_id: string;
  total_feedback: number;
  useful: number;
  not_useful: number;
  flagged: number;
  average_reliability?: number;
}

export interface FeedbackRequestPayload {
  feedback_type: FeedbackType;
  reliability_score?: number;
  comment?: string;
  submitted_by?: string;
}

// --- Country ---

export interface Country {
  country_code: string;
  country_name: string;
  country_name_native: string;
  flag_emoji: string;
  articles_count: number;
  is_eu_member: boolean;
  language_code: string;
}

// --- Source Profiles ---

export interface SourceProfile {
  source_id: string;
  source_name: string;
  source_domain: string;
  credibility_score: number;
  editorial_standards: "rigorous" | "moderate" | "low" | "unknown";
  fact_check_record: "excellent" | "good" | "mixed" | "poor" | "unknown";
  transparency_level: "high" | "moderate" | "low" | "unknown";
  total_articles_analyzed: number;
  average_reliability_score: number | null;
  total_claims_verified: number;
  total_claims_disputed: number;
  false_claim_rate: number;
  source_type: string;
  country_code?: string;
  description?: string;
  website_url?: string;
  first_seen_at?: string;
  last_updated_at?: string;
}

// --- URL Analysis ---

export interface AnalyzeUrlRequest {
  url: string;
}

export interface AnalyzeUrlResponse {
  job_id: string;
  status: "processing" | "completed" | "failed";
  estimated_time?: number;
  // HMAC token returned by POST — required on subsequent GETs for anonymous
  // users (defends against UUID-guessing of other users' submissions).
  access_token?: string;
  article?: Article;
  error?: string;
  decomposed_confidence?: DecomposedConfidence;
  reliability_breakdown?: ReliabilityBreakdown;
  insight_summary?: string;
}

// --- Article Q&A ---

export interface ConversationEntry {
  conversation_id?: string;
  question: string;
  answer: string;
  confidence: number;
  context_used: string[];
  model?: string;
  created_at?: string;
  error?: string;
}

export interface ConversationHistory {
  article_id: string;
  entries: ConversationEntry[];
  total: number;
}

// --- Similar Articles ---

export interface SimilarArticle {
  article_id: string;
  title: string;
  source_name: string;
  similarity_score: number;
  published_date?: string;
  overall_credibility: string;
}

// --- Forecasts ---

export interface ForecastSource {
  source_name: string;
  temperature_avg?: number;
  precipitation_mm?: number;
  wind_speed_ms?: number;
  confidence: number;
  fetched_at: string;
}

export interface ForecastComparison {
  country_code: string;
  country_name: string;
  date_range: string;
  sources: ForecastSource[];
  discrepancy_score: number;
  consensus_summary: string;
}

// --- Feed Preferences ---

export interface FeedPreferences {
  country_codes: string[];
  update_frequency: "daily" | "twice_daily" | "four_times_daily" | "hourly";
  keywords: string[];
  last_updated_at?: string;
}

export interface FeedStatus {
  country_code: string;
  last_update: string;
  article_count: number;
  next_update?: string;
}

// --- User Source Registration ---

export interface UserSourceRegistration {
  registration_id: string;
  user_id: string;
  source_name: string;
  source_url: string;
  feed_type: string;
  reliability_tier: string;
  country_code?: string;
  is_active: boolean;
  approved: boolean;
  last_fetched_at?: string;
  fetch_error?: string;
  created_at?: string;
}

export interface FeedValidationResult {
  url: string;
  valid: boolean;
  title?: string;
  item_count: number;
  error?: string;
}

// --- Weather Claim Validation ---

export interface WeatherValidation {
  weather_validated: boolean;
  weather_deviation_pct?: number;
  weather_data_source?: string;
  weather_metric?: string;
  weather_verdict?: "SUPPORTED" | "CONTRADICTED" | "INCONCLUSIVE";
}

// --- Deep Search ---

export interface DeepSearchCitation {
  type: "internal_article" | "external_web";
  article_id?: string;
  title?: string;
  source_name?: string;
  source_url?: string;
  published_date?: string;
  credibility?: string;
  reliability_score?: number;
  relevance_score?: number;
  excerpt?: string;
}

export interface DeepSearchWeatherContext {
  country_code: string;
  data_points: {
    source: string;
    content: string;
    reliability?: string;
    retrieval_method?: string;
  }[];
}

export interface PromptFingerprint {
  name: string;
  version: string;
  fingerprint: string;
}

export interface HallucinationFlagged {
  text: string;
  reason: string;
  severity: "low" | "medium" | "high" | string;
}

export interface HallucinationCheck {
  hallucination_risk: number;       // 0..1; lower = better grounded
  is_grounded: boolean;
  flagged_segments: HallucinationFlagged[];
  entity_overlap_score?: number;    // 0..1; higher = better
  statistic_accuracy?: number;      // 0..1; higher = better
  overall_confidence?: number;      // 0..1
  checks_performed?: string[];
  prompt?: PromptFingerprint;        // present when the LLM-grounding sub-check ran
}

export interface DeepSearchMethodology {
  queries_run?: { layer: string; scope?: Record<string, any>; hits?: number; skipped?: boolean }[];
  weather_used?: boolean;
  synthesis_model?: string;
  embedding_model?: string;
  external_provider_configured?: boolean;
  sources_consulted?: string[];
  // Phase 4 wave 1 (2026-05-16): the synthesis prompt template is version-
  // pinned via the central registry; this records which version produced
  // this answer.
  retrieval_strategy?: string;
  prompts_used?: { synthesis?: PromptFingerprint } & Record<string, PromptFingerprint | undefined>;
  // Phase 6 wave 2 (2026-05-16): HallucinationDetector runs against the
  // synthesised text + source articles. Null when no sources / detector
  // erored — clients should render "not run" rather than treating absence
  // as "all good".
  hallucination_check?: HallucinationCheck | null;
}

export interface ComparativeAnalysisStructured {
  summary: string;
  similarities: string[];
  differences: string[];
  evidence_strength: "balanced" | "topic_a_stronger" | "topic_b_stronger" | "weak" | string;
  common_gaps: string[];
}

export interface DeepSearchResult {
  query: string;
  answer: string;
  citations: DeepSearchCitation[];
  internal_articles_count: number;
  external_sources_count: number;
  weather_context?: DeepSearchWeatherContext;
  filters: Record<string, any>;
  methodology?: DeepSearchMethodology;
  clarification_needed?: string[];
  searched_at: string;
}

export interface CompareResult {
  query_a: string;
  query_b: string;
  result_a: DeepSearchResult;
  result_b: DeepSearchResult;
  comparative_analysis: string;
  comparative_analysis_structured?: ComparativeAnalysisStructured;
  compared_at: string;
}

// --- Weather Context ---

export interface LocationWeatherContext {
  location_name: string;
  coordinates: { lat: number; lon: number };
  current_weather?: {
    temperature_c?: number;
    humidity_pct?: number;
    precipitation_mm?: number;
    wind_speed_kmh?: number;
    weather_code?: number;
  };
  forecast_7day?: {
    dates: string[];
    max_temps: (number | null)[];
    min_temps: (number | null)[];
    precipitation: (number | null)[];
  };
  historical_normals?: {
    period: string;
    avg_temperature_c: number;
    avg_precipitation_mm: number;
  };
  anomaly?: {
    temperature_deviation_c: number;
    is_anomalous: boolean;
    anomaly_description: string;
  };
}

export interface ArticleWeatherContext {
  article_id: string;
  locations_found: number;
  locations_analyzed: number;
  weather_contexts: LocationWeatherContext[];
}

// --- Analytics ---

export interface ArticleTrend {
  date: string;
  articles_ingested: number;
  articles_verified: number;
  articles_failed: number;
}

export interface ClaimCategoryBreakdown {
  category: string;
  count: number;
  verified: number;
  disputed: number;
  unverified: number;
  avg_confidence: number;
}

export interface SourcePerformance {
  source_name: string;
  source_domain?: string;
  total_articles: number;
  total_claims: number;
  verified_claims: number;
  disputed_claims: number;
  avg_credibility: number;
  false_claim_rate: number;
}

export interface VerificationVerdictDistribution {
  verified: number;
  disputed: number;
  partially_true: number;
  unverified: number;
  total: number;
}

export interface CountryArticleStats {
  country_code: string;
  country_name?: string;
  article_count: number;
  verified_count: number;
  avg_credibility: number;
}

export interface PipelineStatus {
  total_articles: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  ingested_today: number;
  verified_today: number;
  verification_rate: number;
  avg_processing_time_hours?: number;
}

export interface AnalyticsDashboard {
  pipeline: PipelineStatus;
  verdict_distribution: VerificationVerdictDistribution;
  trends_7d: ArticleTrend[];
  top_sources: SourcePerformance[];
  claim_categories: ClaimCategoryBreakdown[];
  country_stats: CountryArticleStats[];
  generated_at: string;
}

// --- User Auth & Dashboard ---

export interface UserProfile {
  user_id: string;
  email: string;
  full_name: string;
  subscription_tier: "FREEMIUM" | "BASIC" | "PROFESSIONAL" | "ENTERPRISE";
  is_verified: boolean;
  created_at: string;
}

export interface ReadingHistoryEntry {
  history_id: string;
  article_id: string;
  article_title: string;
  article_source: string;
  article_credibility?: string;
  read_at: string;
  read_duration_seconds?: number;
}

export interface Bookmark {
  bookmark_id: string;
  article_id: string;
  article_title: string;
  article_source: string;
  article_credibility?: string;
  folder: string;
  notes?: string;
  created_at: string;
}

export interface UserDashboardStats {
  articles_read_week: number;
  articles_read_total: number;
  bookmarks_count: number;
  searches_count: number;
  days_active: number;
  current_tier: string;
  tier_usage: {
    articles_today: number;
    articles_limit: number;
    api_calls_today: number;
    api_calls_limit: number;
  };
}

// --- Map Intelligence ---

export interface MapCountryDetail {
  country_code: string;
  country_name: string;
  continent?: string;
  region?: string;
  flag_emoji?: string;
  coordinates?: { lat: number; lon: number };
  weather?: {
    temperature_c: number;
    humidity_pct: number;
    precipitation_mm: number;
    wind_speed_kmh: number;
  };
  temperature_anomaly?: {
    current: number;
    historical_avg: number;
    deviation: number;
    trend: string;
  };
  article_stats: {
    total: number;
    by_category: Record<string, number>;
    avg_credibility: number;
  };
  recent_articles: {
    article_id: string;
    title: string;
    source_name: string;
    published_date?: string;
    credibility?: string;
    excerpt?: string;
  }[];
  source_coverage: { source_name: string; article_count: number; avg_reliability?: number }[];
  climate_risk: {
    risk_score: number;
    claim_count: number;
    disputed_ratio: number;
  };
}

export interface MapQueryResponse {
  query: string;
  answer: string;
  highlighted_countries: string[];
  matching_articles: number;
  country_highlights: {
    country_code: string;
    country_name: string;
    article_count: number;
    avg_credibility_score?: number;
  }[];
  session_id?: string;
}

// --- Knowledge Graph ---

export interface KnowledgeEntity {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  description?: string;
  article_count: number;
}

export interface EntityRelationship {
  source: KnowledgeEntity;
  target: KnowledgeEntity;
  relationship_type: string;
  strength: number;
  evidence_text?: string;
}

export interface ArticleEntityGraph {
  entities: KnowledgeEntity[];
  relationships: EntityRelationship[];
  connected_articles: { article_id: string; title: string; connection_path: string }[];
}

// --- Intelligence Brief ---

export interface IntelligenceBrief {
  topic: string;
  summary: string;
  key_findings: string[];
  consensus_areas: string[];
  disputed_areas: string[];
  data_gaps: string[];
  article_count: number;
  source_count: number;
  generated_at: string;
}
