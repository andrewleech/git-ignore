"""Unit tests for main module."""

import argparse
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from git_ignore.git_utils import GitError
from git_ignore.ignore_manager import IgnoreError, PatternIssue, PatternSeverity
from git_ignore.main import (
    _get_file_description,
    create_parser,
    display_validation_issues,
    get_target_file_path,
    has_blocking_issues,
    main,
    run_ignore_operation,
    validate_patterns_and_get_issues,
)


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_creation(self):
        """Test that parser is created successfully."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "git-ignore"

    def test_required_patterns_argument(self):
        """Test that patterns argument is required."""
        parser = create_parser()

        # Should succeed with patterns
        args = parser.parse_args(["*.pyc", "build/"])
        assert args.patterns == ["*.pyc", "build/"]

        # Should fail without patterns
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_local_flag(self):
        """Test --local flag parsing."""
        parser = create_parser()

        args = parser.parse_args(["--local", "*.pyc"])
        assert args.local is True
        assert args.global_ignore is False

        args = parser.parse_args(["-l", "*.pyc"])
        assert args.local is True

    def test_global_flag(self):
        """Test --global flag parsing."""
        parser = create_parser()

        args = parser.parse_args(["--global", "*.pyc"])
        assert args.global_ignore is True
        assert args.local is False

        args = parser.parse_args(["-g", "*.pyc"])
        assert args.global_ignore is True

    def test_mutually_exclusive_flags(self):
        """Test that --local and --global are mutually exclusive."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--local", "--global", "*.pyc"])

    def test_no_validate_flag(self):
        """Test --no-validate flag parsing."""
        parser = create_parser()

        args = parser.parse_args(["--no-validate", "*.pyc"])
        assert args.no_validate is True

        args = parser.parse_args(["*.pyc"])
        assert args.no_validate is False

    def test_allow_duplicates_flag(self):
        """Test --allow-duplicates flag parsing."""
        parser = create_parser()

        args = parser.parse_args(["--allow-duplicates", "*.pyc"])
        assert args.allow_duplicates is True

        args = parser.parse_args(["*.pyc"])
        assert args.allow_duplicates is False

    def test_version_flag(self):
        """Test --version flag."""
        parser = create_parser()

        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])


class TestGetTargetFilePath:
    """Tests for get_target_file_path function."""

    @patch("git_ignore.main.get_gitignore_path")
    def test_default_gitignore(self, mock_get_gitignore):
        """Test default behavior returns .gitignore path."""
        args = Mock(global_ignore=False, local=False)
        mock_get_gitignore.return_value = Path("/repo/.gitignore")

        result = get_target_file_path(args)

        assert result == Path("/repo/.gitignore")
        mock_get_gitignore.assert_called_once()

    @patch("git_ignore.main.get_exclude_file_path")
    def test_local_exclude(self, mock_get_exclude):
        """Test --local returns exclude file path."""
        args = Mock(global_ignore=False, local=True)
        mock_get_exclude.return_value = Path("/repo/.git/info/exclude")

        result = get_target_file_path(args)

        assert result == Path("/repo/.git/info/exclude")
        mock_get_exclude.assert_called_once()

    @patch("git_ignore.main.get_global_gitignore_path")
    def test_global_gitignore(self, mock_get_global):
        """Test --global returns global gitignore path."""
        args = Mock(global_ignore=True, local=False)
        mock_get_global.return_value = Path("/home/user/.gitignore_global")

        result = get_target_file_path(args)

        assert result == Path("/home/user/.gitignore_global")
        mock_get_global.assert_called_once()

    @patch("git_ignore.main.get_global_gitignore_path")
    def test_global_not_configured(self, mock_get_global):
        """Test error when global gitignore is not configured."""
        args = Mock(global_ignore=True, local=False)
        mock_get_global.return_value = None

        with pytest.raises(IgnoreError, match="No global gitignore file configured"):
            get_target_file_path(args)

    @patch("git_ignore.main.get_gitignore_path")
    def test_git_error_propagated(self, mock_get_gitignore):
        """Test that GitError is propagated."""
        args = Mock(global_ignore=False, local=False)
        mock_get_gitignore.side_effect = GitError("Not in git repo")

        with pytest.raises(GitError, match="Not in git repo"):
            get_target_file_path(args)


class TestValidatePatternsAndGetIssues:
    """Tests for validate_patterns_and_get_issues function."""

    @patch("git_ignore.main.validate_ignore_patterns")
    def test_normal_validation(self, mock_validate):
        """Test normal validation flow."""
        expected_issues = [PatternIssue("*", PatternSeverity.WARNING, "Broad pattern")]
        mock_validate.return_value = expected_issues

        result = validate_patterns_and_get_issues(["*"])

        assert result == expected_issues
        mock_validate.assert_called_once_with(["*"])

    def test_skip_validation(self):
        """Test that validation is skipped when requested."""
        result = validate_patterns_and_get_issues(["*"], skip_validation=True)
        assert result == []


class TestHasBlockingIssues:
    """Tests for has_blocking_issues function."""

    def test_no_issues(self):
        """Test that empty list returns False."""
        assert has_blocking_issues([]) is False

    def test_no_errors(self):
        """Test that warnings and info don't block."""
        issues = [
            PatternIssue("*", PatternSeverity.WARNING, "Warning"),
            PatternIssue("./file", PatternSeverity.INFO, "Info"),
        ]
        assert has_blocking_issues(issues) is False

    def test_has_errors(self):
        """Test that errors are blocking."""
        issues = [
            PatternIssue("*", PatternSeverity.WARNING, "Warning"),
            PatternIssue("bad\npattern", PatternSeverity.ERROR, "Error"),
        ]
        assert has_blocking_issues(issues) is True


class TestDisplayValidationIssues:
    """Tests for display_validation_issues function."""

    def test_no_issues(self):
        """Test that nothing is printed for empty issues."""
        with patch("sys.stderr") as mock_stderr:
            display_validation_issues([])
            mock_stderr.write.assert_not_called()

    @patch("sys.stderr")
    def test_error_issues(self, mock_stderr):
        """Test display of error issues."""
        issues = [
            PatternIssue("bad\npattern", PatternSeverity.ERROR, "Contains newlines")
        ]
        display_validation_issues(issues)
        mock_stderr.write.assert_called()

    @patch("sys.stderr")
    def test_mixed_issues(self, mock_stderr):
        """Test display of mixed severity issues."""
        issues = [
            PatternIssue("bad\npattern", PatternSeverity.ERROR, "Error message"),
            PatternIssue("*", PatternSeverity.WARNING, "Warning message"),
            PatternIssue("./file", PatternSeverity.INFO, "Info message"),
        ]
        display_validation_issues(issues)
        # Should print all three categories
        assert mock_stderr.write.call_count >= 6  # At least headers + messages


class TestGetFileDescription:
    """Tests for _get_file_description function."""

    def test_global_ignore(self):
        """Test description for global gitignore."""
        args = Mock(global_ignore=True, local=False)
        target_file = Path("/home/user/.gitignore_global")

        result = _get_file_description(target_file, args)

        assert result == "global gitignore (/home/user/.gitignore_global)"

    def test_local_exclude(self):
        """Test description for local exclude file."""
        args = Mock(global_ignore=False, local=True)
        target_file = Path("/repo/.git/info/exclude")

        result = _get_file_description(target_file, args)

        assert result == "local exclude file (/repo/.git/info/exclude)"

    def test_repository_gitignore(self):
        """Test description for repository gitignore."""
        args = Mock(global_ignore=False, local=False)
        target_file = Path("/repo/.gitignore")

        result = _get_file_description(target_file, args)

        assert result == "repository gitignore (/repo/.gitignore)"


# These tests are covered in the new function tests above


class TestMain:
    """Tests for main function."""

    def test_keyboard_interrupt(self):
        """Test handling of KeyboardInterrupt."""
        with patch("git_ignore.main.create_parser") as mock_parser:
            mock_parser.return_value.parse_args.side_effect = KeyboardInterrupt()

            result = main()

            assert result == 130

    @patch("sys.stderr")
    @patch("git_ignore.main.create_parser")
    def test_unexpected_error(self, mock_parser, mock_stderr):
        """Test handling of unexpected errors."""
        mock_parser.return_value.parse_args.side_effect = RuntimeError("Unexpected")

        result = main()

        assert result == 255  # Updated exit code for unexpected errors
        # Verify error message was printed
        assert mock_stderr.write.called

    @patch("git_ignore.main.run_ignore_operation")
    @patch("git_ignore.main.create_parser")
    def test_successful_delegation(self, mock_parser, mock_run_operation):
        """Test that main delegates to run_ignore_operation."""
        args = Mock(patterns=["*.pyc"])
        mock_parser.return_value.parse_args.return_value = args
        mock_run_operation.return_value = 0

        result = main()

        assert result == 0
        mock_run_operation.assert_called_once_with(args)


class TestRunIgnoreOperation:
    """Tests for run_ignore_operation function."""

    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    def test_validation_failure(self, mock_validate, mock_display, mock_has_blocking):
        """Test operation when validation fails."""
        args = Mock(patterns=["bad\npattern"], no_validate=False)
        issues = [PatternIssue("bad\npattern", PatternSeverity.ERROR, "Error")]
        mock_validate.return_value = issues
        mock_has_blocking.return_value = True

        result = run_ignore_operation(args)

        assert result == 1
        mock_display.assert_called_once_with(issues)

    @patch("git_ignore.main.get_target_file_path")
    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    @patch("sys.stderr")
    def test_git_error_handling(
        self,
        mock_stderr,
        mock_validate,
        mock_display,
        mock_has_blocking,
        mock_get_target,
    ):
        """Test handling of GitError."""
        args = Mock(patterns=["*.pyc"], no_validate=False)
        mock_validate.return_value = []
        mock_has_blocking.return_value = False
        mock_get_target.side_effect = GitError("Not in git repo")

        result = run_ignore_operation(args)

        assert result == 2  # Git repository issues
        # Verify error message was printed
        assert mock_stderr.write.called

    @patch("git_ignore.main.get_target_file_path")
    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    @patch("sys.stderr")
    def test_configuration_error_handling(
        self,
        mock_stderr,
        mock_validate,
        mock_display,
        mock_has_blocking,
        mock_get_target,
    ):
        """Test handling of configuration IgnoreError."""
        args = Mock(patterns=["*.pyc"], no_validate=False)
        mock_validate.return_value = []
        mock_has_blocking.return_value = False
        mock_get_target.side_effect = IgnoreError("No global gitignore configured")

        result = run_ignore_operation(args)

        assert result == 3  # Configuration issues
        # Verify error message and help text were printed
        assert mock_stderr.write.call_count >= 2

    @patch("git_ignore.main.add_patterns_to_ignore_file")
    @patch("git_ignore.main._get_file_description")
    @patch("git_ignore.main.get_target_file_path")
    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    def test_successful_execution(
        self,
        mock_validate,
        mock_display,
        mock_has_blocking,
        mock_get_target,
        mock_get_description,
        mock_add_patterns,
    ):
        """Test successful operation execution."""
        args = Mock(
            patterns=["*.pyc", "build/"],
            no_validate=False,
            local=False,
            global_ignore=False,
            allow_duplicates=False,
        )
        mock_validate.return_value = []
        mock_has_blocking.return_value = False
        mock_get_target.return_value = Path("/repo/.gitignore")
        mock_get_description.return_value = "repository gitignore (/repo/.gitignore)"
        mock_add_patterns.return_value = ["*.pyc", "build/"]

        result = run_ignore_operation(args)

        assert result == 0
        mock_add_patterns.assert_called_once_with(
            Path("/repo/.gitignore"),
            ["*.pyc", "build/"],
            avoid_duplicates=True,
        )

    @patch("git_ignore.main.add_patterns_to_ignore_file")
    @patch("git_ignore.main._get_file_description")
    @patch("git_ignore.main.get_target_file_path")
    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    def test_no_patterns_added(
        self,
        mock_validate,
        mock_display,
        mock_has_blocking,
        mock_get_target,
        mock_get_description,
        mock_add_patterns,
    ):
        """Test when no patterns are actually added."""
        args = Mock(
            patterns=["*.pyc"],
            no_validate=False,
            local=False,
            global_ignore=False,
            allow_duplicates=False,
        )
        mock_validate.return_value = []
        mock_has_blocking.return_value = False
        mock_get_target.return_value = Path("/repo/.gitignore")
        mock_get_description.return_value = "repository gitignore (/repo/.gitignore)"
        mock_add_patterns.return_value = []  # No patterns added

        result = run_ignore_operation(args)

        assert result == 0  # Still success

    @patch("git_ignore.main.ensure_info_exclude_exists")
    @patch("git_ignore.main.add_patterns_to_ignore_file")
    @patch("git_ignore.main._get_file_description")
    @patch("git_ignore.main.get_target_file_path")
    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    def test_local_exclude_initialization(
        self,
        mock_validate,
        mock_display,
        mock_has_blocking,
        mock_get_target,
        mock_get_description,
        mock_add_patterns,
        mock_ensure_exclude,
    ):
        """Test that local exclude file is initialized."""
        args = Mock(
            patterns=["*.pyc"],
            no_validate=False,
            local=True,
            global_ignore=False,
            allow_duplicates=False,
        )
        mock_validate.return_value = []
        mock_has_blocking.return_value = False
        exclude_path = Path("/repo/.git/info/exclude")
        mock_get_target.return_value = exclude_path
        mock_get_description.return_value = "local exclude file"
        mock_add_patterns.return_value = ["*.pyc"]

        result = run_ignore_operation(args)

        assert result == 0
        mock_ensure_exclude.assert_called_once_with(exclude_path)

    @patch("git_ignore.main.ensure_info_exclude_exists")
    @patch("git_ignore.main.get_target_file_path")
    @patch("git_ignore.main.has_blocking_issues")
    @patch("git_ignore.main.display_validation_issues")
    @patch("git_ignore.main.validate_patterns_and_get_issues")
    @patch("sys.stderr")
    def test_exclude_initialization_error(
        self,
        mock_stderr,
        mock_validate,
        mock_display,
        mock_has_blocking,
        mock_get_target,
        mock_ensure_exclude,
    ):
        """Test error during exclude file initialization."""
        args = Mock(
            patterns=["*.pyc"],
            no_validate=False,
            local=True,
            global_ignore=False,
            allow_duplicates=False,
        )
        mock_validate.return_value = []
        mock_has_blocking.return_value = False
        mock_get_target.return_value = Path("/repo/.git/info/exclude")
        mock_ensure_exclude.side_effect = IgnoreError("Permission denied")

        result = run_ignore_operation(args)

        assert result == 4  # File system issues
        # Verify error message was printed
        assert mock_stderr.write.called
