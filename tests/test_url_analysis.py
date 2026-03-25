"""
Test script for URL analysis endpoint

Prerequisites:
1. ANTHROPIC_API_KEY must be set in environment
2. PostgreSQL database must be running with url_analyses table
3. API server must be running on http://localhost:8000
4. Must have a valid user account with Basic+ subscription
"""

import requests
import time
import json
import os
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
TEST_URL = "https://www.bbc.com/news/science-environment-63585970"  # BBC climate article

def test_url_analysis():
    """Test the complete URL analysis workflow"""

    print("=" * 80)
    print("URL ANALYSIS ENDPOINT TEST")
    print("=" * 80)

    # Check ANTHROPIC_API_KEY
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY environment variable not set!")
        print("   Please set it before running this test.")
        return

    print(f"\n✓ ANTHROPIC_API_KEY is set: {api_key[:15]}...")

    # Step 1: Login (you need to create a test user first)
    print("\n" + "-" * 80)
    print("STEP 1: Authentication")
    print("-" * 80)

    login_data = {
        "email": "test@example.com",  # Replace with your test account
        "password": "TestPassword123!"
    }

    print(f"Logging in as: {login_data['email']}")

    try:
        login_response = requests.post(
            f"{API_BASE_URL}/api/auth/login",
            json=login_data,
            timeout=10
        )

        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(f"   Response: {login_response.text}")
            print("\n💡 TIP: Create a test user first:")
            print("   POST /api/auth/register")
            print('   {"email": "test@example.com", "password": "TestPassword123!", "full_name": "Test User"}')
            return

        tokens = login_response.json()
        access_token = tokens["access_token"]
        print(f"✓ Login successful! Token: {access_token[:20]}...")

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        print("\n💡 TIP: Make sure the API server is running:")
        print("   cd api && uvicorn main:app --reload")
        return

    # Headers for authenticated requests
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # Step 2: Check usage stats
    print("\n" + "-" * 80)
    print("STEP 2: Check Usage Statistics")
    print("-" * 80)

    try:
        stats_response = requests.get(
            f"{API_BASE_URL}/api/analyze-url/stats/usage",
            headers=headers,
            timeout=10
        )

        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"✓ Current usage stats:")
            print(f"   - Tier: {stats['tier']}")
            print(f"   - Limit: {stats['limit']}")
            print(f"   - Used: {stats['used']}")
            print(f"   - Remaining: {stats['remaining']}")

            if stats['remaining'] == 0 and stats['remaining'] != 'unlimited':
                print("\n❌ Monthly limit exceeded! Cannot submit analysis.")
                return
        else:
            print(f"⚠️  Could not fetch usage stats: {stats_response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"⚠️  Error fetching stats: {e}")

    # Step 3: Submit URL for analysis
    print("\n" + "-" * 80)
    print("STEP 3: Submit URL for Analysis")
    print("-" * 80)

    print(f"Submitting URL: {TEST_URL}")

    analysis_request = {
        "url": TEST_URL
    }

    try:
        submit_response = requests.post(
            f"{API_BASE_URL}/api/analyze-url",
            headers=headers,
            json=analysis_request,
            timeout=10
        )

        if submit_response.status_code == 403:
            print("❌ Access denied! This feature requires Basic+ subscription.")
            print("\n💡 TIP: Update your user's subscription_tier in the database:")
            print("   UPDATE users SET subscription_tier = 'basic' WHERE email = 'test@example.com';")
            return

        if submit_response.status_code == 429:
            print("❌ Rate limit exceeded!")
            print(f"   {submit_response.json()['detail']}")
            return

        if submit_response.status_code != 200:
            print(f"❌ Submission failed: {submit_response.status_code}")
            print(f"   Response: {submit_response.text}")
            return

        job = submit_response.json()
        job_id = job["job_id"]
        print(f"✓ Analysis submitted successfully!")
        print(f"   - Job ID: {job_id}")
        print(f"   - Status: {job['status']}")
        print(f"   - Estimated time: {job['estimated_time']} seconds")

    except requests.exceptions.RequestException as e:
        print(f"❌ Error submitting URL: {e}")
        return

    # Step 4: Poll for results
    print("\n" + "-" * 80)
    print("STEP 4: Wait for Analysis to Complete")
    print("-" * 80)

    max_attempts = 20  # Max 60 seconds (3s * 20)
    attempt = 0

    while attempt < max_attempts:
        attempt += 1
        time.sleep(3)  # Wait 3 seconds between polls

        print(f"Polling attempt {attempt}/{max_attempts}...", end=" ")

        try:
            result_response = requests.get(
                f"{API_BASE_URL}/api/analyze-url/{job_id}",
                headers=headers,
                timeout=10
            )

            if result_response.status_code == 404:
                print("❌ Job not found!")
                return

            if result_response.status_code != 200:
                print(f"❌ Error: {result_response.status_code}")
                return

            result = result_response.json()
            status = result["status"]

            print(f"Status: {status}")

            if status == "completed":
                print("\n✅ Analysis completed successfully!")
                print("\n" + "=" * 80)
                print("RESULTS")
                print("=" * 80)
                print(f"\nURL: {result['submitted_url']}")
                print(f"Title: {result.get('title', 'N/A')}")
                print(f"Source: {result.get('source_name', 'N/A')}")
                print(f"Language: {result.get('language_code', 'N/A')}")
                print(f"\nCredibility Assessment:")
                print(f"  - Reliability Score: {result.get('reliability_score', 'N/A')}")
                print(f"  - Overall Credibility: {result.get('overall_credibility', 'N/A')}")

                claims = result.get("extracted_claims", [])
                print(f"\nExtracted Claims ({len(claims)}):")
                for i, claim in enumerate(claims, 1):
                    print(f"\n  {i}. {claim.get('claim_text', 'N/A')}")
                    print(f"     Type: {claim.get('claim_type', 'N/A')}")
                    print(f"     Importance: {claim.get('importance_score', 'N/A')}")

                timing = result.get("processing_time_ms")
                if timing:
                    print(f"\nProcessing Time: {timing}ms ({timing/1000:.2f}s)")

                print("\n" + "=" * 80)
                print("Text Preview:")
                print("=" * 80)
                text = result.get("extracted_text", "")
                if text:
                    preview = text[:500] + "..." if len(text) > 500 else text
                    print(preview)

                return

            elif status == "failed":
                print("\n❌ Analysis failed!")
                error = result.get("error_message", "Unknown error")
                print(f"   Error: {error}")

                if "Anthropic API key not configured" in error:
                    print("\n💡 TIP: Set ANTHROPIC_API_KEY in your .env file")
                elif "Rate limit" in error:
                    print("\n💡 TIP: Wait a minute and try again")

                return

            elif status == "processing":
                # Continue polling
                continue

        except requests.exceptions.RequestException as e:
            print(f"❌ Error: {e}")
            return

    print("\n⏱️  Timeout: Analysis took longer than expected")
    print("   Check the status later using:")
    print(f"   GET /api/analyze-url/{job_id}")


if __name__ == "__main__":
    test_url_analysis()
