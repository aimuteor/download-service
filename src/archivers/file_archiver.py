"""File archiver for automatically archiving old files."""

import os
import shutil
import tarfile
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from ..config_loader import ArchiveConfig
from ..utils.logger import DownloadLogger


class FileArchiver:
    """Archives old files based on age configuration."""

    def __init__(self, config: ArchiveConfig, logger: DownloadLogger):
        self.config = config
        self.logger = logger
        self.archive_dir = Path(config.archive_dir)
        self.last_check: Optional[datetime] = None

    def should_archive(self, file_path: Path) -> Tuple[bool, int]:
        """
        Check if a file should be archived based on age.
        
        Args:
            file_path: Path to file
            
        Returns:
            Tuple of (should_archive, age_in_days)
        """
        if not file_path.exists():
            return False, 0
        
        if not file_path.is_file():
            return False, 0
        
        # Get file modification time
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        age = datetime.now() - mtime
        age_days = age.days
        
        return age_days > self.config.max_age_days, age_days

    def get_files_to_archive(self, data_dir: Path) -> List[Tuple[Path, int]]:
        """
        Find all files that should be archived.
        
        Args:
            data_dir: Root data directory to scan
            
        Returns:
            List of (file_path, age_in_days) tuples
        """
        files_to_archive = []
        
        if not data_dir.exists():
            return files_to_archive
        
        # Walk through all files
        for root, dirs, files in os.walk(data_dir):
            # Skip archive directory
            if self.archive_dir and str(self.archive_dir) in root:
                continue
                
            for filename in files:
                file_path = Path(root) / filename
                should, age = self.should_archive(file_path)
                if should:
                    files_to_archive.append((file_path, age))
        
        return files_to_archive

    def archive_file(self, file_path: Path) -> Optional[Path]:
        """
        Archive a single file.
        
        Args:
            file_path: Path to file to archive
            
        Returns:
            Path to archived file, or None on failure
        """
        try:
            # Create archive directory structure: archive_dir/YYYYMM/
            archive_date = datetime.now().strftime('%Y%m')
            archive_subdir = self.archive_dir / archive_date
            archive_subdir.mkdir(parents=True, exist_ok=True)
            
            # Generate archive filename
            original_name = file_path.name
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            archive_name = f"{file_path.stem}_{timestamp}{file_path.suffix}.gz"
            archive_path = archive_subdir / archive_name
            
            # Get original size
            original_size = file_path.stat().st_size
            age = (datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)).days
            
            self.logger.archive_start(str(file_path), age)
            
            # Compress and copy file
            with open(file_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb', compresslevel=6) as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Verify archive was created
            if archive_path.exists():
                archive_size = archive_path.stat().st_size
                
                # Remove original file
                file_path.unlink()
                
                self.logger.archive_complete(str(file_path), str(archive_path))
                return archive_path
            else:
                self.logger.error(f"[ARCHIVE FAILED] Could not create archive: {archive_path}")
                return None
                
        except Exception as e:
            self.logger.error(f"[ARCHIVE ERROR] {file_path} | {e}")
            return None

    def archive_files_batch(self, files: List[Tuple[Path, int]], 
                           batch_size: int = 100) -> Tuple[int, int]:
        """
        Archive multiple files.
        
        Args:
            files: List of (file_path, age_in_days) tuples
            batch_size: Number of files to process in one batch
            
        Returns:
            Tuple of (successful, failed) counts
        """
        success = 0
        failed = 0
        
        for file_path, age in files[:batch_size]:
            result = self.archive_file(file_path)
            if result:
                success += 1
            else:
                failed += 1
        
        return success, failed

    def run_archive(self, data_dir: Path) -> Tuple[int, int]:
        """
        Run archive process on data directory.
        
        Args:
            data_dir: Root data directory
            
        Returns:
            Tuple of (archived_count, failed_count)
        """
        if not self.config.enabled:
            self.logger.debug("[ARCHIVE DISABLED]")
            return 0, 0
        
        self.logger.info(f"[ARCHIVE START] Scanning: {data_dir} | Max age: {self.config.max_age_days} days")
        
        files_to_archive = self.get_files_to_archive(data_dir)
        total_files = len(files_to_archive)
        
        if total_files == 0:
            self.logger.info("[ARCHIVE COMPLETE] No files to archive")
            return 0, 0
        
        self.logger.info(f"[ARCHIVE FOUND] {total_files} files to archive")
        
        success, failed = self.archive_files_batch(files_to_archive)
        
        self.logger.info(f"[ARCHIVE COMPLETE] Success: {success} | Failed: {failed}")
        
        self.last_check = datetime.now()
        return success, failed

    def get_archive_stats(self) -> dict:
        """Get archive statistics."""
        total_size = 0
        file_count = 0
        
        if self.archive_dir.exists():
            for root, dirs, files in os.walk(self.archive_dir):
                for filename in files:
                    file_path = Path(root) / filename
                    total_size += file_path.stat().st_size
                    file_count += 1
        
        return {
            'archive_dir': str(self.archive_dir),
            'total_files': file_count,
            'total_size_bytes': total_size,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'last_check': self.last_check.isoformat() if self.last_check else None,
        }
