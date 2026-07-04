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
    let expected_version = env!("CARGO_PKG_VERSION");
    git_ignore_cmd()
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::contains(expected_version));
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

#[test]
fn test_trailing_slash_treated_as_duplicate() -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    init_git_repo(temp_dir.path())?;

    git_ignore_cmd()
        .args(["--local", "planning"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "Added 1 pattern to .git/info/exclude (",
        ));

    // "planning/" differs from the already-present "planning" only by a
    // trailing slash, so it should be rejected as a duplicate.
    git_ignore_cmd()
        .args(["--local", "planning/"])
        .current_dir(temp_dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains(
            "No new patterns added to .git/info/exclude (",
        ));

    let exclude_path = temp_dir.path().join(".git").join("info").join("exclude");
    let content = fs::read_to_string(exclude_path)?;
    assert_eq!(content.matches("planning").count(), 1);

    Ok(())
}

#[test]
fn test_local_exclude_file_in_worktree_is_respected_by_git_status(
) -> Result<(), Box<dyn std::error::Error>> {
    let temp_dir = TempDir::new()?;
    let main_repo = temp_dir.path().join("main");
    fs::create_dir(&main_repo)?;
    init_git_repo(&main_repo)?;

    fs::write(main_repo.join("README.md"), "test")?;
    Command::new("git")
        .args(["add", "."])
        .current_dir(&main_repo)
        .output()?;
    Command::new("git")
        .args(["commit", "-m", "initial commit"])
        .current_dir(&main_repo)
        .output()?;

    let worktree_dir = temp_dir.path().join("worktree");
    let worktree_output = Command::new("git")
        .args([
            "worktree",
            "add",
            "-b",
            "feature",
            worktree_dir.to_str().unwrap(),
        ])
        .current_dir(&main_repo)
        .output()?;
    assert!(
        worktree_output.status.success(),
        "worktree add failed: {}",
        String::from_utf8_lossy(&worktree_output.stderr)
    );

    // info/exclude must land in the directory git status actually reads,
    // not the worktree-private administrative directory.
    git_ignore_cmd()
        .args(["--local", "planning/"])
        .current_dir(&worktree_dir)
        .assert()
        .success();

    fs::create_dir(worktree_dir.join("planning"))?;
    fs::write(worktree_dir.join("planning").join("notes.md"), "notes")?;

    let status_output = Command::new("git")
        .args(["status", "--porcelain"])
        .current_dir(&worktree_dir)
        .output()?;
    let status = String::from_utf8_lossy(&status_output.stdout);
    assert!(
        !status.contains("planning"),
        "expected planning/ to be ignored by git status, got: {status}"
    );

    Ok(())
}
