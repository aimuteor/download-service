#!/usr/bin/env python3
"""
Download Service - Cron-based

Downloads files from multiple data sources (HTTP/HTTPS/SFTP/FTP) with 
datetime-embedded filenames, organizes them into structured directories, 
and archives old files.

Usage:
    python -m src.main                       # Download past data (default)
    python -m src.main --redownload --start 202606181000 --end 202606181200
                                            # Re-download specific time range
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.runner import DownloadRunner


def main():
    parser = argparse.ArgumentParser(
        description='Download Service (Cron-based)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download past data (default, for cron every 5 minutes)
  python -m src.main

  # Redownload specific time range (all sources)
  python -m src.main --redownload --start 202606181000 --end 202606181200

  # Redownload specific source
  python -m src.main --redownload --source radar_http --start 202606181000 --end 202606181200

  # Force re-download even if files exist
  python -m src.main --redownload --start 202606181000 --end 202606181200 --force

  # Show archive stats
  python -m src.main --status
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )
    
    parser.add_argument(
        '--redownload',
        action='store_true',
        help='Redownload files for a specific time range'
    )
    
    parser.add_argument(
        '--start',
        help='Start datetime (YYYYMMDDHHMM format, e.g., 202606181000)'
    )
    
    parser.add_argument(
        '--end',
        help='End datetime (YYYYMMDDHHMM format, e.g., 202606181200)'
    )
    
    parser.add_argument(
        '--source',
        help='Source name to redownload (default: all sources)'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force re-download even if file exists'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Show archive status and exit'
    )
    
    args = parser.parse_args()
    
    # Get absolute config path
    if not Path(args.config).is_absolute():
        config_path = Path(__file__).parent.parent / args.config
    else:
        config_path = Path(args.config)
    
    # Initialize runner
    runner = DownloadRunner(str(config_path))
    runner.initialize()
    
    if args.status:
        stats = runner.get_status()
        print("\n=== Archive Status ===")
        if stats.get('archive_stats'):
            print(f"Directory: {stats['archive_stats']['archive_dir']}")
            print(f"Total files: {stats['archive_stats']['total_files']}")
            print(f"Total size: {stats['archive_stats']['total_size_mb']} MB")
        print(f"Available downloader types: {', '.join(stats['available_downloader_types'])}")
        return
    
    if args.redownload:
        if not args.start or not args.end:
            print("Error: --start and --end are required for redownload")
            parser.print_help()
            return
        print(f"Redownloading: {args.start} to {args.end}...")
        result = runner.redownload(args.start, args.end, args.source, args.force)
    else:
        # Default: download past data based on lookback
        print("Downloading past data...")
        result = runner.run_once()
    
    # Print summary
    print(f"\n=== Complete ===")
    print(f"Duration: {result.duration:.2f}s")
    print(f"Sources processed: {result.sources_processed}")
    print(f"Files downloaded: {result.files_downloaded}")
    print(f"Files failed: {result.files_failed}")
    print(f"Total bytes: {result.total_bytes:,}")


if __name__ == '__main__':
    main()
