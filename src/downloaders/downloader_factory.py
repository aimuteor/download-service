"""Downloader factory for creating and managing downloader instances."""

import os
from typing import Dict, Type
from pathlib import Path

from .base_downloader import BaseDownloader
from .http_downloader import HTTPDownloader
from .sftp_downloader import SFTPDownloader
from .ftp_downloader import FTPDownloader
from ..config_loader import SourceConfig
from ..utils.logger import DownloadLogger


class DownloaderFactory:
    """
    Factory for creating downloader instances.
    
    Supports dynamic loading of downloader plugins from the downloaders directory.
    To add a new downloader type:
    1. Create a new class inheriting from BaseDownloader
    2. Name it with the pattern: <type>_downloader.py (e.g., ftp_downloader.py)
    3. The factory will automatically discover and load it
    """

    # Registry of built-in downloaders
    _downloader_types: Dict[str, Type[BaseDownloader]] = {
        'http': HTTPDownloader,
        'https': HTTPDownloader,
        'sftp': SFTPDownloader,
        'ftp': FTPDownloader,
    }

    def __init__(self, logger: DownloadLogger, timeout: int = 30):
        self.logger = logger
        self.timeout = timeout
        self._instances: Dict[str, BaseDownloader] = {}

    def register_downloader(self, type_name: str, downloader_class: Type[BaseDownloader]) -> None:
        """
        Register a new downloader type.
        
        Args:
            type_name: Name of the downloader type (e.g., 'ftp', 's3')
            downloader_class: Class inheriting from BaseDownloader
        """
        self._downloader_types[type_name.lower()] = downloader_class
        self.logger.info(f"[DOWNLOADER REGISTERED] Type: {type_name} | Class: {downloader_class.__name__}")

    def create(self, source_config: SourceConfig) -> BaseDownloader:
        """
        Create a downloader instance for a source.
        
        Args:
            source_config: Source configuration
            
        Returns:
            Downloader instance
        """
        source_type = source_config.type.lower()
        
        if source_type not in self._downloader_types:
            raise ValueError(
                f"Unknown downloader type: {source_type}. "
                f"Available types: {list(self._downloader_types.keys())}"
            )
        
        downloader_class = self._downloader_types[source_type]
        downloader = downloader_class(source_config, self.logger, self.timeout)
        
        self._instances[source_config.name] = downloader
        self.logger.info(f"[DOWNLOADER CREATED] {source_config.name} | Type: {source_type}")
        
        return downloader

    def get(self, source_name: str) -> BaseDownloader:
        """Get existing downloader instance by source name."""
        return self._instances.get(source_name)

    def get_or_create(self, source_config: SourceConfig) -> BaseDownloader:
        """Get existing instance or create new one."""
        existing = self.get(source_config.name)
        if existing:
            return existing
        return self.create(source_config)

    def close_all(self) -> None:
        """Close all downloader instances."""
        for name, downloader in self._instances.items():
            try:
                if hasattr(downloader, 'close'):
                    downloader.close()
                elif hasattr(downloader, '_cleanup'):
                    downloader._cleanup()
            except Exception as e:
                self.logger.warning(f"[DOWNLOADER CLOSE ERROR] {name} | {e}")
        self._instances.clear()

    @classmethod
    def discover_plugins(cls, plugin_dir: str = None) -> None:
        """
        Discover and load downloader plugins from directory.
        
        Args:
            plugin_dir: Directory containing plugin modules
        """
        if plugin_dir is None:
            plugin_dir = Path(__file__).parent
        else:
            plugin_dir = Path(plugin_dir)

        for file_path in plugin_dir.glob('*_downloader.py'):
            module_name = file_path.stem
            if module_name in ('base_downloader', 'downloader_factory'):
                continue
            
            # Extract type name from filename (e.g., 'ftp_downloader' -> 'ftp')
            type_name = module_name.replace('_downloader', '')
            
            try:
                # Import the module
                import importlib.util
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find downloader class
                class_name = f"{type_name.capitalize()}Downloader"
                if hasattr(module, class_name):
                    cls._downloader_types[type_name] = getattr(module, class_name)
                    print(f"[PLUGIN LOADED] {type_name}: {class_name}")
                    
            except Exception as e:
                print(f"[PLUGIN LOAD FAILED] {module_name} | {e}")

    @classmethod
    def get_available_types(cls) -> list:
        """Get list of available downloader types."""
        return list(cls._downloader_types.keys())
