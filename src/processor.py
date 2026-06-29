"""Source processor for handling download tasks."""

import time
from pathlib import Path
from typing import List
from datetime import datetime
from itertools import product

from .parsers.datetime_parser import DatetimeParser
from .downloaders.base_downloader import DownloadResult
from .downloaders.downloader_factory import DownloaderFactory
from .path_utils import build_destination_path


class SourceProcessor:
    """Handles processing of a single download source."""

    def __init__(self, source, config_loader, logger, status_tracker=None):
        self.source = source
        self.config_loader = config_loader
        self.logger = logger
        self.status_tracker = status_tracker
        self.downloader_factory = DownloaderFactory(logger, timeout=30)

    def process(self) -> List[DownloadResult]:
        """Process source for scheduled download (lookback period)."""
        downloader = self.downloader_factory.get_or_create(self.source)
        datetime_parser = DatetimeParser(self.source.datetime_config)
        datetimes = datetime_parser.calculate_datetime_list()
        return self._process_tasks(downloader, datetimes)

    def process_redownload(self, start_time: datetime, end_time: datetime, 
                          force: bool = False) -> List[DownloadResult]:
        """Process source for redownload with custom time range."""
        downloader = self.downloader_factory.get_or_create(self.source)
        
        # Temporarily set force_download
        original_force = self.source.force_download
        self.source.force_download = force

        # Generate datetime list from start to end
        interval = datetime.timedelta(minutes=self.source.datetime_config.interval_minutes)
        datetimes = []
        current = start_time
        while current <= end_time:
            datetimes.append(current)
            current += interval

        try:
            return self._process_tasks(downloader, datetimes)
        finally:
            self.source.force_download = original_force

    def _process_tasks(self, downloader, datetimes: List[datetime]) -> List[DownloadResult]:
        """Process download tasks for given datetimes."""
        results = []
        datetime_parser = DatetimeParser(self.source.datetime_config)

        # Generate var combinations
        var_names = sorted(self.source.var_arrays.keys())
        var_values_list = [self.source.var_arrays[name] for name in var_names]

        for dt in datetimes:
            filename_base = datetime_parser.generate_filename(
                self.source.filename_pattern, dt
            )

            for var_values in product(*var_values_list):
                # Substitute vars in filename
                filename = filename_base
                for var_name, var_value in zip(var_names, var_values):
                    filename = filename.replace(f'{{{var_name}}}', var_value)

                # Build URL and destination path
                url = downloader.build_url(filename, dt)
                dest_path = self._build_path(dt)

                # Add var subdirectory if configured
                if self.source.destination.dir_array:
                    dir_key = self.source.destination.dir_array_key
                    if dir_key in var_names:
                        key_index = var_names.index(dir_key)
                        dir_name = var_values[key_index]
                        dest_path = dest_path / dir_name

                # Check if file exists
                file_path = dest_path / filename
                if file_path.exists() and not self.source.force_download:
                    self.logger.debug(f"[FILE EXISTS SKIP] {self.source.name} | {filename}")
                    continue

                # Download with retry
                result = self._download_with_retry(
                    downloader, url, dest_path, filename
                )
                results.append(result)

        return results

    def _build_path(self, dt: datetime) -> Path:
        """Build destination path for datetime."""
        dest_config = self.source.destination
        dt_config = self.source.datetime_config
        
        return build_destination_path(
            base_dir=self.config_loader.general.data_dir,
            dest_config=dest_config,
            dt=dt,
            timezone=dt_config.timezone
        )

    def _download_with_retry(self, downloader, url: str, dest_path: Path, 
                            filename: str) -> DownloadResult:
        """Download a single file with retry logic."""
        self.logger.download_start(self.source.name, url, filename)

        for attempt in range(self.config_loader.general.max_retries):
            result = downloader.download(url, dest_path, filename, attempt)

            if result.success:
                if self.status_tracker:
                    self.status_tracker.record_success(self.source.name, self.source.type)
                return result
            elif not result.retryable:
                self._record_failure(result)
                return result
            elif attempt < self.config_loader.general.max_retries - 1:
                self.logger.download_retry(
                    self.source.name, url, attempt + 2,
                    self.config_loader.general.max_retries
                )
                time.sleep(self.config_loader.general.retry_delay_seconds)
            else:
                self._record_failure(result)
                return result

    def _record_failure(self, result: DownloadResult):
        """Record a failed download to status tracker."""
        if self.status_tracker:
            self.status_tracker.record_failure(
                self.source.name, self.source.type,
                result.error or "Unknown error", result.url
            )
