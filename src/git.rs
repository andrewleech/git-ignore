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

        bail!("Not in a git repository (cwd: {}): {}", cwd.display(), stderr.trim());
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
    let resolved = path.canonicalize()
        .with_context(|| format!("Invalid path returned by git: {}", path.display()))?;

    Ok(resolved)
}

/// Get the absolute path to the git directory (.git folder or file)
pub fn get_git_dir() -> anyhow::Result<PathBuf> {
    if let Some(cached) = GIT_DIR_CACHE.get() {
        return Ok(cached.clone());
    }

    let output = run_git_command(&["rev-parse", "--absolute-git-dir"])
        .context("Failed to find git directory")?;
    let path = PathBuf::from(output);
    let validated = validate_git_path(&path)?;

    // Only cache if we succeed
    let _ = GIT_DIR_CACHE.set(validated.clone());
    Ok(validated)
}

/// Get the absolute path to the repository root
pub fn get_repo_root() -> anyhow::Result<PathBuf> {
    if let Some(cached) = REPO_ROOT_CACHE.get() {
        return Ok(cached.clone());
    }

    let output = run_git_command(&["rev-parse", "--show-toplevel"])
        .context("Failed to find repository root")?;
    let path = PathBuf::from(output);
    let validated = validate_git_path(&path)?;

    // Only cache if we succeed
    let _ = REPO_ROOT_CACHE.set(validated.clone());
    Ok(validated)
}

/// Get path to global gitignore file
pub fn get_global_gitignore_path() -> Option<PathBuf> {
    // Try to get configured global gitignore
    if let Ok(output) = run_git_command(&["config", "--global", "core.excludesfile"]) {
        let path = PathBuf::from(output);
        let expanded = if path.starts_with("~") {
            if let Some(home) = env::var_os("HOME") {
                PathBuf::from(home).join(path.strip_prefix("~").unwrap())
            } else {
                return None;
            }
        } else if !path.is_absolute() {
            if let Some(home) = env::var_os("HOME") {
                PathBuf::from(home).join(&path)
            } else {
                return None;
            }
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
    let git_dir = get_git_dir()?;
    Ok(git_dir.join("info").join("exclude"))
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