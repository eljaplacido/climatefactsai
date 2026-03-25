"""
DeepEval test fixtures and golden dataset loaders.

Usage:
    pytest tests/evaluation/ -m evaluation --no-header
"""

import json
import os
from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).parent / "golden_datasets"


@pytest.fixture
def claims_golden_dataset():
    """Load golden dataset for claim extraction evaluation."""
    path = GOLDEN_DIR / "claims_golden.json"
    if not path.exists():
        pytest.skip("Golden dataset not found: claims_golden.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def verdicts_golden_dataset():
    """Load golden dataset for verdict adjudication evaluation."""
    path = GOLDEN_DIR / "verdicts_golden.json"
    if not path.exists():
        pytest.skip("Golden dataset not found: verdicts_golden.json")
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def anthropic_api_key():
    """Ensure Anthropic API key is available."""
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture
def openai_api_key():
    """Ensure OpenAI API key is available (required by DeepEval)."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        pytest.skip("OPENAI_API_KEY not set (required by DeepEval)")
    return key
