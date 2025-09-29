# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Rust CLI tool that adds patterns to git ignore files. Supports adding to `.gitignore`, `.git/info/exclude`, or global gitignore files with validation and duplicate detection.

## Development Commands

### Build and Test
```bash
# Build the project
cargo build

# Build release binary
cargo build --release

# Run all tests
cargo test

# Run only unit tests
cargo test --lib

# Run only integration tests
cargo test --test integration_tests

# Run specific test
cargo test test_add_patterns_to_gitignore

# Run documentation tests
cargo test --doc
```

### Code Quality
```bash
# Check code formatting
cargo fmt --check

# Format code
cargo fmt

# Run linting
cargo clippy --all-targets --all-features -- -D warnings

# Run all quality checks (what CI runs)
cargo fmt --all -- --check && cargo clippy --all-targets --all-features -- -D warnings && cargo test
```

### Development Workflow
```bash
# Quick development cycle
cargo build && cargo test --lib

# Full validation before commit
cargo fmt && cargo clippy --all-targets --all-features -- -D warnings && cargo test
```

## Architecture

### Core Modules
- **`src/main.rs`**: CLI interface using clap derive macros, handles argument parsing and coordinates between modules
- **`src/lib.rs`**: Public API for library usage, consolidates validation logic and exports main functionality
- **`src/git.rs`**: Git repository detection and path resolution, handles worktrees/submodules via `git rev-parse --absolute-git-dir`
- **`src/ignore.rs`**: Core file operations (reading, writing, validation), pattern sanitization and duplicate detection

### Key Design Patterns

**Git Integration**: Uses `git rev-parse --absolute-git-dir` to handle all git repository types:
- Regular repositories (.git directory)
- Submodules (.git file pointing to actual git directory)
- Worktrees (separate working directories)

**Error Handling**: Consolidated to use `anyhow` throughout for consistent error propagation and context.

**Validation Architecture**: Two-phase validation system:
- Pattern validation happens at CLI level with user-friendly display
- Core file operations skip validation (pre-validated by caller)
- Library API has separate validation for programmatic usage

**File Safety**: All file operations include path validation to prevent directory traversal and ensure safe writes.

### Testing Strategy

**Unit Tests**: Located in each module (`#[cfg(test)]`), test individual functions with mocked dependencies.

**Integration Tests**: In `tests/integration_tests.rs`, use `assert_cmd` to test the full CLI with temporary git repositories.

**Test Structure**:
- `init_git_repo()` helper creates temporary git repos for testing
- `git_ignore_cmd()` helper provides access to the compiled binary
- Tests cover success paths, error conditions, and edge cases

### Dependencies

**Runtime Dependencies**:
- `clap` (v4.4): CLI argument parsing with derive macros
- `anyhow` (v1.0): Error handling and context

**Development Dependencies**:
- `assert_cmd` (v2.0): Command-line integration testing
- `predicates` (v3.0): Assertion helpers for test output
- `tempfile` (v3.8): Temporary directory/file creation for tests

### Minimum Supported Rust Version

MSRV: 1.74.0 (due to clap v4.4 requirements)
Matrix tested on: stable, beta, and 1.74.0 across Linux/Windows/macOS

## Release Process

The project uses `./release.sh` script to eliminate version duplication between `Cargo.toml` and git tags. This script provides atomic version bumping with built-in safety checks.

### Usage

```bash
# Patch release (0.2.0 → 0.2.1) - bug fixes
./release.sh patch

# Minor release (0.2.0 → 0.3.0) - new features
./release.sh minor

# Major release (0.2.0 → 1.0.0) - breaking changes
./release.sh major

# Specific version
./release.sh 1.2.3
```

### Script Safety Features

The script includes comprehensive validation:
- **Git repository check** - Ensures you're in a git repo
- **Clean working directory** - Prevents releases with uncommitted changes
- **Branch verification** - Warns if not on main branch (with override option)
- **Version format validation** - Ensures semantic versioning compliance
- **User confirmation** - Shows version change and requires confirmation

### Atomic Operations

Single command execution performs:
1. **Version extraction** - Reads current version from `Cargo.toml`
2. **Version calculation** - Computes new version based on bump type
3. **File updates** - Updates `Cargo.toml` and regenerates `Cargo.lock`
4. **Git operations** - Creates commit and annotated tag atomically
5. **Push instructions** - Provides exact commands for release completion

### Complete Release Workflow

```bash
# 1. Create release (atomic operation)
./release.sh patch

# 2. Push to trigger automated pipeline
git push origin main --tags

# Or push separately for more control:
# git push origin main
# git push origin v0.2.1
```

### CI/CD Release Pipeline

Pushing tags triggers comprehensive automation:
- **Version validation** - Verifies tag matches `Cargo.toml` version
- **Cross-platform builds** - Linux, macOS, Windows binaries
- **GitHub release** - Automatic release with binaries attached
- **crates.io publishing** - Requires `CRATES_IO_TOKEN` repository secret

### Initial Setup

Before first release, configure crates.io authentication:
1. Generate API token at https://crates.io/settings/tokens
2. Add `CRATES_IO_TOKEN` secret in GitHub repository settings
3. Grant `publish-new` and `publish-update` scopes

### Error Recovery

If release fails partway through:
```bash
# Remove tag locally and remotely if needed
git tag -d v1.2.3
git push origin :refs/tags/v1.2.3

# Reset to previous commit if necessary
git reset --hard HEAD~1
```

## Git Integration Patterns

The tool uses `git rev-parse --absolute-git-dir` to robustly handle:
- Regular repositories
- Git submodules (`.git` file pointing to actual git directory)
- Git worktrees (separate working directories sharing git data)

Path resolution functions in `git.rs` cache successful results to avoid repeated git command execution.