  The mental model: think in 3 lanes
     
  Lane: A. Overnight batch
  Latency budget: Hours OK
  Where it should run: GX10 always
  Examples on your platform: RSS enrichment,  
  KG
    canonicalization, training-data
    distillation, prompt-regression eval,     
    full-corpus backfills, weekly trend       
  reports
  ────────────────────────────────────────    
  Lane: B. Background-recent
  Latency budget: Seconds–minutes
  Where it should run: GX10 primary, cloud    
    fallback
  Examples on your platform: URL analysis     
    triggered by user, entity extraction      
    post-ingest, hallucination check, verdict 
    adjudication
  ────────────────────────────────────────    
  Lane: C. User-facing
  Latency budget: Sub-5s, streaming
  Where it should run: Cloud primary today →  
    GX10 specialist later
  Examples on your platform: Article chat Q&A,

    deep-search synthesis, comparison views   

  Your DGX Spark has 128 GB unified memory —  
  that matters because the box can hold       
  multiple models warm simultaneously without 
  swapping. Realistically you can run, all    
  warm at once:

  - nemotron-3-super:120b (~60 GB) for heavy  
  overnight reasoning
  - qwen2.5:14b-instruct (~9 GB Q4) as the    
  workhorse for Lane B
  - qwen2.5:7b-instruct (~5 GB Q4) as the     
  speed model for Lane C
  - BAAI/bge-m3 (~2 GB) for embeddings        
  - 3–5 LoRA specialists (~100 MB each) — see 
  below

  That ~80 GB working set leaves headroom for 
  KV cache and concurrency. So the
  small-model-for-user-features idea doesn't  
  compete with the batch workhorse for memory;
   they coexist.

  Lane A — the clean wins (do these first,    
  zero quality risk)

  These are batch, latency-tolerant,
  structured output. GX10 wins on every axis  
  (cost, privacy, throughput-per-dollar) and  
  quality risk is bounded by the fallback     
  chain:

  1. Article enrichment
  (article_enrichment_service.py) — 600–1,200 
  calls/day, SFT capture already wired, runs  
  in batch. Already plumbed; just needs the   
  Tailscale sidecar.
  2. Entity extraction → KG
  (entity_extraction_service.py) — structured 
  JSON, runs once per article post-ingest.    
  Qwen's guided-JSON mode actually improves   
  schema compliance vs cloud DeepSeek (5%     
  parse-failure rate today).
  3. Embeddings WRITE path with BGE-M3 —      
  multilingual model, write the new article   
  corpus locally; keep query path on ada-002  
  until parity is proven on a held-out set.   
  4. Verdict adjudication + hallucination     
  check — biggest structured-JSON workloads in
   the fact-check pipeline.
  5. Causal analysis, contradiction detection,
   intelligence briefs, scope refinement,     
  Cynefin classifier fallback — low volume, no
   SLO. Move because there's no reason not to.
  6. The eval/regression harness — this is the
   underrated one. Today every prompt change  
  costs API tokens to validate. On GX10 it's  
  free → you can iterate prompts 10× faster   
  without thinking about cost. This alone     
  changes how you do prompt engineering.      

  Direct API saving is modest (~$60–135/mo).  
  The real wins are privacy on user-uploaded  
  research PDFs (the 30k-char research-report 
  path leaks user IP to a 3rd party today) and
   the prompt-iteration flywheel.

  What stays cloud (always)

  - Perplexity Sonar for news discovery — it's
   search, not inference. No local model can  
  replicate a real-time web index.
  - Frontier deep-search synthesis (Sonnet) — 
  per-sentence citation grounding is the      
  strictest output contract on your platform. 
  Don't.
  - Primary + secondary of the multi-LLM claim
   verifier — the entire point is
  provider/family diversity. Collapsing it to 
  local would destroy the calibration signal. 

  The interesting middle: fine-tuned
  specialists

  This is the highest-leverage move you're not
   asking about yet.

  You already capture every cloud DeepSeek    
  call's input+output to
  CLILENS_TRAINING_DATASET_PATH
  (article_enrichment_service.py:610-655).    
  After ~30 days of production traffic, you'll
   have 20–40k labeled training pairs per     
  workload. Fine-tune Qwen-2.5-7B with LoRA on
   that, separately for each narrow task:     

  - A climate-claim-extractor-7B LoRA (~100 MB
   adapter)
  - A verdict-adjudicator-7B LoRA
  - A climate-context-summarizer-7B LoRA      

  Empirical pattern: a 7B fine-tuned on a     
  narrow domain task typically beats a general
   70B+ model on that one task by 5–15% F1, at
   1/100th the cost and 5× the speed. Ollama  
  (and vLLM with --enable-lora) can hot-swap  
  adapters per request, so one 7B base serves 
  N specialists.

  This is where local stops being "the cheaper
   option" and becomes "the better option for 
  narrow tasks." The cloud frontier model     
  stays as the generalist for novel queries   
  the specialist hasn't seen.

  Lane C — yes, user-facing is feasible, but  
  pattern matters

  Honest latency math on Grace Blackwell over 
  Tailscale (LAN-equivalent ~10ms RTT):       

  ┌──────────┬──────────┬───────┬───────┐     
  │          │ Throughp │ 200-t │ 800-t │     
  │  Model   │    ut    │ ok an │ ok an │     
  │          │          │ swer  │ swer  │     
  ├──────────┼──────────┼───────┼───────┤     
  │ Qwen 2.5 │ ~150     │ 1.5s  │ 5.5s  │     
  │  7B Q4   │ tok/s    │       │       │     
  ├──────────┼──────────┼───────┼───────┤     
  │ Qwen 2.5 │ ~80      │ 2.7s  │ 10s   │     
  │  14B Q4  │ tok/s    │       │       │     
  ├──────────┼──────────┼───────┼───────┤     
  │ Nemotron │ ~25      │       │       │     
  │ -3 120B  │ tok/s    │ 8s    │ 32s   │     
  │ Q4       │          │       │       │     
  └──────────┴──────────┴───────┴───────┘     

  With token streaming, the user perceives    
  time-to-first-token (~300–800ms) and reading
   speed (~5 words/s ≈ enough). 7B feels      
  snappy user-side; 14B feels OK with
  streaming; 120B is only for the "deep       
  research" UX where the user expects a wait. 

  The pattern that works for user-facing:     
  route by complexity, not by feature. Your   
  cynefin_router.py already classifies queries
   clear / complicated / complex / chaotic.   
  Extend it as a model-size router:

  - clear (factual lookup, "what year did     
  Paris Agreement sign") → local 7B
  specialist, p95 < 2s
  - complicated (multi-source synthesis,      
  article chat Q&A) → local 14B, p95 < 8s     
  - complex (forecast, scenarios, novel       
  reasoning) → cloud Sonnet, p95 < 15s        
  - chaotic (high-stakes, emergency framing) →
   cloud Sonnet (don't risk local on these)   

  This way ~70% of user-facing queries hit    
  local (and feel faster than today), and the 
  30% that genuinely need frontier reasoning  
  still get it.

  What I'd actually sequence

  Week 1 — finish what's in flight: Tailscale 
  sidecar on Cloud Run, flip enrichment +     
  entity extraction to local. Watch the       
  local_llm_fallbacks table for a week. Cost  
  saving small, quality risk near zero,       
  validates the whole pipeline.

  Week 2–3 — flip the rest of Lane A (causal  
  analysis, contradiction detection,
  summaries, hallucination check, verdict     
  adjudication). Plumbing work: route
  verdict_adjudication through route_chat() — 
  today it bypasses the router
  (services.py:888-898).

  Week 3–4 — embeddings WRITE-path with BGE-M3
   + build the parity test. One-time backfill 
  (~50 min compute) re-embeds the corpus.     

  Week 4–6 — stand up the nightly distillation
   pipeline: take the day's SFT-captured cloud
   outputs, fine-tune a LoRA, run the eval    
  harness, promote if the specialist beats    
  baseline. This is the flywheel that
  compounds.

  Week 6–8 — ship the first
  specialist-for-cloud play: take a fine-tuned
   7B claim extractor and serve it on Cloud   
  Run (or HF Inference) as the new primary,   
  with cloud Sonnet as the cross-check        
  secondary. Local model goes to cloud for    
  low-latency user serving while overnight    
  training stays on GX10. This is the answer  
  to "could fine-tuned models go to cloud for 
  user features" — yes, and that's where the  
  largest quality lift sits.

  Week 8+ — extend cynefin_router as the      
  model-size router for chat Q&A. Stream      
  tokens. Measure the p95 latency by
  complexity bucket.

  The honest summary

  - Cost saving is real but modest —
  $60–135/mo direct. Don't sell the project on
   this number.
  - The real wins are: privacy on user data,  
  unlimited prompt iteration, and a
  distillation flywheel that produces
  task-specialists which beat the cloud       
  generalist on narrow domains.
  - Yes, user-facing is feasible — but only   
  with streaming + a complexity-based router, 
  not as a blanket replacement.
  - The most underrated lever is fine-tuning —
   you already have the labeled data being    
  captured. The 6-week investment to stand up 
  nightly LoRA training is what turns "GX10 is
   cheaper" into "GX10 is better for our      
  domain."