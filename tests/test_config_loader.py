"""Tests for configuration loader."""

import pytest
import tempfile
import yaml
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config_loader import ConfigLoader, GeneralConfig, ArchiveConfig, SourceConfig


class TestConfigLoader:
    """Test ConfigLoader functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config_content = """
general:
  data_dir: "./test_data"
  log_dir: "./test_logs"
  log_level: "DEBUG"
  download_interval_minutes: 10
  max_retries: 5
  retry_delay_seconds: 60

archive:
  enabled: true
  max_age_days: 730
  archive_dir: "./test_archive"
  check_interval_hours: 12

sources:
  - name: "test_http"
    type: "http"
    protocol: "https"
    host: "example.com"
    port: 443
    path: "/data"
    filename_pattern: "file_{YYYYMMDDHHMM}.dat"
    method: "GET"
    auth_type: "basic"
    auth_credentials:
      username: "user"
      password: "pass"
    datetime_config:
      pattern: "%Y%m%d%H%M"
      timezone: "UTC"
      interval_minutes: 15
      offset_minutes: 2
      lookback_minutes: 120
    destination:
      date_dir_pattern: "{dataDir}/{YYYYMMDD}"
      subdir: "test_data"
      var1_array: ["a", "b"]
      output_timezone: "UTC"

  - name: "test_sftp"
    type: "sftp"
    host: "sftp.example.com"
    port: 22
    path: "/data"
    filename_pattern: "sat_{YYYYMMDDHHMM}.nc"
    auth_type: "key"
    auth_credentials:
      username: "sftpuser"
      key_file: "~/.ssh/id_rsa"
"""
        # Create temp config file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        self.temp_file.write(self.config_content)
        self.temp_file.close()

    def teardown_method(self):
        """Clean up temp files."""
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_load_general_config(self):
        """Test loading general configuration."""
        loader = ConfigLoader(self.temp_file.name)
        loader.load()
        
        assert isinstance(loader.general, GeneralConfig)
        assert loader.general.data_dir == "./test_data"
        assert loader.general.log_dir == "./test_logs"
        assert loader.general.log_level == "DEBUG"
        assert loader.general.download_interval_minutes == 10
        assert loader.general.max_retries == 5
        assert loader.general.retry_delay_seconds == 60

    def test_load_archive_config(self):
        """Test loading archive configuration."""
        loader = ConfigLoader(self.temp_file.name)
        loader.load()
        
        assert isinstance(loader.archive, ArchiveConfig)
        assert loader.archive.enabled is True
        assert loader.archive.max_age_days == 730
        assert loader.archive.archive_dir == "./test_archive"
        assert loader.archive.check_interval_hours == 12

    def test_load_sources(self):
        """Test loading source configurations."""
        loader = ConfigLoader(self.temp_file.name)
        loader.load()
        
        assert len(loader.sources) == 2
        
        # Check first source (HTTP)
        http_source = loader.sources[0]
        assert http_source.name == "test_http"
        assert http_source.type == "http"
        assert http_source.protocol == "https"
        assert http_source.host == "example.com"
        assert http_source.port == 443
        assert http_source.method == "GET"
        assert http_source.auth_type == "basic"
        assert http_source.auth_credentials.username == "user"
        assert http_source.auth_credentials.password == "pass"
        assert http_source.datetime_config.interval_minutes == 15
        assert http_source.datetime_config.offset_minutes == 2
        assert http_source.datetime_config.lookback_minutes == 120
        assert "a" in http_source.destination.var1_array
        assert "b" in http_source.destination.var1_array
        
        # Check second source (SFTP)
        sftp_source = loader.sources[1]
        assert sftp_source.name == "test_sftp"
        assert sftp_source.type == "sftp"
        assert sftp_source.auth_type == "key"
        assert sftp_source.auth_credentials.username == "sftpuser"
        assert sftp_source.auth_credentials.key_file == "~/.ssh/id_rsa"

    def test_config_not_found(self):
        """Test handling of missing config file."""
        loader = ConfigLoader("/nonexistent/path/config.yaml")
        
        with pytest.raises(FileNotFoundError):
            loader.load()

    def test_empty_config(self):
        """Test handling of empty config."""
        temp_empty = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_empty.write("")
        temp_empty.close()
        
        loader = ConfigLoader(temp_empty.name)
        loader.load()
        
        # Should have defaults
        assert loader.general.data_dir == "./data"
        assert len(loader.sources) == 0
        
        Path(temp_empty.name).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
