"""Pytest fixtures for J.A.R.V.I.S tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def isolate_test_db(tmp_path: Path):
    """Use a temporary database for each test."""
    test_db_dir = tmp_path / "jarvis_test"
    test_db_dir.mkdir(parents=True, exist_ok=True)

    # Patch the config to use temp directory
    with patch("jarvis.config.config.storage.data_dir", test_db_dir):
        # Also need to reset the cached connection
        import jarvis.storage as storage_module
        original_get_db_path = storage_module.get_db_path

        def test_get_db_path() -> Path:
            return test_db_dir / "jarvis.db"

        with patch.object(storage_module, "get_db_path", test_get_db_path):
            yield test_db_dir


@pytest.fixture
def sample_memory_data():
    """Sample memory data for tests."""
    return [
        {"content": "User prefers dark mode", "tags": "preferences", "importance": 3},
        {"content": "Meeting with John on Monday", "tags": "meetings,work", "importance": 2},
        {"content": "Favorite color is blue", "tags": "preferences", "importance": 1},
    ]


@pytest.fixture
def sample_note_data():
    """Sample note data for tests."""
    return [
        {"title": "Shopping List", "content": "Milk, bread, eggs"},
        {"title": "Project Ideas", "content": "Build a voice assistant"},
        {"title": "Meeting Notes", "content": "Discussed Q4 goals"},
    ]


@pytest.fixture
def sample_task_data():
    """Sample task data for tests."""
    return [
        {"content": "Review pull request", "due_date": "2025-01-15", "priority": "high"},
        {"content": "Update documentation", "due_date": "", "priority": "normal"},
        {"content": "Fix bug #123", "due_date": "2025-01-10", "priority": "urgent"},
    ]
