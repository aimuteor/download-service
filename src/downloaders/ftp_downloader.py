"""FTP downloader with wildcard/glob support."""

import time
import fnmatch
import re
from pathlib import Path
from typing import List, Optional
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
            # Set passive mode for better compatibility
            self.ftp.set_pasv(True)
            self.logger.debug(f"[FTP CONNECTED] {self.source_config.host}")
            return True
        except Exception as e:
            self.logger.error(f"[FTP CONNECT FAILED] {self.name} | {e}")
            return False

    def _cleanup(self):
        """Clean up FTP connection."""
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
            except:
                pass
            return True
        return False

    def build_url(self, filename: str = None, dt: datetime = None) -> str:
        """Build the path component for FTP."""
        path = self.source_config.path
        
        # Apply datetime formatting if provided
        if dt is not None:
            path = format_path_with_datetime(path, dt)
        
        if filename:
            if not path.endswith('/'):
                path = path + '/'
            return path + filename
        return path

    def list_files(self, pattern: str = "*") -> List[str]:
        """
        List files in remote directory matching pattern.
        
        Args:
            pattern: Glob pattern (e.g., "*.jpg", "radar_*")
            
        Returns:
            List of matching filenames
        """
        if not self.ftp:
            if not self.connect():
                return []
        
        try:
            # Change to remote directory
            remote_path = self.source_config.path
            self.ftp.cwd(remote_path)
            
            # List all files
            all_files = self.ftp.nlst()
            
            # Filter by pattern
            matching_files = []
            for filename in all_files:
                # Skip directories
                try:
                    self.ftp.cwd(filename)
                    self.ftp.cwd('..')
                    continue  # Skip directories
                except ftplib.error_perm:
                    pass  # It's a file
                
                if fnmatch.fnmatch(filename, pattern):
                    matching_files.append(filename)
            
            return matching_files
            
        except Exception as e:
            self.logger.error(f"[FTP LIST FAILED] {self.name} | {e}")
            return []

    def download(self, url: str, local_path: Path, filename: str, 
                retry_count: int = 0) -> DownloadResult:
        """Download a single file or multiple files matching a wildcard pattern."""
        
        # Check if filename contains wildcard characters
        if '*' in filename or '?' in filename:
            # Wildcard download - list files and download each
            return self._download_with_wildcard(url, local_path, filename, retry_count)
        
        # Single file download (existing logic)
        return self._download_single(url, local_path, filename, retry_count)
        """
        Download a single file from FTP server.
        
        Args:
            url: Full path to remote file
            local_path: Local directory to save file
            filename: Filename to save as
            retry_count: Current retry attempt
            
        Returns:
            DownloadResult with operation details
        """
        start_time = time.time()
        result = DownloadResult(
            success=False,
            source_name=self.name,
            url=f"ftp://{self.source_config.host}/{url}",
            filename=filename,
            retry_count=retry_count
        )

        try:
            # Connect if not connected
            if not self.ftp:
                if not self.connect():
                    result.error = "Failed to establish FTP connection"
                    self.logger.download_failed(self.name, result.url, result.error, retry_count)
                    return result

            # Check if remote file exists before downloading
            try:
                remote_size = self.ftp.size(url)
                if remote_size is None:
                    result.error = f"Remote file not found: {url}"
                    result.retryable = False  # File not found - don't retry
                    self.logger.download_failed(self.name, result.url, result.error, retry_count)
                    return result
            except ftplib.error_perm:
                result.error = f"Remote file not found: {url}"
                result.retryable = False  # File not found - don't retry
                self.logger.download_failed(self.name, result.url, result.error, retry_count)
                return result

            # Only create directory after confirming remote file exists
            local_path.mkdir(parents=True, exist_ok=True)
            file_path = local_path / filename

            # Download file
            with open(file_path, 'wb') as f:
                self.ftp.retrbinary(f'RETR {url}', f.write)

            # Verify and get size
            if file_path.exists():
                result.file_size = file_path.stat().st_size
                result.local_path = str(file_path)
                result.success = True
                result.duration = time.time() - start_time
                result.content_hash = self.calculate_hash(file_path)

                self.logger.download_success(
                    self.name, filename, result.file_size, result.duration
                )
            else:
                result.error = "File was not created after download"
                self.logger.download_failed(self.name, result.url, result.error, retry_count)

        except ftplib.error_perm as e:
            result.error = f"Permission denied: {str(e)}"
            result.retryable = False  # Don't retry permission errors
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
        except ftplib.error_temp as e:
            result.error = f"Temporary error: {str(e)}"
            # Keep retryable=True for temporary errors (connection might recover)
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
        except (ConnectionError, TimeoutError, OSError) as e:
            # Connection-related errors - cleanup and retry might help
            result.error = f"Connection error: {str(e)}"
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
            self._cleanup()  # Force reconnect on next attempt
        except Exception as e:
            # Unexpected errors - might be connection issue
            result.error = f"FTP error: {str(e)}"
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
            self._cleanup()  # Force reconnect on next attempt

        return result

    def close(self):
        """Close FTP connection."""
        self._cleanup()

    def __del__(self):
        """Cleanup on destruction."""
        self._cleanup()
