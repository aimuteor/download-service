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

# Create test files in FTP directory with date-based subdirectories
(FTP_DIR / "data_1000.txt").write_text("Data file 1000")
(FTP_DIR / "data_2000.txt").write_text("Data file 2000")
(FTP_DIR / "data_3000.txt").write_text("Data file 3000")
(FTP_DIR / "report_20240622.txt").write_text("Report file")
(FTP_DIR / "image_001.jpg").write_text("Image 1")
(FTP_DIR / "image_002.jpg").write_text("Image 2")

# Create date-based subdirectory
DATE_SUBDIR = FTP_DIR / "20260625"
DATE_SUBDIR.mkdir(exist_ok=True)
(DATE_SUBDIR / "data.202606250610").write_text("Data with datetime 1")
(DATE_SUBDIR / "data.202606250620").write_text("Data with datetime 2")
(DATE_SUBDIR / "data.202606250630").write_text("Data with datetime 3")

print(f"FTP test dir: {FTP_DIR}")
print(f"Files created: {list(FTP_DIR.iterdir())}")

FTP_PORT = 21212


def start_ftp_server():
    """Start local FTP server."""
    authorizer = DummyAuthorizer()
    authorizer.add_anonymous(str(FTP_DIR), perm="elradfmw")
    
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.banner = "Test FTP Server"
    
    server = FTPServer(("127.0.0.1", FTP_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    print(f"FTP server started on 127.0.0.1:{FTP_PORT}")
    return server


def test_ftp_simple_path():
    """Test FTP with simple path (no datetime placeholders)."""
    print("\n=== Testing FTP Simple Path ===")
    
    source = SourceConfig(
        name="test_ftp_simple",
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
            "subdir": "ftp_simple",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_simple", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Test connection
    connected = downloader.connect()
    print(f"FTP connection: {'SUCCESS' if connected else 'FAILED'}")
    
    if connected:
        # List files
        files = downloader.list_files("*.txt")
        print(f"Text files: {files}")
        result = len(files) > 0
    else:
        result = False
    
    downloader.close()
    return result


def test_ftp_datetime_path():
    """Test FTP with datetime placeholders in path (simulating real scenario)."""
    print("\n=== Testing FTP Datetime Path ===")
    
    source = SourceConfig(
        name="test_ftp_datetime",
        type="ftp",
        host="127.0.0.1",
        port=FTP_PORT,
        # Path with datetime placeholders - this is what user has in config
        path="/data/{YYYYMMDD}",
        filename_pattern="data.*",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_datetime",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_datetime", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    # Test download with URL that has datetime already replaced
    # In real usage, the URL passed to download() would have datetime replaced
    # by the datetime parser before calling the downloader
    download_path = DOWNLOAD_DIR / "datetime_test"
    
    # The URL has the datetime already replaced (simulating what downloader.py does)
    url_with_datetime = "/20260625/data.202606250610"
    result = downloader.download(url_with_datetime, download_path, "data.202606250610", 0)
    
    print(f"Download success: {result.success}")
    print(f"Error: {result.error}")
    print(f"File size: {result.file_size}")
    
    downloader.close()
    return result.success


def test_ftp_datetime_wildcard():
    """Test FTP wildcard download with datetime path."""
    print("\n=== Testing FTP Datetime Wildcard ===")
    
    source = SourceConfig(
        name="test_ftp_dt_wildcard",
        type="ftp",
        host="127.0.0.1",
        port=FTP_PORT,
        path="/data/{YYYYMMDD}",
        filename_pattern="data.*",
        method="GET",
        force_download=False,
        datetime_config={
            "timezone": "UTC",
            "interval_minutes": 10,
            "offset_minutes": 1,
            "lookback_minutes": 60
        },
        destination={
            "subdir": "ftp_dt_wildcard",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}"
        }
    )
    
    logger = DownloadLogger("test_ftp_dt_wildcard", str(LOG_DIR), "DEBUG")
    downloader = FTPDownloader(source, logger, timeout=10)
    
    download_path = DOWNLOAD_DIR / "datetime_wildcard_test"
    
    # URL with datetime replaced, and wildcard in filename
    url_with_datetime = "/20260625/data.*"
    result = downloader.download(url_with_datetime, download_path, "data.*", 0)
    
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
    
    download_path = DOWNLOAD_DIR / "wildcard_test"
    result = downloader.download("/data_*.txt", download_path, "data_*.txt", 0)
    
    print(f"Download success: {result.success}")
    print(f"Error: {result.error}")
    print(f"File size: {result.file_size}")
    print(f"Files downloaded: {list(download_path.glob('*')) if download_path.exists() else 'dir not created'}")
    
    downloader.close()
    return result.success


def main():
    print("=" * 60)
    print("FTP Downloader Test with Real FTP Server")
    print("=" * 60)
    
    # Start FTP server
    server = start_ftp_server()
    time.sleep(0.5)
    
    try:
        test1 = test_ftp_simple_path()
        test2 = test_ftp_single_download()
        test3 = test_ftp_wildcard_download()
        test4 = test_ftp_datetime_path()
        test5 = test_ftp_datetime_wildcard()
        
        print("\n" + "=" * 60)
        print("Test Summary")
        print("=" * 60)
        print(f"FTP Simple Path:         {'PASS' if test1 else 'FAIL'}")
        print(f"FTP Single Download:     {'PASS' if test2 else 'FAIL'}")
        print(f"FTP Wildcard Download:   {'PASS' if test3 else 'FAIL'}")
        print(f"FTP Datetime Path:       {'PASS' if test4 else 'FAIL'}")
        print(f"FTP Datetime Wildcard:   {'PASS' if test5 else 'FAIL'}")
        
        all_pass = all([test1, test2, test3, test4, test5])
        print(f"\nOverall: {'ALL PASS ✓' if all_pass else 'SOME FAILED'}")
        
    finally:
        server.close_all()
        print("\nFTP server stopped")


if __name__ == "__main__":
    main()
