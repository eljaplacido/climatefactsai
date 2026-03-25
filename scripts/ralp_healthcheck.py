#!/usr/bin/env python3
"""
RALP Health Check — Verify all 7 Docker containers are healthy.
"""

import subprocess
import sys
import json

EXPECTED_CONTAINERS = [
    "clilens-api",
    "clilens-frontend",
    "climatenews-postgres",
    "climatenews-redis",
    "clilens-celery-worker",
    "clilens-celery-beat",
    "climatenews-jaeger",
]


def main():
    print("Checking Docker containers...")

    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as e:
        print(f"Docker not reachable: {e}")
        sys.exit(1)

    running = {}
    for line in result.stdout.strip().split("\n"):
        if "\t" in line:
            name, status = line.split("\t", 1)
            running[name] = status

    all_ok = True
    for container in EXPECTED_CONTAINERS:
        status = running.get(container, "NOT RUNNING")
        healthy = "Up" in status
        icon = "OK" if healthy else "FAIL"
        print(f"  [{icon}] {container}: {status}")
        if not healthy:
            all_ok = False

    if all_ok:
        print(f"\nAll {len(EXPECTED_CONTAINERS)} containers healthy!")
    else:
        missing = [c for c in EXPECTED_CONTAINERS if c not in running or "Up" not in running[c]]
        print(f"\n{len(missing)} container(s) not healthy: {', '.join(missing)}")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
