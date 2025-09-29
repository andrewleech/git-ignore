use assert_cmd::prelude::*;
use predicates::prelude::*;
use std::fs;
use std::path::Path;
use std::process::Command;
use tempfile::TempDir;

/// Initialize a temporary git repository for testing
fn init_git_repo(dir: &Path) -> Result<(), Box<dyn std::error::Error>> {
    Command::new("git")
        .args(["init"])
        .current_dir(dir)
        .output()?;

    Command::new("git")
        .args(["config", "user.name", "Test User"])
        .current_dir(dir)
        .output()?;

    Command::new("git")
        .args(["config", "user.email", "test@example.com"])
        .current_dir(dir)
        .output()?;

    Ok(())
}

/// Get the path to our compiled binary
fn git_ignore_cmd() -> Command {
    Command::cargo_bin("git-ignore").unwrap()
}

#[test]
fn test_help_output() {
    git_ignore_cmd()
        .arg("--help")
        .assert()
        .success()
        .stdout(predicate::str::contains("Add patterns to git ignore files"))
        .stdout(predicate::str::contains("Usage: git-ignore"));
}

#[test]
fn test_version_output() {
    git_ignore_cmd()
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::contains("1.0.0"));
}

#[test]
fn test_add_to_gitignore() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    git_ignore_cmd()
        .args(["*.pyc", "__pycache__/"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Added 2 patterns to .gitignore ("))
        .stdout(predicate::str::contains("*.pyc"))
        .stdout(predicate::str::contains("__pycache__/"));

    let gitignore_path = temp_dir.path().join(".gitignore");
    let content = fs::read_to_string(gitignore_path)?;
    assert!(content.contains("*.pyc"));
    assert!(content.contains("__pycache__/"));

    Ok(())
}

#[test]
fn test_duplicate_prevention() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    // Add pattern first time
    git_ignore_cmd()
        .args(["*.pyc"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Added 1 pattern to .gitignore ("));

    // Try to add same pattern again
    git_ignore_cmd()
        .args(["*.pyc"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "No new patterns added to .gitignore (",
        ));

    Ok(())
}

#[test]
fn test_allow_duplicates_flag() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    // Add pattern first time
    git_ignore_cmd()
        .args(["*.pyc"])
        .current_dir(temp_dir.path())
        .assert()
        .success();

    // Add same pattern again with --allow-duplicates
    git_ignore_cmd()
        .args(["--allow-duplicates", "*.pyc"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Added 1 pattern to .gitignore ("));

    Ok(())
}

#[test]
fn test_local_exclude_file() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    git_ignore_cmd()
        .args(["--local", "*.local"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "Added 1 pattern to .git/info/exclude (",
        ));

    let exclude_path = temp_dir.path().join(".git").join("info").join("exclude");
    let content = fs::read_to_string(exclude_path)?;
    assert!(content.contains("*.local"));

    Ok(())
}

#[test]
fn test_pattern_validation() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    // Test pattern with newlines should fail
    git_ignore_cmd()
        .args(["*.pyc\nmalicious"])
        .current_dir(temp_dir.path())
        .assert()
        .failure()
        .code(1)
        .stderr(predicate::str::contains(
            "ERROR: Found problematic patterns:",
        ))
        .stderr(predicate::str::contains(
            "Pattern contains newline characters",
        ));

    Ok(())
}

#[test]
fn test_no_validate_flag() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    // This should succeed with --no-validate even with problematic patterns
    git_ignore_cmd()
        .args(["--no-validate", "*"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Added 1 pattern to .gitignore ("));

    Ok(())
}

#[test]
fn test_outside_git_repo() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;

    // Don't initialize as git repo
    git_ignore_cmd()
        .args(["*.pyc"])
        .current_dir(temp_dir.path())
        .assert()
        .failure()
        .code(2)
        .stderr(predicate::str::contains(
            "Git error while determining target file",
        ));

    Ok(())
}

#[test]
fn test_conflicting_flags() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    git_ignore_cmd()
        .args(["--local", "--global", "*.pyc"])
        .current_dir(temp_dir.path())
        .assert()
        .failure()
        .stderr(predicate::str::contains(
            "Cannot specify both --local and --global",
        ));

    Ok(())
}

#[test]
fn test_empty_patterns() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    // Should fail if no patterns provided
    git_ignore_cmd()
        .current_dir(temp_dir.path())
        .assert()
        .failure()
        .stderr(predicate::str::contains("required"));

    Ok(())
}

#[test]
fn test_pattern_warnings() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    // Should show warnings but still succeed
    git_ignore_cmd()
        .args(["*", ".git"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stderr(predicate::str::contains("WARNING:"))
        .stdout(predicate::str::contains("Added 2 patterns to .gitignore ("));

    Ok(())
}

#[test]
fn test_info_exclude_template() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    git_ignore_cmd()
        .args(["--local", "build/"])
        .current_dir(temp_dir.path())
        .assert()
        .success();

    let exclude_path = temp_dir.path().join(".git").join("info").join("exclude");
    let content = fs::read_to_string(exclude_path)?;

    // Should contain template comments
    assert!(content.contains("git ls-files --others --exclude-from=.git/info/exclude"));
    assert!(content.contains("build/"));

    Ok(())
}
