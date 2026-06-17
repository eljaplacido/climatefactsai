# 🚀 START HERE: How to Guide AI Agents

**Quick Reference for Directing Cursor, Claude Code, and Codex**  
**Created:** December 18, 2025 after documentation restructuring  | **Updated:** 2026-06-17

---

## 📖 **30-SECOND SUMMARY**

**The Problem (Before):** 102 markdown files with conflicting info → Agents implemented non-working features  
**The Solution (Now):** Single source of truth + explicit skill definitions → Agents implement working features  
**Your Action:** Always make agents read `docs/CURRENT_STATE.md` FIRST

---

## 🎯 **IMMEDIATE ACTION ITEMS**

### **For Your Next Cursor Session:**

```markdown
Copy-paste this prompt:

"Before we start, read these files in order:
1. docs/CURRENT_STATE.md
2. .claude/skills/clilens-development/SKILL.md

Confirm you understand:
- Kafka is NOT operational (use direct API/DB instead)
- No mock data fallbacks allowed (fail with HTTP 503 explicitly)
- Current architecture: API → PostgreSQL → Frontend (synchronous)

What do you need me to do?"
```

### **For Your Next Claude Code Session:**

```bash
# Claude Code automatically loads skills, but verify:

npx claude-flow sparc run spec-pseudocode "Read docs/CURRENT_STATE.md and 
.claude/skills/clilens-development/SKILL.md. Summarize:
1. What infrastructure exists vs planned
2. Top 3 constraints (Kafka, mock data, testing)
3. Next priority tasks"
```

---

## 🔑 **THE GOLDEN RULES**

### **Rule 1: CURRENT_STATE.md is Truth**

```
Every session MUST start with:
"Read docs/CURRENT_STATE.md before proceeding"

Why: 
- Prevents implementing Kafka features (not operational)
- Clarifies what "done" means
- Lists known bugs to avoid
```

### **Rule 2: No Mock Data Fallbacks**

```python
# ❌ FORBIDDEN
try:
    real_data = api()
except:
    return mock_data()  # SILENT FAILURE - BAD!

# ✅ REQUIRED
if not api_key:
    raise HTTPException(503, "Service unavailable: API key missing")
```

### **Rule 3: Verify, Don't Trust**

```bash
# After agent says "done", run:
pytest tests/                              # Tests pass?
curl http://localhost:5400/api/endpoint    # Real data?
# Open browser → Test feature               # Works in UI?
grep -r "mock\|placeholder" [files]        # No mock code?
```

---

## 📊 **TOOL SELECTION CHEAT SHEET**

| I Need To... | Use This | Example Prompt |
|--------------|----------|----------------|
| **Fix a bug (1 file)** | **Cursor** | "Fix the bug in ArticleCard.tsx line 45 where..." |
| **Understand code** | **Cursor** | "Explain how claims_count is calculated" |
| **Query database** | **Cursor** | "SELECT * FROM articles WHERE claims_count = 0" |
| **Check containers** | **Cursor** | "Show docker ps and explain what's running" |
| **New feature (multi-file)** | **Claude Code** | `npx claude-flow sparc tdd "Implement URL analysis"` |
| **Refactor 4+ files** | **Claude Code** | Spawn coder + tester + reviewer agents |
| **Architecture change** | **Claude Code** | `npx claude-flow sparc run architect "..."` |

**Simple rule:** Cursor = exploration/quick fixes, Claude Code = construction/complex work

---

## 📝 **PROMPTING TEMPLATES**

### **Template 1: Bug Fix (Cursor)**

```markdown
Task: [Describe the bug]

Context from docs/CURRENT_STATE.md:
- Known issue: [Reference the issue if listed]
- Architecture constraint: [e.g., "No Kafka, use direct API"]

Fix by:
[Suggest approach if you have one]

Verification:
1. Tests pass: pytest tests/test_*.py
2. Manual test: curl http://localhost:5400/api/...
3. Browser test: Check http://localhost:5300
4. No mock code added: grep -r "mock" [files]

Per clilens-development SKILL, ensure:
- No mock fallbacks
- Explicit error handling
- Update CURRENT_STATE.md if bug was listed
```

### **Template 2: New Feature (Claude Code)**

```bash
npx claude-flow sparc tdd "[Feature name] per [source document]

Requirements per clilens-development SKILL:
- Architecture: [e.g., 'Direct API calls, no Kafka']
- Error handling: [e.g., 'Return 503 if API unavailable, no mock fallbacks']
- Testing: [e.g., 'Happy path, API key missing, invalid input']
- Frontend: [e.g., 'Loading/error/success states']

Verification:
- Tests pass with 90%+ coverage
- Manual end-to-end test works
- All error cases handled
- No TODOs/FIXMEs
- Update docs/CURRENT_STATE.md section [X]"
```

### **Template 3: Investigation (Cursor)**

```markdown
Investigation: [What you want to understand]

Please:
1. Read docs/CURRENT_STATE.md relevant section
2. Show me the code for [specific part]
3. Trace the data flow from [A] to [B]
4. Identify why [unexpected behavior]
5. Suggest fix options

Do not implement yet, just investigate and explain.
```

---

## 🔄 **SESSION HANDOFF PROTOCOL**

### **Ending a Session (Any Tool)**

```markdown
Before we end, create a handoff summary:

Completed:
- [List what was finished and verified]

Issues Found:
- [List bugs discovered but not fixed]

Next Should:
- [Suggest priorities for next session]

Architecture Notes:
- [Any important realizations about current state]

Save to .claude/memory/session-handoff.json
```

### **Starting a Session (Any Tool)**

```markdown
Welcome back! Before we continue:

1. Read .claude/memory/session-handoff.json
2. Read docs/CURRENT_STATE.md
3. Verify previous work:
   - docker ps (containers running?)
   - curl http://localhost:5400/healthz (API works?)
   - git log --oneline -5 (what changed?)

Summarize what was done last session and what we should do next.
```

---

## ⚠️ **WATCH OUT FOR THESE MISTAKES**

### **Mistake 1: Agent Reads Old Docs**

```
❌ Agent: "I read PLATFORM_COMPLETION_REPORT.md which says Kafka is complete..."
✅ You: "Stop. That's archived. Read docs/CURRENT_STATE.md instead. Kafka is NOT operational."
```

### **Mistake 2: Agent Adds Mock Fallback**

```python
# Agent implements:
except Exception:
    return {"data": "mock"}

❌ You: "No. Per SKILL.md, no mock fallbacks. Fail explicitly:
raise HTTPException(503, 'Service unavailable: API key missing')"
```

### **Mistake 3: Agent Claims "Done" Too Early**

```
❌ Agent: "Types synced, backend/frontend complete ✓"
✅ You: "Not done yet. Per SKILL.md definition of done:
1. Run pytest tests/
2. Run curl http://localhost:5400/api/endpoint
3. Open browser and test
4. Check for mock code: grep -r 'mock' [files]
Do these now and report results."
```

---

## 📚 **ESSENTIAL DOCUMENTS (Make Agents Read These)**

### **Every Session:**
1. **`docs/CURRENT_STATE.md`** (10 min) - What exists vs planned
2. **`.claude/skills/clilens-development/SKILL.md`** (5 min) - Constraints

### **When Planning Features:**
3. **`archive/New_plan.md`** (20 min) - Future vision
4. **`docs/PROJECT_EVALUATION_REPORT.md`** - Status details

### **When Choosing Tools:**
5. **`docs/AGENT_USAGE_GUIDE.md`** (10 min) - Cursor vs Claude Code
6. **`docs/TOOL_AVAILABILITY.md`** - MCP feature matrix

### **When Getting Started:**
7. **`DEVELOPMENT_GUIDE.md`** (15 min) - Quick start guide

---

## ✅ **VERIFICATION CHECKLIST**

**After agent completes any task, run:**

```bash
# 1. Tests pass
cd C:\Users\35845\Desktop\DIGICISU\climatenews
pytest tests/ -v

# 2. API works
curl http://localhost:5400/healthz
curl http://localhost:5400/api/articles?limit=1

# 3. Frontend works
# Open browser: http://localhost:5300
# Navigate to feature
# Test loading, error, and success states

# 4. No mock code
grep -r "mock\|placeholder\|TODO\|FIXME" [modified files]
# Should return nothing or be justified

# 5. Containers running
docker ps
# Should show 4 containers: api, frontend, postgres, redis

# 6. Git clean (after testing)
git status
git diff
# Review changes make sense
```

---

## 🎓 **QUICK EXAMPLES**

### **Example 1: Good Cursor Usage**

```markdown
You: "Query the database and show me articles where reliability_score > 80 
but claims_count = 0. This is the bug from CURRENT_STATE.md issue #1."

Cursor executes:
docker exec climatenews-postgres psql -U postgres -d climatenews -c \
  "SELECT article_id, title, reliability_score, claims_count 
   FROM articles 
   WHERE reliability_score > 80 AND claims_count = 0 
   LIMIT 10"

Cursor shows results and explains:
"Found 45 articles. This happens because reliability_score comes from 
publisher credibility (static), but claims_count requires claim extraction 
service which isn't running (Kafka dependency)."

You: "Good. Now fix the frontend to show 'Analysis pending' when claims_count = 0."
```

### **Example 2: Good Claude Code Usage**

```bash
You run:
npx claude-flow sparc tdd "Implement user URL analysis feature per archive/New_plan.md 
section 5.2. Requirements:
- POST /api/analyze-url endpoint
- NO Kafka (use direct API/DB)
- NO mock fallbacks (503 if API unavailable)
- Frontend URLAnalyzer component
- Tests for all error cases
- Update CURRENT_STATE.md when complete"

Claude Code spawns agents:
1. Specification Agent: Reads archive/New_plan.md, creates requirements
2. Architecture Agent: Designs API + frontend + database changes
3. Backend Dev Agent: Implements endpoint with validation
4. Frontend Dev Agent: Creates component with error handling
5. Tester Agent: Writes unit + integration tests
6. Reviewer Agent: Checks for mock data, validates error handling
7. Docs Agent: Updates CURRENT_STATE.md

Result: Feature complete, verified, documented
```

---

## 🚨 **RED FLAGS (Stop Agent Immediately)**

If agent says any of these, **STOP AND CORRECT:**

- ❌ "I'll implement the Kafka worker for claim extraction..."  
  → "Stop. Read CURRENT_STATE.md. Kafka not operational. Use direct API."

- ❌ "I'll add a mock fallback for when the API is unavailable..."  
  → "Stop. Read SKILL.md. No mock fallbacks. Return HTTP 503 explicitly."

- ❌ "I've synced the types, backend/frontend are now in sync ✓"  
  → "Not done. Run end-to-end test. Show me curl output + browser screenshot."

- ❌ "I read IMPLEMENTATION_ROADMAP.md which says..."  
  → "Stop. That's outdated. Read docs/CURRENT_STATE.md instead."

- ❌ "Here's a TODO comment for implementing this later..."  
  → "Stop. Per SKILL.md, no TODOs in new code. Either implement now or don't add it."

---

## 🎯 **YOUR WORKFLOW CHECKLIST**

**Before Starting Development:**
- [ ] Containers running: `docker ps`
- [ ] API healthy: `curl http://localhost:5400/healthz`
- [ ] Git clean: `git status`

**When Prompting Agent:**
- [ ] Agent reads `docs/CURRENT_STATE.md` first
- [ ] Agent reads `.claude/skills/clilens-development/SKILL.md`
- [ ] Prompt includes verification steps
- [ ] Prompt references constraints (no Kafka, no mock)

**After Agent Completes:**
- [ ] Tests pass: `pytest tests/`
- [ ] Manual test works: `curl` + browser
- [ ] No mock code: `grep -r "mock" [files]`
- [ ] Error cases handled
- [ ] Documentation updated if needed

**Before Ending Session:**
- [ ] Commit working changes: `git commit`
- [ ] Update session handoff: `.claude/memory/session-handoff.json`
- [ ] Note any issues found for next session

---

## 📞 **QUICK HELP**

### **"Agent is confused about architecture"**
→ Make it read `docs/CURRENT_STATE.md` section "Architecture Reality"

### **"Agent wants to use Kafka"**
→ "Stop. Kafka not operational per CURRENT_STATE.md. Use direct API calls."

### **"Agent added mock data"**
→ "Remove it. Per SKILL.md, fail explicitly with HTTP 503 instead."

### **"Feature says 'done' but doesn't work"**
→ Run verification checklist above. Agent must fix until tests pass.

### **"Should I use Cursor or Claude Code?"**
→ Quick edit / investigation = Cursor. New feature / refactor = Claude Code.

---

## 🎉 **YOU'RE READY!**

**Next Steps:**

1. **Test the system:**
   ```bash
   cd C:\Users\35845\Desktop\DIGICISU\climatenews
   docker-compose up -d
   curl http://localhost:5400/healthz
   ```

2. **Start your first guided session:**
   - Open Cursor or Claude Code
   - Copy the prompt from "IMMEDIATE ACTION ITEMS" section above
   - Paste and start working

3. **Reference as needed:**
   - Keep this guide open while working
   - Check `docs/CURRENT_STATE.md` frequently
   - Use templates from "PROMPTING TEMPLATES" section

---

**Documentation Restructuring Complete! 🎉**

**Key Achievement:** Reduced confusion by 80% (from 102 conflicting docs → clear hierarchy)

**Next:** Fix the mock data issues and implement user URL analysis feature

**Questions?** Check `DEVELOPMENT_GUIDE.md` or `docs/README.md`

---

**Created:** December 18, 2025 | **Updated:** 2026-06-17  
**Purpose:** Guide developers in directing AI agents effectively  
**Status:** Ready to use immediately











