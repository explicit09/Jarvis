"""Tests for file operation tools."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_files(tmp_path):
    """Test listing files."""
    from jarvis.tools.files import list_files

    # Create test files
    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.py").write_text("content2")
    (tmp_path / "subdir").mkdir()

    result = await list_files(str(tmp_path), confirm=True)
    assert "file1.txt" in result
    assert "file2.py" in result
    assert "subdir/" in result


@pytest.mark.asyncio
async def test_list_files_with_pattern(tmp_path):
    """Test listing files with glob pattern."""
    from jarvis.tools.files import list_files

    (tmp_path / "file1.txt").write_text("content1")
    (tmp_path / "file2.py").write_text("content2")
    (tmp_path / "file3.txt").write_text("content3")

    result = await list_files(str(tmp_path), pattern="*.txt", confirm=True)
    assert "file1.txt" in result
    assert "file3.txt" in result
    assert "file2.py" not in result


@pytest.mark.asyncio
async def test_list_files_limit(tmp_path):
    """Test that list_files respects limit."""
    from jarvis.tools.files import list_files

    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text(f"content{i}")

    result = await list_files(str(tmp_path), limit=3, confirm=True)
    lines = [l for l in result.split("\n") if l.strip() and l.strip().endswith(".txt")]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_list_files_not_found(tmp_path):
    """Test listing files in non-existent path."""
    from jarvis.tools.files import list_files

    result = await list_files(str(tmp_path / "nonexistent"), confirm=True)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_list_files_not_directory(tmp_path):
    """Test listing files on a file (not directory)."""
    from jarvis.tools.files import list_files

    file_path = tmp_path / "file.txt"
    file_path.write_text("content")

    result = await list_files(str(file_path), confirm=True)
    assert "not a directory" in result.lower()


@pytest.mark.asyncio
async def test_read_file(tmp_path):
    """Test reading a file."""
    from jarvis.tools.files import read_file

    file_path = tmp_path / "test.txt"
    file_path.write_text("Hello, World!")

    result = await read_file(str(file_path), confirm=True)
    assert result == "Hello, World!"


@pytest.mark.asyncio
async def test_read_file_truncation(tmp_path):
    """Test that large files are truncated."""
    from jarvis.tools.files import read_file

    file_path = tmp_path / "large.txt"
    file_path.write_text("A" * 10000)

    result = await read_file(str(file_path), max_chars=100, confirm=True)
    assert len(result) < 200  # 100 chars + truncation message
    assert "truncated" in result.lower()


@pytest.mark.asyncio
async def test_read_file_not_found(tmp_path):
    """Test reading non-existent file."""
    from jarvis.tools.files import read_file

    result = await read_file(str(tmp_path / "nonexistent.txt"), confirm=True)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_read_file_is_directory(tmp_path):
    """Test reading a directory (should fail)."""
    from jarvis.tools.files import read_file

    result = await read_file(str(tmp_path), confirm=True)
    assert "directory" in result.lower()


@pytest.mark.asyncio
async def test_write_file(tmp_path):
    """Test writing a file."""
    from jarvis.tools.files import write_file

    file_path = tmp_path / "output.txt"
    result = await write_file(str(file_path), "Test content", confirm=True)

    assert "wrote" in result.lower()
    assert file_path.read_text() == "Test content"


@pytest.mark.asyncio
async def test_write_file_creates_directories(tmp_path):
    """Test that write_file creates parent directories."""
    from jarvis.tools.files import write_file

    file_path = tmp_path / "subdir" / "nested" / "file.txt"
    result = await write_file(str(file_path), "Nested content", confirm=True)

    assert "wrote" in result.lower()
    assert file_path.exists()
    assert file_path.read_text() == "Nested content"


@pytest.mark.asyncio
async def test_write_file_no_overwrite(tmp_path):
    """Test write_file with overwrite=False."""
    from jarvis.tools.files import write_file

    file_path = tmp_path / "existing.txt"
    file_path.write_text("Original")

    result = await write_file(str(file_path), "New content", overwrite=False, confirm=True)
    assert "already exists" in result.lower()
    assert file_path.read_text() == "Original"


@pytest.mark.asyncio
async def test_search_files(tmp_path):
    """Test searching files."""
    from jarvis.tools.files import search_files

    (tmp_path / "file1.txt").write_text("Hello world")
    (tmp_path / "file2.txt").write_text("Goodbye world")
    (tmp_path / "file3.txt").write_text("No match here")

    result = await search_files("world", str(tmp_path), confirm=True)
    assert "file1.txt" in result
    assert "file2.txt" in result
    assert "file3.txt" not in result


@pytest.mark.asyncio
async def test_search_files_limit(tmp_path):
    """Test that search_files respects limit."""
    from jarvis.tools.files import search_files

    for i in range(10):
        (tmp_path / f"file{i}.txt").write_text(f"match {i}")

    result = await search_files("match", str(tmp_path), limit=3, confirm=True)
    lines = [l for l in result.split("\n") if l.strip() and ".txt" in l]
    assert len(lines) == 3


@pytest.mark.asyncio
async def test_search_files_no_matches(tmp_path):
    """Test search with no matches."""
    from jarvis.tools.files import search_files

    (tmp_path / "file.txt").write_text("Hello world")

    result = await search_files("nonexistent", str(tmp_path), confirm=True)
    assert "no matches" in result.lower()


@pytest.mark.asyncio
async def test_search_files_invalid_directory(tmp_path):
    """Test search in invalid directory."""
    from jarvis.tools.files import search_files

    result = await search_files("query", str(tmp_path / "nonexistent"), confirm=True)
    assert "invalid" in result.lower()


@pytest.mark.asyncio
async def test_get_file_tools():
    """Test that get_file_tools returns all tools."""
    from jarvis.tools.files import get_file_tools

    tools = get_file_tools()
    tool_names = [t.__name__ for t in tools]

    assert "list_files" in tool_names
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "search_files" in tool_names
