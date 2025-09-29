//! Main CLI module for git-ignore tool

use clap::{Arg, ArgAction, Command};
use git_ignore::{git, ignore, PatternIssue, PatternSeverity, PatternValidationLevel};
use std::{
    env,
    io::{self, Write},
    process,
};

/// Program version
const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Exit codes
const EXIT_SUCCESS: i32 = 0;
const EXIT_VALIDATION_FAILED: i32 = 1;
const EXIT_GIT_ERROR: i32 = 2;
const EXIT_CONFIG_ERROR: i32 = 3;
const EXIT_FILE_ERROR: i32 = 4;

/// Create and configure the argument parser
fn create_parser() -> Command {
    Command::new("git-ignore")
        .version(VERSION)
        .about("Add patterns to git ignore files")
        .after_help(
            "Examples:\n  \
            git-ignore '*.pyc' '__pycache__/'     # Add to .gitignore\n  \
            git-ignore --local build/             # Add to .git/info/exclude\n  \
            git-ignore --global '*.log'           # Add to global gitignore",
        )
        .arg(
            Arg::new("patterns")
                .help("Patterns to add to ignore file")
                .value_name("PATTERN")
                .required(true)
                .num_args(1..),
        )
        .arg(
            Arg::new("local")
                .long("local")
                .short('l')
                .help("Add patterns to .git/info/exclude instead of .gitignore")
                .action(ArgAction::SetTrue),
        )
        .arg(
            Arg::new("global")
                .long("global")
                .short('g')
                .help("Add patterns to global gitignore file")
                .action(ArgAction::SetTrue),
        )
        .arg(
            Arg::new("no-validate")
                .long("no-validate")
                .help("Skip pattern validation")
                .action(ArgAction::SetTrue),
        )
        .arg(
            Arg::new("allow-duplicates")
                .long("allow-duplicates")
                .help("Allow duplicate patterns to be added")
                .action(ArgAction::SetTrue),
        )
}

/// Display validation issues to stderr
fn display_validation_issues(issues: &[PatternIssue]) {
    if issues.is_empty() {
        return;
    }

    let mut stderr = io::stderr();
    let errors: Vec<_> = issues
        .iter()
        .filter(|i| i.severity == PatternSeverity::Error)
        .collect();
    let warnings: Vec<_> = issues
        .iter()
        .filter(|i| i.severity == PatternSeverity::Warning)
        .collect();
    let infos: Vec<_> = issues
        .iter()
        .filter(|i| i.severity == PatternSeverity::Info)
        .collect();

    if !errors.is_empty() {
        writeln!(stderr, "ERROR: Found problematic patterns:").unwrap();
        for issue in &errors {
            writeln!(stderr, "  {}: {}", issue.pattern, issue.message).unwrap();
        }
    }

    if !warnings.is_empty() {
        if errors.is_empty() {
            writeln!(stderr, "WARNING: Potentially problematic patterns found:").unwrap();
        } else {
            writeln!(stderr, "WARNING: Additional issues:").unwrap();
        }
        for issue in &warnings {
            writeln!(stderr, "  {}: {}", issue.pattern, issue.message).unwrap();
        }
    }

    if !infos.is_empty() && errors.is_empty() && warnings.is_empty() {
        writeln!(stderr, "INFO: Pattern suggestions:").unwrap();
        for issue in infos {
            writeln!(stderr, "  {}: {}", issue.pattern, issue.message).unwrap();
        }
    }
}

/// Check if validation issues should block execution
fn has_blocking_issues(issues: &[PatternIssue]) -> bool {
    issues.iter().any(|i| i.severity == PatternSeverity::Error)
}

/// Get target file path based on arguments
fn get_target_file(local: bool, global: bool) -> anyhow::Result<std::path::PathBuf> {
    if local && global {
        anyhow::bail!("Cannot specify both --local and --global");
    }

    if global {
        git::get_global_gitignore_path()
            .ok_or_else(|| anyhow::anyhow!("No global gitignore configured. Run: git config --global core.excludesfile ~/.gitignore_global"))
    } else if local {
        Ok(git::get_exclude_file_path()?)
    } else {
        Ok(git::get_gitignore_path()?)
    }
}

/// Get file description for user messages
fn get_file_description(file_path: &std::path::Path, local: bool, global: bool) -> String {
    if global {
        format!("global gitignore ({})", file_path.display())
    } else if local {
        format!(".git/info/exclude ({})", file_path.display())
    } else {
        format!(".gitignore ({})", file_path.display())
    }
}

/// Main application logic
fn run() -> anyhow::Result<()> {
    let matches = create_parser().get_matches();

    let patterns: Vec<String> = matches
        .get_many::<String>("patterns")
        .unwrap()
        .cloned()
        .collect();
    let local = matches.get_flag("local");
    let global = matches.get_flag("global");
    let no_validate = matches.get_flag("no-validate");
    let allow_duplicates = matches.get_flag("allow-duplicates");

    // Validate patterns first if not disabled
    let validation_level = if no_validate {
        PatternValidationLevel::None
    } else {
        PatternValidationLevel::Warn
    };

    let issues = if validation_level != PatternValidationLevel::None {
        ignore::validate_ignore_patterns(&patterns)
    } else {
        Vec::new()
    };

    // Display validation issues
    display_validation_issues(&issues);

    // Check if we should continue
    if has_blocking_issues(&issues) {
        anyhow::bail!("Pattern validation failed with errors");
    }

    // Determine target file
    let target_file = get_target_file(local, global)?;

    // Ensure exclude file exists if targeting local
    if local {
        ignore::ensure_info_exclude_exists(&target_file)?;
    }

    // Add patterns to the target file (validation already done above)
    let added_patterns = ignore::add_patterns_to_ignore_file(
        &target_file,
        &patterns,
        !allow_duplicates,
        PatternValidationLevel::None,
    )?;

    // Report results
    let file_description = get_file_description(&target_file, local, global);

    if added_patterns.is_empty() {
        println!("No new patterns added to {file_description} (all patterns already exist)");
        return Ok(());
    }

    // Report success with context
    let pattern_word = if added_patterns.len() == 1 {
        "pattern"
    } else {
        "patterns"
    };
    println!(
        "Added {} {} to {}:",
        added_patterns.len(),
        pattern_word,
        file_description
    );
    for pattern in &added_patterns {
        println!("  {pattern}");
    }

    Ok(())
}

/// Main entry point
fn main() {
    let exit_code = match run() {
        Ok(()) => EXIT_SUCCESS,
        Err(e) => {
            let error_str = e.to_string();

            // Determine appropriate exit code based on error type
            if error_str.contains("Pattern validation failed") {
                EXIT_VALIDATION_FAILED
            } else if error_str.contains("Not in a git repository")
                || error_str.contains("Failed to find git directory")
                || error_str.contains("Failed to find repository root")
                || error_str.contains("Git not found in PATH")
            {
                eprintln!("Git error while determining target file: {e}");
                EXIT_GIT_ERROR
            } else if error_str.contains("No global gitignore")
                || error_str.contains("Configuration error")
            {
                eprintln!("Configuration error: {e}");
                EXIT_CONFIG_ERROR
            } else if error_str.contains("Permission denied")
                || error_str.contains("Failed to write")
                || error_str.contains("Failed to read")
                || error_str.contains("Failed to create")
            {
                eprintln!("File system error: {e}");
                EXIT_FILE_ERROR
            } else {
                eprintln!("Error: {e}");
                EXIT_FILE_ERROR
            }
        }
    };

    process::exit(exit_code);
}
