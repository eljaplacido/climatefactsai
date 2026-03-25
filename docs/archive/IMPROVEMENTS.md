High‑leverage additions for debugging + scale + robustness
Observability (do this first)
End‑to‑end tracing via OpenTelemetry (you already depend on it): standardize on OTLP export + a collector, then instrument FastAPI + SQLAlchemy + Redis + Celery so one request shows the whole pipeline in traces (Jaeger/Tempo). You already list OTel deps in requirements.txt:
opentelemetry-api==1.28.2          # OpenTelemetry APIopentelemetry-sdk==1.28.2          # OpenTelemetry SDKopentelemetry-instrumentation==0.49b2  # Auto-instrumentationopentelemetry-exporter-otlp==1.28.2    # OTLP exporterprometheus-client==0.21.0          # Prometheus metrics
FastAPI metrics that “just work”: add prometheus-fastapi-instrumentator for consistent HTTP metrics (latency buckets, status groups, per-route) instead of ad-hoc prometheus-client usage.
Error tracking + performance: add Sentry on both sides:
Backend: sentry-sdk[fastapi] (captures exceptions + traces)
Frontend: @sentry/nextjs (captures client/server rendering errors)
Celery visibility: add Flower (operator UI) and/or a Prometheus exporter for Celery queue depth / task runtime (critical when debugging “stuck pipelines”).
LLM/agent observability + evaluators (prevents silent regressions)
Langfuse (open-source): tracing, prompt versioning, datasets/experiments, and “LLM-as-judge” style evals. Good fit because you’re iterating prompts and multi-agent flows.
Arize Phoenix (open-source): excellent for trace + evaluation, and plays well with OpenTelemetry/OTLP. Especially useful once you lean harder into retrieval/pgvector.
Prompt regression testing in CI: Promptfoo (open-source) to run prompt suites + red teaming (prompt-injection, leakage) and fail PRs on regressions.
RAG evaluation (if/when you use pgvector retrieval heavily): add RAGAS (or Phoenix’s built-in eval templates) for relevance/faithfulness/hallucination metrics on a fixed dataset.
Architectural improvements (robustness + scaling without pain)
Pick one primary async backbone: right now you have Kafka + Schema Registry and Celery/Redis in deps and compose. That’s a lot of operational surface area. For MVP velocity, your own plan doc argues for Redis/Celery + modular monolith, unless you truly need Kafka-level streaming semantics.
Make async processing safe by design (works for both Kafka or Celery):
Idempotency keys per job/message (dedupe on article_url / content_hash)
Retry policy with backoff + DLQ (Celery: retry + dead-letter routing; Kafka: retry topics + DLQ topics)
Outbox pattern for “write DB then emit event” consistency (prevents ghost publishes)
Unify the backend surface area: you currently have api/ (FastAPI app) and separate src/backend/services/* containers. If you keep microservices, enforce hard boundaries and contracts; if you pivot to a modular monolith, collapse to one deployable + workers to reduce distributed debugging.
Secrets hygiene (robustness + security): your docker-compose.yml contains a hardcoded API key (this will eventually leak via logs, screenshots, git, etc.). This is the single most urgent robustness fix to prevent accidental compromise:
api:  build:    context: .    dockerfile: api/Dockerfile  container_name: clilens-api  depends_on:    - postgres    - redis    - kafka  ports:    - "5200:8000"  environment:    - ENVIRONMENT=development    - PYTHONPATH=/app/src/backend    - ANTHROPIC_API_KEY=sk-ant-api03-...  env_file:    - .env
Quality gates / “evaluators” beyond LLMs
API contract tests: consumer-driven contracts (e.g., Pact) so frontend↔API changes don’t break silently.
Data quality checks for ingestion: Great Expectations (or lightweight schema checks) so “bad scrapes” don’t cascade into LLM costs and failures.
Security automation: pip-audit + bandit + semgrep in CI; on frontend, keep npm audit and add dependency review.

Would CliLens benefit from HumanLayer right now?
Yes—if you’re actually going to run HITL (human review) during MVP. Your code already has a dedicated HITL stage and a moderation queue concept, but the “notify a human and wait for approval” part is mostly a stub. HumanLayer is essentially the missing “human approval + routing + inbox” layer so you don’t have to build Slack/Email workflows + state handling yourself.
Where it fits in your current code
You already have an explicit HITL stage in orchestration (notification TODO):
def _trigger_hitl_review(self, task_id: str) -> bool:    """Käynnistä Human-in-the-Loop -tarkistus"""    self.logger.info("Triggering HITL review", task_id=task_id)    self.state_machine.transition_to(task_id, WorkflowStatus.HITL_REVIEW)    self.state_machine.update_stage(        task_id=task_id,        stage_name="hitlReview",        stage_status=StageStatus.IN_PROGRESS    )    # Lähetä notifikaatio tarkistajalle (esim. Slack webhook)    # Tämä toteutetaan myöhemmin    self.logger.info(        "HITL notification sent",        task_id=task_id,        review_url=f"http://review.climatenews.com/task/{task_id}"    )    return True
And you already model a moderation queue in the trust domain:
def queue_hitl_review(    self,    *,    article_id: str,    priority: int,    assigned_to: Optional[str] = None,    reason: Optional[str] = None,) -> Dict[str, Any]:    """Insert into moderation queue when LangGraph routes to HITL."""    queue_row = self.moderation.enqueue(        article_id=article_id,        priority=priority,        assigned_to=assigned_to,        feedback=reason,    )    self.articles.update_trust_metadata(        article_id,        hitl_status="PENDING",    )    return queue_row
HumanLayer would “productize” this step: notify humans in Slack/Email, collect approve/reject, handle timeouts/escalations, and provide a consistent audit trail for high-stakes actions.
Concrete “how” (minimal, high ROI integration)
Gate publication: require human approval before _publish_content() (or before enqueueing the publication command). This is the most important safety/control point for a news product.
Gate expensive/irreversible actions:
Triggering video renders (costly compute)
Sending emails (SendGrid)
Running paywalled scraping / “questionable” domains (compliance)
Any admin actions affecting user subscriptions/payments
Human-as-tool for verification: when trust score is low or claims are ambiguous, route a “please decide” question to a reviewer instead of letting the agent guess.
Why it’s worth it at this stage (for your project specifically)
You already planned HITL (it’s in the workflow state machine), so HumanLayer saves you from building and debugging a bespoke review system.
Legal/compliance posture: approvals + audit logs reduce risk when summaries could be “too substitutive” or when robots/TDM rules are unclear.
Operational scaling: routing approvals to a team inbox (and escalating) is much easier than DM’ing one person.
When it might be overkill
If you won’t have a human reviewing anything for the next few weeks and you’re still proving ingestion + summarization quality, you can defer it. But the moment you start “publishing” anything automatically, HumanLayer (or something equivalent) becomes a strong safety multiplier.
If you want, I can suggest an exact initial approval policy matrix (“which functions require approval”) tailored to your current services/tasks (Celery + Kafka workflow).