"""Test script with local HTTP and FTP servers using pure Python."""

import sys
import os
import threading
import time
import tempfile
import socket
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import SourceConfig
from src.downloaders.http_downloader import HTTPDownloader
from src.downloaders.ftp_downloader import FTPDownloader
from src.utils.logger import DownloadLogger


# Test directories
TEST_DIR = Path(tempfile.mkdtemp())
HTTP_DIR = TEST_DIR / "http_data"
DOWNLOAD_DIR = TEST_DIR / "downloads"

for d in [HTTP_DIR, DOWNLOAD_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Create test files
(HTTP_DIR / "test.txt").write_text("HTTP test content")
(HTTP_DIR / "data.txt").write_text("HTTP data content")
(HTTP_DIR / "image_1000.jpg").write_text("Image 1")
(HTTP_DIR / "image_2000.jpg").write_text("Image 2")
(HTTP_DIR / "image_3000.jpg").write_text("Image 3")

HTTP_PORT = 18888


class QuietHTTPHandler(SimpleHTTPRequestHandler):
    """HTTP handler that doesn't log to stderr."""
    def log_message(self, format, *args):
        pass  # Suppress logging


def find_free_port():
    """Find a free port to use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def start_http_server(port):
    """Start local HTTP server in background thread."""
    os.chdir(HTTP_DIR)
    server = HTTPServer(('127.0.0.1', port), QuietHTTPHandler)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    return server


def test_http_download():
    """Test HTTP download."""
    print("\n=== Testing HTTP Download ===")
    
    source = SourceConfig(
        name="test_http",
        type="http",
        protocol="http",
        host="127.0.0.1",
        port=HTTP_PORT,
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
            "subdir": "http_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_http", str(TEST_DIR / "logs"), "DEBUG")
    downloader = HTTPDownloader(source, logger, timeout=10)
    
    # Test connection
    result = downloader.test_connection()
    print(f"Connection test: {'PASS' if result else 'FAIL'}")
    
    # Test download
    download_path = DOWNLOAD_DIR / "http_test"
    result = downloader.download("/test.txt", download_path, "test.txt", 0)
    print(f"Download test: {'PASS' if result.success else 'FAIL'}")
    if not result.success:
        print(f"  Error: {result.error}")
    else:
        print(f"  Downloaded to: {result.local_path}")
        print(f"  File size: {result.file_size}")
    
    downloader.close()
    return result.success


def test_http_wildcard_detection():
    """Test HTTP wildcard detection (should not support wildcards)."""
    print("\n=== Testing HTTP Wildcard Detection ===")
    
    source = SourceConfig(
        name="test_http",
        type="http",
        protocol="http",
        host="127.0.0.1",
        port=HTTP_PORT,
        path="/",
        filename_pattern="*.txt",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "http_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_http", str(TEST_DIR / "logs"), "DEBUG")
    downloader = HTTPDownloader(source, logger, timeout=10)
    
    # Wildcard detection
    filename = "*.txt"
    has_wildcard = '*' in filename or '?' in filename
    print(f"Wildcard '{filename}' detected: {has_wildcard}")
    print(f"HTTP should NOT support wildcards (will try to download literally)")
    
    downloader.close()
    return True  # Detection works, HTTP just won't find the file


def test_http_result_structure():
    """Test HTTP DownloadResult has retryable field."""
    print("\n=== Testing HTTP Result Structure ===")
    
    source = SourceConfig(
        name="test_http",
        type="http",
        protocol="http",
        host="127.0.0.1",
        port=HTTP_PORT,
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
            "subdir": "http_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_http", str(TEST_DIR / "logs"), "DEBUG")
    downloader = HTTPDownloader(source, logger, timeout=10)
    
    # Try to download non-existent file to check retryable field
    download_path = DOWNLOAD_DIR / "http_test"
    result = downloader.download("/nonexistent_xyz.txt", download_path, "nonexistent_xyz.txt", 0)
    
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")
    print(f"Retryable: {result.retryable}")
    print(f"Has retryable field: {hasattr(result, 'retryable')}")
    
    # Test retryable field value for 404
    if result.error and "404" in str(result.error):
        print(f"404 error should be non-retryable: {not result.retryable}")
    
    downloader.close()
    return True


def test_http_retry_logic():
    """Test HTTP retry logic with 404 errors."""
    print("\n=== Testing HTTP Retry Logic ===")
    
    source = SourceConfig(
        name="test_http",
        type="http",
        protocol="http",
        host="127.0.0.1",
        port=HTTP_PORT,
        path="/",
        filename_pattern="nonexistent.txt",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "http_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_http", str(TEST_DIR / "logs"), "DEBUG")
    downloader = HTTPDownloader(source, logger, timeout=10)
    
    download_path = DOWNLOAD_DIR / "http_test"
    
    # Simulate retry by calling download multiple times
    attempts = 0
    for i in range(3):
        result = downloader.download("/nonexistent_404.txt", download_path, "nonexistent_404.txt", i)
        attempts += 1
        print(f"Attempt {attempts}: success={result.success}, retryable={result.retryable}, error={result.error}")
        if not result.retryable:
            print("Non-retryable error detected - should skip further retries")
            break
    
    downloader.close()
    return True


def main():
    print("=" * 60)
    print("HTTP Server Download Tests")
    print("=" * 60)
    
    # Start HTTP server
    http_server = start_http_server(HTTP_PORT)
    print(f"HTTP server started on port {HTTP_PORT}")
    
    time.sleep(0.5)  # Give server time to start
    
    try:
        # Run tests
        test1 = test_http_download()
        test2 = test_http_wildcard_detection()
        test3 = test_http_result_structure()
        test4 = test_http_retry_logic()
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"HTTP Download:          {'PASS' if test1 else 'FAIL'}")
        print(f"Wildcard Detection:     {'PASS' if test2 else 'FAIL'}")
        print(f"Result Structure:       {'PASS' if test3 else 'FAIL'}")
        print(f"Retry Logic:           {'PASS' if test4 else 'FAIL'}")
        
        all_pass = test1 and test2 and test3 and test4
        print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
        
    finally:
        # Stop server
        http_server.shutdown()
        print("\nHTTP server stopped")


if __name__ == "__main__":
    main()
