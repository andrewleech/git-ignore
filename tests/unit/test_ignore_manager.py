"""Unit tests for ignore_manager module."""

import os
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

from git_ignore.ignore_manager import (
    IgnoreError,
    PatternIssue,
    PatternSeverity,
    _sanitize_pattern,
    _validate_file_path,
    add_patterns_to_ignore_file,
    ensure_info_exclude_exists,
    read_ignore_patterns,
    validate_ignore_patterns,
    write_ignore_patterns,
)


class TestSanitizePattern:\n    \"\"\"Tests for _sanitize_pattern function.\"\"\"\n\n    def test_normal_pattern(self):\n        \"\"\"Test that normal patterns are unchanged.\"\"\"\n        assert _sanitize_pattern(\"*.pyc\") == \"*.pyc\"\n\n    def test_whitespace_stripped(self):\n        \"\"\"Test that whitespace is stripped.\"\"\"\n        assert _sanitize_pattern(\"  *.pyc  \") == \"*.pyc\"\n\n    def test_newlines_removed(self):\n        \"\"\"Test that newlines are removed.\"\"\"\n        assert _sanitize_pattern(\"*.pyc\\n\") == \"*.pyc\"\n        assert _sanitize_pattern(\"*.pyc\\r\\n\") == \"*.pyc\"\n        assert _sanitize_pattern(\"*.py\\nc\") == \"*.pyc\"\n\n    def test_empty_pattern(self):\n        \"\"\"Test that empty pattern returns empty string.\"\"\"\n        assert _sanitize_pattern(\"\") == \"\"\n        assert _sanitize_pattern(\"   \\n\\r   \") == \"\"\n\n\nclass TestValidateFilePath:\n    \"\"\"Tests for _validate_file_path function.\"\"\"\n\n    def test_valid_path(self, tmp_path):\n        \"\"\"Test that valid path passes validation.\"\"\"\n        file_path = tmp_path / \"gitignore\"\n        _validate_file_path(file_path)  # Should not raise\n\n    def test_path_within_base_dir(self, tmp_path):\n        \"\"\"Test that path within base directory is valid.\"\"\"\n        base_dir = tmp_path\n        file_path = tmp_path / \"subdir\" / \"gitignore\"\n        _validate_file_path(file_path, base_dir)  # Should not raise\n\n    def test_path_outside_base_dir(self, tmp_path):\n        \"\"\"Test that path outside base directory is rejected.\"\"\"\n        base_dir = tmp_path / \"restricted\"\n        file_path = tmp_path / \"outside\" / \"gitignore\"\n        \n        with pytest.raises(IgnoreError, match=\"outside allowed directory\"):\n            _validate_file_path(file_path, base_dir)\n\n    @patch(\"git_ignore.ignore_manager.Path.resolve\")\n    def test_resolution_error(self, mock_resolve):\n        \"\"\"Test error handling when path cannot be resolved.\"\"\"\n        mock_resolve.side_effect = OSError(\"Permission denied\")\n        \n        with pytest.raises(IgnoreError, match=\"Invalid file path\"):\n            _validate_file_path(Path(\"/invalid/path\"))\n\n\nclass TestReadIgnorePatterns:
    """Tests for read_ignore_patterns function."""

    def test_nonexistent_file(self):
        """Test reading from nonexistent file returns empty set."""
        result = read_ignore_patterns(Path("/nonexistent/file"))
        assert result == set()

    def test_empty_file(self, tmp_path):
        """Test reading from empty file returns empty set."""
        file_path = tmp_path / "empty"
        file_path.touch()

        result = read_ignore_patterns(file_path)
        assert result == set()

    def test_file_with_patterns(self, tmp_path):
        """Test reading patterns from file."""
        file_path = tmp_path / "gitignore"
        file_path.write_text("*.pyc\n__pycache__/\nbuild/\n")

        result = read_ignore_patterns(file_path)
        assert result == {"*.pyc", "__pycache__/", "build/"}

    def test_file_with_comments_and_empty_lines(self, tmp_path):
        """Test that comments and empty lines are ignored."""
        content = """# This is a comment
*.pyc
# Another comment

__pycache__/

build/
"""
        file_path = tmp_path / "gitignore"
        file_path.write_text(content)

        result = read_ignore_patterns(file_path)
        assert result == {"*.pyc", "__pycache__/", "build/"}

    def test_file_with_whitespace(self, tmp_path):
        """Test that leading/trailing whitespace is stripped."""
        content = "  *.pyc  \n\t__pycache__/\t\n   build/   \n"
        file_path = tmp_path / "gitignore"
        file_path.write_text(content)

        result = read_ignore_patterns(file_path)
        assert result == {"*.pyc", "__pycache__/", "build/"}

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_read_permission_error(self, mock_file_open):
        """Test error when file cannot be read."""
        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(IgnoreError, match="Failed to read ignore file"):
                read_ignore_patterns(Path("/restricted/file"))

    @patch("builtins.open", side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "invalid"))
    def test_unicode_decode_error(self, mock_file_open):
        """Test error when file contains invalid UTF-8."""
        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(IgnoreError, match="Failed to read ignore file"):
                read_ignore_patterns(Path("/binary/file"))


class TestWriteIgnorePatterns:
    """Tests for write_ignore_patterns function."""

    def test_write_empty_patterns(self, tmp_path):
        """Test that empty patterns list does nothing."""
        file_path = tmp_path / "gitignore"
        write_ignore_patterns(file_path, [])

        assert not file_path.exists()

    def test_write_patterns_new_file(self, tmp_path):
        """Test writing patterns to new file."""
        file_path = tmp_path / "gitignore"
        patterns = ["*.pyc", "__pycache__/", "build/"]

        write_ignore_patterns(file_path, patterns, append=False)

        content = file_path.read_text()
        assert content == "*.pyc\n__pycache__/\nbuild/\n"

    def test_write_patterns_create_parent_dirs(self, tmp_path):
        """Test that parent directories are created."""
        file_path = tmp_path / "nested" / "dir" / "gitignore"
        patterns = ["*.pyc"]

        write_ignore_patterns(file_path, patterns)

        assert file_path.exists()
        assert file_path.read_text() == "*.pyc\n"

    def test_append_to_existing_file_with_newline(self, tmp_path):
        """Test appending to file that ends with newline."""
        file_path = tmp_path / "gitignore"
        file_path.write_text("existing\n")

        write_ignore_patterns(file_path, ["new"], append=True)

        content = file_path.read_text()
        assert content == "existing\nnew\n"

    def test_append_to_existing_file_without_newline(self, tmp_path):
        """Test appending to file that doesn't end with newline."""
        file_path = tmp_path / "gitignore"
        file_path.write_text("existing")

        write_ignore_patterns(file_path, ["new"], append=True)

        content = file_path.read_text()
        assert content == "existing\nnew\n"

    def test_overwrite_existing_file(self, tmp_path):
        """Test overwriting existing file."""
        file_path = tmp_path / "gitignore"
        file_path.write_text("existing\n")

        write_ignore_patterns(file_path, ["new"], append=False)

        content = file_path.read_text()
        assert content == "new\n"

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_write_permission_error(self, mock_file_open):
        """Test error when file cannot be written."""
        with pytest.raises(IgnoreError, match="Failed to write to ignore file"):
            write_ignore_patterns(Path("/restricted/file"), ["pattern"])

    @patch("builtins.open", side_effect=UnicodeEncodeError("utf-8", "", 0, 1, "invalid"))
    def test_unicode_encode_error(self, mock_file_open):
        """Test error when pattern cannot be encoded."""
        with pytest.raises(IgnoreError, match="Failed to write to ignore file"):
            write_ignore_patterns(Path("/test/file"), ["pattern"])


class TestAddPatternsToIgnoreFile:
    """Tests for add_patterns_to_ignore_file function."""

    def test_empty_patterns(self, tmp_path):
        """Test that empty patterns list returns empty list."""
        file_path = tmp_path / "gitignore"
        result = add_patterns_to_ignore_file(file_path, [])
        assert result == []

    def test_add_patterns_to_new_file(self, tmp_path):
        """Test adding patterns to new file."""
        file_path = tmp_path / "gitignore"
        patterns = ["*.pyc", "__pycache__/"]

        result = add_patterns_to_ignore_file(file_path, patterns)

        assert result == ["*.pyc", "__pycache__/"]
        content = file_path.read_text()
        assert "*.pyc\n" in content
        assert "__pycache__/\n" in content

    def test_avoid_duplicates(self, tmp_path):
        """Test avoiding duplicate patterns."""
        file_path = tmp_path / "gitignore"
        file_path.write_text("*.pyc\nexisting\n")

        patterns = ["*.pyc", "__pycache__/", "existing"]
        result = add_patterns_to_ignore_file(file_path, patterns, avoid_duplicates=True)

        assert result == ["__pycache__/"]
        content = file_path.read_text()
        lines = content.strip().split("\n")
        assert lines.count("*.pyc") == 1
        assert lines.count("existing") == 1
        assert "__pycache__/" in lines

    def test_allow_duplicates(self, tmp_path):
        """Test allowing duplicate patterns."""
        file_path = tmp_path / "gitignore"
        file_path.write_text("*.pyc\n")

        patterns = ["*.pyc", "__pycache__/"]
        result = add_patterns_to_ignore_file(file_path, patterns, avoid_duplicates=False)

        assert result == ["*.pyc", "__pycache__/"]
        content = file_path.read_text()
        lines = content.strip().split("\n")
        assert lines.count("*.pyc") == 2

    def test_normalize_patterns(self, tmp_path):
        """Test that patterns are normalized (whitespace stripped)."""
        file_path = tmp_path / "gitignore"
        patterns = ["  *.pyc  ", "\t__pycache__/\t", "   ", ""]

        result = add_patterns_to_ignore_file(file_path, patterns)

        assert result == ["*.pyc", "__pycache__/"]

    @patch("git_ignore.ignore_manager.read_ignore_patterns")
    @patch("git_ignore.ignore_manager.write_ignore_patterns")
    def test_read_error_propagated(self, mock_write, mock_read):
        """Test that IgnoreError from read_ignore_patterns is propagated."""
        mock_read.side_effect = IgnoreError("read error")

        with pytest.raises(IgnoreError, match="read error"):
            add_patterns_to_ignore_file(Path("/test"), ["pattern"])

    @patch("git_ignore.ignore_manager.write_ignore_patterns")
    def test_write_error_propagated(self, mock_write):
        """Test that IgnoreError from write_ignore_patterns is propagated."""
        mock_write.side_effect = IgnoreError("write error")

        with pytest.raises(IgnoreError, match="write error"):
            add_patterns_to_ignore_file(Path("/test"), ["pattern"])


class TestValidateIgnorePatterns:
    """Tests for validate_ignore_patterns function."""

    def test_valid_patterns(self):
        """Test that valid patterns produce no issues."""
        patterns = ["*.pyc", "__pycache__/", "build", "*.log"]
        issues = validate_ignore_patterns(patterns)
        assert issues == []

    def test_newline_in_pattern(self):
        """Test error for patterns containing newlines."""
        patterns = ["*.pyc\n", "file\r\npattern"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 2
        assert all(issue.severity == PatternSeverity.ERROR for issue in issues)
        assert all("newline characters" in issue.message for issue in issues)

    def test_leading_and_trailing_slashes(self):
        """Test info for patterns with leading and trailing slashes."""
        patterns = ["/path/"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 1
        assert issues[0].severity == PatternSeverity.INFO
        assert "leading and trailing slashes" in issues[0].message

    def test_multiple_globstar(self):
        """Test warning for patterns with multiple **."""
        patterns = ["**/**/file"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 1
        assert issues[0].severity == PatternSeverity.WARNING
        assert "multiple '**'" in issues[0].message

    def test_redundant_dot_slash(self):
        """Test info for patterns starting with ./"""
        patterns = ["./file.txt"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 1
        assert issues[0].severity == PatternSeverity.INFO
        assert "starts with './'" in issues[0].message

    def test_dangerous_patterns(self):
        """Test warning for very broad patterns."""
        patterns = ["*", "**", "/"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 3
        for issue in issues:
            assert issue.severity == PatternSeverity.WARNING
            assert "very broad" in issue.message

    def test_important_files(self):
        """Test warning for patterns that might ignore important files."""
        patterns = [".git", ".gitignore", "README.md", "LICENSE"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 4
        for issue in issues:
            assert issue.severity == PatternSeverity.WARNING
            assert "important project files" in issue.message

    def test_empty_patterns_ignored(self):
        """Test that empty patterns are ignored during validation."""
        patterns = ["", "   ", "*.pyc"]
        issues = validate_ignore_patterns(patterns)
        assert issues == []

    def test_pattern_issue_structure(self):
        """Test that PatternIssue has correct structure."""
        patterns = ["/path/"]
        issues = validate_ignore_patterns(patterns)
        assert len(issues) == 1
        issue = issues[0]
        assert isinstance(issue, PatternIssue)
        assert issue.pattern == "/path/"
        assert issue.severity == PatternSeverity.INFO
        assert isinstance(issue.message, str)


class TestEnsureInfoExcludeExists:
    """Tests for ensure_info_exclude_exists function."""

    def test_create_new_exclude_file(self, tmp_path):
        """Test creating new exclude file with default content."""
        exclude_path = tmp_path / "info" / "exclude"

        ensure_info_exclude_exists(exclude_path)

        assert exclude_path.exists()
        content = exclude_path.read_text()
        assert "git ls-files --others --exclude-from" in content
        assert "Lines that start with '#' are comments" in content

    def test_create_parent_directory(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        exclude_path = tmp_path / "deep" / "nested" / "info" / "exclude"

        ensure_info_exclude_exists(exclude_path)

        assert exclude_path.parent.exists()
        assert exclude_path.exists()

    def test_existing_file_unchanged(self, tmp_path):
        """Test that existing exclude file is not modified."""
        exclude_path = tmp_path / "info" / "exclude"
        exclude_path.parent.mkdir(parents=True)
        exclude_path.write_text("existing content")

        ensure_info_exclude_exists(exclude_path)

        assert exclude_path.read_text() == "existing content"

    @patch("git_ignore.ignore_manager.Path.mkdir")
    def test_mkdir_error(self, mock_mkdir):
        """Test error when directory cannot be created."""
        mock_mkdir.side_effect = OSError("Permission denied")

        with pytest.raises(IgnoreError, match="Failed to initialize exclude file"):
            ensure_info_exclude_exists(Path("/restricted/info/exclude"))

    @patch("builtins.open", side_effect=OSError("Permission denied"))
    def test_file_creation_error(self, mock_file_open):
        """Test error when exclude file cannot be created."""
        exclude_path = Path("/test/info/exclude")

        with patch.object(Path, "exists", return_value=False), \
             patch.object(Path, "mkdir"):
            with pytest.raises(IgnoreError, match="Failed to initialize exclude file"):
                ensure_info_exclude_exists(exclude_path)