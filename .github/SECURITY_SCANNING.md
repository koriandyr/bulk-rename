# Security Scanning

This repository implements comprehensive security scanning using multiple open-source tools to identify vulnerabilities in both code (SAST) and dependencies (SCA).

## Scanning Tools

### 1. Bandit - Python SAST
**Purpose:** Static Application Security Testing for Python code

**What it checks:**
- Hardcoded passwords and secrets
- SQL injection vulnerabilities
- Use of insecure functions (`eval`, `exec`, `pickle`)
- Weak cryptography
- Shell injection risks
- Path traversal vulnerabilities

**Severity Levels:** High, Medium, Low

### 2. Safety - Dependency Vulnerability Scanner
**Purpose:** Software Composition Analysis for Python dependencies

**What it checks:**
- Known CVEs in installed packages
- Vulnerable package versions
- Security advisories from multiple databases

**Output:** List of vulnerable dependencies with CVE IDs and recommended fixes

### 3. Semgrep - Multi-language SAST
**Purpose:** Advanced pattern-based security scanning

**What it checks:**
- OWASP Top 10 vulnerabilities
- Security anti-patterns
- Code quality issues with security implications
- Framework-specific security issues

**Rulesets Used:**
- `auto` - Semgrep chooses the rules based on the repository

## Configuration

### Enable/Disable Scanners

All scanners are **enabled by default**. To disable individual scanners, edit the environment variables in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

```yaml
env:
  ENABLE_BANDIT: 'true'    # Set to 'false' to disable
  ENABLE_SAFETY: 'true'    # Set to 'false' to disable
  ENABLE_SEMGREP: 'true'   # Set to 'false' to disable
```

### Running Locally

Install security scanning tools:

```bash
pip install -r requirements-dev.txt
```

#### Run Bandit

```bash
# JSON output
bandit -r bulk_rename/ --skip B404,B603,B607,B101 -f json -o bandit-report.json

# Text output
bandit -r bulk_rename/ --skip B404,B603,B607,B101 -f txt
```

#### Run Safety

```bash
# Check installed dependencies
safety check

# JSON output
safety check --json --output safety-report.json
```

#### Run Semgrep

```bash
# Install Semgrep (not in requirements-dev.txt as it's typically installed globally)
pip install semgrep

# Run with auto rules
semgrep --config=auto --metrics=off bulk_rename/

# Run with Python rules
semgrep --config=p/python --metrics=off bulk_rename/

# Run with security-audit rules
semgrep --config=p/security-audit --metrics=off bulk_rename/

# Run with OWASP Top 10 rules
semgrep --config=p/owasp-top-ten --metrics=off bulk_rename/
```

## CI/CD Integration

### Automated Scanning

Security scans run automatically on:
- Every push to `main` or `develop` branches
- Every pull request targeting `main` or `develop`

### Workflow Steps

1. **Security Scanning Job** runs on Ubuntu (separate from Windows test job for speed)
2. **Bandit** scans Python code for security issues
3. **Safety** checks dependencies for known vulnerabilities
4. **Semgrep** performs advanced pattern-based security analysis
5. **Reports** are uploaded as artifacts (30-day retention)
6. **SARIF** file uploaded to GitHub Security tab (Semgrep results)
7. **Badges** updated on main branch with current security status
8. **PR Comments** added with detailed security findings

### Security Badges

Two badges are displayed in the README:

- **SAST Badge:** Shows total Bandit issues
  - Green: 0 issues
  - Yellow: Medium severity issues only
  - Red: High severity issues present

- **SCA Badge:** Shows Safety vulnerability count
  - Green: 0 vulnerabilities
  - Red: 1+ vulnerabilities

Badge URLs:
```markdown
[![SAST](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/koriandyr/11652bed39b7fe5a00b8313460f88a89/raw/bulk-rename-sast.json)](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml)
[![SCA](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/koriandyr/11652bed39b7fe5a00b8313460f88a89/raw/bulk-rename-sca.json)](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml)
```

## GitHub Issues Integration

### Automatic Issue Creation

When security findings are detected on the `main` branch, the workflow automatically creates GitHub Issues for:
- **HIGH severity** Bandit findings
- **MEDIUM severity** Bandit findings

**Features:**
- **Automatic labeling:** Issues tagged with `security`, `bandit`, and severity labels (`high-severity`, `medium-severity`, `critical`)
- **Duplicate prevention:** Checks existing open issues to avoid creating duplicates
- **Rich context:** Each issue includes:
  - Severity and confidence level
  - CWE identifier (if applicable)
  - File location and line number
  - Problematic code snippet
  - Detailed description and remediation advice
  - Link to the CI run that detected it

**Managing Security Issues:**

1. **View Issues:**
   - Go to the **Issues** tab in your repository
   - Filter by `label:security` to see all security findings
   - Filter by `label:high-severity` for critical issues

2. **Workflow:**
   - Fix the security issue in your code
   - Commit and push the fix
   - Close the issue manually or reference it in your commit message (`Fixes #123`)
   - The issue won't be recreated on subsequent scans

3. **Disable Issue Creation:**
   - Set `ENABLE_BANDIT: 'false'` in the workflow to disable all Bandit scanning
   - Or remove the "Create GitHub Issues" step from the workflow

**Note:** LOW severity findings are not converted to issues but are available in the Bandit reports artifact.

## Pull Request Reporting

Security scan results are automatically posted as PR comments with:

### Bandit Section
- High, Medium, Low severity counts
- Total issues found
- Expandable details with first 100 lines of report

### Safety Section
- Vulnerability count
- Expandable details with CVE information

### Semgrep Section
- Total findings count
- Link to GitHub Security tab for details

### Security Summary
- Total issues across all scanners
- Critical issue count (High + Vulnerabilities)
- Actionable recommendations

## Viewing Results

### GitHub Issues Tab

**Bandit HIGH/MEDIUM severity findings** automatically create GitHub Issues:

1. Go to **Issues** tab
2. Filter by `label:security` or `label:high-severity`
3. Each issue contains:
   - Code location and snippet
   - Severity and CWE information
   - Remediation advice
   - Link to CI run

This is the **primary way** to track and manage security findings from Bandit.

### GitHub Security Tab

**Semgrep findings only** are uploaded to the **Security** tab via SARIF:

1. Go to repository **Security** tab
2. Click **Code scanning alerts**
3. View Semgrep findings with severity, location, and remediation advice

**Note:** Bandit and Safety findings do NOT appear in the Security tab. They appear in:
- GitHub Issues (HIGH/MEDIUM Bandit findings - automatic)
- Artifacts (all findings - downloadable reports)
- PR Comments (all findings - on pull requests)

### GitHub Actions

Download detailed reports from workflow artifacts:

1. Go to **Actions** tab
2. Click on the workflow run
3. Scroll to **Artifacts** section
4. Download:
   - `bandit-reports` - JSON and text reports (all severities)
   - `safety-reports` - JSON and text reports
   - `semgrep-sarif` - SARIF format for GitHub integration

### Local Reports

After running scans locally, reports are saved to:
- `bandit-report.json` / `bandit-report.txt`
- `safety-report.json` / `safety-report.txt`
- `semgrep.sarif` (if using `--sarif` flag)

## Ignoring False Positives

### Bandit

Add comments in code:

```python
# nosec B101
# Explanation of why this is safe
```

Or use a `.bandit` configuration file:

```yaml
# .bandit
exclude_dirs:
  - /test/

skips:
  - B101  # Skip assert_used check in tests
```

### Safety

Ignore specific vulnerabilities:

```bash
safety check --ignore 12345
```

Or create a `.safety-policy.yml` file.

### Semgrep

Add `# nosemgrep: rule-id` comments:

```python
# nosemgrep: python.lang.security.audit.exec-used
exec(trusted_code)  # This is safe because...
```

Or use a `.semgrepignore` file.

## Best Practices

1. **Review All Findings:** Don't ignore security issues without investigation
2. **Update Dependencies:** Address Safety vulnerabilities by updating packages
3. **Fix High Severity First:** Prioritize high-severity Bandit findings
4. **Document Exceptions:** Always comment why a finding is suppressed
5. **Regular Scans:** Security scans run automatically, but run locally before commits
6. **Check Security Tab:** Review Semgrep SARIF uploads in GitHub Security

## Troubleshooting

### Safety Database Issues

If Safety fails with database errors:

```bash
# Try with alternative database
safety check --db https://safetycli.com/api/safety/db/
```

### Semgrep Rate Limiting

Semgrep may hit rate limits if scanning frequently:

- Use local scans for development
- GitHub Actions should have sufficient quota

### False Positives

If scanners report false positives:

1. Verify the finding is truly a false positive
2. Add appropriate ignore comment with explanation
3. Consider if code can be refactored to avoid the pattern
4. Document decision in code comments

## Additional Resources

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Safety Documentation](https://docs.safetycli.com/)
- [Semgrep Documentation](https://semgrep.dev/docs/)
- [OWASP Top 10](https://owasp.org/Top10/)
- [GitHub Code Scanning](https://docs.github.com/en/code-security/code-scanning)

## Security Policy

For reporting security vulnerabilities, see [SECURITY.md](../SECURITY.md) (if exists) or open a private security advisory in the GitHub repository.
