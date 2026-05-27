# Documentation Consolidation Plan — 2026-05-27

Companion to `Platform-Release-Audit-2026-05-27.md §7`. Concrete plan
for the doc-tree pruning required before v1.0.

## State

- **158 total .md files under `docs/`**
- **94 active (excluding `docs/archive/`)**
- **22 files in `docs/improvementplans/`** — half are audit-loop
  snapshots that should be archived
- **9 files in `docs/reports/`** — mix of evergreen specs (e.g.
  `asusgx10inferencestrategy.md`) and dated session reports
- **3 files in `docs/release/`** — this directory becomes the source of
  truth for v1.0 launch posture

## Problem

A new contributor (or future-self in 3 months) cannot tell from the
file names which docs are evergreen reference vs. session-dated audit
snapshots. Several pairs / triples cover the same ground at different
audit loops (e.g. `End2End-Audit-Benchmark-2026-05-27{,b,c,d}.md`).

## Target structure (post-consolidation)

```
docs/
├── README.md                          # Tier 1 — entry point
├── GETTING_STARTED.md                 # Tier 1 — new-contributor onboarding
├── CURRENT_STATE.md                   # Tier 1 — what's live right now
├── ROADMAP.md                         # Tier 1 — what's next
├── release/                           # Tier 1 — launch posture
│   ├── Platform-Release-Audit-2026-05-27.md
│   ├── Security-DevOps-Audit-2026-05-27.md
│   ├── GX10-Offload-Plan-2026-05-27.md
│   └── Documentation-Consolidation-Plan-2026-05-27.md
├── architecture/                      # Tier 2 — evergreen design docs
├── domain/                            # Tier 2 — domain modeling
├── operations/                        # Tier 2 — runbooks
├── api/                               # Tier 2 — API reference
├── golden-examples/                   # Tier 2 — quality references
├── reports/                           # Tier 2 — evergreen strategic docs
│   └── asusgx10inferencestrategy.md   # KEEP — current GX10 strategy
└── archive/                           # Tier 3 — dated session snapshots
    ├── 2026-04/
    ├── 2026-05/
    │   ├── End2End-Audit-Benchmark-2026-05-26.md
    │   ├── End2End-Audit-Benchmark-2026-05-27.md
    │   ├── End2End-Audit-Benchmark-2026-05-27b.md
    │   ├── End2End-Audit-Benchmark-2026-05-27c.md
    │   ├── End2End-Audit-Benchmark-2026-05-27d.md
    │   ├── Honest-Gap-Audit-2026-05-25.md
    │   ├── Honest-Gap-Audit-v2-2026-05-25.md
    │   ├── Phase-10-Session-Summary-2026-05-25.md
    │   └── ... 
    └── 2026-03/
```

## Concrete moves before v1.0 (sequenced)

### Phase 1: archive dated audit loops (1h, no code risk)

Move into `docs/archive/2026-05/`:
- All `End2End-Audit-Benchmark-2026-05-{26,27,27b,27c,27d}.md` — keep
  only as historical record; `Platform-Release-Audit-2026-05-27.md` is
  the synthesis.
- `Honest-Gap-Audit-2026-05-25.md` and its v2 — superseded by release
  audit's gap-ledger.
- `Phase-10-Session-Summary-2026-05-25.md`, `Production-Review-Response-2026-05-25.md`,
  `Resume-Here-2026-05-25.md` — session resumption notes, no longer
  load-bearing.
- `Alignment-Gap-Inventory-2026-05-25.md` — superseded.

Keep in `docs/improvementplans/`:
- `Climatefacts-Strategic-Analysis-2026-05-18.md` — strategic North Star.
- `Climate Platform Analysis and Improvement Plan.md` — recent business
  context.
- `GX10-Workload-Audit-2026-05-25.md` — referenced by `GX10-Offload-Plan`.
- `KG-Robustness-Audit-2026-05-27.md` — KG-specific evergreen audit.
- `Semanticgraphlayerimprovements.md` — semantic layer reference.
- `TruthEngine-PersonaFit-Design-2026-05-25.md` — persona design ref.
- `Golden-Artifact-Examples-2026-05-27b.md` — keep one (b is newest);
  archive the earlier version.
- `GX10-Deployment-Runbook-2026-05-25.md` — runbook, KEEP (or move
  to `docs/operations/`).
- Competitive UX audit + strategic roadmap PDFs — keep as PDFs are
  imported context.

### Phase 2: collapse evaluation reports (30min)

`docs/evaluations/` has 6 dated reports; collapse into one rolling
`EVALUATION_STATE.md` that captures the latest numbers and link the
historical reports under `docs/archive/`.

### Phase 3: prune root-level dated reports (30min)

These root-of-docs files are dated session reports masquerading as
evergreen docs:
- `INTEGRATION_FEASIBILITY_AUDIT.md` — date in body; move to archive
- `MVP_COMPLETION_PLAN.md` — superseded by current state
- `MVP_EUROPE_ROADMAP.md` — superseded by global ROADMAP.md
- `MVP_SUCCESS_REPORT.md` — historical; archive
- `PHASE_1_COMPLETION_REPORT.md` — historical; archive
- `PLATFORM_HEALTH_CHECK.md` — superseded by release audit
- `PROJECT_EVALUATION_REPORT.md` — superseded
- `search_fix_root_cause_analysis.md` — debug postmortem, archive
- `SECURITY_REVIEW.md` — superseded by Security-DevOps-Audit-2026-05-27.md
- `START_HERE_AGENT_GUIDE.md`, `AGENT_USAGE_GUIDE.md` — merge into one
- `TESTING_GUIDE.md`, `TESTING_PHASE_1_FEATURES.md` — merge into one
- `TOOL_AVAILABILITY.md` — defer; CLAUDE.md is authoritative

### Phase 4: writing-style discipline (ongoing)

For every new doc:
1. **Dated session reports** go in `docs/archive/<yyyy-mm>/` from day 1
2. **Evergreen reference** lives in `docs/architecture/`, `docs/domain/`,
   `docs/operations/`, etc.
3. **Release-cycle docs** live in `docs/release/` and are explicitly
   superseded by next cycle's docs (don't accumulate).

## Hard rule going forward

> Audit loops generate file names with dates. After the loop's work is
> shipped, the dated audit moves to `docs/archive/<yyyy-mm>/` within
> the same commit that closes the loop. The release-cycle doc in
> `docs/release/` carries forward the load-bearing findings.

## Numbers (target)

| Before | After |
|---|---|
| 158 total .md | ~70 active + ~90 archived |
| 22 in improvementplans/ | 7-8 (evergreen) |
| 12+ root-level dated reports | 0 (root has only 4-5 Tier-1 files) |
| `docs/release/` empty | 4-5 load-bearing release docs |

## Effort

3 hours total. No code touched. Reversible via git.

## Owner

Single-person task — file moves + a CLAUDE.md note to enforce the
"audit-snapshots → archive in same commit" rule going forward.
