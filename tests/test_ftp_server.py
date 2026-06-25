"""Test FTP downloader with real FTP server using pyftpdlib."""

import sys
import os
import threading
import time
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from src.config_loader import SourceConfig
from src.downloaders.ftp_downloader import FTPDownloader
from src.utils.logger import DownloadLogger


# Test directories
TEST_DIR = Path(tempfile.mkdtemp())
FTP_DIR = TEST_DIR / "ftp_data"
DOWNLOAD_DIR = TEST_DIR / "downloads"
LOG_DIR = TEST_DIR / "logs"

for d in [FTP_DIR, DOWNLOAD_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Create test files in FTP directory
(FTP_DIR / "data_1000.txt").write_text("Data file 1000")
(FTP_DIR / "data_2000.txt").write_text("Data file 2000")
(FTP_DIR / "data_3000.txt").write_text("Data file 3000")
(FTP_DIR / "report_20240622.txt").write_text("Report file")
(FTP_DIR / "image_001.jpg").write_text("Image 1")
(FTP_DIR / "image_002.jpg").write_text("Image 2")

print(f"FTP test dir: {FTP_DIR}")
print(f"Files created: {list(FTP_DIR.iterdir())}")

FTP_PORT = 21212  # Use high port to avoid permission issues


def start_ftp_server():
    """Start local FTP server."""
    authorizer = DummyAuthorizer()
    # Use anonymous access for simplicity
    authorizer.add_anonymous(str(FTP_DIR), perm="elradfmw")
    
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.banner = "Test FTP Server"
    
    # Listen on localhost only
    server = FTPServer(("127.0.0.1", FTP_PORT), handler)
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    print(f"FTP server started on 127.0.0.1:{FTP_PORT}")
    return server


def test_ftp_list_files():
    """Test FTP list_files method."""
    print("\n=== Testing FTP list_files ===")
    
    source = SourceConfig(
        name="test_ftp",
        type="ftp",
        host="127.0.0.1",
        port=FTP_PORT,
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
            "subdir": "ftp_test",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Test connection first
    connected = downloader.connect()
    print(f"FTP connection: {'SUCCESS' if connected else 'FAILED'}")
    
    if connected:
        # List all files
        all_files = downloader.list_files("*")
        print(f"All files: {all_files}")
        
        # List txt files
        txt_files = downloader.list_files("*.txt")
        print(f"Text files (*.txt): {txt_files}")
        
        # List data files
        data_files = downloader.list_files("data_*.txt")
        print(f"Data files (data_*.txt): {data_files}")
        
        result = len(txt_files) > 0
    else:
        result = False
    
    downloader.close()
    return result


def test_ftp_wildcard_download():
    """Test FTP wildcard download."""
    print("\n=== Testing FTP Wildcard Download ===")
    
    source = SourceConfig(
        name="test_ftp_wildcard",
        type="ftp",
        host="127.0.0.1",
        port=FTP_PORT,
        path="/",
        filename_pattern="data_*.txt",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_wildcard",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_wildcard", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Test wildcard download
    download_path = DOWNLOAD_DIR / "wildcard_test"
    result = downloader.download("/data_*.txt", download_path, "data_*.txt", 0)
    
    print(f"Download success: {result.success}")
    print(f"Error: {result.error}")
    print(f"File size: {result.file_size}")
    print(f"Files downloaded: {list(download_path.glob('*')) if download_path.exists() else 'dir not created'}")
    
    downloader.close()
    return result.success


def test_ftp_single_download():
    """Test FTP single file download."""
    print("\n=== Testing FTP Single File Download ===")
    
    source = SourceConfig(
        name="test_ftp_single",
        type="ftp",
        host="127.0.0.1",
        port=FTP_PORT,
        path="/",
        filename_pattern="report_20240622.txt",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_single",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_single", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    download_path = DOWNLOAD_DIR / "single_test"
    result = downloader.download("/report_20240622.txt", download_path, "report_20240622.txt", 0)
    
    print(f"Download success: {result.success}")
    print(f"Error: {result.error}")
    print(f"File size: {result.file_size}")
    
    downloader.close()
    return result.success


def test_ftp_nonexistent():
    """Test FTP download of non-existent file."""
    print("\n=== Testing FTP Non-existent File ===")
    
    source = SourceConfig(
        name="test_ftp_missing",
        type="ftp",
        host="127.0.0.1",
        port=FTP_PORT,
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
            "subdir": "ftp_missing",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_missing", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    download_path = DOWNLOAD_DIR / "missing_test"
    result = downloader.download("/nonexistent.txt", download_path, "nonexistent.txt", 0)
    
    print(f"Download success (should be False): {result.success}")
    print(f"Error: {result.error}")
    print(f"Retryable (should be False): {result.retryable}")
    
    downloader.close()
    # Success = correctly returned error with retryable=False
    return not result.success and not result.retryable


def main():
    print("=" * 60)
    print("FTP Downloader Test with Real FTP Server")
    print("=" * 60)
    
    # Start FTP server
    server = start_ftp_server()
    time.sleep(0.5)  # Give server time to start
    
    try:
        # Run tests
        test1 = test_ftp_list_files()
        test2 = test_ftp_single_download()
        test3 = test_ftp_wildcard_download()
        test4 = test_ftp_nonexistent()
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"FTP list_files:        {'PASS' if test1 else 'FAIL'}")
        print(f"FTP Single Download:   {'PASS' if test2 else 'FAIL'}")
        print(f"FTP Wildcard Download: {'PASS' if test3 else 'FAIL'}")
        print(f"FTP Non-existent:      {'PASS' if test4 else 'FAIL'}")
        
        all_pass = all([test1, test2, test3, test4])
        print(f"\nOverall: {'ALL PASS ✓' if all_pass else 'SOME FAILED'}")
        
    finally:
        server.close_all()
        print("\nFTP server stopped")


if __name__ == "__main__":
    main()
