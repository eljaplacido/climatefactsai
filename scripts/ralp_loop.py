#!/usr/bin/env python3
"""
RALP Loop — Iterative AI-Assisted Development Loop for CliLens.AI

Implements the Read-Attempt-Log-Persist methodology:
1. READ: Load STATE.md + TASK.md + PRD requirements
2. ATTEMPT: Execute the current task (test, lint, build, etc.)
3. LOG: Record success/failure to STATE.md with diagnostics
4. PERSIST: On success, commit; on failure, update state and retry

Usage:
    python scripts/ralp_loop.py --task test           # Run tests until passing
    python scripts/ralp_loop.py --task build           # Build until succeeding
    python scripts/ralp_loop.py --task lint            # Lint until clean
    python scripts/ralp_loop.py --task healthcheck     # Check all services healthy
    python scripts/ralp_loop.py --task e2e             # Full end-to-end validation
    python scripts/ralp_loop.py --task migrate         # Run DB migrations
    python scripts/ralp_loop.py --task custom "cmd"    # Run custom command

Options:
    --max-iterations N    Max retry attempts (default: 5)
    --pause-on-repeat     Pause if same error occurs twice
    --auto-commit         Git commit on success
    --verbose             Show full command output
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = PROJECT_ROOT / "scripts" / "ralp_state.json"
LOG_FILE = PROJECT_ROOT / "scripts" / "ralp_log.md"

# Task definitions: name → (command, success_check, description)
TASK_COMMANDS: Dict[str, Dict] = {
    "test_backend": {
        "cmd": "docker exec clilens-api python -m pytest tests/ -x --tb=short -q",
        "description": "Run backend pytest suite",
        "category": "test",
    },
    "test_frontend": {
        "cmd": "docker exec clilens-frontend npx vitest run --reporter=verbose",
        "description": "Run frontend Vitest suite",
        "category": "test",
    },
    "test": {
        "cmd": "docker exec clilens-api python -m pytest tests/ -x --tb=short -q",
        "description": "Run all tests (backend)",
        "category": "test",
    },
    "build": {
        "cmd": "docker-compose -f docker-compose.simple.yml build",
        "description": "Build all Docker images",
        "category": "build",
    },
    "healthcheck": {
        "cmd": "python scripts/ralp_healthcheck.py",
        "description": "Check all 7 services are healthy",
        "category": "validate",
    },
    "lint": {
        "cmd": "docker exec clilens-api python -m flake8 api/ --max-line-length=120 --ignore=E501,W503",
        "description": "Lint backend Python code",
        "category": "lint",
    },
    "migrate": {
        "cmd": "docker exec climatenews-postgres psql -U postgres -d climatenews -f /migrations/013_oauth_and_user_activity.sql && docker exec climatenews-postgres psql -U postgres -d climatenews -f /migrations/014_query_subscriptions.sql",
        "description": "Run database migrations",
        "category": "migrate",
    },
    "api_smoke": {
        "cmd": "curl -sf http://localhost:5400/health && curl -sf http://localhost:5400/api/articles?limit=1",
        "description": "Smoke test API endpoints",
        "category": "validate",
    },
    "frontend_smoke": {
        "cmd": "curl -sf http://localhost:5300/",
        "description": "Smoke test frontend",
        "category": "validate",
    },
    "e2e": {
        "cmd": "python scripts/ralp_e2e.py",
        "description": "Full end-to-end validation pipeline",
        "category": "validate",
    },
}


def load_state() -> Dict:
    """Load RALP state from JSON file."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "current_task": None,
        "iteration": 0,
        "last_error": None,
        "error_count": 0,
        "consecutive_same_error": 0,
        "history": [],
        "started_at": None,
        "completed_tasks": [],
    }


def save_state(state: Dict):
    """Persist RALP state to JSON file."""
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def log_entry(task: str, iteration: int, success: bool, output: str, error: str = ""):
    """Append to RALP log file."""
    timestamp = datetime.now().isoformat()
    status = "SUCCESS" if success else "FAILURE"
    entry = f"\n## [{status}] {task} — Iteration {iteration} ({timestamp})\n"
    if error:
        entry += f"**Error:** {error[:500]}\n"
    if output:
        entry += f"```\n{output[-1000:]}\n```\n"
    entry += "---\n"

    with open(LOG_FILE, "a") as f:
        f.write(entry)


def run_command(cmd: str, timeout: int = 300) -> Tuple[bool, str, str]:
    """Execute a shell command and return (success, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(PROJECT_ROOT),
        )
        return (
            result.returncode == 0,
            result.stdout,
            result.stderr,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return False, "", str(e)


def ralp_loop(
    task_name: str,
    max_iterations: int = 5,
    pause_on_repeat: bool = True,
    auto_commit: bool = False,
    verbose: bool = False,
    custom_cmd: Optional[str] = None,
):
    """Execute the RALP loop for a given task."""
    state = load_state()

    # Resolve task
    if custom_cmd:
        task_def = {"cmd": custom_cmd, "description": f"Custom: {custom_cmd[:80]}", "category": "custom"}
    elif task_name in TASK_COMMANDS:
        task_def = TASK_COMMANDS[task_name]
    else:
        print(f"Unknown task: {task_name}")
        print(f"Available: {', '.join(TASK_COMMANDS.keys())}")
        sys.exit(1)

    cmd = task_def["cmd"]
    description = task_def["description"]

    print(f"\n{'='*60}")
    print(f"RALP Loop: {description}")
    print(f"Command: {cmd}")
    print(f"Max iterations: {max_iterations}")
    print(f"{'='*60}\n")

    state["current_task"] = task_name
    state["started_at"] = datetime.now().isoformat()

    for iteration in range(1, max_iterations + 1):
        state["iteration"] = iteration
        print(f"\n--- Iteration {iteration}/{max_iterations} ---")

        # ATTEMPT
        success, stdout, stderr = run_command(cmd)
        output = stdout + stderr

        if verbose:
            print(output[-2000:])

        if success:
            # SUCCESS
            print(f"  [PASS] {description}")
            log_entry(task_name, iteration, True, output)

            state["last_error"] = None
            state["error_count"] = 0
            state["consecutive_same_error"] = 0
            state["completed_tasks"].append({
                "task": task_name,
                "iteration": iteration,
                "completed_at": datetime.now().isoformat(),
            })
            save_state(state)

            # Auto-commit on success
            if auto_commit:
                commit_success, _, _ = run_command(
                    f'git add -A && git commit -m "RALP: {task_name} passed (iteration {iteration})"'
                )
                if commit_success:
                    print("  [GIT] Changes committed")

            print(f"\n{'='*60}")
            print(f"RALP COMPLETE: {description} passed on iteration {iteration}")
            print(f"{'='*60}")
            return True

        else:
            # FAILURE
            error_summary = stderr[-300:] if stderr else stdout[-300:]
            print(f"  [FAIL] {error_summary[:200]}")
            log_entry(task_name, iteration, False, output, error_summary)

            # Track repeated errors
            if state["last_error"] and error_summary[:100] == state["last_error"][:100]:
                state["consecutive_same_error"] += 1
            else:
                state["consecutive_same_error"] = 1

            state["last_error"] = error_summary
            state["error_count"] += 1
            state["history"].append({
                "iteration": iteration,
                "error": error_summary[:500],
                "timestamp": datetime.now().isoformat(),
            })
            save_state(state)

            # Pause on repeated errors
            if pause_on_repeat and state["consecutive_same_error"] >= 2:
                print(f"\n  [PAUSE] Same error {state['consecutive_same_error']} times. Human intervention needed.")
                print(f"  Error: {error_summary[:300]}")
                print(f"\n  Review: scripts/ralp_state.json")
                print(f"  Log:    scripts/ralp_log.md")
                return False

    print(f"\n{'='*60}")
    print(f"RALP EXHAUSTED: {description} failed after {max_iterations} iterations")
    print(f"Review scripts/ralp_state.json and scripts/ralp_log.md")
    print(f"{'='*60}")
    return False


def main():
    parser = argparse.ArgumentParser(description="RALP Loop — Iterative AI-Assisted Development")
    parser.add_argument("--task", required=True, help="Task to execute (test, build, lint, healthcheck, e2e, migrate, custom)")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max retry attempts")
    parser.add_argument("--pause-on-repeat", action="store_true", default=True, help="Pause if same error repeats")
    parser.add_argument("--auto-commit", action="store_true", help="Git commit on success")
    parser.add_argument("--verbose", action="store_true", help="Show full output")
    parser.add_argument("command", nargs="?", default=None, help="Custom command (with --task custom)")

    args = parser.parse_args()

    ralp_loop(
        task_name=args.task,
        max_iterations=args.max_iterations,
        pause_on_repeat=args.pause_on_repeat,
        auto_commit=args.auto_commit,
        verbose=args.verbose,
        custom_cmd=args.command,
    )


if __name__ == "__main__":
    main()
