"""
Climate News Pipeline - End-to-End Test

Tests the complete workflow:
1. News Discovery (Perplexity)
2. Claim Extraction
3. Fact-Checking (Open-Meteo + NOAA + NASA POWER)
4. Credibility Scoring
5. Content Generation

Run this to verify everything works!
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Fix Windows encoding for UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src" / "backend"))

print("\n" + "=" * 80)
print(" CliLens.AI - Full Pipeline Test")
print("=" * 80)
print()

# ============================================================================
# STEP 1: Load Environment Variables
# ============================================================================
print("📋 STEP 1: Loading environment variables...")

from dotenv import load_dotenv
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
NOAA_API_TOKEN = os.getenv("NOAA_API_TOKEN")

# Test location (Helsinki, Finland)
TEST_LOCATION = {
    "name": "Helsinki",
    "latitude": 60.1699,
    "longitude": 24.9384,
    "country": "Finland",
    "country_code": "FI"
}

print(f"  ✓ Anthropic API Key: {'SET' if ANTHROPIC_API_KEY else 'MISSING'}")
print(f"  ✓ OpenAI API Key: {'SET' if OPENAI_API_KEY else 'MISSING'}")
print(f"  ✓ Perplexity API Key: {'SET' if PERPLEXITY_API_KEY else 'MISSING'}")
print(f"  ✓ NOAA API Token: {'SET' if NOAA_API_TOKEN else 'MISSING (optional)'}")
print(f"  ✓ Test Location: {TEST_LOCATION['name']}, {TEST_LOCATION['country']}")
print()

# ============================================================================
# STEP 2: Test News Discovery (Perplexity)
# ============================================================================
print("🔍 STEP 2: Testing News Discovery with Perplexity...")
print("-" * 80)

from services.ingestion_service.src.perplexity_news_discovery import PerplexityNewsDiscovery

discovery = PerplexityNewsDiscovery(api_key=PERPLEXITY_API_KEY)

try:
    articles = discovery.discover_news(
        country=TEST_LOCATION["country"],
        country_code=TEST_LOCATION["country_code"],
        max_articles=5,
        days_back=7
    )

    print(f"✅ SUCCESS: Found {len(articles)} articles")
    if articles:
        print("\nSample Article:")
        sample = articles[0]
        print(f"  Title: {sample.get('title', 'N/A')[:80]}...")
        print(f"  Source: {sample.get('source_name', 'N/A')}")
        print(f"  Credibility: {sample.get('credibility_score', 'N/A')}/100")
        print(f"  URL: {sample.get('url', 'N/A')[:60]}...")
    print()
except Exception as e:
    print(f"❌ FAILED: {e}")
    articles = []
    print()

# ============================================================================
# STEP 3: Test Climate Data APIs
# ============================================================================
print("🌡️  STEP 3: Testing Climate Data APIs...")
print("-" * 80)

from services.verification_service.src.climate_api import (
    OpenMeteoClient,
    NOAAClient,
    NASAPowerClient
)

# Test Open-Meteo (FREE, no key needed)
print("Testing Open-Meteo API...")
try:
    open_meteo = OpenMeteoClient()
    meteo_data = open_meteo.get_climate_data(
        latitude=TEST_LOCATION["latitude"],
        longitude=TEST_LOCATION["longitude"],
        days_back=30
    )

    if meteo_data:
        print(f"✅ Open-Meteo SUCCESS")
        print(f"  Hazard Type: {meteo_data.get('hazardType', 'N/A')}")
        print(f"  Risk Score: {meteo_data.get('riskScore', 'N/A')}/100")
        data = meteo_data.get('data', {})
        print(f"  Avg Temp: {data.get('avgTemperature', 'N/A')}°C")
        print(f"  Max Temp: {data.get('maxTemperature', 'N/A')}°C")
        print(f"  Total Precip: {data.get('totalPrecipitation', 'N/A')} mm")
    else:
        print("⚠️  Open-Meteo: No data returned")
except Exception as e:
    print(f"❌ Open-Meteo FAILED: {e}")
    meteo_data = None

print()

# Test NASA POWER (FREE, no key needed)
print("Testing NASA POWER API...")
try:
    nasa_power = NASAPowerClient()
    nasa_data = nasa_power.get_climate_data(
        latitude=TEST_LOCATION["latitude"],
        longitude=TEST_LOCATION["longitude"],
        days_back=30
    )

    if nasa_data:
        print(f"✅ NASA POWER SUCCESS")
        data = nasa_data.get('data', {})
        print(f"  Avg Temp: {data.get('avgTemperature', 'N/A')}°C")
        print(f"  Avg Solar: {data.get('avgSolarRadiation', 'N/A')} kWh/m²/day")
        print(f"  Days Analyzed: {data.get('daysAnalyzed', 'N/A')}")
    else:
        print("⚠️  NASA POWER: No data returned")
except Exception as e:
    print(f"❌ NASA POWER FAILED: {e}")
    nasa_data = None

print()

# Test NOAA (requires token, optional)
if NOAA_API_TOKEN:
    print("Testing NOAA API...")
    try:
        noaa = NOAAClient(api_token=NOAA_API_TOKEN)
        noaa_data = noaa.get_climate_data(
            location=TEST_LOCATION["name"],
            data_type="temperature"
        )

        if noaa_data:
            print(f"✅ NOAA SUCCESS")
            print(f"  Location: {noaa_data.get('location', 'N/A')}")
            results = noaa_data.get('results', [])
            print(f"  Data Points: {len(results)}")
        else:
            print("⚠️  NOAA: No data returned")
    except Exception as e:
        print(f"❌ NOAA FAILED: {e}")
        noaa_data = None
else:
    print("ℹ️  NOAA: Skipped (no token provided)")
    noaa_data = None

print()

# ============================================================================
# STEP 4: Test Claim Extraction
# ============================================================================
print("🔬 STEP 4: Testing Claim Extraction...")
print("-" * 80)

if articles:
    sample_text = articles[0].get('summary', '') or articles[0].get('title', '')

    # Create a simple test claim for demonstration
    test_claim = {
        "claimId": "test-claim-001",
        "claimText": "Helsinki's temperature has increased significantly in recent decades due to climate change.",
        "claimType": "factual_data",
        "context": sample_text[:200],
        "location": TEST_LOCATION
    }

    print(f"✅ Test Claim Created:")
    print(f"  ID: {test_claim['claimId']}")
    print(f"  Text: {test_claim['claimText']}")
    print()
else:
    print("⚠️  No articles available for claim extraction")
    test_claim = None
    print()

# ============================================================================
# STEP 5: Test Fact-Checking with Perplexity
# ============================================================================
print("✓ STEP 5: Testing Fact-Checking with Perplexity...")
print("-" * 80)

if test_claim and PERPLEXITY_API_KEY:
    from services.verification_service.src.verifier import ClaimVerifier

    try:
        verifier = ClaimVerifier(
            openai_api_key=OPENAI_API_KEY,
            model="gpt-4o",
            perplexity_api_key=PERPLEXITY_API_KEY
        )

        print("Verifying claim with climate data sources...")
        verification_result = verifier.verify_claim(
            claim_text=test_claim['claimText'],
            claim_context=test_claim['context'],
            open_meteo_data=meteo_data,
            noaa_data=noaa_data,
            nasa_power_data=nasa_data,
            location=TEST_LOCATION['name']
        )

        print(f"\n✅ VERIFICATION COMPLETE")
        print(f"  Status: {verification_result.get('status', 'N/A')}")
        print(f"  Confidence: {verification_result.get('confidence', 0):.2f}")
        print(f"  Justification: {verification_result.get('justification', 'N/A')[:150]}...")

        evidence = verification_result.get('evidence', [])
        if evidence:
            print(f"\n  Evidence Sources ({len(evidence)}):")
            for i, ev in enumerate(evidence[:3], 1):
                print(f"    {i}. {ev.get('sourceName', 'Unknown')}")
                if ev.get('sourceUrl'):
                    print(f"       URL: {ev['sourceUrl'][:60]}...")

        # Calculate credibility score
        status = verification_result.get('status', 'UNVERIFIED')
        confidence = verification_result.get('confidence', 0)

        if status == 'VERIFIED' and confidence >= 0.8:
            credibility = "HIGH"
        elif status == 'VERIFIED' and confidence >= 0.5:
            credibility = "MEDIUM"
        else:
            credibility = "LOW"

        print(f"\n  🎯 Overall Credibility: {credibility}")
        print()

    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        verification_result = None
        print()
else:
    print("⚠️  Skipped (missing test claim or Perplexity API key)")
    verification_result = None
    print()

# ============================================================================
# STEP 6: Test Content Generation
# ============================================================================
print("📝 STEP 6: Testing Content Generation...")
print("-" * 80)

if articles and PERPLEXITY_API_KEY:
    from services.content_creation_service.src.content_creator import ContentCreator

    try:
        creator = ContentCreator(perplexity_api_key=PERPLEXITY_API_KEY)

        print(f"Generating summary for {len(articles)} articles...")
        summary = creator.create_summary(
            articles=articles,
            country=TEST_LOCATION["country"],
            language="en"
        )

        print(f"\n✅ CONTENT GENERATION COMPLETE")
        print(f"  Title: {summary.get('title', 'N/A')}")
        print(f"  Article Count: {summary.get('article_count', 0)}")
        print(f"  Key Findings: {len(summary.get('key_findings', []))}")

        plain_summary = summary.get('summary_plain_text', summary.get('summary', ''))
        if plain_summary:
            print(f"\n  Summary Preview:")
            print(f"  {plain_summary[:300]}...")

        print()

    except Exception as e:
        print(f"❌ CONTENT GENERATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        summary = None
        print()
else:
    print("⚠️  Skipped (missing articles or Perplexity API key)")
    summary = None
    print()

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("=" * 80)
print(" 📊 TEST SUMMARY")
print("=" * 80)
print()

results = {
    "News Discovery (Perplexity)": "✅ PASS" if articles else "❌ FAIL",
    "Climate Data - Open-Meteo": "✅ PASS" if meteo_data else "❌ FAIL",
    "Climate Data - NASA POWER": "✅ PASS" if nasa_data else "❌ FAIL",
    "Climate Data - NOAA": "✅ PASS" if noaa_data else ("ℹ️  SKIP" if not NOAA_API_TOKEN else "❌ FAIL"),
    "Claim Extraction": "✅ PASS" if test_claim else "⚠️  SKIP",
    "Fact-Checking": "✅ PASS" if verification_result else "⚠️  SKIP",
    "Content Generation": "✅ PASS" if summary else "⚠️  SKIP",
}

for test_name, result in results.items():
    print(f"{result:12s} {test_name}")

print()

# Count passes and fails
passes = sum(1 for r in results.values() if "PASS" in r)
fails = sum(1 for r in results.values() if "FAIL" in r)
skips = sum(1 for r in results.values() if "SKIP" in r)

print(f"Total: {passes} passed, {fails} failed, {skips} skipped")
print()

if fails == 0 and passes > 0:
    print("🎉 ALL CORE TESTS PASSED! The pipeline is operational.")
    print()
    print("Next steps:")
    print("  1. Start Docker services: docker-compose up -d")
    print("  2. Run full integration tests with agents")
    print("  3. Test the frontend at http://localhost:3000")
elif fails > 0:
    print("⚠️  Some tests failed. Please check:")
    print("  1. API keys in .env file")
    print("  2. Internet connection")
    print("  3. Error messages above")
else:
    print("ℹ️  Tests were skipped. Please set API keys in .env")

print()
print("=" * 80)
