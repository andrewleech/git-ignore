"""Main CLI module for git-ignore tool."""

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from . import __version__
from .git_utils import (
    GitError,
    get_exclude_file_path,
    get_gitignore_path,
    get_global_gitignore_path,
)
from .ignore_manager import (
    IgnoreError,
    PatternIssue,
    PatternSeverity,
    add_patterns_to_ignore_file,
    ensure_info_exclude_exists,
    validate_ignore_patterns,
)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        prog="git-ignore",
        description="Add patterns to git ignore files",
        epilog="Examples:\n"
        "  git-ignore '*.pyc' '__pycache__/'     # Add to .gitignore\n"
        "  git-ignore --local build/             # Add to .git/info/exclude\n"
        "  git-ignore --global '*.log'           # Add to global gitignore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "patterns",
        nargs="+",
        help="Patterns to add to ignore file",
        metavar="PATTERN",
    )

    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument(
        "--local",
        "-l",
        action="store_true",
        help="Add patterns to .git/info/exclude instead of .gitignore",
    )
    target_group.add_argument(
        "--global",
        "-g",
        dest="global_ignore",
        action="store_true",
        help="Add patterns to global gitignore file",
    )

    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip pattern validation",
    )

    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Allow duplicate patterns to be added",
    )

    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def get_target_file_path(args: argparse.Namespace) -> Path:
    """Determine the target ignore file path based on arguments.

    Args:
        args: Parsed command line arguments

    Returns:
        Path to target ignore file

    Raises:
        GitError: If not in a git repository (for local operations)
        IgnoreError: If global gitignore is not configured
    """
    if args.global_ignore:
        global_path = get_global_gitignore_path()
        if global_path is None:
            raise IgnoreError(
                "No global gitignore file configured. Set core.excludesfile or "
                "create ~/.config/git/ignore",
                recoverable=True,
            )
        return global_path
    elif args.local:
        return get_exclude_file_path()
    else:
        return get_gitignore_path()


def validate_patterns_and_get_issues(
    patterns: list[str], skip_validation: bool = False
) -> list[PatternIssue]:
    """Validate patterns and return issues.

    Args:
        patterns: List of patterns to validate
        skip_validation: If True, return empty list

    Returns:
        List of validation issues
    """
    if skip_validation:
        return []
    return validate_ignore_patterns(patterns)


def display_validation_issues(issues: list[PatternIssue]) -> None:
    """Display validation issues to user.

    Args:
        issues: List of validation issues to display
    """
    if not issues:
        return

    # Group issues by severity
    errors = [i for i in issues if i.severity == PatternSeverity.ERROR]
    warnings = [i for i in issues if i.severity == PatternSeverity.WARNING]
    infos = [i for i in issues if i.severity == PatternSeverity.INFO]

    # Display errors
    if errors:
        print("ERROR: Found problematic patterns:", file=sys.stderr)
        for issue in errors:
            print(f"  {issue.pattern}: {issue.message}", file=sys.stderr)

    # Display warnings
    if warnings:
        print("WARNING: Potentially problematic patterns:", file=sys.stderr)
        for issue in warnings:
            print(f"  {issue.pattern}: {issue.message}", file=sys.stderr)

    # Display info messages
    if infos:
        for issue in infos:
            print(f"INFO: {issue.pattern}: {issue.message}", file=sys.stderr)


def has_blocking_issues(issues: list[PatternIssue]) -> bool:
    """Check if validation issues contain blocking errors.

    Args:
        issues: List of validation issues

    Returns:
        True if there are error-level issues that should block execution
    """
    return any(issue.severity == PatternSeverity.ERROR for issue in issues)


def run_ignore_operation(args: argparse.Namespace) -> int:
    """Execute the main ignore file operation.

    Args:
        args: Parsed command line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Validate patterns
    issues = validate_patterns_and_get_issues(args.patterns, args.no_validate)
    display_validation_issues(issues)

    if has_blocking_issues(issues):
        return 1  # Pattern validation failed

    # Determine target file
    try:
        target_file = get_target_file_path(args)
    except GitError as e:
        print(f"Git error while determining target file: {e}", file=sys.stderr)
        return 2  # Git repository issues
    except IgnoreError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print(
            "Try 'git config --global core.excludesfile ~/.gitignore_global' "
            "to set a global gitignore",
            file=sys.stderr,
        )
        return 3  # Configuration issues

    # For local ignore, ensure .git/info/exclude exists
    if args.local:
        try:
            ensure_info_exclude_exists(target_file)
        except IgnoreError as e:
            print(f"Error preparing exclude file {target_file}: {e}", file=sys.stderr)
            return 4  # File system issues

    # Add patterns to ignore file
    try:
        added_patterns = add_patterns_to_ignore_file(
            target_file,
            args.patterns,
            avoid_duplicates=not args.allow_duplicates,
        )

        # Determine file type description from actual target file
        file_description = _get_file_description(target_file, args)

        if not added_patterns:
            print(
                f"No new patterns added to {file_description} "
                "(all patterns already exist)"
            )
            return 0

        # Report success with context
        pattern_word = "pattern" if len(added_patterns) == 1 else "patterns"
        print(f"Added {len(added_patterns)} {pattern_word} to {file_description}:")
        for pattern in added_patterns:
            print(f"  {pattern}")

        return 0

    except IgnoreError as e:
        print(f"Error writing patterns to {target_file}: {e}", file=sys.stderr)
        return 4  # File system issues


def _get_file_description(target_file: Path, args: argparse.Namespace) -> str:
    """Get a human-readable description of the target file.

    Args:
        target_file: Path to the target file
        args: Parsed command line arguments

    Returns:
        Human-readable description of the file
    """
    if args.global_ignore:
        return f"global gitignore ({target_file})"
    elif args.local:
        return f"local exclude file ({target_file})"
    else:
        return f"repository gitignore ({target_file})"


def main() -> int:
    """Main entry point for the git-ignore CLI.

    Exit codes:
        0: Success
        1: Pattern validation failed
        2: Git repository issues (not in git repo, etc.)
        3: Configuration issues (no global gitignore configured, etc.)
        4: File system issues (permission denied, disk full, etc.)
        130: Interrupted by user (Ctrl+C)
        255: Unexpected error

    Returns:
        Exit code
    """
    try:
        parser = create_parser()
        args = parser.parse_args()
        return run_ignore_operation(args)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 255


if __name__ == "__main__":
    sys.exit(main())
