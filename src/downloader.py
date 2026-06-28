"""Download runner for cron-based execution."""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from .config_loader import ConfigLoader, SourceConfig, GeneralConfig
from .downloaders.downloader_factory import DownloaderFactory
from .downloaders.base_downloader import DownloadResult
from .parsers.datetime_parser import DatetimeParser
from .archivers.file_archiver import FileArchiver
from .utils.logger import DownloadLogger
from .utils.status_tracker import get_tracker


@dataclass
class CycleStats:
    """Statistics for a download cycle."""
    cycle_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    sources_processed: int = 0
    files_downloaded: int = 0
    files_failed: int = 0
    total_bytes: int = 0
    duration: float = 0.0


class DownloadRunner:
    """Download runner for cron-based execution."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.config_loader = ConfigLoader(config_path)
        self.logger: Optional[DownloadLogger] = None
        self.downloader_factory: Optional[DownloaderFactory] = None
        self.archiver: Optional[FileArchiver] = None
        self.status_tracker = None
        self._cycle_count = 0

    def initialize(self) -> None:
        """Initialize all service components."""
        # Load configuration
        self.config_loader.load()
        general = self.config_loader.general
        
        # Initialize logger
        self.logger = DownloadLogger(
            name="download_service",
            log_dir=general.log_dir,
            log_level=general.log_level
        )
        
        self.logger.info("=" * 60)
        self.logger.info("[INITIALIZING]")
        self.logger.config_loaded(
            len(self.config_loader.sources),
            {'data_dir': general.data_dir}
        )
        
        # Initialize status tracker
        self.status_tracker = get_tracker(general.data_dir)
        
        # Initialize downloader factory
        self.downloader_factory = DownloaderFactory(
            self.logger,
            timeout=30
        )
        
        # Initialize archiver
        self.archiver = FileArchiver(self.config_loader.archive, self.logger)
        
        # Create data directory
        data_dir = Path(general.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Test connections to sources
        self._test_connections()
        
        # Run archive check
        if self.config_loader.archive.enabled:
            self.archiver.run_archive(data_dir)
        
        self.logger.info("[SERVICE INITIALIZED]")

    def _test_connections(self) -> None:
        """Test connections to all configured sources."""
        self.logger.info("[TESTING CONNECTIONS]")
        for source in self.config_loader.sources:
            try:
                downloader = self.downloader_factory.create(source)
                if downloader.test_connection():
                    self.logger.info(f"[CONNECTION OK] {source.name}")
                else:
                    self.logger.warning(f"[CONNECTION FAILED] {source.name}")
            except Exception as e:
                self.logger.error(f"[CONNECTION ERROR] {source.name} | {e}")

    def _build_destination_path(self, source: SourceConfig, dt: datetime) -> Path:
        """
        Build the destination path for a downloaded file.
        
        Args:
            source: Source configuration
            dt: Datetime for path (in UTC)
            
        Returns:
            Path object for the destination directory
        """
        config = source.destination
        general = self.config_loader.general
        
        # Convert datetime to UTC for path
        utc_dt = dt.astimezone(ZoneInfo('UTC'))
        
        # Build datetime replacements dict for path formatting
        datetime_replacements = {
            'YYYY': utc_dt.strftime('%Y'),
            'MM': utc_dt.strftime('%m'),
            'DD': utc_dt.strftime('%d'),
            'HH': utc_dt.strftime('%H'),
            'MI': utc_dt.strftime('%M'),
            'YYYYMMDD': utc_dt.strftime('%Y%m%d'),
        }
        
        # Build path with datetime placeholders
        path_str = config.date_dir_pattern.format(
            dataDir=general.data_dir,
            **datetime_replacements
        )
        
        # Also process subdir with datetime placeholders
        subdir = config.subdir.format(**datetime_replacements)
        
        path = Path(path_str) / subdir
        
        # Add time subdirectory if configured (deprecated, use {HH}{MI} in subdir instead)
        if config.include_hhmm_dir:
            path = path / utc_dt.strftime('%H%M')
        
        return path

    def _process_source(self, source: SourceConfig) -> List[DownloadResult]:
        """
        Process a single source: generate filenames and download files.
        
        Args:
            source: Source configuration
            
        Returns:
            List of download results
        """
        results = []
        downloader = self.downloader_factory.get_or_create(source)
        datetime_parser = DatetimeParser(source.datetime_config)
        
        # Get list of datetimes to download
        datetimes = datetime_parser.calculate_datetime_list()
        
        # Generate all combinations of var values
        var_names = sorted(source.var_arrays.keys())  # e.g., ['var1', 'var2']
        var_values_list = [source.var_arrays[name] for name in var_names]
        
        # Import itertools for cartesian product
        from itertools import product
        
        for dt in datetimes:
            # Generate filename base (without var substitutions)
            filename_base = datetime_parser.generate_filename(
                source.filename_pattern,
                dt
            )
            
            # Iterate through all var combinations
            for var_values in product(*var_values_list):
                # Build var substitution dict
                var_subs = dict(zip(var_names, var_values))
                
                # Substitute vars in filename
                filename = filename_base
                for var_name, var_value in var_subs.items():
                    filename = filename.replace(f'{{{var_name}}}', var_value)
                
                # Build URL (with datetime for path substitution)
                url = downloader.build_url(filename, dt)
                
                # Build destination path
                dest_path = self._build_destination_path(source, dt)
                
                # Add var subdirectory if dir_array is true
                if source.destination.dir_array:
                    # Use the var specified by dir_array_key
                    dir_key = source.destination.dir_array_key
                    if dir_key in var_names:
                        key_index = var_names.index(dir_key)
                        dir_name = var_values[key_index]
                        dest_path = dest_path / dir_name
                
                # Check if file already exists
                file_path = dest_path / filename
                if file_path.exists() and not source.force_download:
                    self.logger.debug(f"[FILE EXISTS SKIP] {source.name} | {filename}")
                    continue
                
                self.logger.download_start(source.name, url, filename)
                
                # Download with retries
                for attempt in range(self.config_loader.general.max_retries):
                    result = downloader.download(url, dest_path, filename, attempt)
                    
                    if result.success:
                        # Record success in status tracker
                        if self.status_tracker:
                            self.status_tracker.record_success(source.name, source.type)
                        results.append(result)
                        break
                    elif not result.retryable:
                        # Non-retryable error (4xx, file not found, etc.) - skip retry
                        self.logger.download_failed(
                            source.name, url, result.error or "Unknown error", attempt
                        )
                        # Record failure in status tracker
                        if self.status_tracker:
                            self.status_tracker.record_failure(
                                source.name, source.type, 
                                result.error or "Unknown error", url
                            )
                        results.append(result)
                        break
                    elif attempt < self.config_loader.general.max_retries - 1:
                        self.logger.download_retry(
                            source.name, url, attempt + 2,
                            self.config_loader.general.max_retries
                        )
                        time.sleep(self.config_loader.general.retry_delay_seconds)
                    else:
                        # All retries exhausted - record failure
                        if self.status_tracker:
                            self.status_tracker.record_failure(
                                source.name, source.type,
                                result.error or "Max retries exceeded", url
                            )
                        results.append(result)
        
        return results

    def run_once(self) -> CycleStats:
        """
        Run a single download cycle.
        
        This is called by cron on schedule.
        
        Returns:
            CycleStats with download results
        """
        self._cycle_count += 1
        stats = CycleStats(
            cycle_id=self._cycle_count,
            start_time=datetime.now()
        )
        
        self.logger.cycle_start(stats.cycle_id)
        
        all_results: List[DownloadResult] = []
        
        # Process each source
        for source in self.config_loader.sources:
            try:
                results = self._process_source(source)
                all_results.extend(results)
                stats.sources_processed += 1
            except Exception as e:
                self.logger.error(f"[SOURCE ERROR] {source.name} | {e}")
        
        # Calculate stats
        for result in all_results:
            if result.success:
                stats.files_downloaded += 1
                stats.total_bytes += result.file_size
            else:
                stats.files_failed += 1
        
        stats.end_time = datetime.now()
        stats.duration = (stats.end_time - stats.start_time).total_seconds()
        
        self.logger.cycle_complete(
            stats.cycle_id,
            stats.files_downloaded,
            stats.files_failed,
            stats.duration
        )
        
        return stats

    def redownload(self, start_dt: str, end_dt: str, source_name: str = None, force: bool = False) -> CycleStats:
        """
        Re-download files for a specific time range.
        
        Args:
            start_dt: Start datetime string (YYYYMMDDHHMM format)
            end_dt: End datetime string (YYYYMMDDHHMM format)
            source_name: Optional source name to filter (default: all sources)
            force: Force re-download even if file exists
            
        Returns:
            CycleStats with download results
        """
        self._cycle_count += 1
        stats = CycleStats(
            cycle_id=self._cycle_count,
            start_time=datetime.now()
        )
        
        self.logger.info(f"[REDOWNLOAD START] {start_dt} to {end_dt} | Source: {source_name or 'ALL'} | Force: {force}")
        
        # Parse start and end datetimes
        start_time = datetime.strptime(start_dt, '%Y%m%d%H%M')
        end_time = datetime.strptime(end_dt, '%Y%m%d%H%M')
        
        # Filter sources
        sources_to_process = []
        for source in self.config_loader.sources:
            if source_name is None or source.name == source_name:
                sources_to_process.append(source)
        
        if not sources_to_process:
            self.logger.warning(f"[REDOWNLOAD] No sources found matching: {source_name}")
            return stats
        
        all_results: List[DownloadResult] = []
        
        for source in sources_to_process:
            try:
                results = self._process_source_redownload(source, start_time, end_time, force)
                all_results.extend(results)
                stats.sources_processed += 1
            except Exception as e:
                self.logger.error(f"[SOURCE ERROR] {source.name} | {e}")
        
        # Calculate stats
        for result in all_results:
            if result.success:
                stats.files_downloaded += 1
                stats.total_bytes += result.file_size
            else:
                stats.files_failed += 1
        
        stats.end_time = datetime.now()
        stats.duration = (stats.end_time - stats.start_time).total_seconds()
        
        self.logger.info(f"[REDOWNLOAD COMPLETE] Downloaded: {stats.files_downloaded} | Failed: {stats.files_failed}")
        
        return stats

    def _process_source_redownload(self, source: SourceConfig, start_time: datetime, 
                                   end_time: datetime, force: bool = False) -> List[DownloadResult]:
        """
        Process a source for redownload with custom time range.
        
        Args:
            source: Source configuration
            start_time: Start datetime
            end_time: End datetime
            force: Force re-download even if file exists
            
        Returns:
            List of download results
        """
        results = []
        downloader = self.downloader_factory.get_or_create(source)
        datetime_parser = DatetimeParser(source.datetime_config)
        
        # Generate all combinations of var values
        var_names = sorted(source.var_arrays.keys())
        var_values_list = [source.var_arrays[name] for name in var_names]
        
        from itertools import product
        
        # Calculate datetime slots between start and end
        interval = timedelta(minutes=source.datetime_config.interval_minutes)
        current_time = start_time
        
        while current_time <= end_time:
            # Generate filename base (without var substitutions)
            filename_base = datetime_parser.generate_filename(
                source.filename_pattern,
                current_time
            )
            
            # Iterate through all var combinations
            for var_values in product(*var_values_list):
                # Build var substitution dict
                var_subs = dict(zip(var_names, var_values))
                
                # Substitute vars in filename
                filename = filename_base
                for var_name, var_value in var_subs.items():
                    filename = filename.replace(f'{{{var_name}}}', var_value)
                
                # Build URL (with datetime for path substitution)
                url = downloader.build_url(filename, current_time)
                
                # Build destination path
                dest_path = self._build_destination_path(source, current_time)
                
                # Add var subdirectory if dir_array is true
                if source.destination.dir_array:
                    # Use the var specified by dir_array_key
                    dir_key = source.destination.dir_array_key
                    if dir_key in var_names:
                        key_index = var_names.index(dir_key)
                        dir_name = var_values[key_index]
                        dest_path = dest_path / dir_name
                
                # Check if file already exists
                file_path = dest_path / filename
                if file_path.exists() and not force:
                    self.logger.debug(f"[FILE EXISTS SKIP] {source.name} | {filename}")
                    continue
                
                self.logger.download_start(source.name, url, filename)
                
                # Download with retries
                for attempt in range(self.config_loader.general.max_retries):
                    result = downloader.download(url, dest_path, filename, attempt)
                    
                    if result.success:
                        results.append(result)
                        break
                    elif not result.retryable:
                        # Non-retryable error (4xx, file not found, etc.) - skip retry
                        self.logger.download_failed(
                            source.name, url, result.error or "Unknown error", attempt
                        )
                        results.append(result)
                        break
                    elif attempt < self.config_loader.general.max_retries - 1:
                        self.logger.download_retry(
                            source.name, url, attempt + 2,
                            self.config_loader.general.max_retries
                        )
                        time.sleep(self.config_loader.general.retry_delay_seconds)
                    else:
                        results.append(result)
            
            current_time += interval
        
        return results

    def get_status(self) -> dict:
        """Get current service status."""
        return {
            'cycle_count': self._cycle_count,
            'archive_stats': self.archiver.get_archive_stats() if self.archiver else None,
            'available_downloader_types': DownloaderFactory.get_available_types(),
        }
