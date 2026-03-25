/**
 * TypeScript type definitions
 */

export interface Article {
  article_id: string;
  title: string;
  url: string;
  author?: string;
  published_date?: string;
  source_name: string;
  source_credibility_score: number;
  excerpt?: string;
  claim_count: number;
  verified_claim_count: number;
  tags: string[];
  content_relevance_score?: number;
  reliability_score?: number;
  overall_credibility: "HIGH" | "MEDIUM" | "LOW";
  created_at: string;
}

export interface FactCheck {
  verification_status: string;
  confidence_score: number;
  justification?: string;
  evidence?: any;
  climatecheck_hazard_type?: string;
  climatecheck_risk_score?: number;
  verified_date?: string;
}

export interface ClaimDetail {
  claim_id: string;
  claim_text: string;
  claim_context?: string;
  claim_type: string;
  fact_check?: FactCheck;
}

export interface ArticleDetail extends Article {
  full_text?: string;
  language_code: string;
  claims: ClaimDetail[];
}

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
