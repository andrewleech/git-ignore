# git-ignore Development Guide

## Project Overview

A Python CLI tool that adds patterns to git ignore files. Supports adding to `.gitignore`, `.git/info/exclude`, or global gitignore files.

## Architecture

- **git_utils.py**: Git repository detection and path resolution
- **ignore_manager.py**: Core ignore file management (reading, writing, duplicate detection)
- **main.py**: CLI interface and argument parsing

## Development Requirements

### Code Quality
- Each module must be tested before review
- All code reviewed by principal-code-reviewer agent
- Follow stdlib-only approach (no external runtime dependencies)

### Development Commands

```bash
# Install development dependencies
uv sync --dev

# Run tests with coverage
uv run pytest

# Run linting
uv run ruff check .

# Format code
uv run ruff format .

# Run all quality checks
uv run ruff check . && uv run ruff format . && uv run pytest
```

### Git Integration Patterns

The tool uses `git rev-parse --absolute-git-dir` to handle:
- Regular repositories
- Submodules (`.git` file pointing to actual git directory)
- Worktrees (separate working directories)

### Testing Strategy

- **Unit Tests**: Mock git commands and file operations
- **Integration Tests**: Use temporary git repositories
- **Coverage Target**: >90% line coverage
- **Test Data**: Include edge cases (empty files, duplicates, permissions)

### Module Development Order

1. git_utils.py → test → review
2. ignore_manager.py → test → review
3. main.py → test → review
4. integration tests → review

## CLI Design

```bash
git-ignore pattern1 pattern2 ...    # Add to .gitignore
git-ignore --local pattern1         # Add to .git/info/exclude
git-ignore --global pattern1        # Add to global gitignore
```

## Error Handling

- Non-git directories: Clear error message
- Permission issues: Helpful error with suggested fixes
- Invalid patterns: Warning but continue with valid ones