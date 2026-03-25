#!/bin/bash
# ==============================================================================
# CliLens.AI - Safe Cleanup Script
# ==============================================================================
# This script removes obsolete files and duplicate code identified in the
# comprehensive code review.
#
# IMPORTANT: Review changes before executing!
# Run with --dry-run first to see what would be deleted
#
# Usage:
#   ./cleanup_script.sh --dry-run    # Preview changes
#   ./cleanup_script.sh              # Execute cleanup
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo -e "${YELLOW}=== DRY RUN MODE - No files will be deleted ===${NC}\n"
fi

# Statistics
DELETED_FILES=0
DELETED_DIRS=0
FREED_SPACE=0

# Function to safely delete a file or directory
safe_delete() {
    local path="$1"
    local type="$2"  # "file" or "dir"
    
    if [ ! -e "$path" ]; then
        echo -e "${YELLOW}⚠️  Not found (already deleted?): $path${NC}"
        return
    fi
    
    # Calculate size
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        SIZE=$(du -sh "$path" | cut -f1)
    else
        # Linux
        SIZE=$(du -sh "$path" 2>/dev/null | cut -f1 || echo "unknown")
    fi
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}[DRY RUN] Would delete $type: $path ($SIZE)${NC}"
    else
        echo -e "${RED}🗑️  Deleting $type: $path ($SIZE)${NC}"
        if [ "$type" = "dir" ]; then
            rm -rf "$path"
            ((DELETED_DIRS++))
        else
            rm -f "$path"
            ((DELETED_FILES++))
        fi
    fi
}

# Function to create archive directory
create_archive() {
    local archive_dir="docs/archive"
    
    if [ ! -d "$archive_dir" ]; then
        if [ "$DRY_RUN" = true ]; then
            echo -e "${BLUE}[DRY RUN] Would create: $archive_dir${NC}"
        else
            echo -e "${GREEN}📁 Creating archive directory: $archive_dir${NC}"
            mkdir -p "$archive_dir"
        fi
    fi
}

# Function to archive a file (move to docs/archive)
archive_file() {
    local file="$1"
    local archive_dir="docs/archive"
    
    if [ ! -f "$file" ]; then
        echo -e "${YELLOW}⚠️  Not found: $file${NC}"
        return
    fi
    
    if [ "$DRY_RUN" = true ]; then
        echo -e "${BLUE}[DRY RUN] Would archive: $file → $archive_dir/${NC}"
    else
        echo -e "${GREEN}📦 Archiving: $file${NC}"
        mv "$file" "$archive_dir/"
        ((DELETED_FILES++))
    fi
}

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         CliLens.AI - Codebase Cleanup Script             ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}\n"

# ==============================================================================
# PHASE 1: DELETE DUPLICATE DIRECTORIES
# ==============================================================================

echo -e "\n${YELLOW}=== PHASE 1: Removing Duplicate Directories ===${NC}\n"

# 1. Delete old /agents/ directory (duplicates /src/backend/services/)
echo "🔍 Checking /agents/ directory..."
safe_delete "agents/" "dir"

# 2. Delete backup directory (use Git instead)
echo "🔍 Checking backup directory..."
safe_delete "agents_backup_20251022/" "dir"

# 3. Delete empty placeholder directories
echo "🔍 Checking placeholder directories..."
safe_delete "srcbackendservices/" "dir"
safe_delete "srcbackendshared/" "dir"
safe_delete "srcfrontendsrc/" "dir"

# 4. Delete abandoned Next.js frontend (if Vite is active)
echo "🔍 Checking for duplicate frontend..."
if [ -d "frontend/src" ] && [ -d "src/frontend" ]; then
    echo -e "${YELLOW}⚠️  WARNING: Both /frontend/ and /src/frontend/ exist${NC}"
    echo -e "${YELLOW}   Active frontend appears to be: /frontend/ (Vite)${NC}"
    echo -e "${YELLOW}   Incomplete migration in: /src/frontend/ (Next.js)${NC}"
    read -p "Delete /src/frontend/? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        safe_delete "src/frontend/" "dir"
    else
        echo -e "${BLUE}ℹ️  Skipping /src/frontend/ (manual decision required)${NC}"
    fi
fi

# 5. Delete virtual environments (regenerate from requirements.txt)
echo "🔍 Checking virtual environments..."
safe_delete "venv/" "dir"
safe_delete "venv311/" "dir"

# ==============================================================================
# PHASE 2: ARCHIVE OBSOLETE DOCUMENTATION
# ==============================================================================

echo -e "\n${YELLOW}=== PHASE 2: Archiving Obsolete Documentation ===${NC}\n"

create_archive

# Status and summary documents (superseded by comprehensive review)
echo "📄 Archiving status documents..."
archive_file "BACKEND_COMPLETION_SUMMARY.md"
archive_file "FRONTEND_COMPLETION_SUMMARY.md"
archive_file "DEVELOPMENT_COMPLETION_SUMMARY.md"
archive_file "PHASE1_COMPLETION_SUMMARY.md"
archive_file "PLATFORM_ENHANCEMENT_SUMMARY.md"
archive_file "MIGRATION_SUMMARY.md"
archive_file "FINAL_MVP_SUMMARY.md"
archive_file "MVP_COMPLETION_STATUS.md"

# Test reports (superseded)
echo "📄 Archiving test reports..."
archive_file "FINAL_MVP_TEST_REPORT.md"
archive_file "API_TEST_SUMMARY.md"
archive_file "api_test_report.json"

# Old cleanup recommendations (superseded by this review)
archive_file "CLEANUP_RECOMMENDATIONS.md"

# Multiple quick start guides (should be consolidated into README)
echo "📄 Archiving duplicate quick start guides..."
archive_file "BACKEND_MVP_GUIDE.md"
archive_file "QUICK_START_V2.md"
archive_file "SIMPLE_TEST.md"
archive_file "START_HERE.md"
archive_file "QUICKSTART.md"

# Historical planning documents
echo "📄 Archiving planning documents..."
archive_file "restructuring_plan.md"

# ==============================================================================
# PHASE 3: DELETE TEST/DEMO SCRIPTS
# ==============================================================================

echo -e "\n${YELLOW}=== PHASE 3: Removing Test/Demo Scripts ===${NC}\n"

echo "🔍 Checking demo and test scripts..."
safe_delete "api_mock.py" "file"
safe_delete "demo.py" "file"
safe_delete "interactive_demo.py" "file"
safe_delete "create_demo_data.py" "file"
safe_delete "fetch_and_save_real_news.py" "file"
safe_delete "fetch_yle_news_simple.py" "file"
safe_delete "populate_live_data.py" "file"
safe_delete "populate_sample_data.py" "file"
safe_delete "insert_sample_articles.sql" "file"
safe_delete "insert_via_api.py" "file"
safe_delete "trigger_workflow.py" "file"
safe_delete "run_full_pipeline.py" "file"

# Keep actual test files in tests/
echo -e "${GREEN}ℹ️  Keeping actual test files in tests/ directory${NC}"

# ==============================================================================
# PHASE 4: CONSOLIDATE REDUNDANT DOCUMENTATION
# ==============================================================================

echo -e "\n${YELLOW}=== PHASE 4: Documentation Cleanup ===${NC}\n"

# Multiple testing guides (consolidate into TESTING.md)
echo "📄 Consolidating testing documentation..."
archive_file "TESTING_GUIDE.md"
archive_file "QUICK_TEST.md"
# Keep TESTING.md as the single source

# Web app guides (consolidate into README)
echo "📄 Consolidating web app guides..."
archive_file "WEB_APP_GUIDE.md"
archive_file "QUICK_START_WEB.md"

# ==============================================================================
# SUMMARY
# ==============================================================================

echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    CLEANUP SUMMARY                        ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}\n"

if [ "$DRY_RUN" = true ]; then
    echo -e "${BLUE}This was a DRY RUN. No files were actually deleted.${NC}"
    echo -e "${BLUE}Run without --dry-run to execute the cleanup.${NC}\n"
else
    echo -e "${GREEN}✅ Cleanup complete!${NC}\n"
    echo -e "📊 Statistics:"
    echo -e "   - Directories deleted: $DELETED_DIRS"
    echo -e "   - Files archived: $DELETED_FILES"
    echo -e "\n💡 Next steps:"
    echo -e "   1. Review changes: git status"
    echo -e "   2. Commit cleanup: git commit -m 'chore: cleanup obsolete files'"
    echo -e "   3. Regenerate venv: python -m venv venv"
    echo -e "   4. Install dependencies: pip install -r requirements.txt"
fi

echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              FILES TO KEEP (DO NOT DELETE)                ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}\n"

echo "✅ KEEP these essential files:"
echo "   - README.md (main entry point)"
echo "   - TESTING.md (testing guide)"
echo "   - COMPREHENSIVE_CODE_REVIEW_2025.md (this review)"
echo "   - RESTRUCTURING_PLAN_ANALYSIS.md (architecture analysis)"
echo "   - docs/ARCHITECTURE.md"
echo "   - docs/DEVELOPMENT.md"
echo "   - docs/WORKFLOW_AND_UX.md"
echo "   - All files in src/"
echo "   - All files in frontend/"
echo "   - All files in api/"
echo "   - All files in infrastructure/"
echo "   - All files in tests/"
echo "   - docker-compose.yml"
echo "   - requirements.txt"

echo -e "\n${YELLOW}⚠️  MANUAL REVIEW NEEDED:${NC}"
echo "   - Verify /agents/ is truly duplicate before deleting"
echo "   - Choose frontend: /frontend/ (Vite) OR /src/frontend/ (Next.js)"
echo "   - Review archived docs in docs/archive/"

echo -e "\n${GREEN}Done! 🎉${NC}\n"

