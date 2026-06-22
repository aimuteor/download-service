"""HTTP/HTTPS downloader with GET and POST support."""

import time
import requests
from pathlib import Path
from typing import Optional
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base_downloader import BaseDownloader, DownloadResult, format_path_with_datetime
from ..utils.logger import DownloadLogger


class HTTPDownloader(BaseDownloader):
    """HTTP/HTTPS downloader supporting GET and POST methods."""

    def __init__(self, source_config, logger: DownloadLogger, timeout: int = 30):
        super().__init__(source_config, logger)
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=0,  # We handle retries ourselves
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update(self.source_config.headers)
        session.headers.setdefault('User-Agent', 'DownloadService/1.0')
        
        return session

    def test_connection(self) -> bool:
        """Test HTTP connection to the server."""
        try:
            url = self.build_url('/')
            response = self.session.head(url, timeout=self.timeout, 
                                        headers=self.get_auth_headers())
            return response.status_code < 400
        except requests.RequestException as e:
            self.logger.warning(f"[CONNECTION TEST FAILED] {self.name} | Error: {e}")
            return False

    def build_url(self, filename: str = None, dt: datetime = None) -> str:
        """Build full URL from components."""
        protocol = self.source_config.protocol
        host = self.source_config.host
        port = self.source_config.port
        path = self.source_config.path
        
        # Apply datetime formatting if provided
        if dt is not None:
            path = format_path_with_datetime(path, dt)

        if filename:
            # Ensure path ends with / if needed
            if not path.endswith('/'):
                path = path + '/'
            full_path = path + filename
        else:
            full_path = path

        if port == 443 or port == 80:
            url = f"{protocol}://{host}{full_path}"
        else:
            url = f"{protocol}://{host}:{port}{full_path}"

        return url

    def download(self, url: str, local_path: Path, filename: str, 
                 retry_count: int = 0) -> DownloadResult:
        """Download file using HTTP GET or POST."""
        start_time = time.time()
        result = DownloadResult(
            success=False,
            source_name=self.name,
            url=url,
            filename=filename,
            retry_count=retry_count
        )

        try:
            # Prepare request first
            headers = self.get_auth_headers()
            
            # Make request based on method
            if self.source_config.method.upper() == 'POST':
                response = self.session.post(
                    url,
                    data=self.source_config.post_data,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
            else:  # GET
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True
                )

            # Check response status BEFORE creating directories
            if response.status_code >= 400:
                result.error = f"HTTP {response.status_code}: {response.reason}"
                # 4xx errors are not retryable (client errors - file doesn't exist or permission denied)
                result.retryable = response.status_code < 500
                self.logger.download_failed(self.name, url, result.error, retry_count)
                return result

            # Only create directory and save file after confirming download will succeed
            local_path.mkdir(parents=True, exist_ok=True)
            file_path = local_path / filename

            # Download with streaming to handle large files
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Get file size
            result.file_size = file_path.stat().st_size
            result.local_path = str(file_path)
            result.success = True
            result.duration = time.time() - start_time

            # Calculate hash for verification
            result.content_hash = self.calculate_hash(file_path)

            self.logger.download_success(
                self.name, filename, result.file_size, result.duration
            )

        except requests.exceptions.Timeout:
            result.error = "Connection timeout"
            self.logger.download_failed(self.name, url, result.error, retry_count)
        except requests.exceptions.ConnectionError as e:
            result.error = f"Connection error: {str(e)}"
            self.logger.download_failed(self.name, url, result.error, retry_count)
            # Close session to reset connection pool on connection errors
            self.close()
        except requests.exceptions.RequestException as e:
            result.error = f"Request error: {str(e)}"
            self.logger.download_failed(self.name, url, result.error, retry_count)
        except (IOError, OSError) as e:
            # Disk full, permission denied, etc.
            result.error = f"Disk error: {str(e)}"
            result.retryable = False  # Don't retry disk errors
            self.logger.download_failed(self.name, url, result.error, retry_count)
        except Exception as e:
            result.error = f"Unexpected error: {str(e)}"
            self.logger.download_failed(self.name, url, result.error, retry_count)

        return result

    def close(self):
        """Close the session."""
        if self.session:
            self.session.close()
