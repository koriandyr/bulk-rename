# Contributing to Bulk Rename

First off, thank you for considering contributing to Bulk Rename! It's people like you that make this tool better for everyone.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Commit Messages](#commit-messages)
- [Pull Request Process](#pull-request-process)
- [Testing Guidelines](#testing-guidelines)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inclusive environment. Be respectful, constructive, and professional in all interactions.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/bulk-rename.git
   cd bulk-rename
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the [existing issues](https://github.com/koriandyr/bulk-rename/issues) to avoid duplicates.

**When filing a bug report, please include:**

- A clear and descriptive title
- Steps to reproduce the issue
- Expected behavior vs actual behavior
- Your environment (OS, Python version, package versions)
- Screenshots or log files if applicable
- Sample files (if the issue is file-specific)

**Bug Report Template:**

```markdown
## Description
Brief description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. ...

## Expected Behavior
What you expected to happen

## Actual Behavior
What actually happened

## Environment
- OS: [e.g., Windows 11, macOS 13, Ubuntu 22.04]
- Python version: [e.g., 3.11.2]
- bulk-rename version: [e.g., 1.0.0]
- ImageMagick version: [output of `magick --version`]
- FFmpeg version: [output of `ffmpeg -version`]

## Additional Context
Any other information, logs, or screenshots
```

### Suggesting Features

We love feature suggestions! Please:

1. **Check existing issues** to see if it's already been suggested
2. **Describe the feature** and its use case clearly
3. **Explain why it would be useful** to most users
4. **Consider the scope** - does it fit the project's goals?

### Improving Documentation

Documentation improvements are always welcome! This includes:

- Fixing typos or unclear wording
- Adding examples or use cases
- Improving installation instructions
- Translating documentation (future)

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- ImageMagick
- FFmpeg

### Setup Steps

1. **Install development dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Install the package in editable mode:**
   ```bash
   pip install -e .
   ```

3. **Verify your setup:**
   ```bash
   # Run tests
   pytest tests/test_bulk_rename.py -v

   # Run linting
   pylint bulk_rename/
   pylint tests/

   # Check coverage
   pytest tests/test_bulk_rename.py --cov=bulk_rename --cov-report=term-missing
   ```

### Running the Development Version

```bash
# Run the module
python -m bulk_rename --folder /path/to/test/folder

# Or use the CLI
bulk-rename --folder /path/to/test/folder
```

## Coding Standards

We maintain high code quality standards. All contributions must meet these requirements:

### Python Code Style

- **Follow PEP 8** - Use standard Python style guidelines
- **Type hints** - Include type annotations for function parameters and returns
- **Docstrings** - Use Google-style docstrings for all public functions, classes, and modules
- **Line length** - Maximum 100 characters (pylint enforced)

**Example:**

```python
def process_file(file_path: Path, metadata: FileMetadata) -> bool:
    """
    Process a single file for renaming and conversion.

    Args:
        file_path: Path to the file to process
        metadata: FileMetadata object containing file information

    Returns:
        bool: True if processing succeeded, False otherwise

    Raises:
        OSError: If file operations fail
        ValueError: If metadata is invalid
    """
    # Implementation here
    pass
```

### Code Quality Requirements

**All code must achieve:**

- **Pylint score**: 10.00/10.00 (no exceptions without justification)
- **Test coverage**: 100% code coverage
- **All tests passing**: No failing tests in CI

**Allowed pylint disables (test files only):**

```python
# pylint: disable=redefined-outer-name  # pytest fixtures
# pylint: disable=too-many-lines       # comprehensive test suites
# pylint: disable=missing-function-docstring  # test names are self-documenting
```

### Naming Conventions

- **Constants**: `UPPER_SNAKE_CASE` (e.g., `MAX_WORKERS`, `IMG_FORMATS`)
- **Functions**: `lower_snake_case` (e.g., `process_folder`, `extract_metadata`)
- **Classes**: `PascalCase` (e.g., `FileMetadata`, `ProcessingStats`)
- **Private/Internal**: Prefix with `_` (e.g., `_internal_helper`)
- **Unused variables**: Prefix with `_` (e.g., `_unused_arg`, `*_args`, `**_kwargs`)

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic changes)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates

### Examples

```bash
feat(rename): add support for custom date formats

Allow users to specify custom date format patterns for file renaming.
Includes new --date-format CLI flag and associated tests.

Closes #123

fix(metadata): handle corrupted EXIF data gracefully

Previously the tool would crash when encountering corrupted EXIF.
Now it logs a warning and falls back to file modification time.

Fixes #456

docs(readme): update installation instructions

Add platform-specific installation steps for ImageMagick and FFmpeg
on Windows, macOS, and Linux.
```

## Pull Request Process

### Before Submitting

1. **Update your branch** with the latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout your-branch
   git rebase main
   ```

2. **Run all quality checks:**
   ```bash
   # Linting
   pylint bulk_rename/
   pylint tests/

   # Tests with coverage
   pytest tests/test_bulk_rename.py -v --cov=bulk_rename --cov-report=term-missing

   # Ensure 100% coverage and 10.00 pylint score
   ```

3. **Update documentation** if needed:
   - Update README.md for new features
   - Add docstrings to new functions
   - Update CHANGELOG.md (if exists)

### Submitting the PR

1. **Push your branch** to your fork:
   ```bash
   git push origin your-branch
   ```

2. **Create a pull request** on GitHub

3. **Fill out the PR template** with:
   - Clear description of changes
   - Related issue numbers (e.g., "Closes #123")
   - Screenshots/examples if UI changes
   - Checklist completion

**PR Template:**

```markdown
## Description
Brief description of changes

## Related Issues
Closes #123
Related to #456

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] My code achieves 10.00/10.00 pylint score
- [ ] My code achieves 100% test coverage

## Testing
Describe the tests you ran and how to reproduce them:
1. Test scenario 1
2. Test scenario 2

## Screenshots (if applicable)
Add screenshots to help explain your changes
```

### Review Process

1. **Automated checks** must pass:
   - CI build must succeed
   - All tests must pass
   - Pylint score must be 10.00/10.00
   - Coverage must be 100%
   - Security scans must pass

2. **Code review** by maintainers:
   - At least one approval required
   - Address all review comments
   - Make requested changes promptly

3. **Merge**:
   - Squash commits if requested
   - Maintainer will merge when ready

## Testing Guidelines

### Writing Tests

- **Location**: Place tests in `tests/test_bulk_rename.py`
- **Naming**: Use descriptive test names: `test_<function>_<scenario>`
- **Structure**: Use pytest fixtures for common setup
- **Coverage**: Aim for 100% line coverage
- **Mocking**: Mock external dependencies (file system, subprocess calls)

**Example Test:**

```python
def test_extract_metadata_handles_corrupted_exif(tmp_path, mock_logger):
    """Test that corrupted EXIF data is handled gracefully."""
    # Arrange
    test_file = tmp_path / "corrupted.jpg"
    test_file.write_bytes(b"invalid image data")

    # Act
    result = extract_exif_timestamp(test_file, mock_logger)

    # Assert
    assert result is None
    mock_logger.warning.assert_called_once()
```

### Running Tests

```bash
# Run all tests
pytest tests/test_bulk_rename.py -v

# Run specific test
pytest tests/test_bulk_rename.py::test_extract_metadata_handles_corrupted_exif -v

# Run with coverage
pytest tests/test_bulk_rename.py --cov=bulk_rename --cov-report=term-missing

# Run with coverage HTML report
pytest tests/test_bulk_rename.py --cov=bulk_rename --cov-report=html
```

### Test Categories

Our test suite covers:

- **Unit tests**: Individual function testing
- **Integration tests**: End-to-end workflows
- **Edge cases**: Boundary conditions, error handling
- **Platform-specific**: Windows/Linux/macOS compatibility

## Getting Help

- **Questions**: Open a [discussion](https://github.com/koriandyr/bulk-rename/discussions)
- **Issues**: Create an [issue](https://github.com/koriandyr/bulk-rename/issues)
- **Documentation**: Check the [README](README.md) and code documentation

## Recognition

All contributors will be recognized in:
- [CONTRIBUTORS.md](CONTRIBUTORS.md)
- GitHub's contributors list
- Release notes (for significant contributions)

---

Thank you for contributing to Bulk Rename! Your efforts help make file organization easier for everyone.
