# Automated Download Service

A cronjob-based Python service that downloads files from multiple data sources (HTTP/HTTPS/SFTP) with datetime-embedded filenames, organizes them into structured directories, and archives old files.

## Features

- **Multiple Protocols**: HTTP/HTTPS (GET/POST) and SFTP support
- **Datetime Parsing**: Parse datetime from filenames with configurable timezone
- **Structured Organization**: Files organized into `{dataDir}/{YYYYMMDD}/{subdir}/{var1}/`
- **Automatic Archives**: Files older than 3 years (configurable) are automatically archived
- **Comprehensive Logging**: Daily rotating logs with error tracking
- **Retry Logic**: Configurable retry attempts with delay
- **100+ Servers**: Designed to handle downloading from 100+ sources
- **Plugin Architecture**: Easy to add new download methods
- **Configuration-Driven**: No code changes needed for configuration

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Edit configuration
vim config/config.yaml

# Set up cron job (runs every 5 minutes)
./setup_cron.sh

# Or manually add to crontab:
*/5 * * * * cd /path/to/download_service && python3 -m src.main --once >> logs/cron.log 2>&1

# Run a single download cycle manually
python -m src.main --once

# Redownload specific time range
python -m src.main --redownload --start 202606181000 --end 202606181200
```

## Cron Setup

The service is designed to run via cron, not as a continuous service.

### Option 1: Use setup script
```bash
./setup_cron.sh
```

### Option 2: Manual crontab
```bash
crontab -e
# Add this line for every 5 minutes:
*/5 * * * * cd /home/user/download_service && python3 -m src.main --once >> logs/cron.log 2>&1
```

### Cron Schedule Options
```bash
# Every 5 minutes (default)
*/5 * * * *

# Every 10 minutes
*/10 * * * *

# Every hour
0 * * * *

# Every day at midnight
0 0 * * *
```

## Configuration

All settings are in `config/config.yaml`. Key sections:

### General Settings
```yaml
general:
  data_dir: "./data"
  log_dir: "./logs"
  download_interval_minutes: 5    # Used for lookback calculation
  max_retries: 3
```

### Source Configuration
Each source defines:
- Protocol (http/https/sftp)
- Host and path
- Filename pattern with datetime placeholders
- Authentication method
- Datetime parsing configuration (timezone, interval, offset, lookback)
- Destination path structure

### Datetime Configuration Example
```yaml
datetime_config:
  pattern: "%Y%m%d%H%M"      # Filename datetime format
  timezone: "Asia/Hong_Kong" # Source file timezone (HKT = UTC+8)
  interval_minutes: 10       # Interval between files
  offset_minutes: 1          # Offset from current time
  lookback_minutes: 60       # How far back to download
```

For current time `2026-06-18 16:48 HKT` with interval=10, offset=1, lookback=60:
Files will be: 202606181646, 202606181636, 202606181626, 202606181616, 202606181606, 202606181556

### Destination Structure
```yaml
destination:
  date_dir_pattern: "{dataDir}/{YYYYMMDD}"
  subdir: "radar_img"
  var1_array: ["tcr", "tms", "cch"]  # Variables to substitute
  output_timezone: "UTC"            # Path uses UTC
```

## Adding New Download Methods

Create a new file in `src/downloaders/` named `{type}_downloader.py`:

```python
from .base_downloader import BaseDownloader, DownloadResult

class MyTypeDownloader(BaseDownloader):
    def __init__(self, source_config, logger, timeout=30):
        super().__init__(source_config, logger)
        # Initialize your downloader
        
    def download(self, url, local_path, filename, retry_count=0):
        # Implement download logic
        pass
        
    def test_connection(self):
        # Test connectivity
        pass
        
    def build_url(self, filename):
        # Build URL from components
        pass
```

The factory will automatically discover and load it.

## Directory Structure

```
download_service/
├── config/
│   └── config.yaml           # Configuration file
├── src/
│   ├── main.py               # Entry point
│   ├── service.py            # Download orchestration
│   ├── config_loader.py      # Configuration management
│   ├── downloaders/           # Download protocol implementations
│   │   ├── base_downloader.py
│   │   ├── http_downloader.py
│   │   ├── sftp_downloader.py
│   │   └── downloader_factory.py
│   ├── parsers/
│   │   └── datetime_parser.py
│   ├── archivers/
│   │   └── file_archiver.py
│   └── utils/
│       └── logger.py
├── logs/                      # Log files (auto-created)
├── data/                      # Downloaded files (auto-created)
├── archive/                   # Archived files (auto-created)
├── setup_cron.sh             # Cron setup script
├── requirements.txt
└── README.md
```

## Command Line Options

```bash
# Download past data (use in cron every 5 minutes)
python -m src.main --once

# Redownload specific time range (all sources)
python -m src.main --redownload --start 202606181000 --end 202606181200

# Redownload specific source
python -m src.main --redownload --source radar_http --start 202606181000 --end 202606181200

# Force re-download even if files exist
python -m src.main --redownload --start 202606181000 --end 202606181200 --force

# Show status
python -m src.main --status
```

### Redownload Options
| Option | Description |
|--------|-------------|
| `--redownload` | Enable redownload mode |
| `--start YYYYMMDDHHMM` | Start datetime (inclusive) |
| `--end YYYYMMDDHHMM` | End datetime (inclusive) |
| `--source NAME` | Filter to specific source (optional) |
| `--force` | Re-download even if files exist (optional) |

## Logging

Logs are written to `logs/download_YYYYMMDD.log` with daily rotation.
Cron output goes to `logs/cron.log`.

Log format:
```
2026-06-18 16:54:00 | INFO     | download_service | service.py:120 | [DOWNLOAD SUCCESS] Source: radar_http | File: radar_tcr_202606181646.jpg | Size: 12345 bytes | Duration: 0.52s
```

## Authentication

Supported methods:
- `none`: No authentication
- `basic`: Username/password (Base64 encoded)
- `bearer`: Bearer token
- `api_key`: API key in header
- `key`: SSH key file for SFTP
