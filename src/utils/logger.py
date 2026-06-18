"""Comprehensive logging utility for the download service."""

import os
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class DownloadLogger:
    """Centralized logging for the download service."""

    def __init__(self, name: str = "download_service", log_dir: str = "./logs", 
                 log_level: str = "INFO", log_to_console: bool = True):
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.log_to_console = log_to_console
        self._logger: Optional[logging.Logger] = None
        self._setup_logger()

    def _setup_logger(self) -> None:
        """Set up the logger with file and console handlers."""
        self._logger = logging.getLogger(self.name)
        self._logger.setLevel(self.log_level)
        self._logger.handlers = []  # Clear existing handlers

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # File handler - daily rotation
        log_file = self.log_dir / f"download_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding='utf-8'
        )
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

        # Error file handler - separate file for errors
        error_file = self.log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        self._logger.addHandler(error_handler)

        # Console handler
        if self.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    def debug(self, msg: str, **kwargs) -> None:
        self._logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs) -> None:
        self._logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        self._logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs) -> None:
        self._logger.error(msg, **kwargs)

    def critical(self, msg: str, **kwargs) -> None:
        self._logger.critical(msg, **kwargs)

    def download_start(self, source: str, url: str, filename: str) -> None:
        self.info(f"[DOWNLOAD START] Source: {source} | URL: {url} | File: {filename}")

    def download_success(self, source: str, filename: str, size: int, duration: float) -> None:
        self.info(f"[DOWNLOAD SUCCESS] Source: {source} | File: {filename} | Size: {size} bytes | Duration: {duration:.2f}s")

    def download_failed(self, source: str, url: str, error: str, retry: int = 0) -> None:
        self.warning(f"[DOWNLOAD FAILED] Source: {source} | URL: {url} | Error: {error} | Retry: {retry}")

    def download_retry(self, source: str, url: str, attempt: int, max_retries: int) -> None:
        self.info(f"[DOWNLOAD RETRY] Source: {source} | URL: {url} | Attempt: {attempt}/{max_retries}")

    def archive_start(self, file_path: str, age_days: int) -> None:
        self.info(f"[ARCHIVE START] File: {file_path} | Age: {age_days} days")

    def archive_complete(self, file_path: str, archive_path: str) -> None:
        self.info(f"[ARCHIVE COMPLETE] File: {file_path} -> Archive: {archive_path}")

    def cycle_start(self, cycle_id: int) -> None:
        self.info(f"[CYCLE START] Cycle ID: {cycle_id}")

    def cycle_complete(self, cycle_id: int, downloaded: int, failed: int, duration: float) -> None:
        self.info(f"[CYCLE COMPLETE] Cycle ID: {cycle_id} | Downloaded: {downloaded} | Failed: {failed} | Duration: {duration:.2f}s")

    def config_loaded(self, sources_count: int, general: dict) -> None:
        self.info(f"[CONFIG LOADED] Sources: {sources_count} | General: {general}")
