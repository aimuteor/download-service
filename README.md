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
*/5 * * * * cd /path/to/download_service && python3 -m src.main >> logs/cron.log 2>&1

# Run a single download cycle manually
python -m src.main

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
*/5 * * * * cd /home/user/download_service && python3 -m src.main >> logs/cron.log 2>&1
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
- `timeout`: Request timeout in seconds (default: 30)
- Authentication method
- Datetime parsing configuration (timezone, interval, offset, lookback)
- Destination path structure (can use defaults)

### Timeout Configuration
Each source can have its own timeout:
```yaml
sources:
  - name: "fast_source"
    timeout: 30                    # Default timeout
  - name: "slow_source"
    timeout: 120                  # Longer timeout for slow connections
```

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

# Path can use datetime placeholders (for dynamic remote paths)
path: "/data/{YYYY}/{MM}/{DD}"

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
  timezone: "Asia/Hong_Kong" # Source file timezone (HKT = UTC+8)
  interval_minutes: 10       # Interval between files
  offset_minutes: 1          # Offset from current time
  lookback_minutes: 60       # How far back to download
```

### Datetime Placeholders in Filename Pattern

Use these placeholders in `filename_pattern`:

| Placeholder | Meaning | Example Output |
|-------------|---------|----------------|
| `{YYYY}` | 4-digit year | 2026 |
| `{MM}` | 2-digit month | 06 |
| `{DD}` | 2-digit day | 22 |
| `{HH}` | 2-digit hour (24h) | 10 |
| `{MI}` | 2-digit minute (MI = Minute to distinguish from MM) | 48 |
| `{YYYYMM}` | Year + month | 202606 |
| `{YYYYMMDD}` | Full date | 20260622 |
| `{YYYYMMDDHH}` | Date + hour | 2026062210 |
| `{YYYYMMDDHHMI}` | Date + hour + minute | 202606221048 |
| `{YYYYMMDDHHMISS}` | Date + hour + minute + second | 20260622104830 |

**Important:** 
- `{MM}` = Month (like strftime `%m`)
- `{MI}` = Minute (to distinguish from `{MM}`)

Example filename patterns:
```yaml
# Using individual placeholders
filename_pattern: "sensor_{var1}_{YYYY}_{MM}_{DD}_{HH}_{MI}.dat"
# Output: sensor_temp_2026_06_22_10_48.dat

# Using combined placeholders
filename_pattern: "data_{YYYYMMDDHHMI}.dat"
# Output: data_202606221048.dat
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

### Datetime Placeholders in Path

Both `date_dir_pattern` and `subdir` support datetime placeholders:

| Placeholder | Meaning | Example Output |
|-------------|---------|----------------|
| `{YYYY}` | 4-digit year | 2026 |
| `{MM}` | 2-digit month | 06 |
| `{DD}` | 2-digit day | 22 |
| `{HH}` | 2-digit hour (24h) | 10 |
| `{MI}` | 2-digit minute | 48 |
| `{YYYYMMDD}` | Full date | 20260622 |

```yaml
# Example: organize by year/month
date_dir_pattern: "{dataDir}/{YYYY}/{MM}/{DD}"
subdir: "radar/{HH}"

# Output: data/2026/06/22/radar/10/sensor_202606221048.dat
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
│   ├── runner.py             # Cycle runner (orchestration)
│   ├── processor.py          # Source processor (download tasks)
│   ├── path_utils.py         # Path building utilities
│   ├── config_loader.py      # Configuration management
│   ├── downloaders/          # Download protocol implementations
│   │   ├── base_downloader.py
│   │   ├── http_downloader.py
│   │   ├── ftp_downloader.py
│   │   ├── sftp_downloader.py
│   │   └── downloader_factory.py
│   ├── parsers/
│   │   └── datetime_parser.py
│   ├── archivers/
│   │   └── file_archiver.py
│   └── utils/
│       ├── logger.py
│       ├── status_tracker.py  # Monitoring status tracker
│       └── sources_config.py  # Sources config generator
├── monitor/
│   └── index.html            # Web monitoring dashboard
├── logs/                     # Log files (auto-created)
├── data/                     # Downloaded files (auto-created)
├── archive/                  # Archived files (auto-created)
├── setup_cron.sh            # Cron setup script
├── requirements.txt
└── README.md
```

## Command Line Options

```bash
# Download past data (default behavior, for cron every 5 minutes)
python -m src.main

# Same as above (explicit)
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

## Testing

### Run All Tests
```bash
cd /path/to/download_service
python -m pytest tests/ -v
```

### Run Specific Test Files
```bash
# Test FTP downloader with real server
python -m pytest tests/test_ftp_server.py -v

# Test HTTP downloader
python -m pytest tests/test_local_servers.py -v

# Test configuration loading
python -m pytest tests/test_config_loader.py -v

# Test datetime parsing
python -m pytest tests/test_datetime_parser.py -v
```

### Run FTP Server Test Manually (with real FTP server)
```bash
cd /path/to/download_service
python tests/test_ftp_server.py
```

This creates a local FTP server using pyftpdlib and tests:
- Simple path download
- Single file download
- Wildcard download
- Datetime path download (simulates `{YYYYMMDD}` in path)
- Datetime wildcard download

### Test Coverage

| Test File | What It Tests |
|-----------|---------------|
| `test_config_loader.py` | Configuration loading and parsing |
| `test_datetime_parser.py` | Datetime placeholder replacement |
| `test_downloaders.py` | HTTP and FTP downloader unit tests |
| `test_ftp_server.py` | FTP downloader with real pyftpdlib server |
| `test_local_servers.py` | HTTP downloader with local HTTP server |

### Running Specific Tests
```bash
# Run a single test function
python -m pytest tests/test_ftp_server.py::test_ftp_wildcard_download -v

# Run tests matching a pattern
python -m pytest tests/ -k "ftp" -v
python -m pytest tests/ -k "datetime" -v
```

### Requirements for Running Tests
```bash
pip install pytest pyftpdlib requests
```

## Monitoring Dashboard

The service includes a web-based monitoring dashboard that shows the status of all download sources in real-time.

### Features

- **Card-based UI**: Each source displayed as a card with status indicators
- **24-hour Statistics**: Success rate, total downloads, failures
- **Error Tracking**: Expandable error details for each source
- **Auto-sorting**: Error cards appear first with red flashing border
- **Auto-refresh**: Updates every 10 minutes

### Setup

1. **Start the Python HTTP server** (from the download_service directory):
```bash
# Navigate to the download_service directory
cd /path/to/download_service

# Start HTTP server on port 8080
python -m http.server 8080
```

2. **Open in browser**:
```
http://your-server:8080/monitor/index.html
```

3. **For local access on same machine**:
```bash
python -m http.server 8080
# Then open: http://localhost:8080/monitor/index.html
```

### Status Card Colors

| Status | Color | Meaning |
|--------|-------|---------|
| Green | Success border | Source working normally |
| Yellow | Warning border | No successful download in >1 hour |
| Red (flashing) | Error border + animation | Current error or no success in >1 hour |

### JSON Status File

The status data is generated at `monitor/status.json` automatically when downloads occur:

```json
{
  "last_updated": "2026-06-28T10:14:00+08:00",
  "sources": {
    "cmaWP_KP": {
      "type": "ftp",
      "current_status": "success",
      "last_success": "2026-06-28T10:10:00+08:00",
      "today_stats": { "total": 45, "success": 44, "failed": 1, "success_rate": 97.8 },
      "last_24h_stats": { "total": 720, "success": 700, "failed": 20, "success_rate": 97.2 },
      "recent_errors": [
        { "time": "2026-06-28T08:30:00+08:00", "message": "Connection timeout", "url": "/path/to/file" }
      ]
    }
  }
}
```

### Background Service

To keep the monitoring page running in the background:

```bash
# Using nohup
nohup python -m http.server 8080 &

# Or using screen/tmux
screen -S monitor
python -m http.server 8080
# Press Ctrl+A, D to detach
```
