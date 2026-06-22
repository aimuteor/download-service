"""FTP downloader with wildcard/glob support."""

import time
import fnmatch
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

    def _ensure_connected(self) -> bool:
        """Ensure FTP connection is established."""
        if self.ftp is None:
            return self.connect()
        return True

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
        if not self._ensure_connected():
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
        
        # Single file download
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

        try:
            # Ensure connection
            if not self._ensure_connected():
                result.error = "Failed to establish FTP connection"
                result.retryable = True
                return result

            # Check if remote file exists before downloading
            try:
                remote_size = self.ftp.size(url)
                if remote_size is None:
                    result.error = f"Remote file not found: {url}"
                    result.retryable = False
                    self.logger.download_failed(self.name, url, result.error, retry_count)
                    return result
            except ftplib.error_perm:
                result.error = f"Remote file not found: {url}"
                result.retryable = False
                self.logger.download_failed(self.name, url, result.error, retry_count)
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
                self.logger.download_failed(self.name, url, result.error, retry_count)

        except ftplib.error_perm as e:
            result.error = f"Permission denied: {str(e)}"
            result.retryable = False
            self.logger.download_failed(self.name, url, result.error, retry_count)
        except ftplib.error_temp as e:
            result.error = f"Temporary error: {str(e)}"
            result.retryable = True
            self.logger.download_failed(self.name, url, result.error, retry_count)
        except (ConnectionError, TimeoutError, OSError) as e:
            result.error = f"Connection error: {str(e)}"
            result.retryable = True
            self.logger.download_failed(self.name, url, result.error, retry_count)
            self._cleanup()
        except (IOError, OSError) as e:
            # Disk full, permission denied, etc.
            result.error = f"Disk error: {str(e)}"
            result.retryable = False  # Don't retry disk errors
            self.logger.download_failed(self.name, url, result.error, retry_count)
        except Exception as e:
            result.error = f"FTP error: {str(e)}"
            result.retryable = True
            self.logger.download_failed(self.name, url, result.error, retry_count)
            self._cleanup()

        return result

    def _download_with_wildcard(self, url: str, local_path: Path, pattern: str, 
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

        try:
            # Ensure connection
            if not self._ensure_connected():
                result.error = "Failed to establish FTP connection"
                return result

            # Get the remote directory path
            remote_dir = self.source_config.path
            if not remote_dir.endswith('/'):
                remote_dir += '/'

            # List files matching pattern
            matching_files = self.list_files(pattern)
            
            if not matching_files:
                result.error = f"No files matching pattern: {pattern}"
                result.retryable = False
                self.logger.download_failed(self.name, url, result.error, retry_count)
                return result

            self.logger.info(f"[FTP WILDCARD] {self.name} | Pattern: {pattern} | Found: {len(matching_files)}")

            # Track results across all files
            total_size = 0
            failed_count = 0
            
            for matched_filename in matching_files:
                file_url = remote_dir + matched_filename
                file_result = self._download_single(file_url, local_path, matched_filename, retry_count)
                
                if file_result.success:
                    total_size += file_result.file_size
                else:
                    failed_count += 1

            # Update aggregate result
            result.success = failed_count == 0
            result.file_size = total_size
            result.duration = time.time() - start_time
            
            if failed_count > 0:
                result.error = f"{failed_count} files failed"

            return result

        except Exception as e:
            result.error = f"FTP wildcard error: {str(e)}"
            result.retryable = True
            self.logger.download_failed(self.name, url, result.error, retry_count)
            self._cleanup()
            return result

    def close(self):
        """Close FTP connection."""
        self._cleanup()

    def __del__(self):
        """Cleanup on destruction."""
        self._cleanup()
