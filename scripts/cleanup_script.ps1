# ==============================================================================
# CliLens.AI - Safe Cleanup Script (Windows PowerShell)
# ==============================================================================
# This script removes obsolete files and duplicate code identified in the
# comprehensive code review.
#
# IMPORTANT: Review changes before executing!
# Run with -WhatIf first to see what would be deleted
#
# Usage:
#   .\cleanup_script.ps1 -WhatIf    # Preview changes (DRY RUN)
#   .\cleanup_script.ps1             # Execute cleanup
# ==============================================================================

[CmdletBinding(SupportsShouldProcess=$true)]
param()

# Statistics
$DeletedFiles = 0
$DeletedDirs = 0

# Function to safely delete a file or directory
function Remove-ItemSafely {
    param(
        [string]$Path,
        [string]$Type
    )
    
    if (-not (Test-Path $Path)) {
        Write-Host "⚠️  Not found (already deleted?): $Path" -ForegroundColor Yellow
        return
    }
    
    # Calculate size
    $Size = if ($Type -eq "dir") {
        (Get-ChildItem $Path -Recurse -ErrorAction SilentlyContinue | 
         Measure-Object -Property Length -Sum).Sum / 1MB
        "$([math]::Round($Size, 2)) MB"
    } else {
        $FileSize = (Get-Item $Path).Length / 1KB
        "$([math]::Round($FileSize, 2)) KB"
    }
    
    if ($PSCmdlet.ShouldProcess($Path, "Delete $Type ($Size)")) {
        Write-Host "🗑️  Deleting $Type : $Path ($Size)" -ForegroundColor Red
        Remove-Item $Path -Recurse -Force -ErrorAction SilentlyContinue
        
        if ($Type -eq "dir") {
            $script:DeletedDirs++
        } else {
            $script:DeletedFiles++
        }
    } else {
        Write-Host "[DRY RUN] Would delete $Type : $Path ($Size)" -ForegroundColor Cyan
    }
}

# Function to create archive directory
function New-ArchiveDirectory {
    $ArchiveDir = "docs\archive"
    
    if (-not (Test-Path $ArchiveDir)) {
        if ($PSCmdlet.ShouldProcess($ArchiveDir, "Create archive directory")) {
            Write-Host "📁 Creating archive directory: $ArchiveDir" -ForegroundColor Green
            New-Item -ItemType Directory -Path $ArchiveDir -Force | Out-Null
        } else {
            Write-Host "[DRY RUN] Would create: $ArchiveDir" -ForegroundColor Cyan
        }
    }
}

# Function to archive a file
function Move-ToArchive {
    param([string]$File)
    
    $ArchiveDir = "docs\archive"
    
    if (-not (Test-Path $File)) {
        Write-Host "⚠️  Not found: $File" -ForegroundColor Yellow
        return
    }
    
    if ($PSCmdlet.ShouldProcess($File, "Archive to $ArchiveDir")) {
        Write-Host "📦 Archiving: $File" -ForegroundColor Green
        Move-Item $File $ArchiveDir -Force
        $script:DeletedFiles++
    } else {
        Write-Host "[DRY RUN] Would archive: $File → $ArchiveDir" -ForegroundColor Cyan
    }
}

Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║         CliLens.AI - Codebase Cleanup Script             ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

if ($WhatIfPreference) {
    Write-Host "=== DRY RUN MODE - No files will be deleted ===`n" -ForegroundColor Yellow
}

# ==============================================================================
# PHASE 1: DELETE DUPLICATE DIRECTORIES
# ==============================================================================

Write-Host "`n=== PHASE 1: Removing Duplicate Directories ===`n" -ForegroundColor Yellow

Write-Host "🔍 Checking /agents/ directory..."
Remove-ItemSafely -Path "agents" -Type "dir"

Write-Host "🔍 Checking backup directory..."
Remove-ItemSafely -Path "agents_backup_20251022" -Type "dir"

Write-Host "🔍 Checking placeholder directories..."
Remove-ItemSafely -Path "srcbackendservices" -Type "dir"
Remove-ItemSafely -Path "srcbackendshared" -Type "dir"
Remove-ItemSafely -Path "srcfrontendsrc" -Type "dir"

Write-Host "🔍 Checking for duplicate frontend..."
if ((Test-Path "frontend\src") -and (Test-Path "src\frontend")) {
    Write-Host "⚠️  WARNING: Both /frontend/ and /src/frontend/ exist" -ForegroundColor Yellow
    Write-Host "   Active frontend appears to be: /frontend/ (Vite)" -ForegroundColor Yellow
    Write-Host "   Incomplete migration in: /src/frontend/ (Next.js)" -ForegroundColor Yellow
    
    $Response = Read-Host "Delete /src/frontend/? [y/N]"
    if ($Response -eq 'y' -or $Response -eq 'Y') {
        Remove-ItemSafely -Path "src\frontend" -Type "dir"
    } else {
        Write-Host "ℹ️  Skipping /src/frontend/ (manual decision required)" -ForegroundColor Cyan
    }
}

Write-Host "🔍 Checking virtual environments..."
Remove-ItemSafely -Path "venv" -Type "dir"
Remove-ItemSafely -Path "venv311" -Type "dir"

# ==============================================================================
# PHASE 2: ARCHIVE OBSOLETE DOCUMENTATION
# ==============================================================================

Write-Host "`n=== PHASE 2: Archiving Obsolete Documentation ===`n" -ForegroundColor Yellow

New-ArchiveDirectory

Write-Host "📄 Archiving status documents..."
Move-ToArchive "BACKEND_COMPLETION_SUMMARY.md"
Move-ToArchive "FRONTEND_COMPLETION_SUMMARY.md"
Move-ToArchive "DEVELOPMENT_COMPLETION_SUMMARY.md"
Move-ToArchive "PHASE1_COMPLETION_SUMMARY.md"
Move-ToArchive "PLATFORM_ENHANCEMENT_SUMMARY.md"
Move-ToArchive "MIGRATION_SUMMARY.md"
Move-ToArchive "FINAL_MVP_SUMMARY.md"
Move-ToArchive "MVP_COMPLETION_STATUS.md"

Write-Host "📄 Archiving test reports..."
Move-ToArchive "FINAL_MVP_TEST_REPORT.md"
Move-ToArchive "API_TEST_SUMMARY.md"
Move-ToArchive "api_test_report.json"

Move-ToArchive "CLEANUP_RECOMMENDATIONS.md"

Write-Host "📄 Archiving duplicate quick start guides..."
Move-ToArchive "BACKEND_MVP_GUIDE.md"
Move-ToArchive "QUICK_START_V2.md"
Move-ToArchive "SIMPLE_TEST.md"
Move-ToArchive "START_HERE.md"
Move-ToArchive "QUICKSTART.md"

Write-Host "📄 Archiving planning documents..."
Move-ToArchive "restructuring_plan.md"

# ==============================================================================
# PHASE 3: DELETE TEST/DEMO SCRIPTS
# ==============================================================================

Write-Host "`n=== PHASE 3: Removing Test/Demo Scripts ===`n" -ForegroundColor Yellow

Write-Host "🔍 Checking demo and test scripts..."
Remove-ItemSafely -Path "api_mock.py" -Type "file"
Remove-ItemSafely -Path "demo.py" -Type "file"
Remove-ItemSafely -Path "interactive_demo.py" -Type "file"
Remove-ItemSafely -Path "create_demo_data.py" -Type "file"
Remove-ItemSafely -Path "fetch_and_save_real_news.py" -Type "file"
Remove-ItemSafely -Path "fetch_yle_news_simple.py" -Type "file"
Remove-ItemSafely -Path "populate_live_data.py" -Type "file"
Remove-ItemSafely -Path "populate_sample_data.py" -Type "file"
Remove-ItemSafely -Path "insert_sample_articles.sql" -Type "file"
Remove-ItemSafely -Path "insert_via_api.py" -Type "file"
Remove-ItemSafely -Path "trigger_workflow.py" -Type "file"
Remove-ItemSafely -Path "run_full_pipeline.py" -Type "file"

Write-Host "ℹ️  Keeping actual test files in tests/ directory" -ForegroundColor Green

# ==============================================================================
# PHASE 4: CONSOLIDATE REDUNDANT DOCUMENTATION
# ==============================================================================

Write-Host "`n=== PHASE 4: Documentation Cleanup ===`n" -ForegroundColor Yellow

Write-Host "📄 Consolidating testing documentation..."
Move-ToArchive "TESTING_GUIDE.md"
Move-ToArchive "QUICK_TEST.md"

Write-Host "📄 Consolidating web app guides..."
Move-ToArchive "WEB_APP_GUIDE.md"
Move-ToArchive "QUICK_START_WEB.md"

# ==============================================================================
# SUMMARY
# ==============================================================================

Write-Host "`n╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    CLEANUP SUMMARY                        ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

if ($WhatIfPreference) {
    Write-Host "This was a DRY RUN. No files were actually deleted." -ForegroundColor Cyan
    Write-Host "Run without -WhatIf to execute the cleanup.`n" -ForegroundColor Cyan
} else {
    Write-Host "✅ Cleanup complete!`n" -ForegroundColor Green
    Write-Host "📊 Statistics:"
    Write-Host "   - Directories deleted: $DeletedDirs"
    Write-Host "   - Files archived: $DeletedFiles"
    Write-Host "`n💡 Next steps:"
    Write-Host "   1. Review changes: git status"
    Write-Host "   2. Commit cleanup: git commit -m 'chore: cleanup obsolete files'"
    Write-Host "   3. Regenerate venv: python -m venv venv"
    Write-Host "   4. Install dependencies: pip install -r requirements.txt"
}

Write-Host "`n╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              FILES TO KEEP (DO NOT DELETE)                ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝`n" -ForegroundColor Green

Write-Host "✅ KEEP these essential files:"
Write-Host "   - README.md (main entry point)"
Write-Host "   - TESTING.md (testing guide)"
Write-Host "   - COMPREHENSIVE_CODE_REVIEW_2025.md (this review)"
Write-Host "   - RESTRUCTURING_PLAN_ANALYSIS.md (architecture analysis)"
Write-Host "   - docs/ARCHITECTURE.md"
Write-Host "   - docs/DEVELOPMENT.md"
Write-Host "   - docs/WORKFLOW_AND_UX.md"
Write-Host "   - All files in src/"
Write-Host "   - All files in frontend/"
Write-Host "   - All files in api/"
Write-Host "   - All files in infrastructure/"
Write-Host "   - All files in tests/"
Write-Host "   - docker-compose.yml"
Write-Host "   - requirements.txt"

Write-Host "`n⚠️  MANUAL REVIEW NEEDED:" -ForegroundColor Yellow
Write-Host "   - Verify /agents/ is truly duplicate before deleting"
Write-Host "   - Choose frontend: /frontend/ (Vite) OR /src/frontend/ (Next.js)"
Write-Host "   - Review archived docs in docs/archive/"

Write-Host "`nDone! 🎉`n" -ForegroundColor Green

