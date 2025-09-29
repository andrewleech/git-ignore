//! Core ignore file management functionality

use crate::{PatternIssue, PatternSeverity, PatternValidationLevel};
use anyhow::{bail, Context};
use std::{
    collections::HashSet,
    fs::{File, OpenOptions},
    io::{BufRead, BufReader, BufWriter, Write},
    path::Path,
};

/// Sanitize a pattern to prevent file corruption
fn sanitize_pattern(pattern: &str) -> String {
    // Remove newlines and carriage returns that could break file format
    pattern.replace(['\n', '\r'], "").trim().to_string()
}

/// Validate that file path is safe to write to
fn validate_file_path(file_path: &Path, base_dir: Option<&Path>) -> anyhow::Result<()> {
    let resolved = if file_path.exists() {
        file_path.canonicalize()
    } else if let Some(parent) = file_path.parent() {
        parent.canonicalize().and_then(|p| {
            file_path
                .file_name()
                .ok_or_else(|| {
                    std::io::Error::new(std::io::ErrorKind::InvalidInput, "Invalid file path")
                })
                .map(|name| p.join(name))
        })
    } else {
        Err(std::io::Error::new(
            std::io::ErrorKind::InvalidInput,
            "Invalid file path",
        ))
    }
    .with_context(|| format!("Invalid file path: {}", file_path.display()))?;

    if let Some(base) = base_dir {
        let base_resolved = base
            .canonicalize()
            .with_context(|| format!("Invalid base directory: {}", base.display()))?;

        if !resolved.starts_with(base_resolved) {
            bail!(
                "File path {} is outside allowed directory",
                file_path.display()
            );
        }
    }

    Ok(())
}

/// Read patterns from ignore file
pub fn read_ignore_patterns(file_path: &Path) -> anyhow::Result<HashSet<String>> {
    if !file_path.exists() {
        return Ok(HashSet::new());
    }

    let file = File::open(file_path)
        .with_context(|| format!("Failed to open ignore file: {}", file_path.display()))?;

    let reader = BufReader::new(file);
    let mut patterns = HashSet::new();

    for line in reader.lines() {
        let line =
            line.with_context(|| format!("Failed to read line from: {}", file_path.display()))?;

        let trimmed = line.trim();

        // Skip empty lines and comments
        if !trimmed.is_empty() && !trimmed.starts_with('#') {
            patterns.insert(trimmed.to_string());
        }
    }

    Ok(patterns)
}

/// Write patterns to ignore file
pub fn write_ignore_patterns(
    file_path: &Path,
    patterns: &[String],
    append: bool,
) -> anyhow::Result<()> {
    if patterns.is_empty() {
        return Ok(());
    }

    validate_file_path(file_path, None)?;

    // Sanitize all patterns before writing
    let sanitized_patterns: Vec<String> = patterns
        .iter()
        .map(|p| sanitize_pattern(p))
        .filter(|p| !p.is_empty())
        .collect();

    if sanitized_patterns.is_empty() {
        return Ok(());
    }

    // Ensure parent directory exists
    if let Some(parent) = file_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create directory: {}", parent.display()))?;
    }

    let mut file = if append {
        OpenOptions::new()
            .create(true)
            .append(true)
            .read(true)
            .open(file_path)
    } else {
        OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(file_path)
    }
    .with_context(|| format!("Failed to write to: {}", file_path.display()))?;

    // Handle newline for append mode
    if append && file.metadata().map(|m| m.len()).unwrap_or(0) > 0 {
        writeln!(file)
            .with_context(|| format!("Failed to write newline to: {}", file_path.display()))?;
    }

    let mut writer = BufWriter::new(&mut file);
    for pattern in sanitized_patterns {
        writeln!(writer, "{pattern}")
            .with_context(|| format!("Failed to write pattern to: {}", file_path.display()))?;
    }

    writer
        .flush()
        .with_context(|| format!("Failed to flush writes to: {}", file_path.display()))?;

    Ok(())
}

/// Add patterns to an ignore file, optionally avoiding duplicates
pub fn add_patterns_to_ignore_file(
    file_path: &Path,
    new_patterns: &[String],
    avoid_duplicates: bool,
    _validation_level: PatternValidationLevel,
) -> anyhow::Result<Vec<String>> {
    if new_patterns.is_empty() {
        return Ok(Vec::new());
    }

    // Skip validation - patterns should be pre-validated by caller
    // The validation_level parameter is kept for API compatibility

    let existing_patterns = if avoid_duplicates {
        read_ignore_patterns(file_path)?
    } else {
        HashSet::new()
    };

    let patterns_to_add: Vec<String> = new_patterns
        .iter()
        .map(|p| sanitize_pattern(p))
        .filter(|p| !p.is_empty() && (!avoid_duplicates || !existing_patterns.contains(p)))
        .collect();

    if !patterns_to_add.is_empty() {
        write_ignore_patterns(file_path, &patterns_to_add, true)?;
    }

    Ok(patterns_to_add)
}

/// Validate ignore patterns
pub fn validate_ignore_patterns(patterns: &[String]) -> Vec<PatternIssue> {
    let mut issues = Vec::new();

    for original_pattern in patterns {
        let pattern = sanitize_pattern(original_pattern);

        // Skip empty patterns after sanitization
        if pattern.is_empty() {
            continue;
        }

        // Check for newline characters in original pattern
        if original_pattern.contains(['\n', '\r']) {
            issues.push(PatternIssue {
                pattern: original_pattern.clone(),
                severity: PatternSeverity::Error,
                message: "Pattern contains newline characters which will corrupt the ignore file"
                    .to_string(),
            });
        }

        // Check for common issues
        if pattern.starts_with('/') && pattern.ends_with('/') && pattern.len() > 2 {
            issues.push(PatternIssue {
                pattern: pattern.clone(),
                severity: PatternSeverity::Info,
                message: "Pattern has leading and trailing slashes - might be too restrictive"
                    .to_string(),
            });
        }

        if pattern.starts_with("./") {
            issues.push(PatternIssue {
                pattern: pattern.clone(),
                severity: PatternSeverity::Info,
                message: "Pattern starts with './' which is redundant".to_string(),
            });
        }

        if pattern.matches("**").count() > 1 {
            issues.push(PatternIssue {
                pattern: pattern.clone(),
                severity: PatternSeverity::Warning,
                message: "Pattern contains multiple '**' which may not work as expected"
                    .to_string(),
            });
        }

        // Check for very broad patterns
        if matches!(pattern.as_str(), "*" | "**" | "/") {
            issues.push(PatternIssue {
                pattern: pattern.clone(),
                severity: PatternSeverity::Warning,
                message: "Pattern is very broad and may ignore more than intended".to_string(),
            });
        }

        // Check for patterns that might ignore important files
        if matches!(
            pattern.as_str(),
            ".git" | ".gitignore" | "README*" | "LICENSE*"
        ) {
            issues.push(PatternIssue {
                pattern: pattern.clone(),
                severity: PatternSeverity::Warning,
                message: "Pattern might ignore important project files".to_string(),
            });
        }
    }

    issues
}

/// Ensure the .git/info/exclude file exists and has proper structure
pub fn ensure_info_exclude_exists(exclude_file_path: &Path) -> anyhow::Result<()> {
    if exclude_file_path.exists() {
        return Ok(());
    }

    // Create the info directory if it doesn't exist
    if let Some(parent) = exclude_file_path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("Failed to create directory: {}", parent.display()))?;
    }

    // Create the exclude file with default template
    let template = r#"# git ls-files --others --exclude-from=.git/info/exclude
# Lines that start with '#' are comments.
# For a project mostly in C, the following would be a good set of
# exclude patterns (uncomment them if you want to use them):
# *.[oa]
# *~
"#;

    std::fs::write(exclude_file_path, template).with_context(|| {
        format!(
            "Failed to initialize exclude file: {}",
            exclude_file_path.display()
        )
    })?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{io::Write, path::PathBuf};
    use tempfile::{NamedTempFile, TempDir};

    #[test]
    fn test_sanitize_pattern() {
        assert_eq!(sanitize_pattern("*.pyc"), "*.pyc");
        assert_eq!(sanitize_pattern("  *.pyc  "), "*.pyc");
        assert_eq!(sanitize_pattern("*.pyc\n"), "*.pyc");
        assert_eq!(sanitize_pattern("*.pyc\r\n"), "*.pyc");
        assert_eq!(sanitize_pattern(""), "");
    }

    #[test]
    fn test_read_ignore_patterns_nonexistent() {
        let result = read_ignore_patterns(&PathBuf::from("/nonexistent/file"));
        assert!(result.is_ok());
        assert_eq!(result.unwrap().len(), 0);
    }

    #[test]
    fn test_read_ignore_patterns() {
        let mut temp_file = NamedTempFile::new().unwrap();
        writeln!(temp_file, "*.pyc").unwrap();
        writeln!(temp_file, "# comment").unwrap();
        writeln!(temp_file).unwrap();
        writeln!(temp_file, "__pycache__/").unwrap();

        let patterns = read_ignore_patterns(temp_file.path()).unwrap();
        assert_eq!(patterns.len(), 2);
        assert!(patterns.contains("*.pyc"));
        assert!(patterns.contains("__pycache__/"));
    }

    #[test]
    fn test_validate_ignore_patterns() {
        let patterns = vec!["*.pyc".to_string(), "build".to_string()];
        let issues = validate_ignore_patterns(&patterns);
        assert_eq!(issues.len(), 0);

        let patterns = vec!["*.pyc\n".to_string()];
        let issues = validate_ignore_patterns(&patterns);
        assert_eq!(issues.len(), 1);
        assert_eq!(issues[0].severity, PatternSeverity::Error);
    }

    #[test]
    fn test_write_ignore_patterns() {
        let temp_dir = TempDir::new().unwrap();
        let temp_file = temp_dir.path().join("test_ignore");

        let patterns = vec!["*.pyc".to_string(), "__pycache__/".to_string()];
        write_ignore_patterns(&temp_file, &patterns, false).unwrap();

        let content = std::fs::read_to_string(&temp_file).unwrap();
        assert!(content.contains("*.pyc\n"));
        assert!(content.contains("__pycache__/\n"));
    }
}
