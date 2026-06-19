"""Download service for cron-based execution."""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

from .config_loader import ConfigLoader, SourceConfig, GeneralConfig
from .downloaders.downloader_factory import DownloaderFactory
from .downloaders.base_downloader import DownloadResult
from .parsers.datetime_parser import DatetimeParser
from .archivers.file_archiver import FileArchiver
from .utils.logger import DownloadLogger


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


class DownloadService:
    """Download service for cron-based operation."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.config_loader = ConfigLoader(config_path)
        self.logger: Optional[DownloadLogger] = None
        self.downloader_factory: Optional[DownloaderFactory] = None
        self.archiver: Optional[FileArchiver] = None
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
        self.logger.info("[SERVICE INITIALIZING]")
        self.logger.config_loaded(
            len(self.config_loader.sources),
            {'data_dir': general.data_dir, 'interval': general.download_interval_minutes}
        )
        
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
        utc_date = dt.strftime('%Y%m%d')
        utc_time = dt.strftime('%H%M')
        
        # Build path with optional time subdirectory
        path = Path(config.date_dir_pattern.format(
            dataDir=general.data_dir,
            YYYYMMDD=utc_date
        )) / config.subdir
        
        # Add time subdirectory if configured
        if config.include_hhmm_dir:
            path = path / utc_time
        
        return path

    def _process_source(self, source: SourceConfig) -> List[DownloadResult]:
        """
        Process a single source: generate filenames and download files.
        
        Args:
            source: Source configuration
            force_download: If True, skip file existence check
            
        Returns:
            List of download results
        """
        results = []
        downloader = self.downloader_factory.get_or_create(source)
        datetime_parser = DatetimeParser(source.datetime_config)
        
        # Get list of datetimes to download
        datetimes = datetime_parser.calculate_datetime_list()
        
        for var1 in source.destination.var1_array:
            for dt in datetimes:
                # Generate filename
                filename = datetime_parser.generate_filename(
                    source.filename_pattern,
                    dt
                )
                
                # Substitute {var1} placeholder
                filename = filename.replace('{var1}', var1)
                
                # Build URL and destination path
                url = downloader.build_url(filename)
                
                dest_path = self._build_destination_path(source, dt)
                dest_path = dest_path / var1  # Add var1 subdirectory
                
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
        
        return results

    def run_once(self) -> CycleStats:
        """
        Run a single download cycle.
        
        This is called by cron every download_interval_minutes.
        
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
        
        # Calculate datetime slots between start and end
        interval = timedelta(minutes=source.datetime_config.interval_minutes)
        current_time = start_time
        
        while current_time <= end_time:
            for var1 in source.destination.var1_array:
                # Generate filename
                filename = datetime_parser.generate_filename(
                    source.filename_pattern,
                    current_time
                )
                
                # Substitute {var1} placeholder
                filename = filename.replace('{var1}', var1)
                
                # Build URL and destination path
                url = downloader.build_url(filename)
                
                dest_path = self._build_destination_path(source, current_time)
                dest_path = dest_path / var1
                
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
