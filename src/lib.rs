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
) -> anyhow::Result<Vec<String>> {
    let gitignore_path = git::get_gitignore_path()?;
    ignore::add_patterns_to_ignore_file(&gitignore_path, patterns, true, validation_level)
}

/// Add patterns to local .git/info/exclude file
pub fn add_patterns_to_exclude(
    patterns: &[String],
    validation_level: PatternValidationLevel,
) -> anyhow::Result<Vec<String>> {
    let exclude_path = git::get_exclude_file_path()?;
    ignore::ensure_info_exclude_exists(&exclude_path)?;
    ignore::add_patterns_to_ignore_file(&exclude_path, patterns, true, validation_level)
}

/// Add patterns to global gitignore file
pub fn add_patterns_to_global(
    patterns: &[String],
    validation_level: PatternValidationLevel,
) -> anyhow::Result<Vec<String>> {
    let global_path = git::get_global_gitignore_path()
        .ok_or_else(|| anyhow::anyhow!("No global gitignore file configured"))?;
    ignore::add_patterns_to_ignore_file(&global_path, patterns, true, validation_level)
}