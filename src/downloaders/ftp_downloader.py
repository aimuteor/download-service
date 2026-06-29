"""FTP downloader with wildcard/glob support."""

import time
import fnmatch
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

import ftplib

from .base_downloader import BaseDownloader, DownloadResult, format_path_with_datetime
from ..utils.logger import DownloadLogger


class FTPDownloader(BaseDownloader):
    """FTP downloader with wildcard pattern support."""

    def __init__(self, source_config, logger: DownloadLogger, timeout: int = 30):
        super().__init__(source_config, logger)
        self.timeout = timeout
        self.ftp: Optional[ftplib.FTP] = None

    # ==================== Connection Management ====================

    def connect(self) -> bool:
        """Establish FTP connection."""
        try:
            self.ftp = ftplib.FTP()
            self.ftp.connect(
                self.source_config.host,
                self.source_config.port,
                timeout=self.timeout
            )
            self.ftp.login(
                self.source_config.auth_credentials.username,
                self.source_config.auth_credentials.password
            )
            self.ftp.set_pasv(True)
            self.ftp.voidcmd('TYPE I')  # Binary mode
            self.logger.debug(f"[FTP CONNECTED] {self.source_config.host}")
            return True
        except Exception as e:
            self.logger.error(f"[FTP CONNECT FAILED] {self.name} | {e}")
            return False

    def _ensure_connected(self) -> bool:
        """Ensure FTP connection is alive."""
        if self.ftp is None:
            return self.connect()
        try:
            self.ftp.voidcmd('NOOP')
            return True
        except Exception:
            return self.connect()

    def _cleanup(self):
        """Close FTP connection."""
        try:
            if self.ftp:
                self.ftp.quit()
        except Exception:
            pass
        finally:
            self.ftp = None

    def test_connection(self) -> bool:
        """Test FTP connection."""
        if self.connect():
            try:
                self.ftp.quit()
            except Exception:
                pass
            return True
        return False

    # ==================== Path Building ====================

    def build_url(self, filename: str = None, dt: datetime = None) -> str:
        """Build the path component for FTP."""
        path = self.source_config.path
        if dt is not None:
            path = format_path_with_datetime(path, dt)
        if filename:
            if not path.endswith('/'):
                path = path + '/'
            return path + filename
        return path

    # ==================== File Operations ====================

    def _cwd_to_path(self, path: str) -> bool:
        """
        Change to directory and set binary mode.
        Returns True if successful.
        """
        try:
            self.ftp.cwd(path)
            self.ftp.voidcmd('TYPE I')  # Ensure binary mode
            return True
        except ftplib.error_perm as e:
            self.logger.warning(f"[FTP CWD FAILED] {path} | {e}")
            return False

    def _get_file_size(self, filename: str) -> Optional[int]:
        """Get remote file size. Returns None if not found."""
        try:
            size = self.ftp.size(filename)
            return size if size is not None else None
        except ftplib.error_perm:
            return None

    def list_files(self, pattern: str = "*", remote_dir: str = None) -> List[str]:
        """List files matching pattern in remote directory."""
        if not self._ensure_connected():
            return []
        
        try:
            # CWD to remote directory
            if remote_dir is None:
                remote_dir = self.source_config.path
            if not self._cwd_to_path(remote_dir):
                return []
            
            # List files
            all_files = self.ftp.nlst()
            matching = [f for f in all_files if fnmatch.fnmatch(f, pattern)]
            self.logger.debug(f"[FTP LIST] {len(matching)} files matching {pattern}")
            return matching
            
        except Exception as e:
            self.logger.error(f"[FTP LIST FAILED] {self.name} | {e}")
            return []

    def _download_file_to_disk(self, filename: str, local_path: Path) -> Tuple[bool, str]:
        """
        Download a single file to disk.
        Returns (success, error_message).
        """
        try:
            with open(local_path, 'wb') as f:
                self.ftp.retrbinary(f'RETR {filename}', f.write)
            return True, ""
        except ftplib.error_perm as e:
            return False, f"Permission denied: {e}"
        except ftplib.error_temp as e:
            return False, f"Temporary error: {e}"
        except Exception as e:
            return False, str(e)

    # ==================== Main Download Methods ====================

    def download(self, url: str, local_path: Path, filename: str, 
                retry_count: int = 0) -> DownloadResult:
        """Download file(s). Handles both single files and wildcards."""
        if '*' in filename or '?' in filename:
            return self._download_wildcard(url, local_path, filename, retry_count)
        return self._download_single(url, local_path, filename, retry_count)

    def _download_single(self, url: str, local_path: Path, filename: str, 
                        retry_count: int) -> DownloadResult:
        """Download a single file (non-wildcard)."""
        start_time = time.time()
        result = DownloadResult(
            success=False,
            source_name=self.name,
            url=url,
            filename=filename,
            retry_count=retry_count,
            retryable=True
        )

        # Ensure connection
        if not self._ensure_connected():
            result.error = "Failed to establish FTP connection"
            return result

        # Extract directory and filename from URL
        url_path = url.lstrip('/')
        parts = url_path.rsplit('/', 1)
        dir_parts = parts[:-1]
        ftp_filename = parts[-1] if parts else url_path
        
        dir_path = '/' + '/'.join(dir_parts) if dir_parts else '/'

        # CWD to directory
        if not self._cwd_to_path(dir_path):
            result.error = f"Directory not found: {dir_path}"
            result.retryable = False
            return result

        # Check file exists
        remote_size = self._get_file_size(ftp_filename)
        if remote_size is None:
            result.error = f"File not found: {url}"
            result.retryable = False
            return result

        # Create local directory and download
        local_path.mkdir(parents=True, exist_ok=True)
        file_path = local_path / filename

        success, error = self._download_file_to_disk(ftp_filename, file_path)
        if not success:
            result.error = error
            result.retryable = isinstance(error, ftplib.error_temp) or 'Temporary' in error
            if not result.retryable:
                self._cleanup()
            return result

        # Success
        if file_path.exists():
            result.file_size = file_path.stat().st_size
            result.local_path = str(file_path)
            result.success = True
            result.duration = time.time() - start_time
            result.content_hash = self.calculate_hash(file_path)

        return result

    def _download_wildcard(self, url: str, local_path: Path, pattern: str, 
                          retry_count: int) -> DownloadResult:
        """Download files matching a wildcard pattern."""
        start_time = time.time()
        result = DownloadResult(
            success=False,
            source_name=self.name,
            url=url,
            filename=pattern,
            retry_count=retry_count,
            retryable=True
        )

        # Ensure connection
        if not self._ensure_connected():
            result.error = "Failed to establish FTP connection"
            return result

        # Extract directory from URL
        url_path = url.lstrip('/')
        parts = url_path.rsplit('/', 1)
        dir_parts = parts[:-1]
        dir_path = '/' + '/'.join(dir_parts) if dir_parts else '/'

        # CWD to directory
        if not self._cwd_to_path(dir_path):
            result.error = f"Directory not found: {dir_path}"
            result.retryable = False
            return result

        # List matching files
        pattern_only = parts[-1] if parts else pattern
        matching_files = self.list_files(pattern_only, remote_dir=dir_path)
        
        if not matching_files:
            result.error = f"No files matching: {pattern}"
            result.retryable = False
            return result

        self.logger.info(f"[FTP WILDCARD] {self.name} | Pattern: {pattern} | Found: {len(matching_files)}")

        # Download each file
        total_size = 0
        failed_count = 0

        # Create local directory
        local_path.mkdir(parents=True, exist_ok=True)

        for matched_filename in matching_files:
            file_path = local_path / matched_filename
            success, error = self._download_file_to_disk(matched_filename, file_path)
            
            if success:
                total_size += file_path.stat().st_size
            else:
                failed_count += 1
                self.logger.debug(f"[FTP WILDCARD FILE FAILED] {matched_filename} | {error}")

        # Build result
        result.success = failed_count == 0
        result.file_size = total_size
        result.duration = time.time() - start_time
        
        if failed_count > 0:
            result.error = f"{failed_count} files failed"
            result.retryable = False  # If some files failed, don't retry the whole pattern

        return result

    def close(self):
        """Close FTP connection."""
        self._cleanup()

    def __del__(self):
        """Cleanup on destruction."""
        self._cleanup()
