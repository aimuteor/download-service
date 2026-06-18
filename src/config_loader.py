"""Configuration loader for the download service."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class DatetimeConfig:
    """Datetime parsing configuration for a source."""
    pattern: str = "%Y%m%d%H%M"
    timezone: str = "UTC"
    interval_minutes: int = 10
    offset_minutes: int = 1
    lookback_minutes: int = 60


@dataclass
class DestinationConfig:
    """Destination path configuration."""
    date_dir_pattern: str = "{dataDir}/{YYYYMMDD}"
    subdir: str = "data"
    var1_array: List[str] = field(default_factory=lambda: ["default"])
    output_timezone: str = "UTC"


@dataclass
class AuthCredentials:
    """Authentication credentials."""
    username: str = ""
    password: str = ""
    token: str = ""
    key_file: str = ""
    api_key: str = ""


@dataclass
class SourceConfig:
    """Configuration for a single download source."""
    name: str
    type: str  # http, sftp
    protocol: str = "https"
    host: str = ""
    port: int = 443
    path: str = "/"
    filename_pattern: str = "{YYYYMMDDHHMM}"
    method: str = "GET"
    auth_type: str = "none"  # none, basic, bearer, api_key, key
    auth_credentials: AuthCredentials = field(default_factory=AuthCredentials)
    headers: Dict[str, str] = field(default_factory=dict)
    post_data: Dict[str, Any] = field(default_factory=dict)
    datetime_config: DatetimeConfig = field(default_factory=DatetimeConfig)
    destination: DestinationConfig = field(default_factory=DestinationConfig)


@dataclass
class ArchiveConfig:
    """Archive configuration."""
    enabled: bool = True
    max_age_days: int = 1095  # 3 years
    archive_dir: str = "./archive"
    check_interval_hours: int = 24


@dataclass
class GeneralConfig:
    """General service configuration."""
    data_dir: str = "./data"
    log_dir: str = "./logs"
    log_level: str = "INFO"
    download_interval_minutes: int = 5
    max_retries: int = 3
    retry_delay_seconds: int = 30
    timezone: str = "UTC"


class ConfigLoader:
    """Loads and validates configuration from YAML file."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "config.yaml"
            )
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._general: GeneralConfig = None
        self._archive: ArchiveConfig = None
        self._sources: List[SourceConfig] = []

    def load(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}

        self._parse_general()
        self._parse_archive()
        self._parse_sources()

    def _parse_general(self) -> None:
        """Parse general configuration."""
        gen = self._config.get('general', {})
        self._general = GeneralConfig(
            data_dir=gen.get('data_dir', './data'),
            log_dir=gen.get('log_dir', './logs'),
            log_level=gen.get('log_level', 'INFO'),
            download_interval_minutes=gen.get('download_interval_minutes', 5),
            max_retries=gen.get('max_retries', 3),
            retry_delay_seconds=gen.get('retry_delay_seconds', 30),
            timezone=gen.get('timezone', 'UTC'),
        )

    def _parse_archive(self) -> None:
        """Parse archive configuration."""
        arc = self._config.get('archive', {})
        self._archive = ArchiveConfig(
            enabled=arc.get('enabled', True),
            max_age_days=arc.get('max_age_days', 1095),
            archive_dir=arc.get('archive_dir', './archive'),
            check_interval_hours=arc.get('check_interval_hours', 24),
        )

    def _parse_sources(self) -> None:
        """Parse source configurations."""
        sources = self._config.get('sources', [])
        for src in sources:
            # Parse auth credentials
            auth_creds = AuthCredentials(
                username=src.get('auth_credentials', {}).get('username', ''),
                password=src.get('auth_credentials', {}).get('password', ''),
                token=src.get('auth_credentials', {}).get('token', ''),
                key_file=src.get('auth_credentials', {}).get('key_file', ''),
                api_key=src.get('auth_credentials', {}).get('api_key', ''),
            )

            # Parse datetime config
            dt_cfg = src.get('datetime_config', {})
            dt_config = DatetimeConfig(
                pattern=dt_cfg.get('pattern', '%Y%m%d%H%M'),
                timezone=dt_cfg.get('timezone', 'UTC'),
                interval_minutes=dt_cfg.get('interval_minutes', 10),
                offset_minutes=dt_cfg.get('offset_minutes', 1),
                lookback_minutes=dt_cfg.get('lookback_minutes', 60),
            )

            # Parse destination config
            dest_cfg = src.get('destination', {})
            destination = DestinationConfig(
                date_dir_pattern=dest_cfg.get('date_dir_pattern', '{dataDir}/{YYYYMMDD}'),
                subdir=dest_cfg.get('subdir', 'data'),
                var1_array=dest_cfg.get('var1_array', ['default']),
                output_timezone=dest_cfg.get('output_timezone', 'UTC'),
            )

            source = SourceConfig(
                name=src.get('name', 'unknown'),
                type=src.get('type', 'http'),
                protocol=src.get('protocol', 'https'),
                host=src.get('host', ''),
                port=src.get('port', 443),
                path=src.get('path', '/'),
                filename_pattern=src.get('filename_pattern', '{YYYYMMDDHHMM}'),
                method=src.get('method', 'GET'),
                auth_type=src.get('auth_type', 'none'),
                auth_credentials=auth_creds,
                headers=src.get('headers', {}),
                post_data=src.get('post_data', {}),
                datetime_config=dt_config,
                destination=destination,
            )
            self._sources.append(source)

    @property
    def general(self) -> GeneralConfig:
        return self._general

    @property
    def archive(self) -> ArchiveConfig:
        return self._archive

    @property
    def sources(self) -> List[SourceConfig]:
        return self._sources

    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = {}
        self._sources = []
        self.load()
