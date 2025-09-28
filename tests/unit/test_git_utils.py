"""Unit tests for git_utils module."""

import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from git_ignore.git_utils import (
    GitError,
    _run_git_command,
    _validate_git_path,
    get_exclude_file_path,
    get_git_dir,
    get_gitignore_path,
    get_global_gitignore_path,
    get_repo_root,
)


class TestRunGitCommand:
    """Tests for _run_git_command function."""

    @patch("git_ignore.git_utils.subprocess.run")
    def test_success(self, mock_run):
        """Test successful git command execution."""
        mock_run.return_value = Mock(stdout="/path/to/repo\n")

        result = _run_git_command(["git", "rev-parse", "--show-toplevel"])

        assert result == "/path/to/repo"
        mock_run.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0,
        )

    @patch("git_ignore.git_utils.subprocess.run")
    def test_custom_timeout(self, mock_run):
        """Test git command with custom timeout."""
        mock_run.return_value = Mock(stdout="output\n")

        _run_git_command(["git", "status"], timeout=10.0)

        mock_run.assert_called_once_with(
            ["git", "status"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,
        )

    @patch("git_ignore.git_utils.subprocess.run")
    def test_empty_output(self, mock_run):
        """Test error when git returns empty output."""
        mock_run.return_value = Mock(stdout="\n")

        with pytest.raises(GitError, match="Git command returned empty output"):
            _run_git_command(["git", "rev-parse", "--absolute-git-dir"])

    @patch("git_ignore.git_utils.subprocess.run")
    @patch("git_ignore.git_utils.Path.cwd")
    def test_called_process_error(self, mock_cwd, mock_run):
        """Test error when git command fails."""
        mock_cwd.return_value = Path("/current/directory")
        mock_run.side_effect = subprocess.CalledProcessError(
            128, ["git"], stderr="fatal: not a git repository"
        )

        with pytest.raises(
            GitError, match=r"Not in a git repository \(cwd: /current/directory\)"
        ):
            _run_git_command(["git", "rev-parse", "--absolute-git-dir"])

    @patch("git_ignore.git_utils.subprocess.run")
    def test_timeout_error(self, mock_run):
        """Test error when git command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired(["git", "status"], 5.0)

        with pytest.raises(GitError, match="Git command timed out"):
            _run_git_command(["git", "status"])

    @patch("git_ignore.git_utils.subprocess.run")
    def test_file_not_found(self, mock_run):
        """Test error when git command not found."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(GitError, match="Git command not found"):
            _run_git_command(["git", "status"])


class TestValidateGitPath:
    """Tests for _validate_git_path function."""

    def test_valid_absolute_path(self, tmp_path):
        """Test validation of valid absolute path."""
        test_path = tmp_path / "test"
        test_path.mkdir()

        result = _validate_git_path(test_path)

        assert result.is_absolute()
        assert result.exists()

    def test_relative_path_resolution(self, tmp_path, monkeypatch):
        """Test validation resolves relative paths."""
        test_dir = tmp_path / "subdir"
        test_dir.mkdir()
        monkeypatch.chdir(tmp_path)

        relative_path = Path("subdir")
        result = _validate_git_path(relative_path)

        assert result.is_absolute()
        assert result == test_dir

    @patch("git_ignore.git_utils.Path.resolve")
    def test_resolution_error(self, mock_resolve):
        """Test error handling when path resolution fails."""
        mock_resolve.side_effect = OSError("Permission denied")

        with pytest.raises(GitError, match="Invalid path returned by git"):
            _validate_git_path(Path("/invalid/path"))


class TestGetGitDir:
    """Tests for get_git_dir function."""

    @patch("git_ignore.git_utils._validate_git_path")
    @patch("git_ignore.git_utils._run_git_command")
    def test_success(self, mock_run_command, mock_validate):
        """Test successful git directory detection."""
        mock_run_command.return_value = "/path/to/.git"
        mock_validate.return_value = Path("/path/to/.git")

        result = get_git_dir()

        assert result == Path("/path/to/.git")
        mock_run_command.assert_called_once_with(
            ["git", "rev-parse", "--absolute-git-dir"]
        )
        mock_validate.assert_called_once_with(Path("/path/to/.git"))

    @patch("git_ignore.git_utils._run_git_command")
    def test_git_error_propagated(self, mock_run_command):
        """Test that GitError from _run_git_command is propagated."""
        # Clear any cached values first
        get_git_dir.cache_clear()

        mock_run_command.side_effect = GitError("test error")

        with pytest.raises(GitError, match="test error"):
            get_git_dir()

    @patch("git_ignore.git_utils._run_git_command")
    def test_caching(self, mock_run_command):
        """Test that get_git_dir caches results."""
        mock_run_command.return_value = "/path/to/.git"

        # Clear cache first
        get_git_dir.cache_clear()

        # Call twice
        result1 = get_git_dir()
        result2 = get_git_dir()

        assert result1 == result2
        # Should only be called once due to caching
        mock_run_command.assert_called_once()


class TestGetRepoRoot:
    """Tests for get_repo_root function."""

    @patch("git_ignore.git_utils._validate_git_path")
    @patch("git_ignore.git_utils._run_git_command")
    def test_success(self, mock_run_command, mock_validate):
        """Test successful repo root detection."""
        mock_run_command.return_value = "/path/to/repo"
        mock_validate.return_value = Path("/path/to/repo")

        result = get_repo_root()

        assert result == Path("/path/to/repo")
        mock_run_command.assert_called_once_with(
            ["git", "rev-parse", "--show-toplevel"]
        )
        mock_validate.assert_called_once_with(Path("/path/to/repo"))

    @patch("git_ignore.git_utils._run_git_command")
    def test_git_error_propagated(self, mock_run_command):
        """Test that GitError from _run_git_command is propagated."""
        # Clear any cached values first
        get_repo_root.cache_clear()

        mock_run_command.side_effect = GitError("test error")

        with pytest.raises(GitError, match="test error"):
            get_repo_root()

    @patch("git_ignore.git_utils._run_git_command")
    def test_caching(self, mock_run_command):
        """Test that get_repo_root caches results."""
        mock_run_command.return_value = "/path/to/repo"

        # Clear cache first
        get_repo_root.cache_clear()

        # Call twice
        result1 = get_repo_root()
        result2 = get_repo_root()

        assert result1 == result2
        # Should only be called once due to caching
        mock_run_command.assert_called_once()


class TestGetGlobalGitignorePath:
    """Tests for get_global_gitignore_path function."""

    @patch("git_ignore.git_utils.subprocess.run")
    def test_configured_path(self, mock_run):
        """Test with configured global gitignore path."""
        mock_run.return_value = Mock(stdout="~/.gitignore_global\n")

        with patch.object(Path, "expanduser") as mock_expanduser:
            mock_expanduser.return_value = Path("/home/user/.gitignore_global")

            result = get_global_gitignore_path()

            assert result == Path("/home/user/.gitignore_global")
            mock_expanduser.assert_called_once()

    @patch("git_ignore.git_utils.subprocess.run")
    def test_configured_relative_path(self, mock_run):
        """Test with configured relative path that gets resolved."""
        mock_run.return_value = Mock(stdout="gitignore\n")

        with (
            patch.object(Path, "expanduser") as mock_expanduser,
            patch.object(Path, "is_absolute", return_value=False),
            patch.object(Path, "resolve", return_value=Path("/resolved/gitignore")),
        ):
            mock_expanduser.return_value = Path("gitignore")

            result = get_global_gitignore_path()

            assert result == Path("/resolved/gitignore")

    @patch("git_ignore.git_utils.subprocess.run")
    @patch("pathlib.Path.exists", return_value=False)
    def test_timeout_error(self, mock_exists, mock_run):
        """Test timeout error is handled gracefully."""
        mock_run.side_effect = subprocess.TimeoutExpired(["git"], 5.0)

        result = get_global_gitignore_path()

        assert result is None

    @patch("git_ignore.git_utils.subprocess.run")
    def test_xdg_config_default(self, mock_run):
        """Test XDG_CONFIG_HOME default path."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

        with (
            patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/config"}),
            patch.object(Path, "exists", return_value=True) as mock_exists,
        ):
            result = get_global_gitignore_path()

        assert result == Path("/custom/config/git/ignore")
        # Verify exists was called on the right path
        mock_exists.assert_called_once()

    @patch("git_ignore.git_utils.subprocess.run")
    def test_home_config_default(self, mock_run):
        """Test ~/.config/git/ignore default path."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

        with (
            patch.dict(os.environ, {"XDG_CONFIG_HOME": ""}),
            patch.object(Path, "home", return_value=Path("/home/user")),
            patch.object(Path, "exists", return_value=True) as mock_exists,
        ):
            result = get_global_gitignore_path()

        assert result == Path("/home/user/.config/git/ignore")
        mock_exists.assert_called_once()

    @patch("git_ignore.git_utils.subprocess.run")
    def test_no_global_gitignore(self, mock_run):
        """Test when no global gitignore exists."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["git"])

        with patch.object(Path, "exists", return_value=False):
            result = get_global_gitignore_path()

        assert result is None


class TestGetExcludeFilePath:
    """Tests for get_exclude_file_path function."""

    @patch("git_ignore.git_utils.get_git_dir")
    def test_success(self, mock_get_git_dir):
        """Test successful exclude file path construction."""
        mock_get_git_dir.return_value = Path("/path/to/.git")

        result = get_exclude_file_path()

        assert result == Path("/path/to/.git/info/exclude")

    @patch("git_ignore.git_utils.get_git_dir")
    def test_git_error_propagated(self, mock_get_git_dir):
        """Test that GitError from get_git_dir is propagated."""
        mock_get_git_dir.side_effect = GitError("test error")

        with pytest.raises(GitError, match="test error"):
            get_exclude_file_path()


class TestGetGitignorePath:
    """Tests for get_gitignore_path function."""

    @patch("git_ignore.git_utils.get_repo_root")
    def test_success(self, mock_get_repo_root):
        """Test successful gitignore path construction."""
        mock_get_repo_root.return_value = Path("/path/to/repo")

        result = get_gitignore_path()

        assert result == Path("/path/to/repo/.gitignore")

    @patch("git_ignore.git_utils.get_repo_root")
    def test_git_error_propagated(self, mock_get_repo_root):
        """Test that GitError from get_repo_root is propagated."""
        mock_get_repo_root.side_effect = GitError("test error")

        with pytest.raises(GitError, match="test error"):
            get_gitignore_path()
