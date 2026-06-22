"""Configuration loader for the download service."""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class DatetimeConfig:
    """Datetime parsing configuration for a source."""
    timezone: str = "UTC"
    interval_minutes: int = 10
    offset_minutes: int = 1
    lookback_minutes: int = 60


@dataclass
class DestinationConfig:
    """Destination path configuration."""
    date_dir_pattern: str = "{dataDir}/{YYYYMMDD}"
    subdir: str = "data"
    include_hhmm_dir: bool = False  # Add {HHMM} subdirectory in path
    # Directory structure option:
    # true = create subdirs based on dir_array_key (e.g., subdir/temp/, subdir/humid/)
    # false = files go directly under subdir (e.g., subdir/sensor_temp_xxx.dat)
    dir_array: bool = True
    # Which var to use for directory name when dir_array is true (e.g., "var1", "var2")
    dir_array_key: str = "var1"


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
    force_download: bool = False  # Force re-download even if file exists
    # Variable arrays for filename substitution (e.g., var1_array: ["temp", "humid"])
    # Corresponding placeholders in filename_pattern: {var1}, {var2}, etc.
    var_arrays: Dict[str, List[str]] = field(default_factory=lambda: {"var1": ["default"]})
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
    """General configuration."""
    data_dir: str = "./data"
    log_dir: str = "./logs"
    log_level: str = "INFO"
    max_retries: int = 3
    retry_delay_seconds: int = 30


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
            max_retries=gen.get('max_retries', 3),
            retry_delay_seconds=gen.get('retry_delay_seconds', 30),
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
        # Get destination defaults from general config
        dest_defaults = self._config.get('destination_defaults', {})
        
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
                timezone=dt_cfg.get('timezone', 'UTC'),
                interval_minutes=dt_cfg.get('interval_minutes', 10),
                offset_minutes=dt_cfg.get('offset_minutes', 1),
                lookback_minutes=dt_cfg.get('lookback_minutes', 60),
            )

            # Parse destination config (with defaults)
            dest_cfg = src.get('destination', {})
            destination = DestinationConfig(
                date_dir_pattern=dest_cfg.get('date_dir_pattern', dest_defaults.get('date_dir_pattern', '{dataDir}/{YYYYMMDD}')),
                subdir=dest_cfg.get('subdir', dest_defaults.get('subdir', 'data')),
                include_hhmm_dir=dest_cfg.get('include_hhmm_dir', dest_defaults.get('include_hhmm_dir', False)),
                dir_array=dest_cfg.get('dir_array', dest_defaults.get('dir_array', True)),
                dir_array_key=dest_cfg.get('dir_array_key', dest_defaults.get('dir_array_key', 'var1')),
            )

            # Parse variable arrays (var1_array, var2_array, etc.)
            var_arrays = {}
            for key, value in src.items():
                if key.endswith('_array'):
                    # e.g., var1_array -> var1
                    var_name = key.rsplit('_array', 1)[0]
                    var_arrays[var_name] = value
            # Also check in destination for backward compat
            for key, value in dest_cfg.items():
                if key.endswith('_array'):
                    var_name = key.rsplit('_array', 1)[0]
                    if var_name not in var_arrays:
                        var_arrays[var_name] = value
            # Default var1 if no arrays specified
            if not var_arrays:
                var_arrays = {"var1": ["default"]}

            source = SourceConfig(
                name=src.get('name', 'unknown'),
                type=src.get('type', 'http'),
                force_download=src.get('force_download', False),
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
                var_arrays=var_arrays,
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
