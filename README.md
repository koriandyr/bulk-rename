# Bulk Rename

[![CI](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml/badge.svg)](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/koriandyr/11652bed39b7fe5a00b8313460f88a89/raw/bulk-rename-coverage.json)](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml)
[![SAST](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/koriandyr/11652bed39b7fe5a00b8313460f88a89/raw/bulk-rename-sast.json)](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml)
[![SCA](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/koriandyr/11652bed39b7fe5a00b8313460f88a89/raw/bulk-rename-sca.json)](https://github.com/koriandyr/bulk-rename/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![PyPI Package](https://img.shields.io/badge/PyPI-coming%20soon-lightgrey)](https://pypi.org/)

> A Python package for intelligently batch renaming media files based on creation dates with automatic format conversion

**Bulk Rename** streamlines your photo and video organization by automatically renaming files using their actual creation timestamps and converting between common media formats. Perfect for photographers, content creators, and anyone managing large media libraries.

## Features

- **File Conversion**:
  - Converts `.heic` files to `.jpg` using ImageMagick
  - Converts `.mov` files to `.mp4` using FFmpeg
  - Deletes original files after successful conversion (sent to Recycle Bin for recovery)

- **File Renaming**:
  - Renames files using their creation date in `YYYYMMDD-SEQUENCE` format
  - Adds a sequence number for files with the same date
  - Preserves extra text from original filenames (e.g., `IMG_1234-edited.jpg` → `20231015-0-edited.jpg`)
  - Only renames files matching specific patterns (e.g., `IMG_`, `VID_`, numeric prefixes)
  - Smart skipping: already-renamed files (matching `YYYYMMDD-N` pattern) are skipped unless metadata date differs

- **Metadata Extraction**:
  - Parallel processing using ThreadPoolExecutor for efficient I/O-bound metadata extraction
  - Extracts creation timestamps from EXIF data (for images) or video metadata
  - Falls back to file modification time if metadata is unavailable
  - Timestamps normalized to UTC throughout processing
  - Uses Windows Property System (propsys) or FFprobe for video timestamps
  - Tracks metadata reliability with `metadata_reliable` flag

- **Safety Features**:
  - Dry-run mode by default (`--commit` flag required to apply changes)
  - Logs all actions to console and rotating log file (10-day retention)
  - Uses Recycle Bin for file deletions (fully recoverable)
  - Skips renaming if filename date matches or is earlier than metadata date
  - Comprehensive error handling with detailed logging

- **Supported Formats**:
  - Images: `.jpg`, `.jpeg`, `.png`, `.heic`
  - Videos: `.mp4`, `.m4v`, `.mov`

- **Performance**:
  - Multi-threaded metadata extraction (configurable worker threads)
  - Efficient constant-time lookups using frozensets
  - Structured data handling with dataclasses (`FileMetadata`, `ProcessingStats`)

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Prerequisites

**Required External Tools:**

- **ImageMagick** - For HEIC to JPEG conversion
  - **Windows**: Download from [imagemagick.org](https://imagemagick.org/script/download.php)
  - **macOS**: `brew install imagemagick`
  - **Linux**: `sudo apt-get install imagemagick` or `sudo yum install ImageMagick`

- **FFmpeg** - For video processing and conversion
  - **Windows**: Download from [ffmpeg.org](https://ffmpeg.org/download.html) or `choco install ffmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Linux**: `sudo apt-get install ffmpeg` or `sudo yum install ffmpeg`

**Python Requirements:**
- Python 3.8 or higher
- pip package manager

### Installation Options

#### Option 1: Install from Source (Recommended)

```bash
# Clone the repository
git clone https://github.com/koriandyr/bulk-rename.git
cd bulk-rename

# Install in development mode
pip install -e .

# Or install as a package
pip install .
```

#### Option 2: Install from PyPI (Coming Soon)

```bash
pip install bulk-rename
```

#### Option 3: Run Without Installation

```bash
# Clone the repository
git clone https://github.com/koriandyr/bulk-rename.git
cd bulk-rename

# Install dependencies
pip install -r requirements.txt

# Run as a module
python -m bulk_rename --folder /path/to/media/folder
```

### Verify Installation

```bash
# Check that bulk-rename is available
bulk-rename --help

# Verify external dependencies
magick --version
ffmpeg -version
```

## Quick Start

```bash
# Preview what would happen (dry-run mode - safe!)
bulk-rename --folder /path/to/your/photos

# Review the output, then apply changes
bulk-rename --folder /path/to/your/photos --commit
```

## Usage

### Basic Usage

Run the tool in dry-run mode (no changes applied):

```bash
bulk-rename --folder /path/to/media/folder
```

Apply changes to files:

```bash
bulk-rename --folder /path/to/media/folder --commit
```

### Command Line Options

- `--folder PATH`: Path to the folder containing media files (default: current directory)
- `--commit` or `-c`: Apply changes to disk (default: dry-run mode)

### Examples

Process files in the current directory (dry-run):

```bash
python -m bulk_rename
# Or if installed:
bulk-rename
```

Process files in a specific folder and apply changes:

```bash
python -m bulk_rename --folder "C:\Users\Username\Pictures\Vacation" --commit
# Or if installed:
bulk-rename --folder "C:\Users\Username\Pictures\Vacation" --commit
```

## How It Works

1. **Metadata Collection**: Scans all supported files and extracts creation timestamps
2. **File Conversion**: Converts HEIC images to JPEG and MOV videos to MP4
3. **File Renaming**: Renames files matching predefined patterns using the format `YYYYMMDD-SEQUENCE[EXTRA_TEXT]`

### Renaming Patterns

Files are renamed only if they match these patterns:
- `IM_`, `IMG_`, `IMG_E`, `VD_` followed by digits
- Pure numeric filenames
- Four letters followed by four digits (e.g., `ABCD1234`)
- `BulkPics` followed by digits
- `P` followed by letter/digit and six digits
- Existing `YYYYMMDD-` format (for reprocessing)

### Example Output

**Original files:**
- `IMG_1234.jpg` (taken 2023-10-15)
- `IMG_5678.jpg` (taken 2023-10-15)
- `IMG_1234-edited.jpg` (taken 2023-10-15, with extra text)
- `VID_0001.mov` (taken 2023-10-16)
- `photo.heic` (taken 2023-10-17)
- `20231018-0.jpg` (already renamed, taken 2023-10-18)

**After processing:**
- `20231015-0.jpg` (from IMG_1234.jpg)
- `20231015-1.jpg` (from IMG_5678.jpg)
- `20231015-2-edited.jpg` (from IMG_1234-edited.jpg, extra text preserved)
- `20231016-0.mp4` (converted from VID_0001.mov)
- `20231017-0.jpg` (converted from photo.heic)
- `20231018-0.jpg` (skipped, already in correct format)

## Logging

The script creates a rotating log file (`bulk_rename.log`) that keeps 10 days of logs with automatic daily rotation. All actions are logged with timestamps, including:

- File conversions (HEIC→JPG, MOV→MP4)
- Rename operations (both dry-run and committed)
- Metadata extraction details (timestamp source, reliability)
- Skipped files and skip reasons
- Errors and warnings with detailed context
- Processing summary with statistics and elapsed time

Logs are written to both console and file for convenient monitoring.

## Safety Notes

- **Dry-run first**: Always run without `--commit` first to preview changes
- **Backup important files**: While the script uses the Recycle Bin, important files should be backed up
- **Check logs**: Review the log file for any errors or skipped files
- **Metadata reliability**: The script prefers EXIF/video metadata over file timestamps, but falls back gracefully

## Development

### Setup

For development, install additional dependencies:

```bash
pip install -r requirements-dev.txt
```

This includes:
- **pylint**: Code linting (target: 10.00/10 score)
- **pytest**: Test framework
- **pytest-cov**: Coverage reporting
- **pytest-mock**: Mocking utilities
- **pywin32-stubs**: Type stubs for pywin32

### Running Tests

The project includes a comprehensive unit test suite with 100% code coverage.

Run all tests:

```bash
pytest tests/test_bulk_rename.py -v
```

Run tests with coverage report:

```bash
pytest tests/test_bulk_rename.py -v --cov=bulk_rename --cov-report=term-missing
```

Or using the virtual environment:

```bash
.venv/Scripts/python.exe -m pytest tests/test_bulk_rename.py -v --cov=bulk_rename --cov-report=term-missing
```

### Test Suite Overview

The test suite includes comprehensive coverage for:
- **Constants**: Validation of file format sets and patterns
- **Dataclasses**: `FileMetadata` and `ProcessingStats` initialization
- **Logging**: Logger setup and configuration
- **File Operations**: Rename operations, dry-run vs commit modes
- **Metadata Extraction**: EXIF, video metadata, fallback timestamps
- **File Conversion**: HEIC→JPG and MOV→MP4 conversion with error handling
- **Renaming Logic**: Pattern matching, date parsing, skip conditions
- **Parallel Processing**: Multi-threaded metadata collection
- **Integration**: End-to-end folder processing workflows
- **Edge Cases**: Error conditions, missing dependencies, malformed data

All tests follow the same coding standards as production code (PEP 8, Google-style docstrings, type hints where applicable).

### Linting

Run linting with pylint (target: 10.00/10):

```bash
pylint bulk_rename/
pylint tests/
```

Or using the virtual environment:

```bash
.venv/Scripts/python.exe -m pylint bulk_rename/
.venv/Scripts/python.exe -m pylint tests/
```

### Code Quality Standards

- **PEP 8**: Follow PEP 8 style guidelines
- **Pylint Score**: All code must achieve 10.00/10
- **Docstrings**: Use Google-style docstrings for all public functions
- **Type Hints**: Include type hints for function parameters and return values
- **Code Coverage**: Maintain 100% test coverage

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on:

- How to submit bug reports and feature requests
- The process for submitting pull requests
- Code style guidelines and quality standards
- Development setup and testing requirements

## Contributors

See [CONTRIBUTORS.md](CONTRIBUTORS.md) for a list of people who have contributed to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [Pillow](https://python-pillow.org/) for image processing
- Uses [ImageMagick](https://imagemagick.org/) for HEIC conversion
- Uses [FFmpeg](https://ffmpeg.org/) for video processing
- Testing powered by [pytest](https://pytest.org/)

## Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Search [existing issues](https://github.com/koriandyr/bulk-rename/issues)
3. Create a [new issue](https://github.com/koriandyr/bulk-rename/issues/new) with details

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes in each version (coming soon).

## Architecture

The script is organized around three main phases:

1. **Metadata Collection Phase**
   - Scans folder for supported file types using frozenset lookups
   - Parallel metadata extraction using ThreadPoolExecutor (8 workers by default)
   - Creates `FileMetadata` objects with timestamp, source, and reliability info
   - Falls back gracefully from EXIF → video metadata → file modification time

2. **Conversion Phase**
   - Converts HEIC images to JPG using ImageMagick
   - Converts MOV videos to MP4 using FFmpeg
   - Original files sent to Recycle Bin for recovery
   - Updates metadata objects with conversion status

3. **Renaming Phase**
   - Filters files by pattern matching (only known patterns renamed)
   - Skips already-renamed files unless metadata date differs
   - Assigns sequence numbers per date
   - Preserves extra text from original filenames
   - Commits changes only if `--commit` flag provided

**Key Data Structures:**
- `FileMetadata`: Tracks file path, timestamp, source, reliability, conversion status
- `ProcessingStats`: Accumulates conversion/rename counts and timing

## Troubleshooting

### Common Issues

1. **"magick command not found"**: Ensure ImageMagick is installed and in PATH
2. **"ffmpeg command not found"**: Ensure FFmpeg is installed and in PATH
3. **Permission errors**: Ensure write access to the target folder
4. **No files processed**: Check that files match supported formats and naming patterns
5. **Tests fail on Windows**: Ensure pywin32 is properly installed (`pip install pywin32`)
6. **Coverage not 100%**: Verify all code paths are tested; use `--cov-report=term-missing` to identify gaps

### Log Analysis

Check the log file (`bulk_rename.log`) for detailed error messages and processing information. The log includes:
- Timestamp sources for each file
- Skip reasons for files not processed
- Detailed error messages with stack traces
- Processing statistics summary</content>
<parameter name="filePath">e:\git\personal\bulk_rename\README.md