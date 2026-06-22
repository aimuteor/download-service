"""Test script for HTTP and FTP downloaders."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import ConfigLoader, SourceConfig
from src.downloaders.http_downloader import HTTPDownloader
from src.downloaders.ftp_downloader import FTPDownloader
from src.utils.logger import DownloadLogger


def test_http_downloader():
    """Test HTTP downloader initialization and connection."""
    print("\n=== Testing HTTP Downloader ===")
    
    # Create a test source config
    source = SourceConfig(
        name="test_http",
        type="http",
        protocol="https",
        host="httpbin.org",
        port=443,
        path="/",
        filename_pattern="test.txt",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_http", "./logs", "DEBUG")
    downloader = HTTPDownloader(source, logger, timeout=10)
    
    # Test connection
    print(f"Testing connection to {source.host}...")
    result = downloader.test_connection()
    print(f"Connection test: {'PASS' if result else 'FAIL'}")
    
    # Test build_url
    url = downloader.build_url("test.txt")
    print(f"Built URL: {url}")
    
    # Close
    downloader.close()
    print("HTTP Downloader test complete")


def test_ftp_downloader():
    """Test FTP downloader initialization and connection."""
    print("\n=== Testing FTP Downloader ===")
    
    # Create a test source config
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="ftp.debian.org",
        port=21,
        path="/debian",
        filename_pattern="*.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "anonymous", "password": "anonymous@example.com"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Test connection
    print(f"Testing connection to {source.host}...")
    try:
        result = downloader.test_connection()
        print(f"Connection test: {'PASS' if result else 'FAIL'}")
    except Exception as e:
        print(f"Connection test FAIL: {e}")
    
    # Test build_url
    url = downloader.build_url("test.txt")
    print(f"Built URL: {url}")
    
    # Test list_files
    print("Testing list_files...")
    try:
        files = downloader.list_files("*.txt")
        print(f"Found {len(files)} matching files")
    except Exception as e:
        print(f"list_files FAIL: {e}")
    
    # Close
    downloader.close()
    print("FTP Downloader test complete")


def test_ftp_wildcard():
    """Test FTP wildcard handling."""
    print("\n=== Testing FTP Wildcard ===")
    
    source = SourceConfig(
        name="test_ftp_wildcard",
        type="ftp",
        host="ftp.debian.org",
        port=21,
        path="/debian",
        filename_pattern="*.txt",
        method="GET",
        force_download=False,
        auth_credentials={"username": "anonymous", "password": "anonymous@example.com"},
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_wildcard", "./logs", "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Check if wildcard is detected
    filename = "*.txt"
    has_wildcard = '*' in filename or '?' in filename
    print(f"Wildcard detection for '{filename}': {has_wildcard}")
    
    downloader.close()


def test_result_retryable():
    """Test DownloadResult retryable field."""
    print("\n=== Testing DownloadResult ===")
    
    from src.downloaders.base_downloader import DownloadResult
    
    result = DownloadResult(
        success=False,
        source_name="test",
        url="http://test.com",
        filename="test.txt",
        retry_count=0
    )
    
    print(f"Default retryable: {result.retryable}")
    
    result2 = DownloadResult(
        success=False,
        source_name="test",
        url="http://test.com",
        filename="test.txt",
        retry_count=0,
        retryable=False
    )
    
    print(f"Explicit retryable=False: {result2.retryable}")


if __name__ == "__main__":
    print("=" * 50)
    print("Downloader Tests")
    print("=" * 50)
    
    test_result_retryable()
    test_http_downloader()
    test_ftp_wildcard()
    test_ftp_downloader()
    
    print("\n" + "=" * 50)
    print("Tests Complete")
    print("=" * 50)
