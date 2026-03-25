<!-- DEPRECATED DOCUMENT -->
⚠️ **This document is deprecated and kept for historical reference only.**

**Current documentation:** See [../GETTING_STARTED.md](../GETTING_STARTED.md) | [../README.md](../README.md)

---

# Documentation Archive - Deprecation Notice

**⚠️ IMPORTANT: This directory contains historical and deprecated documentation.**

---

## Purpose of This Archive

This archive contains documentation that is **no longer current** but preserved for historical reference. These documents show the evolution of the CliLens.AI platform and may contain useful context about past decisions.

---

## Why Documents Are Archived

Documents are moved to this archive when:
1. **Replaced by newer documentation** - Content has been consolidated into current docs
2. **Outdated information** - Technical details no longer match current implementation
3. **Completed milestones** - Project phases that are now finished
4. **Superseded by architectural changes** - Approaches that were replaced

---

## How to Use This Archive

### For New Developers
**Do NOT use these documents for current development.**
- ✅ Use: [../README.md](../README.md) for navigation
- ✅ Use: Documents in `docs/` (not in archive/)
- ❌ Avoid: Anything in `docs/archive/`

### For Historical Context
These documents are valuable for:
- Understanding why certain decisions were made
- Seeing how the architecture evolved
- Learning from past migration efforts
- Researching completed features

### For AI Assistants
When using AI assistants (Claude, Cursor, etc.):
- **Inform AI:** "Ignore docs/archive/ - use only current documentation"
- **If needed:** "Check docs/archive/ for historical context on [topic]"

---

## Archived Documents Inventory

### Completion Summaries (2025)
- `FINAL_MVP_SUMMARY.md` - MVP completion report
- `DEVELOPMENT_COMPLETION_SUMMARY.md` - Development phase wrap-up
- `BACKEND_COMPLETION_SUMMARY.md` - Backend implementation summary
- `FRONTEND_COMPLETION_SUMMARY.md` - Frontend implementation summary
- `MVP_COMPLETION_STATUS.md` - MVP status report
- `PHASE1_COMPLETION_SUMMARY.md` - Phase 1 completion
- `PLATFORM_ENHANCEMENT_SUMMARY.md` - Enhancement summary
- `VERIFICATION_SUCCESS_SUMMARY.md` - Verification feature summary

### Port Migration (November 2025)
- `PORT_MAPPINGS.md` - Old port reference
- `PORT_MIGRATION_GUIDE.md` - Migration instructions (completed)
- `PORT_UPDATE_SUMMARY.md` - Port update summary
- `START_HERE_PORTS.md` - Port-related quickstart

### Quickstart Guides (Multiple Versions)
**Reason for deprecation:** Consolidated into `docs/GETTING_STARTED.md`
- `QUICKSTART.md` - Original quickstart
- `QUICK_START_V2.md` - Second iteration
- `QUICK_START_BACKEND.md` - Backend-specific
- `QUICK_START_WEB.md` - Web-specific
- `START_HERE.md` - General start guide
- `SIMPLE_TEST.md` - Simple testing guide
- `QUICK_TEST.md` - Quick test guide

### API Testing & Reports
- `API_TEST_SUMMARY.md` - API testing results
- `BACKEND_MVP_GUIDE.md` - Backend MVP documentation
- `FINAL_MVP_TEST_REPORT.md` - Final testing report

### Code Reviews & Planning
- `COMPREHENSIVE_CODE_REVIEW_2025.md` - Code review (October 2025)
- `PRIORITY_ACTION_PLAN.md` - Action plan (completed)
- `MIGRATION_SUMMARY.md` - Migration activities

### UI Examples
- `ui_example/image.png` - Historical UI screenshot

---

## Current Documentation Location

**Instead of using archived docs, refer to:**

| Topic | Current Location |
|-------|-----------------|
| **Getting Started** | `docs/GETTING_STARTED.md` ⭐ Coming Soon |
| **Architecture** | `docs/architecture/ARCHITECTURE.md` |
| **Development** | `docs/architecture/DEVELOPMENT.md` |
| **API Reference** | `docs/api/backend.md` |
| **Deployment** | `docs/architecture/DEPLOYMENT.md` |
| **Domain Specs** | `docs/domain/*.md` |
| **Runbooks** | `docs/runbooks/*.md` ⭐ Coming Soon |
| **Services** | `docs/services/*.md` ⭐ Coming Soon |

See [../README.md](../README.md) for complete navigation.

---

## Archival Policy

### When to Archive a Document
1. **Before archiving:**
   - Ensure content is preserved in current docs if still relevant
   - Add redirect/notice at top of document pointing to new location
   - Update all links pointing to this document

2. **Archive process:**
   - Move document to `docs/archive/`
   - Update this DEPRECATED_NOTICE.md
   - Add git commit explaining why archived

3. **Never archive:**
   - Current implementation documentation
   - Active project plans
   - API contracts still in use

### Document Retention
- Keep archived docs for **minimum 1 year**
- After 1 year, evaluate if still providing value
- Documents older than 2 years may be removed if no longer referenced

---

## Questions About Archived Content?

**Found information in archive that seems useful?**
1. Check if it exists in current documentation
2. If not, consider creating PR to restore relevant content
3. Ask team: #climatenews-dev Slack channel

**Need to understand past decision?**
- Review relevant archived document
- Check git history for context
- Ask team members who were involved

---

**Archive Established:** 2025-11-20
**Last Reviewed:** 2025-11-20
**Next Review:** 2026-11-20

**Tip:** Use `git log docs/archive/` to see when documents were archived and why.
