"""Git repository utilities for path detection and resolution."""

import subprocess  # nosec B404
from functools import lru_cache
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Raised when git operations fail."""


def _run_git_command(args: list[str], timeout: float = 5.0) -> str:
    """Execute git command and return stdout.

    Args:
        args: Git command arguments
        timeout: Command timeout in seconds

    Returns:
        Command stdout stripped of whitespace

    Raises:
        GitError: If git command fails or git is not found
    """
    try:
        result = subprocess.run(  # nosec B603
            args,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        if not stdout:
            raise GitError(f"Git command returned empty output: {' '.join(args)}")
        return stdout
    except subprocess.CalledProcessError as e:
        cwd = Path.cwd()
        stderr = e.stderr.strip() if e.stderr else "Unknown error"
        raise GitError(f"Not in a git repository (cwd: {cwd}): {stderr}") from e
    except subprocess.TimeoutExpired as e:
        raise GitError(f"Git command timed out: {' '.join(args)}") from e
    except FileNotFoundError as e:
        raise GitError("Git command not found") from e


def _validate_git_path(path: Path) -> Path:
    """Validate that git returned a reasonable path.

    Args:
        path: Path returned by git command

    Returns:
        Validated absolute path

    Raises:
        GitError: If path is invalid or doesn't exist
    """
    try:
        resolved = path.resolve()
        if not resolved.is_absolute():
            raise GitError(f"Git returned non-absolute path: {path}")
        return resolved
    except (OSError, RuntimeError) as e:
        raise GitError(f"Invalid path returned by git: {path} ({e})") from e


@lru_cache(maxsize=1)
def get_git_dir() -> Path:
    """Get the absolute path to the .git directory.

    Returns:
        Absolute path to .git directory

    Raises:
        GitError: If not in a git repository or git command fails
    """
    stdout = _run_git_command(["git", "rev-parse", "--absolute-git-dir"])
    path = Path(stdout)
    return _validate_git_path(path)


@lru_cache(maxsize=1)
def get_repo_root() -> Path:
    """Get the root directory of the git repository.

    Returns:
        Absolute path to repository root

    Raises:
        GitError: If not in a git repository or git command fails
    """
    stdout = _run_git_command(["git", "rev-parse", "--show-toplevel"])
    path = Path(stdout)
    return _validate_git_path(path)


def get_global_gitignore_path() -> Optional[Path]:
    """Get the path to the global gitignore file.

    Returns:
        Path to global gitignore file if configured, None otherwise

    Note:
        This function has different error handling than other functions in this module.
        It returns None instead of raising GitError when no global gitignore is found,
        as this is a valid state (user may not have configured global gitignore).
    """
    # Try to get configured global gitignore
    try:
        # nosec B603,B607 - Safe git config call with hardcoded arguments
        result = subprocess.run(
            ["git", "config", "--global", "core.excludesfile"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5.0,
        )
        path_str = result.stdout.strip()
        if path_str:
            path = Path(path_str).expanduser()
            if not path.is_absolute():
                path = path.resolve()
            return path
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
    ):
        pass

    # Check default locations
    import os

    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        default_path = Path(xdg_config) / "git" / "ignore"
    else:
        default_path = Path.home() / ".config" / "git" / "ignore"

    if default_path.exists():
        return default_path

    return None


def get_exclude_file_path() -> Path:
    """Get the path to the repository's exclude file (.git/info/exclude).

    Returns:
        Path to exclude file

    Raises:
        GitError: If not in a git repository
    """
    git_dir = get_git_dir()
    return git_dir / "info" / "exclude"


def get_gitignore_path() -> Path:
    """Get the path to the repository's .gitignore file.

    Returns:
        Path to .gitignore file in repository root

    Raises:
        GitError: If not in a git repository
    """
    repo_root = get_repo_root()
    return repo_root / ".gitignore"
