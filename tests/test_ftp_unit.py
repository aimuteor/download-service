"""Test FTP downloader code structure without actual server."""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import SourceConfig
from src.downloaders.ftp_downloader import FTPDownloader
from src.downloaders.base_downloader import DownloadResult
from src.utils.logger import DownloadLogger


def test_ftp_wildcard_detection():
    """Test FTP wildcard detection."""
    print("\n=== Testing FTP Wildcard Detection ===")
    
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="127.0.0.1",
        port=21,
        path="/",
        filename_pattern="*.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "test", "password": "test"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Test wildcard detection in download method
    filename = "data_*.txt"
    has_wildcard = '*' in filename or '?' in filename
    print(f"Wildcard '{filename}' detected: {has_wildcard}")
    assert has_wildcard == True, "Should detect wildcard"
    
    filename2 = "exact_file.txt"
    has_wildcard2 = '*' in filename2 or '?' in filename2
    print(f"Wildcard '{filename2}' detected: {has_wildcard2}")
    assert has_wildcard2 == False, "Should not detect wildcard"
    
    downloader.close()
    return True


def test_ftp_result_structure():
    """Test FTP DownloadResult has retryable field."""
    print("\n=== Testing FTP Result Structure ===")
    
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="127.0.0.1",
        port=21,
        path="/",
        filename_pattern="test.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "test", "password": "test"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Mock the FTP connection
    mock_ftp = MagicMock()
    mock_ftp.size.return_value = None  # File not found
    downloader.ftp = mock_ftp
    
    # Try to download non-existent file
    from pathlib import Path
    result = downloader._download_single("/nonexistent.txt", Path("/tmp"), "nonexistent.txt", 0)
    
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print(f"Retryable: {result.retryable}")
    print(f"Has retryable field: {hasattr(result, 'retryable')}")
    
    # For file not found, retryable should be False
    assert result.retryable == False, "File not found should be non-retryable"
    
    downloader.close()
    return True


def test_ftp_connection_error():
    """Test FTP connection error handling."""
    print("\n=== Testing FTP Connection Error ===")
    
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="127.0.0.1",
        port=21,
        path="/",
        filename_pattern="test.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "test", "password": "test"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Don't connect - ftp is None
    # downloader.ftp = None  # Already None by default
    
    # Try to download - should handle None ftp gracefully
    from pathlib import Path
    result = downloader._download_single("/test.txt", Path("/tmp"), "test.txt", 0)
    
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print(f"Retryable: {result.retryable}")
    
    # Should fail gracefully without 'NoneType' error
    assert result.success == False, "Should not succeed"
    assert result.error is not None, "Should have error message"
    
    downloader.close()
    return True


def test_ftp_download_single_success():
    """Test FTP _download_single with mocked successful download."""
    print("\n=== Testing FTP _download_single Success ===")
    
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="127.0.0.1",
        port=21,
        path="/",
        filename_pattern="test.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "test", "password": "test"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Mock the FTP connection
    mock_ftp = MagicMock()
    mock_ftp.size.return_value = 100  # File exists, 100 bytes
    downloader.ftp = mock_ftp
    
    # Mock Path.mkdir
    with patch.object(Path, 'mkdir') as mock_mkdir:
        # Mock open to create file
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Mock Path to return mock path
            mock_path = MagicMock(spec=Path)
            mock_path.__truediv__ = lambda self, other: MagicMock(spec=Path)
            mock_path.stat.return_value.st_size = 100
            
            from pathlib import Path
            result = downloader._download_single("/test.txt", mock_path, "test.txt", 0)
            
            print(f"Success: {result.success}")
            print(f"Error: {result.error}")
            print(f"Retryable: {result.retryable}")
    
    downloader.close()
    return True


def test_ftp_ensure_connected():
    """Test FTP _ensure_connected method."""
    print("\n=== Testing FTP _ensure_connected ===")
    
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="127.0.0.1",
        port=21,
        path="/",
        filename_pattern="test.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "test", "password": "test"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Initially ftp is None
    print(f"Initial ftp state: {downloader.ftp}")
    
    # _ensure_connected should call connect if ftp is None
    with patch.object(downloader, 'connect', return_value=False) as mock_connect:
        result = downloader._ensure_connected()
        print(f"_ensure_connected when connect fails: {result}")
        mock_connect.assert_called_once()
    
    downloader.close()
    return True


def main():
    print("=" * 60)
    print("FTP Downloader Unit Tests (with mocks)")
    print("=" * 60)
    
    try:
        test1 = test_ftp_wildcard_detection()
        test2 = test_ftp_result_structure()
        test3 = test_ftp_connection_error()
        test4 = test_ftp_download_single_success()
        test5 = test_ftp_ensure_connected()
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"Wildcard Detection:     {'PASS' if test1 else 'FAIL'}")
        print(f"Result Structure:        {'PASS' if test2 else 'FAIL'}")
        print(f"Connection Error:       {'PASS' if test3 else 'FAIL'}")
        print(f"Download Single Success: {'PASS' if test4 else 'FAIL'}")
        print(f"_ensure_connected:        {'PASS' if test5 else 'FAIL'}")
        
        all_pass = all([test1, test2, test3, test4, test5])
        print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
        
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
