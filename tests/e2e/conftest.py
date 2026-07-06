"""E2E test fixtures."""
import pytest


@pytest.fixture
def base_url():
    """Frontend dev server URL."""
    return 'http://localhost:5173'
