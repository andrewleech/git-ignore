//! Git repository utilities for path detection and resolution

use crate::{GitError};
use std::{
    env,
    path::{Path, PathBuf},
    process::Command,
    sync::OnceLock,
};

/// Cache for git directory path
static GIT_DIR_CACHE: OnceLock<Result<PathBuf, GitError>> = OnceLock::new();

/// Cache for repository root path
static REPO_ROOT_CACHE: OnceLock<Result<PathBuf, GitError>> = OnceLock::new();

/// Execute git command and return stdout
fn run_git_command(args: &[&str], _timeout_secs: u64) -> Result<String, GitError> {
    let output = Command::new("git")
        .args(args)
        .output()
        .map_err(|_| GitError::NotFound)?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

        return Err(GitError::NotInRepository {
            cwd,
            message: stderr.trim().to_string(),
        });
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let result = stdout.trim();

    if result.is_empty() {
        return Err(GitError::CommandFailed {
            message: format!("Git command returned empty output: git {}", args.join(" ")),
        });
    }

    Ok(result.to_string())
}

/// Validate that git returned a reasonable path
fn validate_git_path(path: &Path) -> Result<PathBuf, GitError> {
    let resolved = path.canonicalize().map_err(|_| GitError::CommandFailed {
        message: format!("Invalid path returned by git: {}", path.display()),
    })?;

    Ok(resolved)
}

/// Get the absolute path to the git directory (.git folder or file)
pub fn get_git_dir() -> Result<PathBuf, GitError> {
    GIT_DIR_CACHE
        .get_or_init(|| {
            let output = run_git_command(&["rev-parse", "--absolute-git-dir"], 5)?;
            let path = PathBuf::from(output);
            validate_git_path(&path)
        })
        .as_ref()
        .map(|p| p.clone())
        .map_err(|e| e.clone())
}

/// Get the absolute path to the repository root
pub fn get_repo_root() -> Result<PathBuf, GitError> {
    REPO_ROOT_CACHE
        .get_or_init(|| {
            let output = run_git_command(&["rev-parse", "--show-toplevel"], 5)?;
            let path = PathBuf::from(output);
            validate_git_path(&path)
        })
        .as_ref()
        .map(|p| p.clone())
        .map_err(|e| e.clone())
}

/// Get path to global gitignore file
pub fn get_global_gitignore_path() -> Option<PathBuf> {
    // Try to get configured global gitignore
    if let Ok(output) = run_git_command(&["config", "--global", "core.excludesfile"], 5) {
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
pub fn get_exclude_file_path() -> Result<PathBuf, GitError> {
    let git_dir = get_git_dir()?;
    Ok(git_dir.join("info").join("exclude"))
}

/// Get path to repository's .gitignore file
pub fn get_gitignore_path() -> Result<PathBuf, GitError> {
    let repo_root = get_repo_root()?;
    Ok(repo_root.join(".gitignore"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;

    #[test]
    fn test_run_git_command_failure() {
        let result = run_git_command(&["nonexistent-command"], 1);
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