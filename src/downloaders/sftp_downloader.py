"""SFTP downloader for secure file transfer."""

import time
import stat
from pathlib import Path
from typing import Optional
from datetime import datetime

import paramiko

from .base_downloader import BaseDownloader, DownloadResult, format_path_with_datetime
from ..utils.logger import DownloadLogger


class SFTPDownloader(BaseDownloader):
    """SFTP downloader for secure file transfer."""

    def __init__(self, source_config, logger: DownloadLogger, timeout: int = 30):
        super().__init__(source_config, logger)
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None

    def _get_ssh_key(self):
        """Load SSH key for authentication."""
        creds = self.source_config.auth_credentials
        key_file = Path(creds.key_file).expanduser()
        
        try:
            if key_file.exists():
                # Try without passphrase first
                try:
                    return paramiko.Ed25519Key.from_private_key_file(str(key_file))
                except paramiko.SSHException:
                    pass
                try:
                    return paramiko.RSAKey.from_private_key_file(str(key_file))
                except paramiko.SSHException:
                    pass
                try:
                    return paramiko.ECDSAKey.from_private_key_file(str(key_file))
                except paramiko.SSHException:
                    pass
                # Try with passphrase if password is provided
                if creds.password:
                    try:
                        return paramiko.Ed25519Key.from_private_key_file(
                            str(key_file), password=creds.password
                        )
                    except paramiko.SSHException:
                        pass
                    return paramiko.RSAKey.from_private_key_file(
                        str(key_file), password=creds.password
                    )
            raise FileNotFoundError(f"SSH key file not found: {key_file}")
        except Exception as e:
            self.logger.error(f"[SSH KEY ERROR] {self.name} | {e}")
            raise

    def connect(self) -> bool:
        """Establish SFTP connection."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            creds = self.source_config.auth_credentials
            
            # Connect with appropriate authentication
            connect_kwargs = {
                'hostname': self.source_config.host,
                'port': self.source_config.port,
                'timeout': self.timeout,
                'look_for_keys': False,
                'allow_agent': False,
            }

            if self.source_config.auth_type == 'key':
                connect_kwargs['pkey'] = self._get_ssh_key()
                connect_kwargs['username'] = creds.username
            else:  # password
                connect_kwargs['username'] = creds.username
                connect_kwargs['password'] = creds.password

            self.client.connect(**connect_kwargs)
            self.sftp = self.client.open_sftp()
            
            self.logger.debug(f"[SFTP CONNECTED] {self.name} | {self.source_config.host}")
            return True

        except Exception as e:
            self.logger.error(f"[SFTP CONNECTION FAILED] {self.name} | {e}")
            self._cleanup()
            return False

    def _cleanup(self):
        """Clean up SFTP connection."""
        try:
            if self.sftp:
                self.sftp.close()
            if self.client:
                self.client.close()
        except Exception:
            pass
        finally:
            self.sftp = None
            self.client = None

    def test_connection(self) -> bool:
        """Test SFTP connection."""
        if self.connect():
            self._cleanup()
            return True
        return False

    def build_url(self, filename: str = None, dt: datetime = None) -> str:
        """Build the path component for SFTP (not a traditional URL)."""
        path = self.source_config.path
        
        # Apply datetime formatting if provided
        if dt is not None:
            path = format_path_with_datetime(path, dt)
        
        if filename:
            if not path.endswith('/'):
                path = path + '/'
            return path + filename
        return path

    def download(self, remote_path: str, local_path: Path, filename: str,
                 retry_count: int = 0) -> DownloadResult:
        """Download file via SFTP."""
        start_time = time.time()
        result = DownloadResult(
            success=False,
            source_name=self.name,
            url=f"sftp://{self.source_config.host}:{self.source_config.port}{remote_path}",
            filename=filename,
            retry_count=retry_count
        )

        try:
            # Connect if not connected
            if not self.sftp:
                if not self.connect():
                    result.error = "Failed to establish SFTP connection"
                    self.logger.download_failed(self.name, result.url, result.error, retry_count)
                    return result

            # Check if remote file exists before downloading
            try:
                remote_stats = self.sftp.stat(remote_path)
            except FileNotFoundError:
                result.error = f"Remote file not found: {remote_path}"
                result.retryable = False  # File not found - don't retry
                self.logger.download_failed(self.name, result.url, result.error, retry_count)
                return result

            # Only create directory after confirming remote file exists
            local_path.mkdir(parents=True, exist_ok=True)
            file_path = local_path / filename

            # Download file
            self.sftp.get(remote_path, str(file_path))

            # Verify file exists and get size
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

        except FileNotFoundError:
            result.error = f"Remote file not found: {remote_path}"
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
        except PermissionError as e:
            result.error = f"Permission denied: {str(e)}"
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
        except Exception as e:
            result.error = f"SFTP error: {str(e)}"
            self.logger.download_failed(self.name, result.url, result.error, retry_count)
            self._cleanup()  # Force reconnect on next attempt

        return result

    def list_remote_files(self, remote_dir: str = None) -> list:
        """List files in remote directory."""
        if not self.sftp:
            if not self.connect():
                return []
        
        try:
            if remote_dir is None:
                remote_dir = self.source_config.path
            
            files = self.sftp.listdir(remote_dir)
            return files
        except Exception as e:
            self.logger.error(f"[SFTP LIST FAILED] {self.name} | {e}")
            return []

    def __del__(self):
        """Cleanup on destruction."""
        self._cleanup()
