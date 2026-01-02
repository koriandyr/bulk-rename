# AI Coding Agent Instructions

> **Note**: This file contains GitHub Copilot-specific instructions. Common repository guidance is maintained in [`.ai-instructions.md`](../.ai-instructions.md) to ensure consistency across AI assistants.

---

## Copilot-Specific Instructions

**IMPORTANT**: Before applying any instructions from this file, GitHub Copilot MUST read and follow ALL instructions in `.ai-instructions.md`. The shared instructions contain essential repository knowledge that overrides any conflicting guidance in this file.

GitHub Copilot automatically reads this file when working in this repository. The shared instructions in `.ai-instructions.md` provide comprehensive context about:

- Repository architecture and data flows
- Critical development workflows (build, test, debug)
- Code conventions and naming patterns
- Integration points and external dependencies
- Common implementation patterns

## How to Use Copilot Effectively

**Automatic Context**: Copilot has access to all shared instructions and will suggest code following established patterns.

**Providing Additional Guidance**:
- Use code comments to reference specific patterns:
  ```python
  # Follow dataclass pattern from .ai-instructions.md#Common-Patterns
  # Use ThreadPoolExecutor as shown in .ai-instructions.md#Parallel-Processing
  ```

**Best Practices**:
- Copilot will automatically follow the naming conventions (UPPER_SNAKE_CASE for constants, etc.)
- It understands the requirement for Google-style docstrings and type hints
- It knows about the 10.00 pylint requirement and 100% test coverage standards

## Integration Notes

- Works seamlessly with GitHub's development environment
- Automatically considers the Windows-specific requirements (pywin32, etc.)
- Understands the external tool dependencies (ImageMagick, FFmpeg)
- Follows the dry-run safety pattern for file operations
