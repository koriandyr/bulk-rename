"""Bulk Rename - A tool for batch renaming media files based on creation dates."""

__version__ = "1.0.0"

__all__ = ["__version__"]

# Import all functions and classes from main module to make them available at package level
try:
    from .main import (
        ALLOWED_SUFFIXES,
        DEST_PATTERN,
        IMG_FORMATS,
        MAX_WORKERS,
        PATTERNS_TO_RENAME,
        VIDEO_FORMATS,
        FileMetadata,
        ProcessingStats,
        _extract_single_file_metadata,
        collect_file_metadata,
        convert_files,
        convert_heic_to_jpg,
        convert_mov_to_mp4,
        extract_exif_timestamp,
        extract_video_timestamp,
        fallback_timestamp,
        get_media_created_date_time,
        log_summary,
        main,
        parse_filename_date,
        process_folder,
        rename_file,
        rename_files,
        setup_logger,
        should_skip_file,
    )
    # Add successfully imported items to __all__
    __all__.extend([
        "ALLOWED_SUFFIXES", "DEST_PATTERN", "IMG_FORMATS", "MAX_WORKERS",
        "PATTERNS_TO_RENAME", "VIDEO_FORMATS", "FileMetadata", "ProcessingStats",
        "_extract_single_file_metadata", "collect_file_metadata", "convert_files",
        "convert_heic_to_jpg", "convert_mov_to_mp4", "extract_exif_timestamp",
        "extract_video_timestamp", "fallback_timestamp", "get_media_created_date_time",
        "log_summary", "main", "parse_filename_date", "process_folder",
        "rename_file", "rename_files", "setup_logger", "should_skip_file",
    ])
except ImportError as e:  # pragma: no cover
    # If imports fail (e.g., missing dependencies), at least expose __version__
    # Only triggers with missing dependencies - cannot test in normal conditions
    import warnings  # pragma: no cover
    warnings.warn(f"Some bulk_rename functionality may be unavailable: {e}",
                  ImportWarning)  # pragma: no cover
