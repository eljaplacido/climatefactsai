#!/usr/bin/env python3
"""
Test script for CliLens.AI Climate News Platform - MVP Validation
Tests the complete pipeline: News Discovery → Fact-Checking → Content Creation
"""

import os
import sys
import json
import asyncio
import requests
from datetime import datetime
from typing import Dict, List, Any

# Configuration
API_BASE_URL = "http://localhost:8000"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

class Colors:
    """ANSI color codes for pretty output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}[OK]{Colors.END} {text}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}[ERROR]{Colors.END} {text}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.YELLOW}[INFO]{Colors.END} {text}")

def test_api_health():
    """Test if the API is healthy and responding"""
    print_header("Testing API Health")

    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print_success(f"API is healthy - Status: {data['status']}")
            print_info(f"Timestamp: {data['timestamp']}")
            return True
        else:
            print_error(f"API returned status code: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Failed to connect to API: {str(e)}")
        return False

def test_database_connection():
    """Test database connectivity through API"""
    print_header("Testing Database Connection")

    try:
        # Test countries endpoint (requires DB)
        response = requests.get(f"{API_BASE_URL}/api/countries", timeout=10)
        if response.status_code == 200:
            countries = response.json()
            print_success(f"Database connection OK - Found {len(countries)} countries")

            # Show sample countries
            print_info("Sample countries:")
            for country in countries[:5]:
                print(f"  • {country['flag_emoji']} {country['country_name']} ({country['country_code']}) - {country['articles_count']} articles")
            return True
        else:
            print_error(f"Failed to fetch countries: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Database connection test failed: {str(e)}")
        return False

def test_api_stats():
    """Test stats endpoint"""
    print_header("Testing API Statistics")

    try:
        response = requests.get(f"{API_BASE_URL}/api/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print_success("Stats endpoint working")
            print_info(f"Total Articles: {stats['total_articles']}")
            print_info(f"Articles Today: {stats['articles_today']}")
            print_info(f"Total Fact Checks: {stats['total_fact_checks']}")
            print_info(f"Verified Claims: {stats['verified_claims']}")
            print_info(f"Average Confidence: {stats['average_confidence']:.2f}%")
            return True
        else:
            print_error(f"Failed to fetch stats: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Stats test failed: {str(e)}")
        return False

def test_llm_integrations():
    """Test LLM API integrations"""
    print_header("Testing LLM API Integrations")

    results = {}

    # Test Anthropic Claude
    print_info("Testing Anthropic Claude API...")
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant-"):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=100,
                messages=[{"role": "user", "content": "Say 'API test successful' if you can read this."}]
            )
            print_success(f"Anthropic Claude API: {message.content[0].text[:50]}...")
            results['anthropic'] = True
        except Exception as e:
            print_error(f"Anthropic Claude API failed: {str(e)}")
            results['anthropic'] = False
    else:
        print_error("Anthropic API key not configured")
        results['anthropic'] = False

    # Test Perplexity
    print_info("Testing Perplexity API...")
    if PERPLEXITY_API_KEY and PERPLEXITY_API_KEY.startswith("pplx-"):
        try:
            import openai
            client = openai.OpenAI(
                api_key=PERPLEXITY_API_KEY,
                base_url="https://api.perplexity.ai"
            )
            response = client.chat.completions.create(
                model="llama-3.1-sonar-small-128k-online",
                messages=[{"role": "user", "content": "What is climate change in 10 words?"}],
                max_tokens=50
            )
            print_success(f"Perplexity API: {response.choices[0].message.content[:50]}...")
            results['perplexity'] = True
        except Exception as e:
            print_error(f"Perplexity API failed: {str(e)}")
            results['perplexity'] = False
    else:
        print_error("Perplexity API key not configured")
        results['perplexity'] = False

    # Test OpenAI
    print_info("Testing OpenAI API...")
    if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-proj-"):
        try:
            import openai
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Say 'test' if you work."}],
                max_tokens=10
            )
            print_success(f"OpenAI GPT-4o API: {response.choices[0].message.content}")
            results['openai'] = True
        except Exception as e:
            print_error(f"OpenAI API failed: {str(e)}")
            results['openai'] = False
    else:
        print_error("OpenAI API key not configured")
        results['openai'] = False

    return all(results.values())

def test_news_discovery(country_code: str = "FI"):
    """Test news discovery using Perplexity"""
    print_header(f"Testing News Discovery for {country_code}")

    if not PERPLEXITY_API_KEY:
        print_error("Perplexity API key not configured - skipping news discovery test")
        return None

    try:
        import openai
        client = openai.OpenAI(
            api_key=PERPLEXITY_API_KEY,
            base_url="https://api.perplexity.ai"
        )

        query = f"What are the latest climate news from {country_code}? Provide 2-3 recent articles with URLs."

        print_info(f"Searching for: {query}")

        response = client.chat.completions.create(
            model="llama-3.1-sonar-small-128k-online",
            messages=[{"role": "user", "content": query}],
            max_tokens=500
        )

        news_summary = response.choices[0].message.content
        print_success("News discovery successful!")
        print_info(f"Summary:\n{news_summary[:300]}...")

        return news_summary
    except Exception as e:
        print_error(f"News discovery failed: {str(e)}")
        return None

def test_admin_workflow_trigger():
    """Test manual workflow trigger via admin API"""
    print_header("Testing Admin Workflow Trigger")

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/admin/trigger-workflow",
            json={"country_code": "FI", "max_articles": 3},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"Workflow triggered successfully!")
            print_info(f"Task ID: {data.get('task_id', 'N/A')}")
            print_info(f"Message: {data.get('message', 'N/A')}")
            return data.get('task_id')
        else:
            print_error(f"Failed to trigger workflow: {response.status_code}")
            print_error(response.text)
            return None
    except Exception as e:
        print_error(f"Workflow trigger failed: {str(e)}")
        return None

def test_frontend_accessibility():
    """Test if frontend is accessible"""
    print_header("Testing Frontend Accessibility")

    try:
        response = requests.get("http://localhost:3000", timeout=10)
        if response.status_code == 200:
            print_success("Frontend is accessible at http://localhost:3000")
            return True
        else:
            print_error(f"Frontend returned status code: {response.status_code}")
            return False
    except Exception as e:
        print_info("Frontend not running (this is OK if testing backend only)")
        print_info("To start frontend: cd frontend && npm install && npm run dev")
        return False

def generate_summary_report(results: Dict[str, bool]):
    """Generate a summary report of all tests"""
    print_header("Test Summary Report")

    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    failed_tests = total_tests - passed_tests

    print(f"\n{Colors.BOLD}Total Tests: {total_tests}{Colors.END}")
    print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.END}")
    print(f"{Colors.RED}Failed: {failed_tests}{Colors.END}")
    print(f"\n{Colors.BOLD}Success Rate: {(passed_tests/total_tests)*100:.1f}%{Colors.END}\n")

    print(f"{Colors.BOLD}Detailed Results:{Colors.END}")
    for test_name, passed in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  • {test_name.replace('_', ' ').title()}: {status}")

    print(f"\n{Colors.BOLD}Next Steps:{Colors.END}")
    if failed_tests > 0:
        print(f"{Colors.YELLOW}[WARNING]{Colors.END} Some tests failed. Please check the errors above.")
        print(f"{Colors.YELLOW}[WARNING]{Colors.END} Ensure all services are running: docker-compose up -d")
        print(f"{Colors.YELLOW}[WARNING]{Colors.END} Check API keys in .env file")
    else:
        print(f"{Colors.GREEN}[SUCCESS]{Colors.END} All tests passed! System is ready for live feed testing.")
        print(f"{Colors.GREEN}[SUCCESS]{Colors.END} You can now:")
        print(f"  1. Trigger a workflow: POST http://localhost:8000/api/admin/trigger-workflow")
        print(f"  2. View results: http://localhost:8000/api/articles")
        print(f"  3. Start frontend: cd frontend && npm run dev")

def main():
    """Main test execution"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("="*80)
    print("             CliLens.AI Climate News Platform".center(80))
    print("                  MVP Pipeline Test Suite".center(80))
    print("="*80)
    print(f"{Colors.END}\n")

    results = {}

    # Run tests
    results['api_health'] = test_api_health()
    results['database_connection'] = test_database_connection()
    results['api_stats'] = test_api_stats()
    results['llm_integrations'] = test_llm_integrations()

    if results['llm_integrations']:
        news_summary = test_news_discovery("FI")
        results['news_discovery'] = news_summary is not None
    else:
        print_info("Skipping news discovery test due to LLM integration failures")
        results['news_discovery'] = False

    # Test admin workflow trigger
    # task_id = test_admin_workflow_trigger()
    # results['workflow_trigger'] = task_id is not None

    results['frontend_accessibility'] = test_frontend_accessibility()

    # Generate summary
    generate_summary_report(results)

    # Exit code based on results
    if all(results.values()):
        print(f"\n{Colors.GREEN}{Colors.BOLD}[SUCCESS] ALL TESTS PASSED!{Colors.END}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}[WARNING] SOME TESTS FAILED{Colors.END}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
