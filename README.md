# git-ignore

[![CI/CD Pipeline](https://github.com/andrewleech/git-ignore/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/andrewleech/git-ignore/actions/workflows/ci-cd.yml)
[![Crates.io](https://img.shields.io/crates/v/git-ignore.svg)](https://crates.io/crates/git-ignore)
[![Rust versions](https://img.shields.io/badge/rust-1.70%2B-blue.svg)](https://forge.rust-lang.org/infra/channel-releases.html)

A command-line tool for easily adding patterns to git ignore files. Supports adding patterns to `.gitignore`, `.git/info/exclude`, or global gitignore files with validation and duplicate detection.

## Features

- **Multiple target files**: Add patterns to `.gitignore`, `.git/info/exclude`, or global gitignore
- **Smart duplicate detection**: Automatically avoids adding duplicate patterns
- **Pattern validation**: Warns about potentially problematic patterns
- **Git repository awareness**: Works with regular repos, submodules, and worktrees
- **Cross-platform**: Works on Linux, macOS, and Windows
- **Fast and reliable**: Minimal dependencies, comprehensive test coverage

## Installation

### From crates.io (recommended)

**With cargo (fastest and most reliable):**
```bash
cargo install git-ignore
```

### Pre-built binaries

Download pre-built binaries for your platform from the [releases page](https://github.com/andrewleech/git-ignore/releases).

### From source

**Prerequisites:** Rust 1.70+ ([install via rustup](https://rustup.rs/))

```bash
git clone https://github.com/andrewleech/git-ignore.git
cd git-ignore
cargo build --release
```

The binary will be available at `target/release/git-ignore`.

### For development

```bash
git clone https://github.com/andrewleech/git-ignore.git
cd git-ignore
cargo build
cargo test
```

## Usage

### Basic Usage

Add patterns to the repository's `.gitignore` file:

```bash
git-ignore "*.pyc" "__pycache__/" "build/"
```

### Target Specific Files

Add patterns to `.git/info/exclude` (not shared with others):

```bash
git-ignore --local "*.tmp" "my-personal-notes.txt"
```

Add patterns to your global gitignore:

```bash
git-ignore --global "*.log" ".DS_Store"
```

### Options

- `--local`, `-l`: Add patterns to `.git/info/exclude` instead of `.gitignore`
- `--global`, `-g`: Add patterns to global gitignore file
- `--no-validate`: Skip pattern validation
- `--allow-duplicates`: Allow duplicate patterns to be added
- `--version`, `-v`: Show version information
- `--help`, `-h`: Show help message

### Examples

```bash
# Add Python-specific patterns
git-ignore "*.pyc" "*.pyo" "__pycache__/" ".pytest_cache/"

# Add build artifacts (local only, not shared)
git-ignore --local "build/" "dist/" "*.egg-info/"

# Add OS-specific patterns globally
git-ignore --global ".DS_Store" "Thumbs.db" "*.swp"

# Allow duplicates (useful for scripting)
git-ignore --allow-duplicates "*.log"

# Skip validation for special patterns
git-ignore --no-validate "*"
```

## Pattern Validation

git-ignore automatically validates patterns and provides feedback:

- **ERROR**: Patterns that would corrupt the ignore file (e.g., containing newlines)
- **WARNING**: Potentially problematic patterns (e.g., very broad patterns like `*`)
- **INFO**: Patterns that could be simplified (e.g., `./file` → `file`)

```bash
$ git-ignore "*"
WARNING: Potentially problematic patterns:
  *: Pattern is very broad and may ignore more than intended
Added 1 pattern to repository gitignore (.gitignore):
  *
```

Use `--no-validate` to skip validation when needed.

## Exit Codes

git-ignore uses semantic exit codes:

- `0`: Success
- `1`: Pattern validation failed
- `2`: Git repository issues (not in git repo, etc.)
- `3`: Configuration issues (no global gitignore configured, etc.)
- `4`: File system issues (permission denied, disk full, etc.)
- `130`: Interrupted by user (Ctrl+C)
- `255`: Unexpected error

## Configuration

### Global Gitignore Setup

To use `--global`, configure your global gitignore file:

```bash
# Set global gitignore file
git config --global core.excludesfile ~/.gitignore_global

# Or use the default location
mkdir -p ~/.config/git
touch ~/.config/git/ignore
```

### Integration with Scripts

git-ignore is designed to work well in scripts:

```bash
#!/bin/bash
# Add standard Python patterns
if git-ignore "*.pyc" "__pycache__/" ".pytest_cache/"; then
    echo "Added Python ignore patterns"
else
    echo "Failed to add patterns (exit code: $?)" >&2
    exit 1
fi
```

## Development

### Setup

```bash
git clone https://github.com/andrewleech/git-ignore.git
cd git-ignore
cargo build
```

### Running Tests

```bash
# Unit tests
cargo test --lib

# Integration tests
cargo test --test integration_tests

# All tests
cargo test
```

### Code Quality

```bash
# Linting
cargo clippy -- -D warnings

# Formatting
cargo fmt --check

# Full check
cargo clippy --all-targets --all-features -- -D warnings
```

### Building

```bash
# Build release binary
cargo build --release

# Test the built binary
./target/release/git-ignore --version
```

## Architecture

The project consists of three main modules:

- **`git.rs`**: Git repository detection and path resolution
- **`ignore.rs`**: Core ignore file operations (reading, writing, validation)
- **`main.rs`**: CLI interface and argument parsing

See [CLAUDE.md](CLAUDE.md) for detailed development information.

## Supported Platforms

- **Rust**: 1.70.0+
- **Operating Systems**: Linux, macOS, Windows
- **Git**: Any version with `git rev-parse` support

## Comparison with Alternatives

| Feature | git-ignore | Manual editing | Other tools |
|---------|------------|---------------|-------------|
| Duplicate detection | ✅ | ❌ | Varies |
| Pattern validation | ✅ | ❌ | Limited |
| Multiple targets | ✅ | Manual | Limited |
| Git integration | ✅ | ❌ | Basic |
| Cross-platform | ✅ | ✅ | Varies |
| Batch operations | ✅ | Tedious | Limited |

## Troubleshooting

### Common Issues

**"Not in a git repository"**
- Ensure you're running the command from within a git repository
- For `--local` option, the repository must have a `.git` directory

**"No global gitignore file configured"**
- Set up a global gitignore file: `git config --global core.excludesfile ~/.gitignore_global`
- Or create the default location: `~/.config/git/ignore`

**Permission errors**
- Ensure you have write permissions to the target file
- For global gitignore, ensure the directory exists and is writable

**Patterns not working as expected**
- Check pattern validation warnings
- Verify patterns follow [gitignore syntax](https://git-scm.com/docs/gitignore)

### Getting Help

1. Check this README and the `--help` output
2. Look at the integration tests for usage examples
3. Open an issue on [GitHub](https://github.com/andrewleech/git-ignore/issues)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass and code is formatted
5. Submit a pull request

See [CLAUDE.md](CLAUDE.md) for development guidelines.

## License

MIT License. See [LICENSE](LICENSE) file for details.