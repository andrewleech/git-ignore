"""Core ignore file management functionality."""

from enum import Enum
from pathlib import Path
from typing import NamedTuple


class IgnoreError(Exception):
    """Raised when ignore file operations fail."""

    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


class PatternSeverity(Enum):
    """Severity levels for pattern validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PatternIssue(NamedTuple):
    """Represents a pattern validation issue."""
    pattern: str
    severity: PatternSeverity
    message: str


def _sanitize_pattern(pattern: str) -> str:
    """Sanitize a pattern to prevent file corruption.

    Args:
        pattern: Raw pattern to sanitize

    Returns:
        Sanitized pattern safe for writing to file
    """
    # Remove newlines and carriage returns that could break file format
    return pattern.replace("\n", "").replace("\r", "").strip()


def _validate_file_path(file_path: Path, base_dir: Path = None) -> None:
    """Validate that file path is safe to write to.

    Args:
        file_path: Path to validate
        base_dir: Optional base directory to restrict writes to

    Raises:
        IgnoreError: If path is unsafe
    """
    try:
        resolved_path = file_path.resolve()
        if base_dir:
            base_resolved = base_dir.resolve()
            try:
                resolved_path.relative_to(base_resolved)
            except ValueError:
                raise IgnoreError(
                    f"Path {file_path} is outside allowed directory {base_dir}",
                    recoverable=False
                ) from None
    except OSError as e:
        raise IgnoreError(
            f"Invalid file path {file_path}: {e}", recoverable=False
        ) from e


def read_ignore_patterns(file_path: Path) -> set[str]:
    """Read existing patterns from an ignore file.

    Args:
        file_path: Path to ignore file

    Returns:
        Set of patterns found in the file (excluding comments and empty lines)

    Raises:
        IgnoreError: If file cannot be read
    """
    if not file_path.exists():
        return set()

    try:
        with file_path.open("r", encoding="utf-8") as f:
            patterns = set()
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.add(line)
            return patterns
    except (OSError, UnicodeDecodeError) as e:
        raise IgnoreError(f"Failed to read ignore file {file_path}: {e}") from e


def write_ignore_patterns(
    file_path: Path, patterns: list[str], append: bool = True
) -> None:
    """Write patterns to an ignore file.

    Args:
        file_path: Path to ignore file
        patterns: List of patterns to write
        append: If True, append to existing file; if False, overwrite

    Raises:
        IgnoreError: If file cannot be written
    """
    if not patterns:
        return

    _validate_file_path(file_path)

    # Sanitize all patterns before writing
    sanitized_patterns = [
        _sanitize_pattern(p) for p in patterns if _sanitize_pattern(p)
    ]
    if not sanitized_patterns:
        return

    # Ensure parent directory exists
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise IgnoreError(
            f"Failed to create directory {file_path.parent}: {e}",
            recoverable=True
        ) from e

    try:
        mode = "a" if append else "w"
        with file_path.open(mode, encoding="utf-8", newline="\n") as f:
            # Handle newline for append mode more safely
            if append and file_path.stat().st_size > 0:
                # Always add a newline when appending to non-empty file
                # This avoids the race condition from checking file content
                f.write("\n")

            for pattern in sanitized_patterns:
                f.write(f"{pattern}\n")
    except (OSError, UnicodeEncodeError) as e:
        raise IgnoreError(f"Failed to write to ignore file {file_path}: {e}") from e


def add_patterns_to_ignore_file(
    file_path: Path, new_patterns: list[str], avoid_duplicates: bool = True
) -> list[str]:
    """Add patterns to an ignore file, optionally avoiding duplicates.

    Args:
        file_path: Path to ignore file
        new_patterns: List of patterns to add
        avoid_duplicates: If True, skip patterns that already exist

    Returns:
        List of patterns that were actually added

    Raises:
        IgnoreError: If file operations fail
    """
    if not new_patterns:
        return []

    # Normalize patterns (strip whitespace)
    normalized_patterns = [
        pattern.strip() for pattern in new_patterns if pattern.strip()
    ]

    if avoid_duplicates:
        existing_patterns = read_ignore_patterns(file_path)
        patterns_to_add = [p for p in normalized_patterns if p not in existing_patterns]
    else:
        patterns_to_add = normalized_patterns

    if patterns_to_add:
        write_ignore_patterns(file_path, patterns_to_add, append=True)

    return patterns_to_add


def validate_ignore_patterns(patterns: list[str]) -> list[PatternIssue]:
    """Validate ignore patterns and return structured issues.

    Args:
        patterns: List of patterns to validate

    Returns:
        List of PatternIssue objects describing validation problems
    """
    issues = []

    for pattern in patterns:
        original_pattern = pattern
        pattern = pattern.strip()
        if not pattern:
            continue

        # Check for patterns that contain problematic characters
        if "\n" in original_pattern or "\r" in original_pattern:
            issues.append(PatternIssue(
                original_pattern,
                PatternSeverity.ERROR,
                "Pattern contains newline characters which will corrupt the ignore file"
            ))

        # Check for common issues
        if pattern.startswith("/") and pattern.endswith("/"):
            issues.append(PatternIssue(
                pattern,
                PatternSeverity.INFO,
                "Pattern has leading and trailing slashes - might be too restrictive"
            ))

        if pattern.count("**") > 1:
            issues.append(PatternIssue(
                pattern,
                PatternSeverity.WARNING,
                "Pattern has multiple '**' which may not work as expected"
            ))

        if pattern.startswith("./"):
            issues.append(PatternIssue(
                pattern,
                PatternSeverity.INFO,
                "Pattern starts with './' which is redundant"
            ))

        # Check for potentially dangerous patterns
        dangerous_patterns = ["*", "**", "/"]
        if pattern in dangerous_patterns:
            issues.append(PatternIssue(
                pattern,
                PatternSeverity.WARNING,
                "Pattern is very broad and may ignore more than intended"
            ))

        # Check for patterns that might ignore important files
        if pattern in [".git", ".gitignore", "README*", "LICENSE*"]:
            issues.append(PatternIssue(
                pattern,
                PatternSeverity.WARNING,
                "Pattern might ignore important project files"
            ))

    return issues


def ensure_info_exclude_exists(exclude_file_path: Path) -> None:
    """Ensure the .git/info/exclude file exists and has proper structure.

    Args:
        exclude_file_path: Path to .git/info/exclude file

    Raises:
        IgnoreError: If directory cannot be created or file cannot be initialized
    """
    try:
        # Create the info directory if it doesn't exist
        exclude_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create the exclude file if it doesn't exist
        if not exclude_file_path.exists():
            with exclude_file_path.open("w", encoding="utf-8") as f:
                f.write("# git ls-files --others --exclude-from=.git/info/exclude\n")
                f.write("# Lines that start with '#' are comments.\n")
                f.write("# For a project mostly in C, the following would be a good set of\n")
                f.write("# exclude patterns (uncomment them if you want to use them):\n")
                f.write("# *.[oa]\n")
                f.write("# *~\n")
    except OSError as e:
        raise IgnoreError(f"Failed to initialize exclude file {exclude_file_path}: {e}") from e
