"""Base downloader class and download result."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import hashlib


@dataclass
class DownloadResult:
    """Result of a download operation."""
    success: bool
    source_name: str
    url: str
    local_path: Optional[str] = None
    filename: Optional[str] = None
    file_size: int = 0
    error: Optional[str] = None
    retry_count: int = 0
    duration: float = 0.0
    content_hash: Optional[str] = None

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "FAILED"
        return f"[{status}] {self.source_name} | {self.filename} | {self.file_size} bytes | {self.duration:.2f}s"


class BaseDownloader(ABC):
    """Abstract base class for all downloaders."""

    def __init__(self, source_config, logger):
        self.source_config = source_config
        self.logger = logger
        self.name = source_config.name

    @abstractmethod
    def download(self, url: str, local_path: Path, filename: str, retry_count: int = 0) -> DownloadResult:
        """
        Download a file from URL to local path.
        
        Args:
            url: Full URL to download from
            local_path: Directory to save the file
            filename: Filename to save as
            retry_count: Current retry attempt number
            
        Returns:
            DownloadResult with operation details
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test connection to the data source."""
        pass

    @abstractmethod
    def build_url(self, filename: str) -> str:
        """Build the full URL for a filename."""
        pass

    def get_auth_headers(self) -> dict:
        """Get authentication headers based on auth type."""
        headers = {}
        auth_type = self.source_config.auth_type
        creds = self.source_config.auth_credentials

        if auth_type == 'basic':
            import base64
            auth_str = f"{creds.username}:{creds.password}"
            encoded = base64.b64encode(auth_str.encode()).decode()
            headers['Authorization'] = f"Basic {encoded}"
        elif auth_type == 'bearer':
            headers['Authorization'] = f"Bearer {creds.token}"
        elif auth_type == 'api_key':
            headers['X-API-Key'] = creds.api_key

        return headers

    @staticmethod
    def calculate_hash(file_path: Path, algorithm: str = 'sha256') -> str:
        """Calculate hash of a file."""
        hash_func = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def file_exists_and_valid(self, file_path: Path, expected_size: int = 0) -> bool:
        """Check if file exists and is valid."""
        if not file_path.exists():
            return False
        if expected_size > 0 and file_path.stat().st_size != expected_size:
            return False
        return True
