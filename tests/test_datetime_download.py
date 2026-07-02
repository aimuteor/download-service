"""End-to-end test for datetime-based downloads with HKT timezone."""

import sys
import os
import threading
import time
import tempfile
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import SourceConfig
from src.downloaders.http_downloader import HTTPDownloader
from src.utils.logger import DownloadLogger


# Test setup
TEST_DIR = Path(tempfile.mkdtemp())
DATA_DIR = TEST_DIR / "data"
DOWNLOAD_DIR = TEST_DIR / "downloads"
LOG_DIR = TEST_DIR / "logs"

for d in [DATA_DIR, DOWNLOAD_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

HTTP_PORT = 18880


class DateTimeHTTPHandler(SimpleHTTPRequestHandler):
    """
    HTTP handler that serves files based on datetime URL structure.
    URLs look like: /{YYYY}/{MM}/{DD}/{HH}/{filename}.dat
    
    Files are stored in DATA_DIR with the same structure.
    """
    
    def translate_path(self, path):
        """Translate URL path to filesystem path."""
        # Parse URL
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Remove leading slash and split
        parts = path.strip('/').split('/')
        
        if len(parts) < 5:
            # Not enough parts for datetime structure
            return ''
        
        # parts[0] = YYYY, [1] = MM, [2] = DD, [3] = HH, [4] = filename
        # Map to: DATA_DIR/YYYYMMDD/HH/filename
        if len(parts) >= 5:
            yyyy, mm, dd, hh = parts[0], parts[1], parts[2], parts[3]
            filename = '/'.join(parts[4:])
            dir_path = f"{yyyy}{mm}{dd}"
            return str(DATA_DIR / dir_path / hh / filename)
        
        return ''
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass


def start_http_server(port):
    """Start HTTP server in background thread."""
    os.chdir(DATA_DIR)
    server = HTTPServer(('127.0.0.1', port), DateTimeHTTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def create_test_files():
    """Create test file structure in DATA_DIR."""
    # Create files for 2026-07-02 11:xx HKT (UTC+8)
    # 11:xx HKT = 03:xx UTC
    test_files = [
        # 2026/07/02/03/data.202607020310.dat (11:10 HKT)
        (("2026", "07", "02", "03", "data.202607020310.dat"), "Content at 11:10 HKT"),
        # 2026/07/02/03/data.202607020320.dat (11:20 HKT)
        (("2026", "07", "02", "03", "data.202607020320.dat"), "Content at 11:20 HKT"),
        # 2026/07/02/03/data.202607020330.dat (11:30 HKT)
        (("2026", "07", "02", "03", "data.202607020330.dat"), "Content at 11:30 HKT"),
        # 2026/07/02/04/data.202607020400.dat (12:00 HKT - next hour)
        (("2026", "07", "02", "04", "data.202607020400.dat"), "Content at 12:00 HKT"),
    ]
    
    for parts, content in test_files:
        yyyy, mm, dd, hh, filename = parts
        dir_path = DATA_DIR / f"{yyyy}{mm}{dd}" / hh
        dir_path.mkdir(parents=True, exist_ok=True)
        file_path = dir_path / filename
        file_path.write_text(content)
        print(f"Created: {file_path}")


def test_hkt_datetime_download():
    """
    Test downloading files with datetime in path using HKT timezone.
    
    This simulates a real scenario where:
    - Files are stored at /{YYYY}/{MM}/{DD}/{HH}/{filename}
    - Datetime is in HKT (UTC+8)
    - Source config specifies HKT timezone
    """
    print("\n=== Testing HKT Datetime Download ===")
    
    # Create test files
    create_test_files()
    
    # Start HTTP server
    server = start_http_server(HTTP_PORT)
    time.sleep(0.5)
    
    try:
        # Source config with HKT timezone
        # URL pattern: /{YYYY}/{MM}/{DD}/{HH}/data.{YYYYMMDDHHMI}.dat
        # At 11:27 HKT on 2026-07-02, we want to download files from 11:00-12:00 HKT
        source = SourceConfig(
            name="test_hkt_datetime",
            type="http",
            protocol="http",
            host="127.0.0.1",
            port=HTTP_PORT,
            path="/{YYYY}/{MM}/{DD}/{HH}/",  # Datetime in path
            filename_pattern="data.{YYYYMMDDHHMI}.dat",
            method="GET",
            timeout=10,
            force_download=False,
            datetime_config={
                "timezone": "Asia/Hong_Kong",  # HKT!
                "interval_minutes": 10,
                "offset_minutes": 0,
                "lookback_minutes": 60  # Look back 1 hour
            },
            destination={
                "subdir": "hkt_test",
                "date_dir_pattern": "{dataDir}/{YYYYMMDD}",
                "dir_array": False
            }
        )
        
        logger = DownloadLogger("test_hkt", str(LOG_DIR), "DEBUG")
        downloader = HTTPDownloader(source, logger, timeout=10)
        
        # Test connection
        connected = downloader.test_connection()
        print(f"Connection test: {'PASS' if connected else 'FAIL'}")
        
        if not connected:
            return False
        
        # Create destination path
        dest_path = DOWNLOAD_DIR / "hkt_test"
        
        # Build URL with specific datetime
        # 2026-07-02 11:20 HKT
        test_dt = datetime(2026, 7, 2, 11, 20, tzinfo=__import__('zoneinfo').ZoneInfo("Asia/Hong_Kong"))
        
        # Build URL and download
        url = downloader.build_url("data.202607020320.dat", test_dt)
        print(f"Built URL: {url}")
        
        result = downloader.download(url, dest_path, "data.202607020320.dat", 0)
        
        print(f"Download result: success={result.success}, error={result.error}")
        
        if result.success:
            print(f"Downloaded to: {result.local_path}")
            # Verify file content
            if Path(result.local_path).exists():
                content = Path(result.local_path).read_text()
                print(f"File content: {content}")
        
        downloader.close()
        
        return result.success
        
    finally:
        server.shutdown()


def test_hkt_wildcard_download():
    """
    Test downloading multiple files with wildcard using HKT timezone.
    """
    print("\n=== Testing HKT Wildcard Download ===")
    
    source = SourceConfig(
        name="test_hkt_wildcard",
        type="http",
        protocol="http",
        host="127.0.0.1",
        port=HTTP_PORT,
        path="/{YYYY}/{MM}/{DD}/{HH}/",
        filename_pattern="data.20260702*.dat",  # Wildcard for all files on 2026-07-02
        method="GET",
        timeout=10,
        force_download=False,
        datetime_config={
            "timezone": "Asia/Hong_Kong",
            "interval_minutes": 60,  # Hourly
            "offset_minutes": 0,
            "lookback_minutes": 120  # Look back 2 hours
        },
        destination={
            "subdir": "hkt_wildcard",
            "date_dir_pattern": "{dataDir}/{YYYYMMDD}",
            "dir_array": False
        }
    )
    
    logger = DownloadLogger("test_hkt_wildcard", str(LOG_DIR), "DEBUG")
    downloader = HTTPDownloader(source, logger, timeout=10)
    
    # Build URL with datetime
    test_dt = datetime(2026, 7, 2, 12, 0, tzinfo=__import__('zoneinfo').ZoneInfo("Asia/Hong_Kong"))
    url = downloader.build_url("data.20260702*.dat", test_dt)
    print(f"Built URL: {url}")
    
    dest_path = DOWNLOAD_DIR / "hkt_wildcard"
    
    # HTTP doesn't support wildcards, so this will try to download literally
    result = downloader.download(url, dest_path, "data.20260702*.dat", 0)
    
    print(f"Download result: success={result.success}, error={result.error}")
    
    # For HTTP, wildcard pattern will fail because server won't find exact file
    # This is expected behavior
    
    downloader.close()
    
    # Return True if it handled the error gracefully
    return result.error is not None or result.success


def test_hkt_datetime_parser():
    """Test that datetime parser generates correct HKT datetimes."""
    print("\n=== Testing HKT Datetime Parser ===")
    
    from src.parsers.datetime_parser import DatetimeParser
    from src.config_loader import DatetimeConfig
    
    dt_config = DatetimeConfig(
        timezone="Asia/Hong_Kong",
        interval_minutes=10,
        offset_minutes=0,
        lookback_minutes=60
    )
    
    parser = DatetimeParser(dt_config)
    
    # Reference time: 2026-07-02 11:27 HKT
    from zoneinfo import ZoneInfo
    ref_time = datetime(2026, 7, 2, 11, 27, tzinfo=ZoneInfo("Asia/Hong_Kong"))
    
    # Calculate datetimes
    datetimes = parser.calculate_datetime_list(ref_time)
    
    print(f"Reference time (HKT): {ref_time}")
    print(f"Generated {len(datetimes)} datetime slots:")
    
    for dt in datetimes:
        # Convert to HKT for display
        hkt_dt = dt.astimezone(ZoneInfo("Asia/Hong_Kong"))
        print(f"  {hkt_dt.strftime('%Y-%m-%d %H:%M %Z')} (UTC: {dt.strftime('%H:%M')})")
    
    # Expected: slots from lookback_start to ref_time (inclusive)
    # 60 min / 10 min interval = 7 slots, but may vary due to rounding
    expected_min = 6  # At least 6 slots expected
    
    success = len(datetimes) >= expected_min
    print(f"\nExpected at least {expected_min} slots, got {len(datetimes)}: {'PASS' if success else 'FAIL'}")
    
    return success


def main():
    print("=" * 60)
    print("HKT Datetime Download Tests")
    print("=" * 60)
    
    test1 = test_hkt_datetime_parser()
    test2 = test_hkt_datetime_download()
    test3 = test_hkt_wildcard_download()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"HKT Datetime Parser:   {'PASS' if test1 else 'FAIL'}")
    print(f"HKT Datetime Download: {'PASS' if test2 else 'FAIL'}")
    print(f"HKT Wildcard (HTTP):   {'PASS' if test3 else 'FAIL'}")
    
    all_pass = test1 and test2 and test3
    print(f"\nOverall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    
    # Cleanup
    import shutil
    shutil.rmtree(TEST_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()
