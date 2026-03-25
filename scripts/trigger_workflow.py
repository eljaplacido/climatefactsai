"""
Simple script to trigger a manual workflow via the API.
This will kick off the content discovery -> fact checking -> content creation pipeline.
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000"

def trigger_workflow():
    """Trigger a manual workflow execution"""
    print("Triggering manual workflow...")

    try:
        response = requests.post(
            f"{API_BASE_URL}/api/admin/trigger-workflow",
            json={"task_id": None},  # Auto-generate task ID
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Workflow triggered successfully!")
            print(f"  Task ID: {data.get('task_id')}")
            print(f"  Status: {data.get('status')}")
            print(f"  Message: {data.get('message')}")
            return data.get('task_id')
        else:
            print(f"✗ Failed to trigger workflow: {response.status_code}")
            print(f"  Response: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to API. Make sure services are running.")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def check_workflow_status(task_id):
    """Check the status of a workflow"""
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/admin/workflows",
            params={"limit": 10},
            timeout=10
        )

        if response.status_code == 200:
            workflows = response.json()
            for wf in workflows:
                if wf.get('task_id') == task_id:
                    print(f"\nWorkflow Status for {task_id}:")
                    print(f"  Status: {wf.get('status')}")
                    print(f"  Current Stage: {wf.get('current_stage')}")
                    print(f"  Started: {wf.get('started_at')}")
                    return wf
            print(f"Workflow {task_id} not found in recent workflows")
            return None
        else:
            print(f"Failed to get workflow status: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error checking workflow status: {e}")
        return None


def get_stats():
    """Get current API stats"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/stats", timeout=10)

        if response.status_code == 200:
            stats = response.json()
            print("\n=== Current Stats ===")
            print(f"Total Articles: {stats.get('total_articles')}")
            print(f"Articles Today: {stats.get('articles_today')}")
            print(f"Total Fact Checks: {stats.get('total_fact_checks')}")
            print(f"Verified Claims: {stats.get('verified_claims')}")
            print(f"Average Confidence: {stats.get('average_confidence'):.2f}%")
            print(f"Last Updated: {stats.get('last_updated')}")
            return stats
        else:
            print(f"Failed to get stats: {response.status_code}")
            return None

    except Exception as e:
        print(f"Error getting stats: {e}")
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("Climate News MVP - Workflow Trigger")
    print("=" * 60)
    print()

    # Check current stats
    print("Checking current stats...")
    get_stats()

    print("\n" + "=" * 60)
    input("Press Enter to trigger a new workflow...")

    # Trigger workflow
    task_id = trigger_workflow()

    if task_id:
        print("\nWorkflow triggered! The pipeline will:")
        print("1. Discover climate news articles from configured sources")
        print("2. Extract claims from articles")
        print("3. Verify claims against climate data sources")
        print("4. Create content summaries")
        print("\nThis may take several minutes...")

        # Wait and check status
        print("\nWaiting 30 seconds before checking status...")
        time.sleep(30)

        check_workflow_status(task_id)

        print("\nYou can check the workflow logs using:")
        print(f"  docker-compose logs -f orchestration-service")
        print(f"  docker-compose logs -f ingestion-service")
        print(f"  docker-compose logs -f verification-service")

        print("\nOnce complete, check updated stats:")
        time.sleep(5)
        get_stats()
