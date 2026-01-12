"""Tests for code analysis tools."""

from __future__ import annotations

import pytest


class TestAnalyzePythonCode:
    """Tests for Python code analysis."""

    def test_analyze_functions(self):
        """Test extracting functions from Python code."""
        from jarvis.tools.code_analysis import _analyze_python_code

        code = """
def foo():
    pass

async def bar():
    pass

def baz(x, y):
    return x + y
"""
        result = _analyze_python_code(code)
        assert "foo" in result.functions
        assert "bar" in result.functions
        assert "baz" in result.functions

    def test_analyze_classes(self):
        """Test extracting classes from Python code."""
        from jarvis.tools.code_analysis import _analyze_python_code

        code = """
class MyClass:
    pass

class AnotherClass(BaseClass):
    def method(self):
        pass
"""
        result = _analyze_python_code(code)
        assert "MyClass" in result.classes
        assert "AnotherClass" in result.classes

    def test_analyze_imports(self):
        """Test extracting imports from Python code."""
        from jarvis.tools.code_analysis import _analyze_python_code

        code = """
import os
import sys
from pathlib import Path
from typing import Optional, List
"""
        result = _analyze_python_code(code)
        assert "os" in result.imports
        assert "sys" in result.imports
        assert "pathlib:Path" in result.imports


class TestAnalyzeNonPythonCode:
    """Tests for non-Python code analysis."""

    def test_analyze_javascript_functions(self):
        """Test extracting functions from JavaScript code."""
        from jarvis.tools.code_analysis import _analyze_non_python_code

        code = """
function foo() {
    return 1;
}

const bar = () => {
    return 2;
};
"""
        result = _analyze_non_python_code(code)
        assert "foo" in result["functions"]

    def test_analyze_javascript_classes(self):
        """Test extracting classes from JavaScript code."""
        from jarvis.tools.code_analysis import _analyze_non_python_code

        code = """
class MyComponent {
    constructor() {}
}
"""
        result = _analyze_non_python_code(code)
        assert "MyComponent" in result["classes"]


@pytest.mark.asyncio
async def test_analyze_code_python_file(tmp_path):
    """Test analyzing a Python file."""
    from jarvis.tools.code_analysis import analyze_code

    file_path = tmp_path / "test.py"
    file_path.write_text("""
def hello():
    print("Hello")

class Greeter:
    pass
""")

    result = await analyze_code(str(file_path), confirm=True)
    assert "hello" in result
    assert "Greeter" in result


@pytest.mark.asyncio
async def test_analyze_code_not_found(tmp_path):
    """Test analyzing non-existent file."""
    from jarvis.tools.code_analysis import analyze_code

    result = await analyze_code(str(tmp_path / "nonexistent.py"), confirm=True)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_analyze_code_directory(tmp_path):
    """Test analyzing a directory (should fail)."""
    from jarvis.tools.code_analysis import analyze_code

    result = await analyze_code(str(tmp_path), confirm=True)
    assert "not found" in result.lower() or "directory" in result.lower()


@pytest.mark.asyncio
async def test_get_project_structure(tmp_path):
    """Test getting project structure."""
    from jarvis.tools.code_analysis import get_project_structure

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("main")
    (tmp_path / "src" / "utils.py").write_text("utils")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("test")
    (tmp_path / "README.md").write_text("readme")

    result = await get_project_structure(str(tmp_path), confirm=True)
    assert "src/" in result
    assert "main.py" in result
    assert "tests/" in result
    assert "README.md" in result


@pytest.mark.asyncio
async def test_get_project_structure_empty(tmp_path):
    """Test getting structure of empty directory."""
    from jarvis.tools.code_analysis import get_project_structure

    result = await get_project_structure(str(tmp_path), confirm=True)
    assert "no files" in result.lower()


@pytest.mark.asyncio
async def test_get_project_structure_invalid(tmp_path):
    """Test getting structure of invalid directory."""
    from jarvis.tools.code_analysis import get_project_structure

    result = await get_project_structure(str(tmp_path / "nonexistent"), confirm=True)
    assert "invalid" in result.lower()


@pytest.mark.asyncio
async def test_count_lines(tmp_path):
    """Test counting lines of code."""
    from jarvis.tools.code_analysis import count_lines

    (tmp_path / "file1.py").write_text("line1\nline2\nline3")
    (tmp_path / "file2.py").write_text("line1\nline2")
    (tmp_path / "file3.js").write_text("line1")

    result = await count_lines(str(tmp_path), confirm=True)
    assert "total lines:" in result.lower()
    assert ".py" in result
    assert ".js" in result


@pytest.mark.asyncio
async def test_count_lines_invalid_directory(tmp_path):
    """Test counting lines in invalid directory."""
    from jarvis.tools.code_analysis import count_lines

    result = await count_lines(str(tmp_path / "nonexistent"), confirm=True)
    assert "invalid" in result.lower()


@pytest.mark.asyncio
async def test_find_todos(tmp_path):
    """Test finding TODO comments."""
    from jarvis.tools.code_analysis import find_todos

    (tmp_path / "file1.py").write_text("# TODO: implement this\ncode")
    (tmp_path / "file2.py").write_text("# FIXME: fix this bug\ncode")
    (tmp_path / "file3.py").write_text("# HACK: temporary workaround\ncode")
    (tmp_path / "file4.py").write_text("# Just a comment\ncode")

    result = await find_todos(str(tmp_path), confirm=True)
    assert "TODO" in result
    assert "FIXME" in result
    assert "HACK" in result
    assert "file4.py" not in result


@pytest.mark.asyncio
async def test_find_todos_none(tmp_path):
    """Test finding TODOs when none exist."""
    from jarvis.tools.code_analysis import find_todos

    (tmp_path / "clean.py").write_text("# No todos here\ncode")

    result = await find_todos(str(tmp_path), confirm=True)
    assert "no todo" in result.lower()


@pytest.mark.asyncio
async def test_find_todos_limit(tmp_path):
    """Test that find_todos respects limit."""
    from jarvis.tools.code_analysis import find_todos

    content = "\n".join([f"# TODO: item {i}" for i in range(20)])
    (tmp_path / "many_todos.py").write_text(content)

    result = await find_todos(str(tmp_path), limit=5, confirm=True)
    todo_lines = [l for l in result.split("\n") if "TODO" in l]
    assert len(todo_lines) == 5


@pytest.mark.asyncio
async def test_diff_files(tmp_path):
    """Test diffing two files."""
    from jarvis.tools.code_analysis import diff_files

    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("line1\nline2\nline3")
    file_b.write_text("line1\nmodified\nline3")

    result = await diff_files(str(file_a), str(file_b), confirm=True)
    assert "-line2" in result
    assert "+modified" in result


@pytest.mark.asyncio
async def test_diff_files_identical(tmp_path):
    """Test diffing identical files."""
    from jarvis.tools.code_analysis import diff_files

    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("same content")
    file_b.write_text("same content")

    result = await diff_files(str(file_a), str(file_b), confirm=True)
    assert "identical" in result.lower()


@pytest.mark.asyncio
async def test_diff_files_not_found(tmp_path):
    """Test diffing with non-existent file."""
    from jarvis.tools.code_analysis import diff_files

    file_a = tmp_path / "a.txt"
    file_a.write_text("content")

    result = await diff_files(str(file_a), str(tmp_path / "nonexistent.txt"), confirm=True)
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_get_code_analysis_tools():
    """Test that get_code_analysis_tools returns all tools."""
    from jarvis.tools.code_analysis import get_code_analysis_tools

    tools = get_code_analysis_tools()
    tool_names = [t.__name__ for t in tools]

    assert "analyze_code" in tool_names
    assert "get_project_structure" in tool_names
    assert "count_lines" in tool_names
    assert "find_todos" in tool_names
    assert "diff_files" in tool_names
    assert "explain_code" in tool_names
