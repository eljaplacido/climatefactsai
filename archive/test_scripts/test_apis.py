"""
Comprehensive API and LLM Testing Script
Tests all external services and generates a report
"""

import os
import sys
import json
import requests
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# API Keys
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
NOAA_API_TOKEN = os.getenv("NOAA_API_TOKEN")
NASA_API_KEY = os.getenv("NOAA_API_KEY", "DEMO_KEY")

# Test Results
results = {
    "timestamp": datetime.now().isoformat(),
    "tests": []
}


def test_perplexity_api():
    """Test Perplexity API"""
    print("\n[1/6] Testing Perplexity API...")

    if not PERPLEXITY_API_KEY:
        return {
            "service": "Perplexity API",
            "status": "FAIL",
            "error": "API key not found",
            "details": "PERPLEXITY_API_KEY not set in .env"
        }

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "user",
                "content": "What is the latest climate news from Finland? Keep it brief."
            }
        ],
        "max_tokens": 100
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "service": "Perplexity API",
                "status": "OK",
                "model": "llama-3.1-sonar-small-128k-online",
                "response_preview": content[:100] + "..." if len(content) > 100 else content,
                "has_citations": bool(data.get("citations"))
            }
        else:
            return {
                "service": "Perplexity API",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}",
                "details": response.text[:200]
            }
    except Exception as e:
        return {
            "service": "Perplexity API",
            "status": "FAIL",
            "error": str(e)
        }


def test_anthropic_api():
    """Test Anthropic Claude API"""
    print("[2/6] Testing Anthropic Claude API...")

    if not ANTHROPIC_API_KEY:
        return {
            "service": "Anthropic Claude API",
            "status": "FAIL",
            "error": "API key not found",
            "details": "ANTHROPIC_API_KEY not set in .env"
        }

    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    payload = {
        "model": "claude-3-sonnet-20240229",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user",
                "content": "Explain climate change in one sentence."
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            content = data.get("content", [{}])[0].get("text", "")

            return {
                "service": "Anthropic Claude API",
                "status": "OK",
                "model": data.get("model"),
                "response_preview": content[:100] + "..." if len(content) > 100 else content,
                "usage": data.get("usage", {})
            }
        else:
            return {
                "service": "Anthropic Claude API",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}",
                "details": response.text[:200]
            }
    except Exception as e:
        return {
            "service": "Anthropic Claude API",
            "status": "FAIL",
            "error": str(e)
        }


def test_openai_api():
    """Test OpenAI API"""
    print("[3/6] Testing OpenAI API...")

    if not OPENAI_API_KEY:
        return {
            "service": "OpenAI API",
            "status": "FAIL",
            "error": "API key not found",
            "details": "OPENAI_API_KEY not set in .env"
        }

    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": "What is climate change in one sentence?"
            }
        ],
        "max_tokens": 50
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "service": "OpenAI API",
                "status": "OK",
                "model": data.get("model"),
                "response_preview": content[:100] + "..." if len(content) > 100 else content,
                "usage": data.get("usage", {})
            }
        else:
            return {
                "service": "OpenAI API",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}",
                "details": response.text[:200]
            }
    except Exception as e:
        return {
            "service": "OpenAI API",
            "status": "FAIL",
            "error": str(e)
        }


def test_database():
    """Test PostgreSQL database connection"""
    print("[4/6] Testing PostgreSQL Database...")

    try:
        import psycopg2

        conn = psycopg2.connect(
            host="localhost",
            port=5433,
            database="climatenews",
            user="postgres",
            password="climatenews123"
        )

        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        article_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM countries")
        country_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return {
            "service": "PostgreSQL Database",
            "status": "OK",
            "host": "localhost:5433",
            "database": "climatenews",
            "article_count": article_count,
            "country_count": country_count
        }
    except Exception as e:
        return {
            "service": "PostgreSQL Database",
            "status": "FAIL",
            "error": str(e)
        }


def test_fastapi():
    """Test FastAPI backend"""
    print("[5/6] Testing FastAPI Backend...")

    try:
        # Test health endpoint
        response = requests.get("http://localhost:8000/health", timeout=5)

        if response.status_code == 200:
            # Test stats endpoint
            stats_response = requests.get("http://localhost:8000/api/stats", timeout=5)

            if stats_response.status_code == 200:
                stats = stats_response.json()

                return {
                    "service": "FastAPI Backend",
                    "status": "OK",
                    "url": "http://localhost:8000",
                    "health": "healthy",
                    "stats": stats
                }

        return {
            "service": "FastAPI Backend",
            "status": "FAIL",
            "error": f"HTTP {response.status_code}"
        }
    except Exception as e:
        return {
            "service": "FastAPI Backend",
            "status": "FAIL",
            "error": str(e)
        }


def test_climate_data_apis():
    """Test NOAA and NASA climate data APIs"""
    print("[6/6] Testing Climate Data APIs (NOAA/NASA)...")

    results_list = []

    # Test NOAA (if configured)
    if NOAA_API_TOKEN and NOAA_API_TOKEN.strip():
        try:
            url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/datasets"
            headers = {"token": NOAA_API_TOKEN}
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                results_list.append({
                    "service": "NOAA Climate Data API",
                    "status": "OK",
                    "available_datasets": len(response.json().get("results", []))
                })
            else:
                results_list.append({
                    "service": "NOAA Climate Data API",
                    "status": "FAIL",
                    "error": f"HTTP {response.status_code}"
                })
        except Exception as e:
            results_list.append({
                "service": "NOAA Climate Data API",
                "status": "FAIL",
                "error": str(e)
            })
    else:
        results_list.append({
            "service": "NOAA Climate Data API",
            "status": "SKIP",
            "note": "API token not configured"
        })

    # Test NASA (using DEMO_KEY)
    try:
        url = f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}&count=1"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            results_list.append({
                "service": "NASA API",
                "status": "OK",
                "note": "Using DEMO_KEY - limited rate"
            })
        else:
            results_list.append({
                "service": "NASA API",
                "status": "FAIL",
                "error": f"HTTP {response.status_code}"
            })
    except Exception as e:
        results_list.append({
            "service": "NASA API",
            "status": "FAIL",
            "error": str(e)
        })

    return results_list


def print_report(results):
    """Print formatted report"""
    print("\n" + "=" * 80)
    print("API & SERVICE TEST REPORT")
    print("=" * 80)
    print(f"Timestamp: {results['timestamp']}")
    print("=" * 80)

    passed = 0
    failed = 0
    skipped = 0

    for test in results['tests']:
        if isinstance(test, list):
            # Handle nested test results
            for subtest in test:
                print_test_result(subtest)
                if subtest['status'] == 'OK':
                    passed += 1
                elif subtest['status'] == 'SKIP':
                    skipped += 1
                else:
                    failed += 1
        else:
            print_test_result(test)
            if test['status'] == 'OK':
                passed += 1
            elif test['status'] == 'SKIP':
                skipped += 1
            else:
                failed += 1

    print("=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 80)

    # Save to file
    with open("api_test_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nFull report saved to: api_test_report.json")


def print_test_result(test):
    """Print individual test result"""
    status_symbol = "[OK]" if test['status'] == 'OK' else "[FAIL]" if test['status'] == 'FAIL' else "[SKIP]"
    print(f"\n{status_symbol} {test['service']}")

    for key, value in test.items():
        if key not in ['service', 'status']:
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")


def main():
    """Run all tests"""
    print("=" * 80)
    print("CLIMATE NEWS MVP - API & SERVICE DIAGNOSTIC")
    print("=" * 80)

    # Run tests
    results['tests'].append(test_perplexity_api())
    results['tests'].append(test_anthropic_api())
    results['tests'].append(test_openai_api())
    results['tests'].append(test_database())
    results['tests'].append(test_fastapi())
    results['tests'].append(test_climate_data_apis())

    # Print report
    print_report(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
