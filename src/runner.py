"""Download runner for cron-based execution."""

from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .config_loader import ConfigLoader
from .archivers.file_archiver import FileArchiver
from .utils.logger import DownloadLogger
from .utils.status_tracker import get_tracker
from .utils.sources_config import save_sources_config
from .processor import SourceProcessor


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
        self.status_tracker = get_tracker("./monitor")

        # Save source configs for monitoring page
        save_sources_config(self.config_loader.sources, "./monitor/sources.json")

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
        from .downloaders.downloader_factory import DownloaderFactory
        factory = DownloaderFactory(self.logger, timeout=30)
        
        self.logger.info("[TESTING CONNECTIONS]")
        for source in self.config_loader.sources:
            try:
                downloader = factory.create(source)
                if downloader.test_connection():
                    self.logger.info(f"[CONNECTION OK] {source.name}")
                else:
                    self.logger.warning(f"[CONNECTION FAILED] {source.name}")
            except Exception as e:
                self.logger.error(f"[CONNECTION ERROR] {source.name} | {e}")

    def run_once(self) -> CycleStats:
        """Run a single download cycle."""
        self._cycle_count += 1
        stats = CycleStats(
            cycle_id=self._cycle_count,
            start_time=datetime.now()
        )

        self.logger.cycle_start(stats.cycle_id)
        all_results = self._process_all_sources()

        # Calculate stats
        for result in all_results:
            if result.success:
                stats.files_downloaded += 1
                stats.total_bytes += result.file_size
            else:
                stats.files_failed += 1

        stats.sources_processed = len(self.config_loader.sources)
        stats.end_time = datetime.now()
        stats.duration = (stats.end_time - stats.start_time).total_seconds()

        self.logger.cycle_complete(
            stats.cycle_id,
            stats.files_downloaded,
            stats.files_failed,
            stats.duration
        )

        return stats

    def redownload(self, start_dt: str, end_dt: str, source_name: str = None, 
                  force: bool = False) -> CycleStats:
        """Re-download files for a specific time range."""
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
        sources_to_process = [
            s for s in self.config_loader.sources
            if source_name is None or s.name == source_name
        ]

        if not sources_to_process:
            self.logger.warning(f"[REDOWNLOAD] No sources found matching: {source_name}")
            return stats

        all_results = []
        for source in sources_to_process:
            try:
                processor = SourceProcessor(source, self.config_loader, self.logger, self.status_tracker)
                results = processor.process_redownload(start_time, end_time, force)
                all_results.extend(results)
            except Exception as e:
                self.logger.error(f"[SOURCE ERROR] {source.name} | {e}")

        # Calculate stats
        for result in all_results:
            if result.success:
                stats.files_downloaded += 1
                stats.total_bytes += result.file_size
            else:
                stats.files_failed += 1

        stats.sources_processed = len(sources_to_process)
        stats.end_time = datetime.now()
        stats.duration = (stats.end_time - stats.start_time).total_seconds()

        self.logger.info(f"[REDOWNLOAD COMPLETE] Downloaded: {stats.files_downloaded} | Failed: {stats.files_failed}")

        return stats

    def _process_all_sources(self):
        """Process all configured sources."""
        from .downloaders.downloader_factory import DownloaderFactory
        
        all_results = []
        factory = DownloaderFactory(self.logger, timeout=30)
        
        for source in self.config_loader.sources:
            try:
                processor = SourceProcessor(source, self.config_loader, self.logger, self.status_tracker)
                results = processor.process()
                all_results.extend(results)
            except Exception as e:
                self.logger.error(f"[SOURCE ERROR] {source.name} | {e}")
        
        return all_results

    def get_status(self) -> dict:
        """Get current service status."""
        from .downloaders.downloader_factory import DownloaderFactory
        
        return {
            'cycle_count': self._cycle_count,
            'archive_stats': self.archiver.get_archive_stats() if self.archiver else None,
            'available_downloader_types': DownloaderFactory.get_available_types(),
        }
