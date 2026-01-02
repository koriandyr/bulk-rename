"""
bulk_rename.py

Batch renames image and video files in a folder using creation date and sequence number.
Converts .heic files to .jpg using ImageMagick. Supports dry-run and commit modes.

Features:
    - Converts .heic images to .jpg and deletes originals (if --commit).
    - Renames files using their creation date and a sequence number.
    - Supports .jpg, .jpeg, .png, .mp4, .m4v, .mov, and .heic files.
    - Extracts creation date from EXIF or video metadata when possible.
    - Logs all actions to both console and a rotating log file.

Usage:
    python bulk_rename.py --folder <folder_path> [--commit]

Dependencies:
    - Pillow
    - pywin32 (for win32com.propsys)
    - send2trash (for deleting files using the recycle bin, so recovery is possible)
    - ImageMagick (for .heic conversion, must be installed and in PATH)
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import logging
import json
import mimetypes
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import re
import subprocess
import sys
from timeit import default_timer as timer
from typing import Optional, Tuple

from PIL import Image, UnidentifiedImageError
from send2trash import send2trash

# Windows-specific imports (only available on Windows)
try:
    # pylint: disable=no-name-in-module
    from pywintypes import com_error
    # pylint: disable=import-error,no-name-in-module
    from win32com.propsys import propsys, pscon  # type: ignore
    import pythoncom  # type: ignore
    WINDOWS_AVAILABLE = True
except ImportError:  # pragma: no cover
    # On non-Windows platforms, these won't be available
    # Platform-specific code, tested via WINDOWS_AVAILABLE mock
    com_error = Exception  # Fallback for exception handling  # pylint: disable=invalid-name
    propsys = None  # pragma: no cover
    pscon = None  # pragma: no cover
    pythoncom = None  # pragma: no cover
    WINDOWS_AVAILABLE = False  # pragma: no cover

# File format constants - frozensets for O(1) lookup
IMG_FORMATS = frozenset({'.png', '.jpg', '.jpeg', '.heic'})
VIDEO_FORMATS = frozenset({'.m4v', '.mov', '.mp4'})
ALLOWED_SUFFIXES = IMG_FORMATS | VIDEO_FORMATS

# Default number of worker threads for parallel metadata extraction
MAX_WORKERS = 8


@dataclass
class FileMetadata:  # pylint: disable=too-many-instance-attributes
    """Metadata for a media file being processed."""
    original_path: Path
    timestamp: datetime
    extension: str
    original_name: str
    metadata_reliable: bool
    timestamp_source: str
    was_converted: bool = False
    skip_reason: Optional[str] = None  # None=not skipped, 'pattern', 'already_renamed'


@dataclass
class ProcessingStats:
    """Statistics from processing a folder of media files."""
    heic_count: int = 0
    mov_count: int = 0
    rename_count: int = 0
    commit: bool = False
    elapsed: timedelta = field(default_factory=timedelta)


def setup_logger(script_name: str, verbose: bool = False) -> logging.Logger:
    """Configures and returns a logger for the script.

    Args:
        script_name (str): Name of the script for log file naming.
        verbose (bool): If True, set log level to DEBUG; otherwise INFO.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(__name__)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = TimedRotatingFileHandler(
        f"{script_name}.log", when="d", backupCount=10, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger

def rename_file(src_path: Path,
                dst_path: Path,
                commit: bool,
                logger: logging.Logger) -> bool:
    """Rename a file to a new destination path.

    Args:
        src_path (Path): Source file path.
        dst_path (Path): Destination file path.
        commit (bool): If True, perform the rename. If False, dry run.
        logger (logging.Logger): Logger instance.

    Returns:
        bool: True if rename was successful, False otherwise.
    """
    if src_path == dst_path:
        logger.info(
            "Skipping rename: source and destination are the same (%s)", src_path.name
        )
        return False

    logger.info("Renaming %s to %s", src_path.name, dst_path.name)
    if commit:
        try:
            src_path.rename(dst_path)
            logger.info("Rename successful: %s -> %s", src_path.name, dst_path.name)
            return True
        except OSError as e:
            logger.error("Rename failed for %s: %s", src_path.name, e)
            return False
    else:
        logger.info("Would rename %s to %s", src_path.name, dst_path.name)
        return True

def fallback_timestamp(path: Path,
                       logger: logging.Logger) -> datetime:
    """Returns the file's last modified timestamp as a fallback.

    Args:
        path (Path): Path to the file.

    Returns:
        datetime: The file's modification time.
    """

    local_timestamp = datetime.fromtimestamp(path.stat().st_mtime)
    fallback_utc = local_timestamp.astimezone(timezone.utc)
    logger.debug("%s fallback timestamp used: %s",
                 path.name,
                 fallback_utc.isoformat())
    return fallback_utc

def extract_exif_timestamp(image_path: Path,
                           logger: logging.Logger) -> Tuple[Optional[datetime], str]:
    """Extracts the original capture timestamp from an image's EXIF metadata,
    normalized to UTC. Falls back to filename-based timestamp if EXIF is unreadable.

    Args:
        image_path (Path): Path to the image file (e.g., JPEG, HEIC).
        logger (logging.Logger): Logger for debug and exception messages.

    Returns:
        datetime or None: The extracted timestamp in UTC if available,
        otherwise fallback timestamp in UTC.
    """
    datetime_original_tag = 36867  # DateTimeOriginal
    datetime_tag = 306             # DateTime

    try:
        with Image.open(image_path) as img_file:
            exif = img_file.getexif()
            raw_ts = None

            if datetime_original_tag in exif:
                raw_ts = exif[datetime_original_tag]
                source = "EXIF DateTimeOriginal"
            elif datetime_tag in exif:
                raw_ts = exif[datetime_tag]
                source = "EXIF DateTime"
            else:
                raw_ts = None
                source = "no EXIF timestamp"

            if raw_ts:
                naive_dt = datetime.strptime(raw_ts, "%Y:%m:%d %H:%M:%S")
                utc_dt = naive_dt.replace(tzinfo=timezone.utc)
                logger.debug("%s timestamp extracted from %s: %s",
                             image_path.name,
                             source,
                             utc_dt.isoformat())
                return utc_dt, source

    except UnidentifiedImageError as e:
        file_size = image_path.stat().st_size
        mime_type, _ = mimetypes.guess_type(image_path)
        logger.error("Image metadata failed (%s), using fallback timestamp", e)
        logger.debug("%s may be corrupted or misnamed. Size: %d bytes, MIME type: %s",
                     image_path.name,
                     file_size,
                     mime_type)
    except (OSError, ValueError, KeyError) as e:
        logger.exception("Unexpected error reading EXIF from %s: %s",
                         image_path.name,
                         e)

    fallback_dt = fallback_timestamp(path=image_path, logger=logger)
    logger.debug("%s fallback timestamp used: %s",
                 image_path.name,
                 fallback_dt.isoformat())
    return fallback_dt, 'fallback'

def extract_video_timestamp(video_path: Path,
                            logger: logging.Logger) -> tuple[Optional[datetime], str]:
    """Extracts the creation timestamp from a video file using propsys or ffprobe,
    normalized to UTC.

    Args:
        video_path (Path): Path to the video file (e.g., MOV, MP4).
        logger (logging.Logger): Logger for debug and warning messages.

    Returns:
        datetime or None: The extracted timestamp in UTC if found,
        otherwise fallback timestamp in UTC.
    """
    # Resolve path once for propsys (requires absolute path)
    resolved_path = str(video_path.resolve())

    # Try Windows propsys first (only on Windows)
    if WINDOWS_AVAILABLE:
        try:
            # Initialize COM for this thread (required for multithreading)
            pythoncom.CoInitialize()
            try:
                properties = propsys.SHGetPropertyStoreFromParsingName(resolved_path)
                date_created = properties.GetValue(pscon.PKEY_Media_DateEncoded).GetValue()
                if isinstance(date_created, datetime):
                    utc_dt = date_created.astimezone(timezone.utc)
                    logger.debug(("%s timestamp extracted from propsys: %s"),
                                 video_path.name,
                                 utc_dt.isoformat())
                    return utc_dt, 'propsys'
            finally:
                # Always uninitialize COM when done
                pythoncom.CoUninitialize()  # pylint: disable=no-member
        except (OSError, AttributeError, ValueError, com_error) as e:
            logger.warning("%s propsys metadata failed: %s, trying ffprobe",
                           video_path.name,
                           e)
    else:
        logger.debug("%s skipping propsys (not available on this platform)", video_path.name)

    # Fallback to ffprobe
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_entries', 'format_tags=creation_time',
            '-i', str(video_path)
        ],
        capture_output=True,
        text=True,
        check=False)

        data = json.loads(result.stdout)
        if ts := data.get('format', {}).get('tags', {}).get('creation_time'):
            # Normalize ISO timestamp to UTC
            parsed_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            utc_dt = parsed_dt.astimezone(timezone.utc)
            logger.debug("%s timestamp extracted from ffprobe: %s",
                         video_path.name,
                         utc_dt.isoformat())
            return utc_dt, 'ffprobe'
    except subprocess.CalledProcessError as e:
        logger.warning("%s ffprobe failed: %s, using fallback timestamp",
                       video_path.name,
                       e)

    # Final fallback
    return fallback_timestamp(path=video_path,
                              logger=logger), 'fallback'

def get_media_created_date_time(filename: Path,
                                logger: logging.Logger) -> tuple[Optional[datetime], str]:
    """Extract the creation timestamp from image or video metadata.

    Attempts to read EXIF or video metadata. Falls back to filesystem timestamp.

    Args:
        filename (Path): Path to the media file.
        logger (logging.Logger): Logger instance.

    Returns:
        datetime: The creation datetime (timezone-aware if possible).
    """
    logger.debug('Extracting timestamp from %s', filename.name)
    suffix = filename.suffix.lower()

    if suffix in VIDEO_FORMATS:
        return extract_video_timestamp(filename, logger)
    if suffix in IMG_FORMATS:
        return extract_exif_timestamp(filename, logger)

    # Fallback for unknown file types - use birthtime if available, else mtime
    stat_info = filename.stat()
    if hasattr(stat_info, 'st_birthtime'):
        return datetime.fromtimestamp(stat_info.st_birthtime, tz=timezone.utc), 'birthtime'
    return fallback_timestamp(filename, logger), 'fallback'

def _extract_single_file_metadata(file: Path,
                                   logger: logging.Logger) -> Optional[FileMetadata]:
    """Extract metadata for a single file. Used by parallel executor."""
    if file.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    timestamp, source = get_media_created_date_time(file, logger)
    return FileMetadata(
        original_path=file,
        timestamp=timestamp,
        extension=file.suffix.lower(),
        original_name=file.name,
        metadata_reliable=source.lower() not in ('fallback', 'birthtime'),
        timestamp_source=source
    )


def collect_file_metadata(file_list: list[Path],
                          logger: logging.Logger) -> list[FileMetadata]:
    """Collects metadata for each file including timestamp and renaming info.

    Uses parallel processing for improved performance on large folders.
    """
    metadata_list: list[FileMetadata] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_extract_single_file_metadata, f, logger): f
            for f in file_list
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                metadata_list.append(result)

    return metadata_list

def convert_heic_to_jpg(src_path: Path,
                        commit: bool,
                        logger: logging.Logger) -> Optional[Path]:
    """Convert a .heic file to .jpg using ImageMagick.

    Args:
        src_path (Path): Path to the .heic file.
        commit (bool): If True, perform the conversion and delete the original.
        logger (logging.Logger): Logger instance.

    Returns:
        Optional[Path]: Path to the new .jpg file if successful, None if failed.
    """
    dst_path = src_path.with_suffix('.jpg')
    if dst_path.exists():
        logger.info("Skipping conversion: %s already exists", dst_path.name)
        return dst_path

    logger.info("Converting %s to %s", src_path.name, dst_path.name)
    if commit:
        try:
            subprocess.run(
                ['magick', str(src_path), '-define', 'heic:preserve-exif=true', str(dst_path)],
                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if dst_path.exists():
                logger.info("Conversion successful: %s", dst_path.name)
                try:
                    send2trash(str(src_path))
                    logger.info("Sent original .heic file to Recycle Bin: %s", src_path.name)
                except OSError as e:
                    logger.error("Failed to send original .heic file to Recycle Bin: %s", e)
            else:
                logger.error(
                    "Conversion failed: %s not found after conversion", dst_path.name
                )
                return None
        except subprocess.CalledProcessError as e:
            logger.error("Conversion failed for %s: %s", src_path.name, e)
            return None
    else:
        logger.info("Would convert %s to %s", src_path.name, dst_path.name)

    return dst_path

def convert_mov_to_mp4(src_path: Path,
                       commit: bool,
                       logger: logging.Logger) -> Optional[Path]:
    """Convert a .mov file to .mp4 using ffmpeg.

    Args:
        src_path (Path): Path to the .mov file.
        commit (bool): If True, perform the conversion and delete the original.
        logger (logging.Logger): Logger instance.

    Returns:
        Optional[Path]: Path to the new .mp4 file if successful, None if failed.
    """
    dst_path = src_path.with_suffix('.mp4')
    if dst_path.exists():
        logger.info("Skipping conversion: %s already exists", dst_path.name)
        return dst_path

    logger.info("Converting %s to %s", src_path.name, dst_path.name)
    cmd = [
        'ffmpeg', '-y', '-i', str(src_path),
        '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-movflags', '+faststart', str(dst_path)
    ]

    if commit:
        result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0 and dst_path.exists() and dst_path.stat().st_size > 100000:
            logger.info("Conversion successful: %s", dst_path.name)
            try:
                send2trash(str(src_path))
                logger.info("Sent original .MOV file to Recycle Bin: %s", src_path.name)
            except OSError as e:
                logger.error("Failed to send original .MOV file to Recycle Bin: %s", e)
        else:
            logger.error(
                "Conversion failed for %s: %s", src_path.name, result.stderr.decode()
            )
            return None
    else:
        logger.info("Would run: %s", ' '.join(cmd))
    return dst_path

# Precompiled patterns for filename matching
PATTERNS_TO_RENAME = [
    re.compile(r'^(IM_|IMG_|IMG_E|VD_)\d+', re.I),
    re.compile(r'^\d+(_\d+)?', re.I),
    re.compile(r'^[A-Z]{4}\d{4}', re.I),
    re.compile(r'^BulkPics\s\d+', re.I),
    re.compile(r'^P([A-Z]|\d)\d{6}', re.I),
    re.compile(r'^(\d{8})-\d+', re.I)
]
DEST_PATTERN = re.compile(r'^(\d{8})-\d+', re.I)


def parse_filename_date(filename: str) -> Optional[datetime]:
    """Extract date from filename matching YYYYMMDD-N pattern."""
    match = DEST_PATTERN.search(filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def convert_files(metadata_list: list[FileMetadata],
                  commit: bool,
                  logger: logging.Logger) -> tuple[int, int]:
    """Convert HEIC to JPG and MOV to MP4, updating metadata entries in place.

    Returns:
        Tuple of (heic_count, mov_count) conversions performed.
    """
    heic_count = 0
    mov_count = 0

    for entry in metadata_list:
        ext = entry.extension.lower()

        if ext == '.heic':
            converted = convert_heic_to_jpg(src_path=entry.original_path,
                                            commit=commit, logger=logger)
            if converted:
                entry.original_path = converted
                entry.extension = '.jpg'
                entry.was_converted = True
                heic_count += 1
        elif ext == '.mov':
            converted = convert_mov_to_mp4(src_path=entry.original_path,
                                           commit=commit, logger=logger)
            if converted and converted.suffix.lower() == '.mp4':
                entry.original_path = converted
                entry.extension = '.mp4'
                entry.was_converted = True
                mov_count += 1
        else:
            logger.debug('No conversion needed for %s', entry.original_path)

    return heic_count, mov_count


def should_skip_file(entry: FileMetadata,
                     logger: logging.Logger) -> tuple[bool, str, Optional[str]]:
    """Check if file should be skipped for renaming.

    Returns:
        Tuple of (should_skip, extra_text, skip_reason).
        If should_skip is True, extra_text is empty and skip_reason is set.
    """
    filename = entry.original_path.name
    matched_pattern = next((p for p in PATTERNS_TO_RENAME
                            if p.search(filename)), None)

    if not matched_pattern:
        logger.debug('Skipping %s, no matching pattern', filename)
        return True, '', 'pattern'

    match = DEST_PATTERN.search(filename)
    if match:
        filename_dt = parse_filename_date(filename)

        if not entry.metadata_reliable:
            logger.debug("Skipping %s: metadata unavailable, trusting filename", filename)
            return True, '', 'already_renamed'

        if filename_dt and filename_dt.date() <= entry.timestamp.date():
            logger.debug(("Skipping %s: filename date is earlier than or matches "
                          "metadata timestamp"), filename)
            return True, '', 'already_renamed'

        logger.info("Renaming %s: filename date mismatch with actual timestamp", filename)
        return False, filename[match.end():], None

    return False, matched_pattern.sub('', filename), None


def rename_files(metadata_list: list[FileMetadata],
                 folder_path: Path,
                 commit: bool,
                 logger: logging.Logger) -> int:
    """Rename files matching predefined patterns using their metadata timestamp.

    Returns:
        Number of files renamed.
    """
    rename_count = 0
    count = 0
    last_date = ''

    # Cache existing filenames for O(1) collision detection
    existing_names = {f.name for f in folder_path.iterdir() if f.is_file()}

    for entry in sorted(metadata_list, key=lambda x: (x.timestamp, x.original_path.name)):
        prefix = entry.timestamp.strftime("%Y%m%d")

        if entry.was_converted:
            logger.debug("Converted file %s evaluated for renaming", entry.original_path.name)

        count = count + 1 if last_date == prefix else 0
        last_date = prefix

        should_skip, extra_text, skip_reason = should_skip_file(entry, logger)
        if should_skip:
            entry.skip_reason = skip_reason
            continue

        dst_name = f"{prefix}-{count}{extra_text}"
        while dst_name in existing_names:
            count += 1
            dst_name = f"{prefix}-{count}{extra_text}"

        if rename_file(entry.original_path, folder_path / dst_name, commit=commit, logger=logger):
            # Update cache: remove old name, add new name
            existing_names.discard(entry.original_path.name)
            existing_names.add(dst_name)
            rename_count += 1

    return rename_count


def log_summary(metadata_list: list[FileMetadata],
                stats: ProcessingStats,
                logger: logging.Logger) -> None:
    """Log processing summary statistics.

    Args:
        metadata_list: List of file metadata.
        stats: Processing statistics.
        logger: Logger instance.
    """
    total_converted = stats.heic_count + stats.mov_count
    logger.info("\nConverted %d files total", total_converted)
    logger.info("  - %d .heic files to .jpg", stats.heic_count)
    logger.info("  - %d .mov files to .mp4", stats.mov_count)

    converted_entries = sum(1 for e in metadata_list if e.was_converted)
    logger.info("Evaluated %d entries for renaming", len(metadata_list))
    logger.info("  - %d were converted files", converted_entries)

    if stats.commit:
        logger.info("Renamed %d files", stats.rename_count)
    else:
        logger.info("Would rename %d files. Use --commit to apply changes.", stats.rename_count)

    # Use tracked skip reasons instead of recalculating
    skipped_due_to_pattern = sum(1 for e in metadata_list if e.skip_reason == 'pattern')
    skipped_due_to_match = sum(1 for e in metadata_list if e.skip_reason == 'already_renamed')

    logger.info("Skipped %d files", skipped_due_to_pattern + skipped_due_to_match)
    logger.info("  - %d had no matching pattern", skipped_due_to_pattern)
    logger.info("  - %d were already renamed with matching timestamp", skipped_due_to_match)

    logger.info("Finished in %s seconds", stats.elapsed)


def process_folder(folder: str, commit: bool, logger: logging.Logger) -> int:
    """
    Processes a folder of media files by converting and renaming them based on metadata.

    This function performs three main tasks:
    1. Collects metadata from all files in the folder.
    2. Converts `.heic` files to `.jpg` and `.mov` files to `.mp4`.
    3. Renames files that match known patterns using their metadata timestamp.

    Files are renamed to the format: `YYYYMMDD-<sequence><extra_text>`, where:
    - `YYYYMMDD` is derived from the file's timestamp.
    - `<sequence>` is an incrementing counter for files with the same date.
    - `<extra_text>` preserves any suffix from the original filename.

    Args:
        folder (str): Absolute or relative path to the folder containing media files.
        commit (bool): If True, apply changes to disk. If False, simulate actions.
        logger (logging.Logger): Logger instance for recording progress.

    Returns:
        int: Exit code. Returns 0 on success.
    """
    start = timer()
    logger.info('Processing folder: %s', folder)

    folder_path = Path(folder)
    # Use list comprehension with early suffix filtering to reduce unnecessary processing
    file_list = [f for f in folder_path.iterdir()
                 if f.is_file() and f.suffix.lower() in ALLOWED_SUFFIXES]

    metadata_list = collect_file_metadata(file_list=file_list, logger=logger)
    heic_count, mov_count = convert_files(metadata_list, commit, logger)
    rename_count = rename_files(metadata_list, folder_path, commit, logger)

    stats = ProcessingStats(
        heic_count=heic_count,
        mov_count=mov_count,
        rename_count=rename_count,
        commit=commit,
        elapsed=timedelta(seconds=timer() - start)
    )
    log_summary(metadata_list, stats, logger)

    return 0

def main():
    """Parses arguments, sets up logging, and runs the folder processing."""
    parser = argparse.ArgumentParser(
        description='Rename image/video files and convert .heic to .jpg.'
    )
    parser.add_argument(
        '--folder',
        type=str,
        default='.',
        help='Folder containing files to process'
    )
    parser.add_argument(
        '-c',
        '--commit',
        action='store_true',
        default=False,
        help='Apply changes to disk'
    )
    parser.add_argument(
        '-v',
        '--verbose',
        action='store_true',
        default=False,
        help='Enable verbose (DEBUG) logging'
    )
    args = parser.parse_args()

    folder = args.folder.strip()
    commit = args.commit

    if not os.path.isdir(folder):
        print(f"Invalid folder: {folder}")
        sys.exit(1)

    script_name = os.path.basename(sys.argv[0])
    logger = setup_logger(script_name, verbose=args.verbose)
    logger.info("*** Starting script: %s ***", script_name)

    sys.exit(process_folder(folder, commit, logger))

if __name__ == '__main__':  # pragma: no cover
    main()
