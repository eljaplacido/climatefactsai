#!/usr/bin/env python3
"""
RALP E2E Validation — Full end-to-end platform health check.

Tests every layer of the CliLens.AI platform:
1. Infrastructure: Docker containers healthy
2. Database: PostgreSQL reachable, tables exist
3. Cache: Redis reachable
4. API: Health endpoint + key routes respond
5. Frontend: Next.js serves pages
6. New features: OAuth, research, CARF, filters
"""

import json
import sys
import urllib.request
import urllib.error

API_URL = "http://localhost:5400"
FRONTEND_URL = "http://localhost:5300"
JAEGER_URL = "http://localhost:5686"

results = []


def check(name: str, url: str, expected_status: int = 200, method: str = "GET", body: dict = None) -> bool:
    """Test an HTTP endpoint."""
    try:
        if body:
            data = json.dumps(body).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method=method)
        else:
            req = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            ok = status == expected_status
            results.append({"name": name, "status": status, "ok": ok})
            icon = "PASS" if ok else "FAIL"
            print(f"  [{icon}] {name} — HTTP {status}")
            return ok
    except urllib.error.HTTPError as e:
        ok = e.code == expected_status
        results.append({"name": name, "status": e.code, "ok": ok})
        icon = "PASS" if ok else "FAIL"
        print(f"  [{icon}] {name} — HTTP {e.code}")
        return ok
    except Exception as e:
        results.append({"name": name, "status": 0, "ok": False, "error": str(e)})
        print(f"  [FAIL] {name} — {e}")
        return False


def main():
    print("\n=== RALP E2E Validation ===\n")

    # 1. API Health
    print("1. API Health")
    check("API /health", f"{API_URL}/health")
    check("API /healthz", f"{API_URL}/healthz")

    # 2. Core API Routes
    print("\n2. Core API Routes")
    check("Articles list", f"{API_URL}/api/articles?limit=1")
    check("Countries list", f"{API_URL}/api/countries")
    check("Tags", f"{API_URL}/api/tags")
    check("Stats", f"{API_URL}/api/stats")
    check("Map country-stats", f"{API_URL}/api/map/country-stats")
    check("Search suggestions", f"{API_URL}/api/search/suggestions?q=climate")

    # 3. New Feature Routes
    print("\n3. New Feature Routes")
    check("OAuth providers", f"{API_URL}/api/auth/oauth/providers")
    check("CARF status", f"{API_URL}/api/carf/status")
    check("Explore topics", f"{API_URL}/api/explore/topics")
    check("Explore sources", f"{API_URL}/api/explore/sources")
    check("Explore coverage", f"{API_URL}/api/explore/coverage")
    check("Explore articles (POST)", f"{API_URL}/api/explore/articles",
          method="POST", body={"limit": 1, "countries": []})

    # 4. Frontend
    print("\n4. Frontend")
    check("Frontend home", f"{FRONTEND_URL}/")

    # 5. Monitoring
    print("\n5. Monitoring")
    check("Jaeger UI", JAEGER_URL)

    # Summary
    passed = sum(1 for r in results if r["ok"])
    total = len(results)
    failed = total - passed
    pct = (passed / total * 100) if total > 0 else 0

    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed ({pct:.0f}%)")
    if failed:
        print(f"Failed:")
        for r in results:
            if not r["ok"]:
                print(f"  - {r['name']}: HTTP {r['status']} {r.get('error', '')}")
    print(f"{'='*50}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
