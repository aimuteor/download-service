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
- Protocol (http/https/sftp/ftp)
- Host and path
- Filename pattern with datetime placeholders and variables ({var1}, {var2}, etc.)
- For FTP: supports wildcard patterns (e.g., `*.jpg`, `radar_*`)
- `varN_array`: Arrays for variable substitution (e.g., `var1_array: ["temp", "humid"]`)
- `force_download`: Re-download even if file exists
- Authentication method
- Datetime parsing configuration (timezone, interval, offset, lookback)
- Destination path structure (can use defaults)

### Variable Arrays
Variables in filename pattern (`{var1}`, `{var2}`, etc.) are substituted from arrays:
```yaml
filename_pattern: "sensor_{var1}_{var2}_{YYYYMMDDHHMM}.dat"
var1_array: ["temp", "humid"]      # Values for {var1}
var2_array: ["day", "night"]        # Values for {var2}
```
This generates: sensor_temp_day_*.dat, sensor_temp_night_*.dat, sensor_humid_day_*.dat, etc.

### Global Destination Defaults
```yaml
destination_defaults:
  date_dir_pattern: "{dataDir}/{YYYYMMDD}"
  output_timezone: "UTC"
  include_hhmm_dir: false
  dir_array: true        # true = subdir/{var}/file, false = subdir/file
  dir_array_key: "var1"  # which var to use for directory name
```

### Source Options
```yaml
# Force re-download even if file exists (useful for static filenames)
force_download: true

# Variable arrays for filename substitution
var1_array: ["temp", "humid", "pressure"]
var2_array: ["day", "night"]

# Destination settings (override defaults)
destination:
  subdir: "sensor_data"
  dir_array: true          # true = subdir/temp/file.dat, false = subdir/file.dat
  dir_array_key: "var1"    # which var to use for directory (var1, var2, etc.)
  include_hhmm_dir: true   # Adds {HHMM} subdirectory
```

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
Files will be: 202606181641, 202606181631, 202606181621, 202606181611, 202606181601, 202606181551

Algorithm:
1. Find today's day start (00:00) in the specified timezone
2. Calculate diff in minutes from current time to day start
3. Round down diff by interval, then add offset to get latest slot
4. Generate slots by subtracting interval until lookback is exceeded

### Destination Structure (defaults from destination_defaults)
```yaml
destination_defaults:
  date_dir_pattern: "{dataDir}/{YYYYMMDD}"
  output_timezone: "UTC"
  include_hhmm_dir: false
  dir_array: true

# Per-source overrides:
destination:
  subdir: "radar_img"
  dir_array: false  # Override: files go directly under subdir
  include_hhmm_dir: true  # Override default
```

### Path Structure Examples

With `dir_array: true` and `dir_array_key: "var1"` (default - use var1 for directory):
```
data/20260619/sensor_data/temp/sensor_temp_day_202606191430.dat
data/20260619/sensor_data/humid/sensor_humid_day_202606191430.dat
data/20260619/sensor_data/pressure/sensor_pressure_night_202606191430.dat
```

With `dir_array: true` and `dir_array_key: "var2"` (use var2 for directory):
```
data/20260619/sensor_data/day/sensor_temp_day_202606191430.dat
data/20260619/sensor_data/night/sensor_temp_night_202606191430.dat
data/20260619/sensor_data/day/sensor_humid_day_202606191430.dat
```

With `dir_array: false` (files go directly under subdir):
```
data/20260619/sensor_data/sensor_temp_day_202606191430.dat
data/20260619/sensor_data/sensor_humid_day_202606191430.dat
data/20260619/sensor_data/sensor_pressure_night_202606191430.dat
```

With `include_hhmm_dir: true`:
```
data/20260619/sensor_data/1430/temp/sensor_temp_day_202606191430.dat
```

With `include_hhmm_dir: false`:
```
data/20260619/radar_img/tcr/radar_tcr_202606181646.jpg
```

With `include_hhmm_dir: true`:
```
data/20260619/radar_img/1646/tcr/radar_tcr_202606181646.jpg
```

### Static Filename Sources

For files with unchanging names (e.g., `radar_latest.jpg`):
```yaml
- name: "static_radar"
  filename_pattern: "radar_latest.jpg"  # Static filename
  force_download: true                   # Must be true to re-download
  var1_array: ["latest"]                # Variable array for substitution
  datetime_config:
    interval_minutes: 5                 # How often to check for updates
    lookback_minutes: 5
  destination:
    subdir: "radar_static"
    include_hhmm_dir: true              # Organize by download time
    dir_array: false                   # No var subdir needed
```
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

## FTP Download with Wildcards

FTP supports wildcard patterns for downloading multiple files at once:

```yaml
- name: "ftp_radar"
  type: "ftp"
  host: "ftp.example.com"
  port: 21
  path: "/radar/data"
  filename_pattern: "radar_*.jpg"  # Wildcard - downloads all matching files
  auth_type: "basic"
  auth_credentials:
    username: "anonymous"
    password: "anonymous@example.com"
```

### Wildcard Patterns
- `*.jpg` - All JPEG files
- `radar_*` - All files starting with "radar_"
- `data_202606*.dat` - All files starting with "data_202606" and ending with ".dat"

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
