# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Note**: Common repository guidance is maintained in [`.ai-instructions.md`](.ai-instructions.md) to ensure consistency across AI assistants. This file contains Claude-specific instructions.

## Claude Code Integration

**IMPORTANT**: Before applying any instructions from this file, Claude Code MUST read and follow ALL instructions in `.ai-instructions.md`. The shared instructions contain essential repository knowledge that takes precedence over any tool-specific guidance in this file.

Claude Code automatically reads this file when working in this repository. The shared instructions in `.ai-instructions.md` provide comprehensive context about the codebase.

## Quick Commands Reference

```bash
# Run linting (target: 10.00/10)
python -m pylint bulk_rename/
python -m pylint tests/

# Run tests with coverage
python -m pytest tests/test_bulk_rename.py -v --cov=bulk_rename --cov-report=term-missing

# Run script as module (dry-run)
python -m bulk_rename --folder /path/to/folder

# Run script (commit changes)
python -m bulk_rename --folder /path/to/folder --commit

# Or if installed as package
bulk-rename --folder /path/to/folder
bulk-rename --folder /path/to/folder --commit

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies (includes pylint, pywin32-stubs)
pip install -r requirements-dev.txt

# Install package in development mode
pip install -e .
```

## Claude-Specific Usage Tips

**Chat Commands**: Use these in Claude chat for specific guidance:
- "Follow the patterns in .ai-instructions.md for [specific task]"
- "Check .ai-instructions.md#Common-Patterns for implementation examples"
- "Use the error handling approach from .ai-instructions.md"

**Context Awareness**: Claude automatically understands:
- Windows-specific requirements and pywin32 usage
- External tool dependencies (ImageMagick, FFmpeg)
- The 10.00 pylint and 100% coverage requirements
- Dataclass patterns and parallel processing approaches

## Development Workflow

When using Claude Code:
1. **Automatic Context**: Repository knowledge is pre-loaded
2. **Reference Shared Instructions**: Use `.ai-instructions.md` references for consistency
3. **Follow Established Patterns**: Claude will suggest code following the documented conventions
4. **Safety First**: Always use dry-run mode for file operations
- Pylint score of 10.00/10
- Type hints where applicable
- Use `_` prefix for unused test variables

Allowed pylint disables for test modules:
```python
# pylint: disable=redefined-outer-name  # pytest fixtures
# pylint: disable=too-many-lines       # comprehensive test suites
# pylint: disable=missing-function-docstring  # test function names are self-documenting
```

**Code Coverage**
- Target: 100% code coverage
- Use `# pragma: no cover` only for entry point blocks (`if __name__ == '__main__'`)
- Run coverage report to identify untested code paths
