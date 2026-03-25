"""
Standalone test runner for refactor unit tests.

Runs tests without depending on the old Kafka-based conftest.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root / "src" / "backend"))

# Run tests manually
if __name__ == "__main__":
    import pytest

    # Run with minimal plugins to avoid conftest issues
    sys.exit(
        pytest.main([
            str(Path(__file__).parent),
            "-v",
            "--tb=short",
            "-p", "no:cacheprovider",  # Disable cache
            "--ignore=conftest.py",  # Ignore old conftest
        ])
    )
