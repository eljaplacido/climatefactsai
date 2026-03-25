-- =============================================================================
-- CLIMATE NEWS MULTI-AGENT SYSTEM - DATABASE INITIALIZATION
-- =============================================================================
-- PostgreSQL + pgvector -tietokantaskeema
-- 
-- Tämä skripti luo kaikki tarvittavat taulut pitkäaikaiseen muistiin:
-- 1. Articles (artikkeliarkisto)
-- 2. Claims (faktatarkistetut väitteet)
-- 3. FactChecks (todennukset)
-- 4. SourceCredibility (lähteiden uskottavuus)
-- 5. ContentPackages (julkaistut sisältöpaketit)
-- =============================================================================

-- Aktivoi pgvector-laajennus
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- MIGRATION REGISTRY — tracks which migrations have been applied
-- =============================================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);

-- Seed initial migration entry for this init script
INSERT INTO schema_migrations (version, description)
VALUES (0, 'init.sql - core schema creation')
ON CONFLICT (version) DO NOTHING;

-- =============================================================================
-- SOURCE CREDIBILITY TABLE
-- Ylläpitää tietoa uutislähteistä ja niiden uskottavuuspisteistä
-- =============================================================================

CREATE TABLE IF NOT EXISTS source_credibility (
    source_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_name VARCHAR(255) NOT NULL UNIQUE,
    source_url TEXT NOT NULL,
    source_type VARCHAR(50) DEFAULT 'news_website', -- news_website, blog, social_media
    
    -- Uskottavuuspisteet (Ad Fontes Media / NewsGuard -tyyli)
    overall_score INTEGER CHECK (overall_score >= 0 AND overall_score <= 100),
    factual_reporting_score INTEGER CHECK (factual_reporting_score >= 0 AND factual_reporting_score <= 100),
    transparency_score INTEGER CHECK (transparency_score >= 0 AND transparency_score <= 100),
    opinion_vs_news_score INTEGER CHECK (opinion_vs_news_score >= 0 AND opinion_vs_news_score <= 100),
    
    -- Metatiedot
    country_code CHAR(2), -- ISO 3166-1 alpha-2
    language_code CHAR(2), -- ISO 639-1
    is_active BOOLEAN DEFAULT true,
    last_reviewed_at TIMESTAMP WITH TIME ZONE,
    
    -- Aikaleimoja
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_source_credibility_score ON source_credibility(overall_score DESC);
CREATE INDEX idx_source_credibility_name ON source_credibility(source_name);

-- =============================================================================
-- ARTICLES TABLE
-- Arkistoi kaikki käsitellyt artikkelit
-- =============================================================================

CREATE TABLE IF NOT EXISTS articles (
    article_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Perusmetatiedot
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    author VARCHAR(255),
    published_date TIMESTAMP WITH TIME ZONE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Lähdetiedot
    source_id UUID REFERENCES source_credibility(source_id),
    source_name VARCHAR(255),
    
    -- Sisältö
    extracted_text TEXT NOT NULL,
    excerpt TEXT,
    language_code CHAR(2) DEFAULT 'fi',
    
    -- Vektori semanttiseen hakuun (OpenAI ada-002 = 1536 dimensions)
    embedding vector(1536),
    
    -- Kategoriat ja tagit
    categories TEXT[], -- Array of category strings
    tags TEXT[],
    
    -- Paikkatieto
    location_name VARCHAR(255),
    location_latitude DECIMAL(10, 8),
    location_longitude DECIMAL(11, 8),
    location_country CHAR(2),
    
    -- Laatumetriikat
    source_credibility_score INTEGER,
    content_relevance_score DECIMAL(3, 2), -- 0.00 - 1.00
    reliability_score INTEGER CHECK (reliability_score >= 0 AND reliability_score <= 100),
    overall_credibility VARCHAR(20), -- HIGH, MEDIUM, LOW, MIXED
    
    -- Tehtävä-ID (linkki workflow:hun)
    task_id VARCHAR(50),
    
    -- Tilastoja
    claims_count INTEGER DEFAULT 0,
    verified_claims_count INTEGER DEFAULT 0,
    
    -- Aikaleimoja
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indeksit
CREATE INDEX idx_articles_published_date ON articles(published_date DESC);
CREATE INDEX idx_articles_task_id ON articles(task_id);
CREATE INDEX idx_articles_source ON articles(source_id);
CREATE INDEX idx_articles_location ON articles(location_name);
CREATE INDEX idx_articles_credibility ON articles(overall_credibility);

-- Vektori-indeksi semanttiseen hakuun (IVFFlat-algoritmi)
CREATE INDEX idx_articles_embedding ON articles 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- =============================================================================
-- CLAIMS TABLE
-- Tallentaa kaikki tunnistetut väitteet artikkeleista
-- =============================================================================

CREATE TABLE IF NOT EXISTS claims (
    claim_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Linkki artikkeliin
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    
    -- Väitteen sisältö
    claim_text TEXT NOT NULL,
    claim_context TEXT, -- Konteksti artikkelissa
    claim_type VARCHAR(50), -- factual_data, prediction, policy_statement, etc.
    
    -- Paikkatieto
    location_name VARCHAR(255),
    location_latitude DECIMAL(10, 8),
    location_longitude DECIMAL(11, 8),
    location_country CHAR(2),
    
    -- NER-entiteetit (JSON-muodossa)
    entities JSONB,
    
    -- Aikaleimoja
    identified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_claims_article ON claims(article_id);
CREATE INDEX idx_claims_type ON claims(claim_type);
CREATE INDEX idx_claims_location ON claims(location_name);

-- =============================================================================
-- FACT_CHECKS TABLE
-- Tallentaa kaikki suoritetut faktatarkistukset
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_checks (
    fact_check_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Linkki väitteeseen
    claim_id UUID NOT NULL REFERENCES claims(claim_id) ON DELETE CASCADE,
    
    -- Todennuksen tulos
    verification_status VARCHAR(20) NOT NULL, -- VERIFIED, UNVERIFIED, MISLEADING, LACKS_CONTEXT, FALSE
    confidence_score DECIMAL(3, 2) NOT NULL, -- 0.00 - 1.00
    justification TEXT NOT NULL,
    
    -- Todistusaineisto (JSON-array)
    evidence JSONB NOT NULL,
    
    -- ClimateCheck-tiedot (jos sovellettavissa)
    climatecheck_hazard_type VARCHAR(50),
    climatecheck_risk_score INTEGER CHECK (climatecheck_risk_score >= 1 AND climatecheck_risk_score <= 100),
    
    -- Agentti-info
    fact_check_agent_version VARCHAR(50),
    processing_time_ms INTEGER,
    
    -- API-kutsut
    api_calls_made JSONB, -- {"climateCheck": 2, "noaa": 1, "nasa": 1}
    
    -- Tehtävä-ID
    task_id VARCHAR(50),
    
    -- Aikaleimoja
    verified_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fact_checks_claim ON fact_checks(claim_id);
CREATE INDEX idx_fact_checks_status ON fact_checks(verification_status);
CREATE INDEX idx_fact_checks_confidence ON fact_checks(confidence_score DESC);
CREATE INDEX idx_fact_checks_task ON fact_checks(task_id);
CREATE INDEX idx_fact_checks_verified_at ON fact_checks(verified_at DESC);

-- =============================================================================
-- CONTENT_PACKAGES TABLE
-- Tallentaa julkaistut sisältöpaketit (yhteenveto + video)
-- =============================================================================

CREATE TABLE IF NOT EXISTS content_packages (
    package_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Tehtävä-ID (linkki workflow:hun)
    task_id VARCHAR(50) NOT NULL UNIQUE,
    
    -- Sisältö
    headline TEXT NOT NULL,
    excerpt TEXT,
    summary_markdown TEXT NOT NULL,
    summary_plain_text TEXT NOT NULL,
    
    -- Video
    video_url TEXT,
    video_duration_seconds INTEGER,
    
    -- Metatiedot
    publication_date TIMESTAMP WITH TIME ZONE NOT NULL,
    language_code CHAR(2) DEFAULT 'fi',
    
    -- Kohdepaikkatieto
    target_location_name VARCHAR(255),
    target_location_latitude DECIMAL(10, 8),
    target_location_longitude DECIMAL(11, 8),
    target_location_country CHAR(2),
    
    -- Kategoriat ja tagit
    categories TEXT[],
    tags TEXT[],
    
    -- Lähteet (JSON-array article_id:istä)
    source_article_ids JSONB NOT NULL,
    
    -- Laatumetriikat
    content_relevance_score DECIMAL(3, 2),
    semantic_similarity DECIMAL(3, 2),
    keyword_coverage DECIMAL(3, 2),
    readability_grade_level DECIMAL(4, 2),
    average_source_credibility INTEGER,
    
    -- Tilastoja
    word_count INTEGER,
    estimated_reading_time_minutes INTEGER,
    verified_claims_count INTEGER DEFAULT 0,
    
    -- HITL-tarkistus
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    hitl_feedback TEXT,
    
    -- Julkaisustatus
    published_to_cms BOOLEAN DEFAULT false,
    cms_content_id VARCHAR(100),
    published_urls TEXT[],
    
    -- Aikaleimoja
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_content_packages_task ON content_packages(task_id);
CREATE INDEX idx_content_packages_publication_date ON content_packages(publication_date DESC);
CREATE INDEX idx_content_packages_location ON content_packages(target_location_name);
CREATE INDEX idx_content_packages_cms_status ON content_packages(published_to_cms);

-- =============================================================================
-- WORKFLOW_LOGS TABLE
-- Tallentaa workflow-tasoiset logit auditointia varten
-- =============================================================================

CREATE TABLE IF NOT EXISTS workflow_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id VARCHAR(50) NOT NULL,
    
    -- Log-tiedot
    stage VARCHAR(50) NOT NULL, -- discovery, factChecking, contentCreation, etc.
    event_type VARCHAR(50) NOT NULL, -- started, completed, failed
    status VARCHAR(20), -- IN_PROGRESS, COMPLETED, FAILED
    
    message TEXT,
    error_message TEXT,
    metadata JSONB,
    
    -- Aikaleima
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_workflow_logs_task ON workflow_logs(task_id);
CREATE INDEX idx_workflow_logs_stage ON workflow_logs(stage);
CREATE INDEX idx_workflow_logs_timestamp ON workflow_logs(timestamp DESC);

-- =============================================================================
-- COST_TRACKING TABLE
-- Seuraa API-kustannuksia tehtävä- ja päivätasolla
-- =============================================================================

CREATE TABLE IF NOT EXISTS cost_tracking (
    cost_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id VARCHAR(50) NOT NULL,
    
    -- Kustannustyyppi
    cost_type VARCHAR(50) NOT NULL, -- llm_claude, llm_gpt4o, api_climatecheck, etc.
    cost_usd DECIMAL(10, 6) NOT NULL,
    
    -- LLM-tiedot (jos sovellettavissa)
    model_name VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    
    -- Metatiedot
    details JSONB,
    
    -- Aikaleima
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cost_tracking_task ON cost_tracking(task_id);
CREATE INDEX idx_cost_tracking_type ON cost_tracking(cost_type);
CREATE INDEX idx_cost_tracking_timestamp ON cost_tracking(timestamp DESC);

-- =============================================================================
-- HELPER VIEWS
-- Näkymät helpottamaan tiedon hakemista
-- =============================================================================

-- Näkymä: Päivittäiset kustannukset
CREATE OR REPLACE VIEW daily_costs AS
SELECT 
    DATE(timestamp) as date,
    cost_type,
    SUM(cost_usd) as total_cost_usd,
    COUNT(*) as api_call_count
FROM cost_tracking
GROUP BY DATE(timestamp), cost_type
ORDER BY date DESC, total_cost_usd DESC;

-- Näkymä: Artikkelit verifioiduilla väitteillä
CREATE OR REPLACE VIEW articles_with_verifications AS
SELECT 
    a.article_id,
    a.title,
    a.url,
    a.published_date,
    a.source_name,
    a.source_credibility_score,
    a.overall_credibility,
    COUNT(c.claim_id) as total_claims,
    COUNT(CASE WHEN fc.verification_status = 'VERIFIED' THEN 1 END) as verified_claims,
    COUNT(CASE WHEN fc.verification_status = 'FALSE' THEN 1 END) as false_claims,
    AVG(fc.confidence_score) as avg_confidence
FROM articles a
LEFT JOIN claims c ON a.article_id = c.article_id
LEFT JOIN fact_checks fc ON c.claim_id = fc.claim_id
GROUP BY a.article_id;

-- =============================================================================
-- TRIGGER FUNCTIONS
-- Automaattiset päivitykset
-- =============================================================================

-- Trigger: Päivitä updated_at automaattisesti
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Liitä trigger tauluihin
CREATE TRIGGER update_articles_updated_at
    BEFORE UPDATE ON articles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_source_credibility_updated_at
    BEFORE UPDATE ON source_credibility
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_content_packages_updated_at
    BEFORE UPDATE ON content_packages
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- COUNTRIES TABLE
-- Reference table for supported countries with metadata
-- =============================================================================

CREATE TABLE IF NOT EXISTS countries (
    country_code CHAR(2) PRIMARY KEY, -- ISO 3166-1 alpha-2
    country_name VARCHAR(100) NOT NULL,
    country_name_native VARCHAR(100),
    flag_emoji VARCHAR(10),
    language_code CHAR(2) NOT NULL, -- Primary language (ISO 639-1)
    is_eu_member BOOLEAN DEFAULT false,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_countries_enabled ON countries(enabled);
CREATE INDEX idx_countries_eu_member ON countries(is_eu_member);

-- Add country_code foreign key constraint to articles table
ALTER TABLE articles ADD CONSTRAINT fk_articles_country
    FOREIGN KEY (country_code) REFERENCES countries(country_code) ON DELETE SET NULL;

-- =============================================================================
-- SEED DATA
-- Alustusdataa kehitystä ja testausta varten
-- =============================================================================

-- EU Countries (31 total - 27 EU members + 4 EEA/EFTA)
INSERT INTO countries (country_code, country_name, country_name_native, flag_emoji, language_code, is_eu_member, enabled)
VALUES
    -- Nordic Countries
    ('FI', 'Finland', 'Suomi', '🇫🇮', 'fi', true, true),
    ('SE', 'Sweden', 'Sverige', '🇸🇪', 'sv', true, true),
    ('DK', 'Denmark', 'Danmark', '🇩🇰', 'da', true, true),
    ('NO', 'Norway', 'Norge', '🇳🇴', 'no', false, true), -- EEA
    ('IS', 'Iceland', 'Ísland', '🇮🇸', 'is', false, true), -- EEA

    -- Western Europe
    ('DE', 'Germany', 'Deutschland', '🇩🇪', 'de', true, true),
    ('FR', 'France', 'France', '🇫🇷', 'fr', true, true),
    ('NL', 'Netherlands', 'Nederland', '🇳🇱', 'nl', true, true),
    ('BE', 'Belgium', 'België', '🇧🇪', 'nl', true, true),
    ('LU', 'Luxembourg', 'Luxembourg', '🇱🇺', 'fr', true, true),
    ('AT', 'Austria', 'Österreich', '🇦🇹', 'de', true, true),
    ('CH', 'Switzerland', 'Schweiz', '🇨🇭', 'de', false, true), -- EFTA
    ('LI', 'Liechtenstein', 'Liechtenstein', '🇱🇮', 'de', false, true), -- EEA

    -- Southern Europe
    ('ES', 'Spain', 'España', '🇪🇸', 'es', true, true),
    ('PT', 'Portugal', 'Portugal', '🇵🇹', 'pt', true, true),
    ('IT', 'Italy', 'Italia', '🇮🇹', 'it', true, true),
    ('GR', 'Greece', 'Ελλάδα', '🇬🇷', 'el', true, true),
    ('MT', 'Malta', 'Malta', '🇲🇹', 'mt', true, true),
    ('CY', 'Cyprus', 'Κύπρος', '🇨🇾', 'el', true, true),

    -- Eastern Europe
    ('PL', 'Poland', 'Polska', '🇵🇱', 'pl', true, true),
    ('CZ', 'Czech Republic', 'Česko', '🇨🇿', 'cs', true, true),
    ('SK', 'Slovakia', 'Slovensko', '🇸🇰', 'sk', true, true),
    ('HU', 'Hungary', 'Magyarország', '🇭🇺', 'hu', true, true),
    ('RO', 'Romania', 'România', '🇷🇴', 'ro', true, true),
    ('BG', 'Bulgaria', 'България', '🇧🇬', 'bg', true, true),
    ('SI', 'Slovenia', 'Slovenija', '🇸🇮', 'sl', true, true),
    ('HR', 'Croatia', 'Hrvatska', '🇭🇷', 'hr', true, true),

    -- Baltic Countries
    ('EE', 'Estonia', 'Eesti', '🇪🇪', 'et', true, true),
    ('LV', 'Latvia', 'Latvija', '🇱🇻', 'lv', true, true),
    ('LT', 'Lithuania', 'Lietuva', '🇱🇹', 'lt', true, true),

    -- Ireland
    ('IE', 'Ireland', 'Éire', '🇮🇪', 'en', true, true)
ON CONFLICT (country_code) DO NOTHING;

-- Lisää esimerkkejä uutislähteistä
INSERT INTO source_credibility (source_name, source_url, overall_score, factual_reporting_score, transparency_score, country_code, language_code)
VALUES
    ('Helsingin Sanomat', 'https://www.hs.fi', 85, 90, 85, 'FI', 'fi'),
    ('Yle', 'https://yle.fi', 92, 95, 90, 'FI', 'fi'),
    ('MTV Uutiset', 'https://www.mtvuutiset.fi', 80, 82, 78, 'FI', 'fi')
ON CONFLICT (source_name) DO NOTHING;

-- =============================================================================
-- GRANTS & PERMISSIONS
-- Käyttöoikeudet (tuotannossa tarkemmat oikeudet)
-- =============================================================================

-- Luo read-only -käyttäjä raportointia varten (valinnainen)
-- CREATE USER climatenews_readonly WITH PASSWORD 'your_password_here';
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO climatenews_readonly;

COMMIT;

-- =============================================================================
-- ARTICLE_FEEDBACK TABLE
-- Captures user feedback on fact check quality / usefulness
-- =============================================================================

CREATE TABLE IF NOT EXISTS article_feedback (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    article_id UUID NOT NULL REFERENCES articles(article_id) ON DELETE CASCADE,
    feedback_type VARCHAR(20) NOT NULL, -- USEFUL, NOT_USEFUL, FLAGGED
    reliability_score INTEGER CHECK (reliability_score BETWEEN 0 AND 100),
    comment TEXT,
    submitted_by VARCHAR(100),
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_article ON article_feedback(article_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON article_feedback(feedback_type);
