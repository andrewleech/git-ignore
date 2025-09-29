//! Git-ignore library for managing git ignore files
//!
//! This library provides functionality to add patterns to various git ignore files:
//! - Repository `.gitignore`
//! - Local `.git/info/exclude`
//! - Global gitignore file
//!
//! # Examples
//!
//! ```no_run
//! use git_ignore::{add_patterns_to_gitignore, PatternValidationLevel};
//!
//! let patterns = vec!["*.log".to_string(), "build/".to_string()];
//! add_patterns_to_gitignore(&patterns, PatternValidationLevel::Warn)?;
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```

pub mod git;
pub mod ignore;

use std::path::PathBuf;
use thiserror::Error;

/// Git-specific errors
#[derive(Error, Debug, Clone)]
pub enum GitError {
    #[error("Not in a git repository (cwd: {cwd}): {message}")]
    NotInRepository { cwd: PathBuf, message: String },
    #[error("Git command failed: {message}")]
    CommandFailed { message: String },
    #[error("Git command timed out: {command}")]
    Timeout { command: String },
    #[error("Git not found in PATH")]
    NotFound,
}

/// File operation errors
#[derive(Error, Debug)]
pub enum IgnoreError {
    #[error("Failed to read ignore file {path}: {source}")]
    ReadFailed { path: PathBuf, source: std::io::Error },
    #[error("Failed to write to ignore file {path}: {source}")]
    WriteFailed { path: PathBuf, source: std::io::Error },
    #[error("Failed to create directory {path}: {source}")]
    CreateDirFailed { path: PathBuf, source: std::io::Error },
    #[error("Invalid file path: {path} is outside allowed directory")]
    InvalidPath { path: PathBuf },
    #[error("Failed to initialize exclude file {path}: {source}")]
    InitializeFailed { path: PathBuf, source: std::io::Error },
}

/// Pattern validation severity levels
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PatternSeverity {
    /// Informational message
    Info,
    /// Warning about potentially problematic pattern
    Warning,
    /// Error that prevents pattern from being added
    Error,
}

/// A pattern validation issue
#[derive(Debug, Clone)]
pub struct PatternIssue {
    pub pattern: String,
    pub severity: PatternSeverity,
    pub message: String,
}

/// Pattern validation level
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PatternValidationLevel {
    /// Skip all validation
    None,
    /// Show warnings and errors, but only fail on errors
    Warn,
    /// Show all issues and fail on any issue
    Strict,
}

/// Add patterns to repository .gitignore file
pub fn add_patterns_to_gitignore(
    patterns: &[String],
    validation_level: PatternValidationLevel,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let gitignore_path = git::get_gitignore_path()?;
    ignore::add_patterns_to_ignore_file(&gitignore_path, patterns, true, validation_level)
}

/// Add patterns to local .git/info/exclude file
pub fn add_patterns_to_exclude(
    patterns: &[String],
    validation_level: PatternValidationLevel,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let exclude_path = git::get_exclude_file_path()?;
    ignore::ensure_info_exclude_exists(&exclude_path)?;
    ignore::add_patterns_to_ignore_file(&exclude_path, patterns, true, validation_level)
}

/// Add patterns to global gitignore file
pub fn add_patterns_to_global(
    patterns: &[String],
    validation_level: PatternValidationLevel,
) -> Result<Vec<String>, Box<dyn std::error::Error>> {
    let global_path = git::get_global_gitignore_path()
        .ok_or("No global gitignore file configured")?;
    ignore::add_patterns_to_ignore_file(&global_path, patterns, true, validation_level)
}