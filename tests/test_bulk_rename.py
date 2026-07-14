"""
Comprehensive unit tests for bulk_rename package.

This module provides unit tests for all functions in the bulk_rename package,
achieving 100% code coverage. Tests are organized by function/class
and use pytest fixtures for common setup.

Run with: pytest test_bulk_rename.py -v --cov=bulk_rename --cov-report=term-missing

Dependencies:
    - pytest>=8.0.0
    - pytest-cov>=4.1.0
    - pytest-mock>=3.12.0
"""
# pylint: disable=redefined-outer-name,too-many-lines,missing-function-docstring

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from PIL import UnidentifiedImageError

from bulk_rename.main import (
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


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_folder(tmp_path):
    """Create a temporary folder with test files."""
    # Create test image files
    (tmp_path / "IMG_1234.jpg").write_bytes(b"fake image data")
    (tmp_path / "IMG_5678.jpg").write_bytes(b"fake image data")
    (tmp_path / "VID_0001.mp4").write_bytes(b"fake video data")
    (tmp_path / "test.heic").write_bytes(b"fake heic data")
    (tmp_path / "video.mov").write_bytes(b"fake mov data")
    (tmp_path / "20231015-0.jpg").write_bytes(b"already renamed")
    (tmp_path / "random.txt").write_bytes(b"not a media file")
    return tmp_path


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = MagicMock(spec=logging.Logger)
    return logger


@pytest.fixture
def sample_metadata():
    """Create sample FileMetadata entries."""
    return [
        FileMetadata(
            original_path=Path("/test/IMG_1234.jpg"),
            timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
            extension=".jpg",
            original_name="IMG_1234.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF DateTimeOriginal",
        ),
        FileMetadata(
            original_path=Path("/test/IMG_5678.jpg"),
            timestamp=datetime(2023, 10, 15, 14, 0, 0, tzinfo=timezone.utc),
            extension=".jpg",
            original_name="IMG_5678.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF DateTimeOriginal",
        ),
    ]


# =============================================================================
# Tests for Constants
# =============================================================================

class TestConstants:
    """Test module-level constants."""

    def test_img_formats_is_frozenset(self):
        assert isinstance(IMG_FORMATS, frozenset)

    def test_img_formats_contains_expected(self):
        assert '.jpg' in IMG_FORMATS
        assert '.jpeg' in IMG_FORMATS
        assert '.png' in IMG_FORMATS
        assert '.heic' in IMG_FORMATS

    def test_video_formats_is_frozenset(self):
        assert isinstance(VIDEO_FORMATS, frozenset)

    def test_video_formats_contains_expected(self):
        assert '.mp4' in VIDEO_FORMATS
        assert '.mov' in VIDEO_FORMATS
        assert '.m4v' in VIDEO_FORMATS

    def test_allowed_suffixes_is_union(self):
        assert ALLOWED_SUFFIXES == IMG_FORMATS | VIDEO_FORMATS

    def test_max_workers_is_positive(self):
        assert MAX_WORKERS > 0
        assert isinstance(MAX_WORKERS, int)

    def test_patterns_to_rename_compiled(self):
        assert len(PATTERNS_TO_RENAME) > 0
        for pattern in PATTERNS_TO_RENAME:
            assert hasattr(pattern, 'search')

    def test_dest_pattern_compiled(self):
        assert hasattr(DEST_PATTERN, 'search')
        match = DEST_PATTERN.search("20231015-0.jpg")
        assert match is not None
        assert match.group(1) == "20231015"


# =============================================================================
# Tests for Dataclasses
# =============================================================================

class TestFileMetadata:
    """Test FileMetadata dataclass."""

    def test_create_with_required_fields(self):
        fm = FileMetadata(
            original_path=Path("/test/file.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="file.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        assert fm.was_converted is False
        assert fm.skip_reason is None

    def test_create_with_all_fields(self):
        fm = FileMetadata(
            original_path=Path("/test/file.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="file.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
            was_converted=True,
            skip_reason="pattern",
        )
        assert fm.was_converted is True
        assert fm.skip_reason == "pattern"

    def test_mutable_fields(self):
        fm = FileMetadata(
            original_path=Path("/test/file.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="file.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        fm.was_converted = True
        fm.skip_reason = "already_renamed"
        assert fm.was_converted is True
        assert fm.skip_reason == "already_renamed"


class TestProcessingStats:
    """Test ProcessingStats dataclass."""

    def test_default_values(self):
        stats = ProcessingStats()
        assert stats.heic_count == 0
        assert stats.mov_count == 0
        assert stats.rename_count == 0
        assert stats.commit is False
        assert stats.elapsed == timedelta()

    def test_custom_values(self):
        stats = ProcessingStats(
            heic_count=5,
            mov_count=3,
            rename_count=10,
            commit=True,
            elapsed=timedelta(seconds=30),
        )
        assert stats.heic_count == 5
        assert stats.mov_count == 3
        assert stats.rename_count == 10
        assert stats.commit is True
        assert stats.elapsed == timedelta(seconds=30)


# =============================================================================
# Tests for setup_logger
# =============================================================================

class TestSetupLogger:
    """Test setup_logger function."""

    def test_returns_logger(self, tmp_path):
        os.chdir(tmp_path)
        logger = setup_logger("test_script")
        assert isinstance(logger, logging.Logger)
        # Clean up handlers
        logger.handlers.clear()

    def test_default_level_is_info(self, tmp_path):
        os.chdir(tmp_path)
        logger = setup_logger("test_script", verbose=False)
        assert logger.level == logging.INFO
        logger.handlers.clear()

    def test_verbose_level_is_debug(self, tmp_path):
        os.chdir(tmp_path)
        logger = setup_logger("test_script", verbose=True)
        assert logger.level == logging.DEBUG
        logger.handlers.clear()

    def test_has_file_and_console_handlers(self, tmp_path):
        os.chdir(tmp_path)
        logger = setup_logger("test_script")
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "TimedRotatingFileHandler" in handler_types
        assert "StreamHandler" in handler_types
        logger.handlers.clear()


# =============================================================================
# Tests for rename_file
# =============================================================================

class TestRenameFile:
    """Test rename_file function."""

    def test_skip_same_path(self, mock_logger, tmp_path):
        src = tmp_path / "test.jpg"
        src.write_bytes(b"test")
        result = rename_file(src, src, commit=True, logger=mock_logger)
        assert result is False
        mock_logger.info.assert_called()

    def test_dry_run_returns_true(self, mock_logger, tmp_path):
        src = tmp_path / "src.jpg"
        dst = tmp_path / "dst.jpg"
        src.write_bytes(b"test")
        result = rename_file(src, dst, commit=False, logger=mock_logger)
        assert result is True
        assert src.exists()  # File not actually renamed
        assert not dst.exists()

    def test_commit_renames_file(self, mock_logger, tmp_path):
        src = tmp_path / "src.jpg"
        dst = tmp_path / "dst.jpg"
        src.write_bytes(b"test")
        result = rename_file(src, dst, commit=True, logger=mock_logger)
        assert result is True
        assert not src.exists()
        assert dst.exists()

    def test_commit_handles_error(self, mock_logger, tmp_path):
        src = tmp_path / "nonexistent.jpg"
        dst = tmp_path / "dst.jpg"
        result = rename_file(src, dst, commit=True, logger=mock_logger)
        assert result is False
        mock_logger.error.assert_called()


# =============================================================================
# Tests for fallback_timestamp
# =============================================================================

class TestFallbackTimestamp:
    """Test fallback_timestamp function."""

    def test_returns_datetime(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")
        result = fallback_timestamp(test_file, mock_logger)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_logs_debug(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")
        fallback_timestamp(test_file, mock_logger)
        mock_logger.debug.assert_called()


# =============================================================================
# Tests for extract_exif_timestamp
# =============================================================================

class TestExtractExifTimestamp:
    """Test extract_exif_timestamp function."""

    def test_extracts_datetime_original(self, mock_logger):
        mock_exif = {36867: "2023:10:15 12:30:45"}
        with patch("bulk_rename.main.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_img.getexif.return_value = mock_exif
            mock_img.__enter__ = Mock(return_value=mock_img)
            mock_img.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_img

            result, source = extract_exif_timestamp(Path("/test.jpg"), mock_logger)
            assert result == datetime(2023, 10, 15, 12, 30, 45, tzinfo=timezone.utc)
            assert source == "EXIF DateTimeOriginal"

    def test_extracts_datetime_tag(self, mock_logger):
        mock_exif = {306: "2023:10:15 12:30:45"}
        with patch("bulk_rename.main.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_img.getexif.return_value = mock_exif
            mock_img.__enter__ = Mock(return_value=mock_img)
            mock_img.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_img

            result, source = extract_exif_timestamp(Path("/test.jpg"), mock_logger)
            assert result == datetime(2023, 10, 15, 12, 30, 45, tzinfo=timezone.utc)
            assert source == "EXIF DateTime"

    def test_no_exif_uses_fallback(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")
        mock_exif = {}
        with patch("bulk_rename.main.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_img.getexif.return_value = mock_exif
            mock_img.__enter__ = Mock(return_value=mock_img)
            mock_img.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_img

            result, source = extract_exif_timestamp(test_file, mock_logger)
            assert isinstance(result, datetime)
            assert source == "fallback"

    def test_unidentified_image_uses_fallback(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")

        with patch("bulk_rename.main.Image.open") as mock_open:
            mock_open.side_effect = UnidentifiedImageError("test")
            result, source = extract_exif_timestamp(test_file, mock_logger)
            assert isinstance(result, datetime)
            assert source == "fallback"
            mock_logger.error.assert_called()

    def test_os_error_uses_fallback(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")

        with patch("bulk_rename.main.Image.open") as mock_open:
            mock_open.side_effect = OSError("test")
            result, source = extract_exif_timestamp(test_file, mock_logger)
            assert isinstance(result, datetime)
            assert source == "fallback"


# =============================================================================
# Tests for extract_video_timestamp
# =============================================================================

class TestExtractVideoTimestamp:
    """Test extract_video_timestamp function."""

    def test_propsys_success(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"test")
        expected_dt = datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Mock both WINDOWS_AVAILABLE and propsys for cross-platform testing
        with patch("bulk_rename.main.WINDOWS_AVAILABLE", True):
            with patch("bulk_rename.main.propsys") as mock_propsys_module:
                mock_props = MagicMock()
                mock_value = MagicMock()
                mock_value.GetValue.return_value = expected_dt
                mock_props.GetValue.return_value = mock_value
                mock_propsys_module.SHGetPropertyStoreFromParsingName.return_value = mock_props

                # Mock pscon module as well
                with patch("bulk_rename.main.pscon") as mock_pscon:
                    mock_pscon.PKEY_Media_DateEncoded = "mock_key"

                    result, source = extract_video_timestamp(test_file, mock_logger)
                    assert result == expected_dt
                    assert source == "propsys"

    def test_propsys_fails_ffprobe_success(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"test")

        # Mock WINDOWS_AVAILABLE and propsys for cross-platform testing
        with patch("bulk_rename.main.WINDOWS_AVAILABLE", True):
            with patch("bulk_rename.main.propsys") as mock_propsys_module:
                mock_propsys_module.SHGetPropertyStoreFromParsingName.side_effect = (
                    OSError("propsys failed")
                )

                with patch("bulk_rename.main.pscon") as mock_pscon:
                    mock_pscon.PKEY_Media_DateEncoded = "mock_key"

                    ffprobe_output = json.dumps({
                        "format": {"tags": {"creation_time": "2023-10-15T12:00:00Z"}}
                    })
                    with patch("bulk_rename.main.subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(stdout=ffprobe_output, returncode=0)

                        result, source = extract_video_timestamp(test_file, mock_logger)
                        assert result == datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
                        assert source == "ffprobe"

    def test_both_fail_uses_fallback(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"test")

        # Mock WINDOWS_AVAILABLE and propsys for cross-platform testing
        with patch("bulk_rename.main.WINDOWS_AVAILABLE", True):
            with patch("bulk_rename.main.propsys") as mock_propsys_module:
                mock_propsys_module.SHGetPropertyStoreFromParsingName.side_effect = (
                    OSError("propsys failed")
                )

                with patch("bulk_rename.main.pscon") as mock_pscon:
                    mock_pscon.PKEY_Media_DateEncoded = "mock_key"

                    with patch("bulk_rename.main.subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(stdout="{}", returncode=0)

                        result, source = extract_video_timestamp(test_file, mock_logger)
                        assert isinstance(result, datetime)
                        assert source == "fallback"

    def test_ffprobe_with_offset_timestamp(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"test")

        # Mock WINDOWS_AVAILABLE and propsys for cross-platform testing
        with patch("bulk_rename.main.WINDOWS_AVAILABLE", True):
            with patch("bulk_rename.main.propsys") as mock_propsys_module:
                mock_propsys_module.SHGetPropertyStoreFromParsingName.side_effect = (
                    OSError("propsys failed")
                )

                with patch("bulk_rename.main.pscon") as mock_pscon:
                    mock_pscon.PKEY_Media_DateEncoded = "mock_key"

                    ffprobe_output = json.dumps({
                        "format": {"tags": {"creation_time": "2023-10-15T12:00:00+05:00"}}
                    })
                    with patch("bulk_rename.main.subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(stdout=ffprobe_output, returncode=0)

                        result, source = extract_video_timestamp(test_file, mock_logger)
                        assert result.tzinfo == timezone.utc
                        assert source == "ffprobe"

    def test_non_windows_platform_uses_ffprobe(self, mock_logger, tmp_path):
        """Test that non-Windows platforms skip propsys and use ffprobe directly."""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"test")

        # Mock WINDOWS_AVAILABLE as False to simulate non-Windows platform
        with patch("bulk_rename.main.WINDOWS_AVAILABLE", False):
            ffprobe_output = json.dumps({
                "format": {"tags": {"creation_time": "2023-10-15T12:00:00Z"}}
            })
            with patch("bulk_rename.main.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout=ffprobe_output, returncode=0)

                result, source = extract_video_timestamp(test_file, mock_logger)
                assert result == datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
                assert source == "ffprobe"
                # Verify that debug log was called about skipping propsys
                mock_logger.debug.assert_any_call(
                    "%s skipping propsys (not available on this platform)",
                    test_file.name
                )


# =============================================================================
# Tests for get_media_created_date_time
# =============================================================================

class TestGetMediaCreatedDateTime:
    """Test get_media_created_date_time function."""

    def test_routes_video_formats(self, mock_logger, tmp_path):
        for ext in ['.mp4', '.mov', '.m4v']:
            test_file = tmp_path / f"test{ext}"
            test_file.write_bytes(b"test")

            with patch("bulk_rename.main.extract_video_timestamp") as mock_extract:
                mock_extract.return_value = (datetime.now(timezone.utc), "propsys")
                get_media_created_date_time(test_file, mock_logger)
                mock_extract.assert_called_once()

    def test_routes_image_formats(self, mock_logger, tmp_path):
        for ext in ['.jpg', '.jpeg', '.png', '.heic']:
            test_file = tmp_path / f"test{ext}"
            test_file.write_bytes(b"test")

            with patch("bulk_rename.main.extract_exif_timestamp") as mock_extract:
                mock_extract.return_value = (datetime.now(timezone.utc), "EXIF")
                get_media_created_date_time(test_file, mock_logger)
                mock_extract.assert_called()


# =============================================================================
# Tests for _extract_single_file_metadata
# =============================================================================

class TestExtractSingleFileMetadata:
    """Test _extract_single_file_metadata function."""

    def test_returns_none_for_unsupported_suffix(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test")
        result = _extract_single_file_metadata(test_file, mock_logger)
        assert result is None

    def test_returns_metadata_for_supported_suffix(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")

        with patch("bulk_rename.main.get_media_created_date_time") as mock_get:
            mock_get.return_value = (datetime.now(timezone.utc), "EXIF")
            result = _extract_single_file_metadata(test_file, mock_logger)
            assert isinstance(result, FileMetadata)
            assert result.extension == ".jpg"

    def test_metadata_reliable_for_exif(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")

        with patch("bulk_rename.main.get_media_created_date_time") as mock_get:
            mock_get.return_value = (datetime.now(timezone.utc), "EXIF DateTimeOriginal")
            result = _extract_single_file_metadata(test_file, mock_logger)
            assert result.metadata_reliable is True

    def test_metadata_unreliable_for_fallback(self, mock_logger, tmp_path):
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"test")

        with patch("bulk_rename.main.get_media_created_date_time") as mock_get:
            mock_get.return_value = (datetime.now(timezone.utc), "fallback")
            result = _extract_single_file_metadata(test_file, mock_logger)
            assert result.metadata_reliable is False


# =============================================================================
# Tests for collect_file_metadata
# =============================================================================

class TestCollectFileMetadata:
    """Test collect_file_metadata function."""

    def test_collects_metadata_parallel(self, mock_logger, tmp_path):
        files = []
        for i in range(5):
            f = tmp_path / f"IMG_{i:04d}.jpg"
            f.write_bytes(b"test")
            files.append(f)

        with patch("bulk_rename.main.get_media_created_date_time") as mock_get:
            mock_get.return_value = (datetime.now(timezone.utc), "EXIF")
            result = collect_file_metadata(files, mock_logger)
            assert len(result) == 5

    def test_filters_unsupported_files(self, mock_logger, tmp_path):
        jpg_file = tmp_path / "test.jpg"
        txt_file = tmp_path / "test.txt"
        jpg_file.write_bytes(b"test")
        txt_file.write_bytes(b"test")

        with patch("bulk_rename.main.get_media_created_date_time") as mock_get:
            mock_get.return_value = (datetime.now(timezone.utc), "EXIF")
            result = collect_file_metadata([jpg_file, txt_file], mock_logger)
            assert len(result) == 1


# =============================================================================
# Tests for convert_heic_to_jpg
# =============================================================================

class TestConvertHeicToJpg:
    """Test convert_heic_to_jpg function."""

    def test_skip_if_dst_exists(self, mock_logger, tmp_path):
        src = tmp_path / "test.heic"
        dst = tmp_path / "test.jpg"
        src.write_bytes(b"heic")
        dst.write_bytes(b"jpg")

        result = convert_heic_to_jpg(src, commit=True, logger=mock_logger)
        assert result == dst

    def test_dry_run_returns_dst_path(self, mock_logger, tmp_path):
        src = tmp_path / "test.heic"
        src.write_bytes(b"heic")

        result = convert_heic_to_jpg(src, commit=False, logger=mock_logger)
        assert result == tmp_path / "test.jpg"
        mock_logger.info.assert_called()

    def test_commit_calls_magick(self, mock_logger, tmp_path):
        src = tmp_path / "test.heic"
        dst = tmp_path / "test.jpg"
        src.write_bytes(b"heic")

        def create_dst(*_args, **_kwargs):
            dst.write_bytes(b"jpg")
            return MagicMock(returncode=0)

        with patch("bulk_rename.main.subprocess.run", side_effect=create_dst) as mock_run:
            with patch("bulk_rename.main.send2trash") as mock_trash:
                result = convert_heic_to_jpg(src, commit=True, logger=mock_logger)
                assert result == dst
                mock_run.assert_called_once()
                mock_trash.assert_called_once()

    def test_commit_handles_conversion_failure(self, mock_logger, tmp_path):
        src = tmp_path / "test.heic"
        src.write_bytes(b"heic")

        with patch("bulk_rename.main.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "magick")
            result = convert_heic_to_jpg(src, commit=True, logger=mock_logger)
            assert result is None
            mock_logger.error.assert_called()

    def test_handles_trash_failure(self, mock_logger, tmp_path):
        src = tmp_path / "test.heic"
        dst = tmp_path / "test.jpg"
        src.write_bytes(b"heic")

        def create_dst(*_args, **_kwargs):
            dst.write_bytes(b"jpg")
            return MagicMock(returncode=0)

        with patch("bulk_rename.main.subprocess.run", side_effect=create_dst):
            with patch("bulk_rename.main.send2trash") as mock_trash:
                mock_trash.side_effect = OSError("trash failed")
                result = convert_heic_to_jpg(src, commit=True, logger=mock_logger)
                assert result == dst
                mock_logger.error.assert_called()

    def test_dst_not_created_after_conversion(self, mock_logger, tmp_path):
        src = tmp_path / "test.heic"
        src.write_bytes(b"heic")

        with patch("bulk_rename.main.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Don't create dst file
            result = convert_heic_to_jpg(src, commit=True, logger=mock_logger)
            assert result is None


# =============================================================================
# Tests for convert_mov_to_mp4
# =============================================================================

class TestConvertMovToMp4:
    """Test convert_mov_to_mp4 function."""

    def test_skip_if_dst_exists(self, mock_logger, tmp_path):
        src = tmp_path / "test.mov"
        dst = tmp_path / "test.mp4"
        src.write_bytes(b"mov")
        dst.write_bytes(b"mp4")

        result = convert_mov_to_mp4(src, commit=True, logger=mock_logger)
        assert result == dst

    def test_dry_run_logs_command(self, mock_logger, tmp_path):
        src = tmp_path / "test.mov"
        src.write_bytes(b"mov")

        result = convert_mov_to_mp4(src, commit=False, logger=mock_logger)
        assert result == tmp_path / "test.mp4"

    def test_commit_calls_ffmpeg(self, mock_logger, tmp_path):
        src = tmp_path / "test.mov"
        dst = tmp_path / "test.mp4"
        src.write_bytes(b"mov")

        def create_dst(*_args, **_kwargs):
            dst.write_bytes(b"x" * 200000)
            return MagicMock(returncode=0)

        with patch("bulk_rename.main.subprocess.run", side_effect=create_dst) as mock_run:
            with patch("bulk_rename.main.send2trash") as _mock_trash:
                result = convert_mov_to_mp4(src, commit=True, logger=mock_logger)
                assert result == dst
                mock_run.assert_called_once()

    def test_commit_handles_ffmpeg_failure(self, mock_logger, tmp_path):
        src = tmp_path / "test.mov"
        src.write_bytes(b"mov")

        with patch("bulk_rename.main.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr=b"error")
            result = convert_mov_to_mp4(src, commit=True, logger=mock_logger)
            assert result is None

    def test_handles_small_output_file(self, mock_logger, tmp_path):
        src = tmp_path / "test.mov"
        dst = tmp_path / "test.mp4"
        src.write_bytes(b"mov")

        def create_small_dst(*_args, **_kwargs):
            dst.write_bytes(b"small")  # Less than 100000 bytes
            return MagicMock(returncode=0, stderr=b"")

        with patch("bulk_rename.main.subprocess.run", side_effect=create_small_dst):
            result = convert_mov_to_mp4(src, commit=True, logger=mock_logger)
            assert result is None


# =============================================================================
# Tests for convert_files
# =============================================================================

class TestConvertFiles:
    """Test convert_files function."""

    def test_converts_heic_files(self, mock_logger, tmp_path):
        heic_file = tmp_path / "test.heic"
        heic_file.write_bytes(b"heic")

        metadata = [
            FileMetadata(
                original_path=heic_file,
                timestamp=datetime.now(timezone.utc),
                extension=".heic",
                original_name="test.heic",
                metadata_reliable=True,
                timestamp_source="EXIF",
            )
        ]

        with patch("bulk_rename.main.convert_heic_to_jpg") as mock_convert:
            mock_convert.return_value = tmp_path / "test.jpg"
            heic_count, mov_count = convert_files(metadata, commit=True, logger=mock_logger)
            assert heic_count == 1
            assert mov_count == 0
            assert metadata[0].was_converted is True
            assert metadata[0].extension == ".jpg"

    def test_converts_mov_files(self, mock_logger, tmp_path):
        mov_file = tmp_path / "test.mov"
        mov_file.write_bytes(b"mov")

        metadata = [
            FileMetadata(
                original_path=mov_file,
                timestamp=datetime.now(timezone.utc),
                extension=".mov",
                original_name="test.mov",
                metadata_reliable=True,
                timestamp_source="propsys",
            )
        ]

        with patch("bulk_rename.main.convert_mov_to_mp4") as mock_convert:
            result_path = tmp_path / "test.mp4"
            result_path.write_bytes(b"mp4")
            mock_convert.return_value = result_path
            heic_count, mov_count = convert_files(metadata, commit=True, logger=mock_logger)
            assert heic_count == 0
            assert mov_count == 1
            assert metadata[0].was_converted is True

    def test_skips_other_formats(self, mock_logger, tmp_path):
        jpg_file = tmp_path / "test.jpg"
        jpg_file.write_bytes(b"jpg")

        metadata = [
            FileMetadata(
                original_path=jpg_file,
                timestamp=datetime.now(timezone.utc),
                extension=".jpg",
                original_name="test.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            )
        ]

        heic_count, mov_count = convert_files(metadata, commit=True, logger=mock_logger)
        assert heic_count == 0
        assert mov_count == 0
        assert metadata[0].was_converted is False

    def test_no_convert_flag_skips_conversions(self, mock_logger, tmp_path):
        heic_file = tmp_path / "test.heic"
        mov_file = tmp_path / "test.mov"
        heic_file.write_bytes(b"heic")
        mov_file.write_bytes(b"mov")

        metadata = [
            FileMetadata(
                original_path=heic_file,
                timestamp=datetime.now(timezone.utc),
                extension=".heic",
                original_name="test.heic",
                metadata_reliable=True,
                timestamp_source="EXIF",
            ),
            FileMetadata(
                original_path=mov_file,
                timestamp=datetime.now(timezone.utc),
                extension=".mov",
                original_name="test.mov",
                metadata_reliable=True,
                timestamp_source="propsys",
            )
        ]

        with patch("bulk_rename.main.convert_heic_to_jpg") as mock_heic:
            with patch("bulk_rename.main.convert_mov_to_mp4") as mock_mov:
                heic_count, mov_count = convert_files(
                    metadata, commit=True, logger=mock_logger, no_convert=True
                )
                assert heic_count == 0
                assert mov_count == 0
                assert metadata[0].was_converted is False
                assert metadata[1].was_converted is False
                mock_heic.assert_not_called()
                mock_mov.assert_not_called()
                mock_logger.info.assert_called_with(
                    "Skipping Apple file conversion (--no-convert flag set)"
                )


# =============================================================================
# Tests for parse_filename_date
# =============================================================================

class TestParseFilenameDate:
    """Test parse_filename_date function."""

    def test_parses_valid_date(self):
        result = parse_filename_date("20231015-0.jpg")
        assert result == datetime(2023, 10, 15, tzinfo=timezone.utc)

    def test_parses_date_with_sequence(self):
        result = parse_filename_date("20231015-123.jpg")
        assert result == datetime(2023, 10, 15, tzinfo=timezone.utc)

    def test_returns_none_for_no_match(self):
        result = parse_filename_date("IMG_1234.jpg")
        assert result is None

    def test_returns_none_for_invalid_date(self):
        result = parse_filename_date("99991399-0.jpg")
        assert result is None


# =============================================================================
# Tests for should_skip_file
# =============================================================================

class TestShouldSkipFile:
    """Test should_skip_file function."""

    def test_skip_no_matching_pattern(self, mock_logger):
        entry = FileMetadata(
            original_path=Path("/test/random_file.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="random_file.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        should_skip, extra_text, reason = should_skip_file(entry, mock_logger)
        assert should_skip is True
        assert extra_text == ""
        assert reason == "pattern"

    def test_no_skip_img_pattern(self, mock_logger):
        entry = FileMetadata(
            original_path=Path("/test/IMG_1234.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="IMG_1234.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        should_skip, _extra_text, reason = should_skip_file(entry, mock_logger)
        assert should_skip is False
        assert reason is None

    def test_skip_already_renamed_unreliable_metadata(self, mock_logger):
        entry = FileMetadata(
            original_path=Path("/test/20231015-0.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="20231015-0.jpg",
            metadata_reliable=False,
            timestamp_source="fallback",
        )
        should_skip, _extra_text, reason = should_skip_file(entry, mock_logger)
        assert should_skip is True
        assert reason == "already_renamed"

    def test_skip_already_renamed_matching_date(self, mock_logger):
        entry = FileMetadata(
            original_path=Path("/test/20231015-0.jpg"),
            timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
            extension=".jpg",
            original_name="20231015-0.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        should_skip, _extra_text, reason = should_skip_file(entry, mock_logger)
        assert should_skip is True
        assert reason == "already_renamed"

    def test_no_skip_date_mismatch(self, mock_logger):
        entry = FileMetadata(
            original_path=Path("/test/20231020-0.jpg"),
            timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
            extension=".jpg",
            original_name="20231020-0.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        should_skip, _extra_text, reason = should_skip_file(entry, mock_logger)
        assert should_skip is False
        assert reason is None

    def test_extracts_extra_text_from_pattern(self, mock_logger):
        entry = FileMetadata(
            original_path=Path("/test/IMG_1234_extra.jpg"),
            timestamp=datetime.now(timezone.utc),
            extension=".jpg",
            original_name="IMG_1234_extra.jpg",
            metadata_reliable=True,
            timestamp_source="EXIF",
        )
        should_skip, extra_text, _reason = should_skip_file(entry, mock_logger)
        assert should_skip is False
        assert "_extra.jpg" in extra_text


# =============================================================================
# Tests for rename_files
# =============================================================================

class TestRenameFiles:
    """Test rename_files function."""

    def test_renames_files_in_order(self, mock_logger, tmp_path):
        file1 = tmp_path / "IMG_0001.jpg"
        file2 = tmp_path / "IMG_0002.jpg"
        file1.write_bytes(b"test1")
        file2.write_bytes(b"test2")

        metadata = [
            FileMetadata(
                original_path=file1,
                timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
                extension=".jpg",
                original_name="IMG_0001.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            ),
            FileMetadata(
                original_path=file2,
                timestamp=datetime(2023, 10, 15, 14, 0, 0, tzinfo=timezone.utc),
                extension=".jpg",
                original_name="IMG_0002.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            ),
        ]

        count = rename_files(metadata, tmp_path, commit=True, logger=mock_logger)
        assert count == 2
        assert (tmp_path / "20231015-0.jpg").exists()
        assert (tmp_path / "20231015-1.jpg").exists()

    def test_handles_collision(self, mock_logger, tmp_path):
        file1 = tmp_path / "IMG_0001.jpg"
        existing = tmp_path / "20231015-0.jpg"
        file1.write_bytes(b"test1")
        existing.write_bytes(b"existing")

        metadata = [
            FileMetadata(
                original_path=file1,
                timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
                extension=".jpg",
                original_name="IMG_0001.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            ),
        ]

        count = rename_files(metadata, tmp_path, commit=True, logger=mock_logger)
        assert count == 1
        assert (tmp_path / "20231015-1.jpg").exists()

    def test_sets_skip_reason(self, mock_logger, tmp_path):
        file1 = tmp_path / "random.jpg"
        file1.write_bytes(b"test")

        metadata = [
            FileMetadata(
                original_path=file1,
                timestamp=datetime.now(timezone.utc),
                extension=".jpg",
                original_name="random.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            ),
        ]

        rename_files(metadata, tmp_path, commit=True, logger=mock_logger)
        assert metadata[0].skip_reason == "pattern"

    def test_dry_run(self, mock_logger, tmp_path):
        file1 = tmp_path / "IMG_0001.jpg"
        file1.write_bytes(b"test")

        metadata = [
            FileMetadata(
                original_path=file1,
                timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
                extension=".jpg",
                original_name="IMG_0001.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            ),
        ]

        count = rename_files(metadata, tmp_path, commit=False, logger=mock_logger)
        assert count == 1
        assert file1.exists()  # Not actually renamed


# =============================================================================
# Tests for log_summary
# =============================================================================

class TestLogSummary:
    """Test log_summary function."""

    def test_logs_all_stats(self, mock_logger):
        metadata = [
            FileMetadata(
                original_path=Path("/test/file.jpg"),
                timestamp=datetime.now(timezone.utc),
                extension=".jpg",
                original_name="file.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
                was_converted=True,
                skip_reason=None,
            ),
            FileMetadata(
                original_path=Path("/test/file2.jpg"),
                timestamp=datetime.now(timezone.utc),
                extension=".jpg",
                original_name="file2.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
                skip_reason="pattern",
            ),
            FileMetadata(
                original_path=Path("/test/file3.jpg"),
                timestamp=datetime.now(timezone.utc),
                extension=".jpg",
                original_name="file3.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
                skip_reason="already_renamed",
            ),
        ]
        stats = ProcessingStats(
            heic_count=2,
            mov_count=1,
            rename_count=5,
            commit=True,
            elapsed=timedelta(seconds=10),
        )

        log_summary(metadata, stats, mock_logger)
        assert mock_logger.info.call_count >= 5

    def test_dry_run_message(self, mock_logger):
        stats = ProcessingStats(rename_count=5, commit=False)
        log_summary([], stats, mock_logger)
        # Check that "Would rename" message was logged
        calls = [str(c) for c in mock_logger.info.call_args_list]
        assert any("Would rename" in c for c in calls)

    def test_no_convert_flag_skips_conversion_logs(self, mock_logger):
        metadata = [
            FileMetadata(
                original_path=Path("/test/file.jpg"),
                timestamp=datetime.now(timezone.utc),
                extension=".jpg",
                original_name="file.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
            )
        ]
        stats = ProcessingStats(
            heic_count=0,
            mov_count=0,
            rename_count=1,
            commit=True,
            no_convert=True,
            elapsed=timedelta(seconds=5),
        )

        log_summary(metadata, stats, mock_logger)

        # Verify conversion stats are NOT logged
        calls = [str(c) for c in mock_logger.info.call_args_list]
        assert not any("Converted" in c for c in calls)
        assert not any(".heic files to .jpg" in c for c in calls)
        assert not any(".mov files to .mp4" in c for c in calls)
        assert not any("were converted files" in c for c in calls)

        # Verify standard stats are still logged
        assert any("Evaluated" in c for c in calls)
        assert any("Renamed" in c for c in calls)


# =============================================================================
# Tests for process_folder
# =============================================================================

class TestProcessFolder:
    """Test process_folder function."""

    def test_processes_folder(self, mock_logger, tmp_path):
        jpg_file = tmp_path / "IMG_1234.jpg"
        jpg_file.write_bytes(b"test")

        with patch("bulk_rename.main.collect_file_metadata") as mock_collect:
            mock_collect.return_value = [
                FileMetadata(
                    original_path=jpg_file,
                    timestamp=datetime(2023, 10, 15, tzinfo=timezone.utc),
                    extension=".jpg",
                    original_name="IMG_1234.jpg",
                    metadata_reliable=True,
                    timestamp_source="EXIF",
                )
            ]
            with patch("bulk_rename.main.convert_files") as mock_convert:
                mock_convert.return_value = (0, 0)
                with patch("bulk_rename.main.rename_files") as mock_rename:
                    mock_rename.return_value = 1
                    result = process_folder(str(tmp_path), commit=False, logger=mock_logger)
                    assert result == 0

    def test_filters_by_suffix(self, mock_logger, tmp_path):
        jpg_file = tmp_path / "test.jpg"
        txt_file = tmp_path / "test.txt"
        jpg_file.write_bytes(b"jpg")
        txt_file.write_bytes(b"txt")

        with patch("bulk_rename.main.collect_file_metadata") as mock_collect:
            mock_collect.return_value = []
            process_folder(str(tmp_path), commit=False, logger=mock_logger)
            # Check that only jpg was passed
            call_args = mock_collect.call_args[1]["file_list"]
            assert len(call_args) == 1
            assert call_args[0].suffix == ".jpg"


# =============================================================================
# Tests for main
# =============================================================================

class TestMain:
    """Test main function."""

    def test_invalid_folder_exits(self):
        with patch("sys.argv", ["bulk-rename", "--folder", "/nonexistent/path"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_valid_folder_runs(self, tmp_path):
        with patch("sys.argv", ["bulk-rename", "--folder", str(tmp_path)]):
            with patch("bulk_rename.main.process_folder") as mock_process:
                mock_process.return_value = 0
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

    def test_verbose_flag(self, tmp_path):
        with patch("sys.argv", ["bulk-rename", "--folder", str(tmp_path), "-v"]):
            with patch("bulk_rename.main.process_folder") as mock_process:
                mock_process.return_value = 0
                with patch("bulk_rename.main.setup_logger") as mock_logger:
                    mock_logger.return_value = MagicMock()
                    with pytest.raises(SystemExit):
                        main()
                    mock_logger.assert_called_with(
                        "bulk-rename", verbose=True
                    )

    def test_commit_flag(self, tmp_path):
        with patch("sys.argv", ["bulk-rename", "--folder", str(tmp_path), "-c"]):
            with patch("bulk_rename.main.process_folder") as mock_process:
                mock_process.return_value = 0
                with pytest.raises(SystemExit):
                    main()
                mock_process.assert_called_once()
                assert mock_process.call_args[0][1] is True  # commit=True

    def test_no_convert_flag(self, tmp_path):
        with patch("sys.argv", ["bulk-rename", "--folder", str(tmp_path), "--no-convert"]):
            with patch("bulk_rename.main.process_folder") as mock_process:
                mock_process.return_value = 0
                with pytest.raises(SystemExit):
                    main()
                mock_process.assert_called_once()
                assert mock_process.call_args[0][3] is True  # no_convert=True


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================

class TestAdditionalCoverage:
    """Tests for additional coverage of edge cases."""

    def test_ffprobe_called_process_error(self, mock_logger, tmp_path):
        """Test subprocess.CalledProcessError in ffprobe (lines 265-266)."""
        test_file = tmp_path / "test.mp4"
        test_file.write_bytes(b"test")

        # Mock WINDOWS_AVAILABLE and propsys for cross-platform testing
        with patch("bulk_rename.main.WINDOWS_AVAILABLE", True):
            with patch("bulk_rename.main.propsys") as mock_propsys_module:
                mock_propsys_module.SHGetPropertyStoreFromParsingName.side_effect = (
                    OSError("propsys failed")
                )

                with patch("bulk_rename.main.pscon") as mock_pscon:
                    mock_pscon.PKEY_Media_DateEncoded = "mock_key"

                    with patch("bulk_rename.main.subprocess.run") as mock_run:
                        mock_run.side_effect = subprocess.CalledProcessError(1, "ffprobe")
                        result, source = extract_video_timestamp(test_file, mock_logger)
                        assert isinstance(result, datetime)
                        assert source == "fallback"
                        mock_logger.warning.assert_called()

    def test_mov_trash_failure(self, mock_logger, tmp_path):
        """Test OSError when trashing MOV file (lines 409-410)."""
        src = tmp_path / "test.mov"
        dst = tmp_path / "test.mp4"
        src.write_bytes(b"mov")

        def create_large_dst(*_args, **_kwargs):
            dst.write_bytes(b"x" * 200000)
            return MagicMock(returncode=0)

        with patch("bulk_rename.main.subprocess.run", side_effect=create_large_dst):
            with patch("bulk_rename.main.send2trash") as mock_trash:
                mock_trash.side_effect = OSError("trash failed")
                result = convert_mov_to_mp4(src, commit=True, logger=mock_logger)
                # Should still return dst path even if trash fails
                assert result == dst
                mock_logger.error.assert_called()

    def test_converted_file_debug_log(self, mock_logger, tmp_path):
        """Test debug log for converted files (line 534)."""
        file1 = tmp_path / "IMG_0001.jpg"
        file1.write_bytes(b"test")

        metadata = [
            FileMetadata(
                original_path=file1,
                timestamp=datetime(2023, 10, 15, 12, 0, 0, tzinfo=timezone.utc),
                extension=".jpg",
                original_name="IMG_0001.jpg",
                metadata_reliable=True,
                timestamp_source="EXIF",
                was_converted=True,  # Mark as converted
            ),
        ]

        rename_files(metadata, tmp_path, commit=True, logger=mock_logger)
        # Check that debug was called for converted file
        debug_calls = [str(c) for c in mock_logger.debug.call_args_list]
        assert any("Converted file" in c for c in debug_calls)

    def test_unknown_file_type_uses_birthtime(self, mock_logger, tmp_path):
        """Test birthtime path for unknown file types (line 298)."""
        # Create a file with an extension not in IMG_FORMATS or VIDEO_FORMATS
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"test")

        # Create a mock stat_result with st_birthtime
        mock_stat_result = MagicMock()
        mock_stat_result.st_birthtime = 1234567890.0

        # Patch the stat method on pathlib.Path
        with patch.object(Path, 'stat', return_value=mock_stat_result):
            # Call get_media_created_date_time
            result, source = get_media_created_date_time(test_file, mock_logger)
            assert isinstance(result, datetime)
            assert source == "birthtime"
            # Verify the timestamp matches our mock
            expected = datetime.fromtimestamp(1234567890.0, tz=timezone.utc)
            assert result == expected

    def test_unknown_file_type_without_birthtime(self, mock_logger, tmp_path):
        """Test fallback when st_birthtime is not available (line 299)."""
        # Create a file with an extension not in IMG_FORMATS or VIDEO_FORMATS
        test_file = tmp_path / "test.xyz"
        test_file.write_bytes(b"test")

        # Mock stat to not have st_birthtime attribute
        with patch("bulk_rename.main.Path.stat") as mock_stat:
            # Create a stat_result without st_birthtime
            mock_stat_result = MagicMock()
            del mock_stat_result.st_birthtime  # Ensure attribute doesn't exist
            mock_stat_result.st_mtime = 1234567890.0
            mock_stat.return_value = mock_stat_result

            # Call get_media_created_date_time
            result, source = get_media_created_date_time(test_file, mock_logger)
            assert isinstance(result, datetime)
            assert source == "fallback"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_folder(self, mock_logger, tmp_path):
        with patch("bulk_rename.main.collect_file_metadata") as mock_collect:
            mock_collect.return_value = []
            result = process_folder(str(tmp_path), commit=False, logger=mock_logger)
            assert result == 0

    def test_pattern_matching_all_types(self, mock_logger):
        patterns = [
            ("IMG_1234.jpg", True),
            ("IM_1234.jpg", True),
            ("IMG_E1234.jpg", True),
            ("VD_1234.jpg", True),
            ("1234.jpg", True),
            ("1234_5678.jpg", True),
            ("ABCD1234.jpg", True),
            ("BulkPics 1234.jpg", True),
            ("PA123456.jpg", True),
            ("P1234567.jpg", True),
            ("20231015-0.jpg", True),
            ("random.jpg", False),
        ]
        for filename, should_match in patterns:
            entry = FileMetadata(
                original_path=Path(f"/test/{filename}"),
                timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc),
                extension=".jpg",
                original_name=filename,
                metadata_reliable=True,
                timestamp_source="EXIF",
            )
            _skip, _, reason = should_skip_file(entry, mock_logger)
            if should_match:
                assert reason != "pattern", f"{filename} should match a pattern"
            else:
                assert reason == "pattern", f"{filename} should not match any pattern"

    def test_case_insensitive_suffix(self, mock_logger, tmp_path):
        file_upper = tmp_path / "test.JPG"
        file_upper.write_bytes(b"test")

        with patch("bulk_rename.main.get_media_created_date_time") as mock_get:
            mock_get.return_value = (datetime.now(timezone.utc), "EXIF")
            result = _extract_single_file_metadata(file_upper, mock_logger)
            assert result is not None
            assert result.extension == ".jpg"
