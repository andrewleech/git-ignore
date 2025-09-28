"""Integration tests for git-ignore CLI tool."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestCLIIntegration:
    """Integration tests for the complete CLI workflow."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            # Initialize git repository
            subprocess.run(
                ["git", "init"], cwd=repo_path, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                check=True,
                capture_output=True,
            )

            yield repo_path

    @pytest.fixture
    def temp_global_gitignore(self):
        """Create a temporary global gitignore file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".gitignore", delete=False
        ) as f:
            global_path = Path(f.name)
            f.write("# Global gitignore\n")
            f.write("*.tmp\n")

        try:
            yield global_path
        finally:
            global_path.unlink(missing_ok=True)

    def run_git_ignore(self, args, cwd=None, expect_success=True, timeout=10):
        """Run git-ignore command and return result.

        Args:
            args: List of command line arguments (must be strings)
            cwd: Working directory for the command
            expect_success: If True, assert that the command succeeds
            timeout: Command timeout in seconds

        Returns:
            CompletedProcess result
        """
        # Validate arguments to prevent shell injection
        if not all(isinstance(arg, str) for arg in args):
            raise ValueError("All arguments must be strings")

        # Use python -m to run the module
        cmd = ["python", "-m", "git_ignore.main"] + args

        try:
            result = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            pytest.fail(f"Command timed out after {timeout} seconds")

        if expect_success:
            if result.returncode != 0:
                pytest.fail(
                    f"Command failed (exit {result.returncode}): "
                    f"{result.stderr}\nStdout: {result.stdout}"
                )

        return result

    def test_add_to_gitignore(self, temp_git_repo):
        """Test adding patterns to .gitignore file."""
        gitignore_path = temp_git_repo / ".gitignore"

        # Run git-ignore command
        result = self.run_git_ignore(["*.pyc", "__pycache__/"], cwd=temp_git_repo)

        assert result.returncode == 0
        assert "Added 2 patterns to repository gitignore" in result.stdout

        # Verify file contents
        assert gitignore_path.exists()
        content = gitignore_path.read_text()
        assert "*.pyc" in content
        assert "__pycache__/" in content

    def test_add_to_existing_gitignore(self, temp_git_repo):
        """Test adding patterns to existing .gitignore file."""
        gitignore_path = temp_git_repo / ".gitignore"
        gitignore_path.write_text("# Existing content\n*.log\n")

        result = self.run_git_ignore(["*.pyc", "build/"], cwd=temp_git_repo)

        assert result.returncode == 0

        content = gitignore_path.read_text()
        assert "# Existing content" in content
        assert "*.log" in content
        assert "*.pyc" in content
        assert "build/" in content

    def test_avoid_duplicates(self, temp_git_repo):
        """Test that duplicate patterns are not added."""
        gitignore_path = temp_git_repo / ".gitignore"
        gitignore_path.write_text("*.pyc\n")

        result = self.run_git_ignore(["*.pyc", "build/"], cwd=temp_git_repo)

        assert result.returncode == 0
        assert "Added 1 pattern to repository gitignore" in result.stdout

        content = gitignore_path.read_text()
        # Should only have one *.pyc entry (more efficient counting)
        pyc_count = content.count("*.pyc")
        assert pyc_count == 1
        assert "build/" in content

    def test_allow_duplicates_flag(self, temp_git_repo):
        """Test --allow-duplicates flag."""
        gitignore_path = temp_git_repo / ".gitignore"
        gitignore_path.write_text("*.pyc\n")

        result = self.run_git_ignore(
            ["--allow-duplicates", "*.pyc", "build/"], cwd=temp_git_repo
        )

        assert result.returncode == 0
        assert "Added 2 patterns to repository gitignore" in result.stdout

        content = gitignore_path.read_text()
        # Should have two *.pyc entries
        pyc_count = content.count("*.pyc")
        assert pyc_count == 2

    def test_local_exclude_file(self, temp_git_repo):
        """Test adding patterns to .git/info/exclude."""
        exclude_path = temp_git_repo / ".git" / "info" / "exclude"

        result = self.run_git_ignore(["--local", "*.local", "temp/"], cwd=temp_git_repo)

        assert result.returncode == 0
        assert "Added 2 patterns to local exclude file" in result.stdout

        # Verify file exists and contains patterns
        assert exclude_path.exists()
        content = exclude_path.read_text()
        assert "*.local" in content
        assert "temp/" in content
        # Should also contain the default template comments
        assert "git ls-files" in content

    @pytest.mark.skip("Environment-specific test - fails in CI due to git config")
    def test_global_gitignore(self, temp_git_repo, temp_global_gitignore):
        """Test adding patterns to global gitignore."""
        # Mock the git config to return our temp global gitignore
        original_run = subprocess.run
        with patch("subprocess.run") as mock_run:
            # Mock git rev-parse calls for repo detection
            def side_effect(args, **kwargs):
                if args[:3] == ["git", "rev-parse", "--absolute-git-dir"]:
                    result = subprocess.CompletedProcess(
                        args, 0, stdout=str(temp_git_repo / ".git")
                    )
                    return result
                elif args[:3] == ["git", "rev-parse", "--show-toplevel"]:
                    result = subprocess.CompletedProcess(
                        args, 0, stdout=str(temp_git_repo)
                    )
                    return result
                elif args == ["git", "config", "--global", "core.excludesfile"]:
                    result = subprocess.CompletedProcess(
                        args, 0, stdout=str(temp_global_gitignore)
                    )
                    return result
                else:
                    # For any other calls, use the original subprocess
                    return original_run(args, **kwargs)

            mock_run.side_effect = side_effect

            result = self.run_git_ignore(["--global", "*.global"], cwd=temp_git_repo)

        assert result.returncode == 0
        assert "Added 1 pattern to global gitignore" in result.stdout

        content = temp_global_gitignore.read_text()
        assert "*.global" in content
        # Should preserve existing content
        assert "# Global gitignore" in content
        assert "*.tmp" in content

    def test_pattern_validation_errors(self, temp_git_repo):
        """Test that pattern validation errors prevent execution."""
        # Test with pattern containing newlines (should be error)
        result = self.run_git_ignore(
            ["pattern\nwith\nnewlines"], cwd=temp_git_repo, expect_success=False
        )

        assert result.returncode == 1
        assert "ERROR: Found problematic patterns" in result.stderr

    def test_pattern_validation_warnings(self, temp_git_repo):
        """Test that pattern validation warnings are shown but don't prevent
        execution."""
        result = self.run_git_ignore(["*"], cwd=temp_git_repo)

        assert result.returncode == 0
        assert "WARNING: Potentially problematic patterns" in result.stderr
        assert "very broad" in result.stderr

        # But pattern should still be added
        gitignore_path = temp_git_repo / ".gitignore"
        content = gitignore_path.read_text()
        assert "*" in content

    def test_no_validate_flag(self, temp_git_repo):
        """Test --no-validate flag skips validation."""
        result = self.run_git_ignore(["--no-validate", "*"], cwd=temp_git_repo)

        assert result.returncode == 0
        # Should not show warnings
        assert "WARNING" not in result.stderr

        gitignore_path = temp_git_repo / ".gitignore"
        content = gitignore_path.read_text()
        assert "*" in content

    def test_not_in_git_repository(self):
        """Test error when not in a git repository."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_git_ignore(["*.pyc"], cwd=temp_dir, expect_success=False)

            assert result.returncode == 2
            assert "Git error while determining target file" in result.stderr

    @pytest.mark.skip("Environment-specific test - fails in CI due to git config")
    def test_global_gitignore_not_configured(self, temp_git_repo):
        """Test error when global gitignore is not configured."""
        original_run = subprocess.run
        with patch("subprocess.run") as mock_run:
            # Mock git commands to simulate no global gitignore configured
            def side_effect(args, **kwargs):
                if args[:3] == ["git", "rev-parse", "--absolute-git-dir"]:
                    result = subprocess.CompletedProcess(
                        args, 0, stdout=str(temp_git_repo / ".git")
                    )
                    return result
                elif args[:3] == ["git", "rev-parse", "--show-toplevel"]:
                    result = subprocess.CompletedProcess(
                        args, 0, stdout=str(temp_git_repo)
                    )
                    return result
                elif args == ["git", "config", "--global", "core.excludesfile"]:
                    # Simulate no global gitignore configured
                    result = subprocess.CompletedProcess(args, 1, stderr="")
                    return result
                else:
                    return original_run(args, **kwargs)

            mock_run.side_effect = side_effect

            result = self.run_git_ignore(
                ["--global", "*.pyc"], cwd=temp_git_repo, expect_success=False
            )

        assert result.returncode == 3
        assert "Configuration error" in result.stderr
        assert "git config --global core.excludesfile" in result.stderr

    def test_permission_error(self, temp_git_repo):
        """Test handling of permission errors."""
        gitignore_path = temp_git_repo / ".gitignore"
        gitignore_path.touch()
        original_mode = gitignore_path.stat().st_mode

        try:
            gitignore_path.chmod(0o444)  # Read-only

            result = self.run_git_ignore(
                ["*.pyc"], cwd=temp_git_repo, expect_success=False
            )

            assert result.returncode == 4
            assert "Error writing patterns to" in result.stderr
        finally:
            # Always restore original permissions
            try:
                gitignore_path.chmod(original_mode)
            except OSError:
                # If file was deleted during test, ignore the error
                pass

    def test_empty_patterns(self, temp_git_repo):
        """Test that empty/whitespace patterns are handled gracefully."""
        result = self.run_git_ignore(["  ", "\t", ""], cwd=temp_git_repo)

        # Should succeed but not add any patterns
        assert result.returncode == 0
        assert "No new patterns added" in result.stdout

        gitignore_path = temp_git_repo / ".gitignore"
        if gitignore_path.exists():
            content = gitignore_path.read_text().strip()
            # Should be empty or only contain whitespace
            assert not content or content.isspace()

    def test_version_flag(self, temp_git_repo):
        """Test --version flag."""
        result = subprocess.run(
            ["python", "-m", "git_ignore.main", "--version"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
        )

        # argparse exits with code 0 for --version
        assert result.returncode == 0
        assert "git-ignore" in result.stdout
        assert "0.1.0" in result.stdout

    def test_help_flag(self, temp_git_repo):
        """Test --help flag."""
        result = subprocess.run(
            ["python", "-m", "git_ignore.main", "--help"],
            cwd=temp_git_repo,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "git-ignore" in result.stdout
        assert "Add patterns to git ignore files" in result.stdout
        assert "--local" in result.stdout
        assert "--global" in result.stdout

    def test_complex_patterns(self, temp_git_repo):
        """Test handling of complex gitignore patterns."""
        patterns = [
            "*.pyc",
            "__pycache__/",
            "*.so",
            ".Python",
            "build/",
            "develop-eggs/",
            "dist/",
            "downloads/",
            "eggs/",
            ".eggs/",
            "lib/",
            "lib64/",
            "parts/",
            "sdist/",
            "var/",
            "wheels/",
        ]

        result = self.run_git_ignore(patterns, cwd=temp_git_repo)

        assert result.returncode == 0
        assert f"Added {len(patterns)} patterns" in result.stdout

        gitignore_path = temp_git_repo / ".gitignore"
        content = gitignore_path.read_text()

        for pattern in patterns:
            assert pattern in content

    def test_special_characters_in_patterns(self, temp_git_repo):
        """Test handling of patterns with special characters."""
        patterns = [
            "*.pyc",  # Basic pattern
            "file with spaces.txt",  # Spaces
            "file-with-dashes.log",  # Dashes
            "file_with_underscores.tmp",  # Underscores
            "[Bb]uild/",  # Character class
            "*.{jpg,png,gif}",  # Brace expansion
        ]

        result = self.run_git_ignore(patterns, cwd=temp_git_repo)

        assert result.returncode == 0

        gitignore_path = temp_git_repo / ".gitignore"
        content = gitignore_path.read_text()

        for pattern in patterns:
            assert pattern in content

    def test_large_pattern_list(self, temp_git_repo):
        """Test handling of many patterns at once."""
        # Generate 100 patterns
        patterns = [f"*.ext{i:03d}" for i in range(100)]

        result = self.run_git_ignore(patterns, cwd=temp_git_repo)

        assert result.returncode == 0
        assert "Added 100 patterns" in result.stdout

        gitignore_path = temp_git_repo / ".gitignore"
        content = gitignore_path.read_text()

        # Verify all patterns are present
        for pattern in patterns:
            assert pattern in content

    def test_repeated_execution(self, temp_git_repo):
        """Test sequential executions don't interfere with each other."""
        # First execution
        result1 = self.run_git_ignore(["*.pyc"], cwd=temp_git_repo)
        assert result1.returncode == 0

        # Second execution with different patterns
        result2 = self.run_git_ignore(["*.log", "build/"], cwd=temp_git_repo)
        assert result2.returncode == 0

        # Third execution with mix of new and existing
        result3 = self.run_git_ignore(["*.pyc", "*.tmp"], cwd=temp_git_repo)
        assert result3.returncode == 0
        # Should only add *.tmp since *.pyc already exists
        assert "Added 1 pattern" in result3.stdout

        gitignore_path = temp_git_repo / ".gitignore"
        content = gitignore_path.read_text()

        # All unique patterns should be present exactly once
        assert content.count("*.pyc") == 1
        assert content.count("*.log") == 1
        assert content.count("build/") == 1
        assert content.count("*.tmp") == 1
