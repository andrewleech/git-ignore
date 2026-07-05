//! Git repository utilities for path detection and resolution

use anyhow::{bail, Context};
use std::{
    env,
    path::{Path, PathBuf},
    process::Command,
    sync::OnceLock,
};

/// Cache for git directory path
static GIT_DIR_CACHE: OnceLock<PathBuf> = OnceLock::new();

/// Cache for git common directory path
static GIT_COMMON_DIR_CACHE: OnceLock<PathBuf> = OnceLock::new();

/// Cache for repository root path
static REPO_ROOT_CACHE: OnceLock<PathBuf> = OnceLock::new();

/// Execute git command and return stdout
fn run_git_command(args: &[&str]) -> anyhow::Result<String> {
    let output = Command::new("git")
        .args(args)
        .output()
        .with_context(|| "Git not found in PATH")?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

        bail!(
            "Not in a git repository (cwd: {}): {}",
            cwd.display(),
            stderr.trim()
        );
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let result = stdout.trim();

    if result.is_empty() {
        bail!("Git command returned empty output: git {}", args.join(" "));
    }

    Ok(result.to_string())
}

/// Validate that git returned a reasonable path
fn validate_git_path(path: &Path) -> anyhow::Result<PathBuf> {
    let resolved = path
        .canonicalize()
        .with_context(|| format!("Invalid path returned by git: {}", path.display()))?;

    Ok(resolved)
}

/// Resolve a path-valued `git rev-parse <rev_parse_arg>` invocation, caching
/// the validated result.
fn cached_git_path(
    cache: &OnceLock<PathBuf>,
    rev_parse_arg: &str,
    error_context: &'static str,
) -> anyhow::Result<PathBuf> {
    if let Some(cached) = cache.get() {
        return Ok(cached.clone());
    }

    let output = run_git_command(&["rev-parse", rev_parse_arg]).context(error_context)?;
    let path = PathBuf::from(output);
    let validated = validate_git_path(&path)?;

    // Only cache if we succeed
    let _ = cache.set(validated.clone());
    Ok(validated)
}

/// Get the absolute path to the git directory (.git folder or file).
///
/// In a linked worktree, this is the worktree-private administrative
/// directory (`.git/worktrees/<name>`), not the directory shared with the
/// main repository and its other worktrees. For a file git reads from the
/// shared location regardless of which worktree is active (e.g.
/// `info/exclude`), use `get_git_common_dir` instead.
pub fn get_git_dir() -> anyhow::Result<PathBuf> {
    cached_git_path(
        &GIT_DIR_CACHE,
        "--absolute-git-dir",
        "Failed to find git directory",
    )
}

/// Get the absolute path to the git common directory.
///
/// In a linked worktree, `get_git_dir` returns the worktree-private
/// administrative directory (`.git/worktrees/<name>`), but git reads
/// `info/exclude` from the common directory shared by the main repository
/// and all of its worktrees. Callers that need `info/exclude` must resolve
/// it against this path rather than `get_git_dir`.
pub fn get_git_common_dir() -> anyhow::Result<PathBuf> {
    cached_git_path(
        &GIT_COMMON_DIR_CACHE,
        "--git-common-dir",
        "Failed to find git common directory",
    )
}

/// Get the absolute path to the repository root
pub fn get_repo_root() -> anyhow::Result<PathBuf> {
    cached_git_path(
        &REPO_ROOT_CACHE,
        "--show-toplevel",
        "Failed to find repository root",
    )
}

/// Get path to global gitignore file
pub fn get_global_gitignore_path() -> Option<PathBuf> {
    // Try to get configured global gitignore
    if let Ok(output) = run_git_command(&["config", "--global", "core.excludesfile"]) {
        let path = PathBuf::from(output);
        let expanded = if path.starts_with("~") {
            let home = env::var_os("HOME")?;
            PathBuf::from(home).join(path.strip_prefix("~").unwrap())
        } else if !path.is_absolute() {
            let home = env::var_os("HOME")?;
            PathBuf::from(home).join(&path)
        } else {
            path
        };

        if expanded.exists() {
            return Some(expanded);
        }
    }

    // Check default locations
    if let Some(xdg_config) = env::var_os("XDG_CONFIG_HOME") {
        let path = PathBuf::from(xdg_config).join("git").join("ignore");
        if path.exists() {
            return Some(path);
        }
    }

    if let Some(home) = env::var_os("HOME") {
        let home_path = PathBuf::from(&home);

        let path = home_path.join(".config").join("git").join("ignore");
        if path.exists() {
            return Some(path);
        }

        let path = home_path.join(".gitignore_global");
        if path.exists() {
            return Some(path);
        }

        let path = home_path.join(".gitignore");
        if path.exists() {
            return Some(path);
        }
    }

    None
}

/// Get path to repository's .git/info/exclude file
pub fn get_exclude_file_path() -> anyhow::Result<PathBuf> {
    let git_common_dir = get_git_common_dir()?;
    Ok(git_common_dir.join("info").join("exclude"))
}

/// Get path to repository's .gitignore file
pub fn get_gitignore_path() -> anyhow::Result<PathBuf> {
    let repo_root = get_repo_root()?;
    Ok(repo_root.join(".gitignore"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn test_run_git_command_failure() {
        let result = run_git_command(&["nonexistent-command"]);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_git_path() {
        let current_dir = env::current_dir().unwrap();
        let result = validate_git_path(&current_dir);
        assert!(result.is_ok());

        let invalid_path = Path::new("/nonexistent/path/that/should/not/exist");
        let result = validate_git_path(invalid_path);
        assert!(result.is_err());
    }

    #[test]
    fn test_get_global_gitignore_path() {
        // This test might fail if no global gitignore is configured
        // but should not panic
        let _ = get_global_gitignore_path();
    }
}
