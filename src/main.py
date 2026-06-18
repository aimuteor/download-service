#!/usr/bin/env python3
"""
Automated Download Service

A service that automatically downloads files from multiple data sources
(HTTP/HTTPS/SFTP) with datetime-embedded filenames, organizes them into
structured directories, and archives old files.

Usage:
    python -m src.main                    # Start service
    python -m src.main --once             # Run single cycle
    python -m src.main --config path.yaml  # Use custom config
    python -m src.main --status           # Show status
"""

import sys
import os
import argparse
import signal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.service import DownloadService


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\nShutdown signal received...")
    if service:
        service.stop()
    sys.exit(0)


service = None


def main():
    global service
    
    parser = argparse.ArgumentParser(
        description='Automated Download Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main                        Start the service
  python -m src.main --once                 Run a single download cycle
  python -m src.main --config custom.yaml    Use custom config file
  python -m src.main --status               Show service status
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run a single download cycle and exit'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show service status and exit'
    )
    
    args = parser.parse_args()
    
    # Handle signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get absolute config path
    if not Path(args.config).is_absolute():
        config_path = Path(__file__).parent.parent / args.config
    else:
        config_path = Path(args.config)
    
    # Initialize service
    service = DownloadService(str(config_path))
    
    if args.status:
        service.initialize()
        status = service.get_status()
        print("\n=== Download Service Status ===")
        print(f"Running: {status['running']}")
        print(f"Cycles completed: {status['cycle_count']}")
        print(f"Available downloader types: {', '.join(status['available_downloader_types'])}")
        if status['archive_stats']:
            print(f"\nArchive Stats:")
            print(f"  Directory: {status['archive_stats']['archive_dir']}")
            print(f"  Total files: {status['archive_stats']['total_files']}")
            print(f"  Total size: {status['archive_stats']['total_size_mb']} MB")
        return
    
    if args.once:
        print("Running single download cycle...")
        service.initialize()
        stats = service.run_once()
        print(f"\n=== Cycle {stats.cycle_id} Complete ===")
        print(f"Duration: {stats.duration:.2f}s")
        print(f"Sources processed: {stats.sources_processed}")
        print(f"Files downloaded: {stats.files_downloaded}")
        print(f"Files failed: {stats.files_failed}")
        print(f"Total bytes: {stats.total_bytes:,}")
    else:
        print("Starting Download Service...")
        print("Press Ctrl+C to stop")
        service.start()


if __name__ == '__main__':
    main()
