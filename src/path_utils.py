"""Path building utilities for download destinations."""

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def build_destination_path(
    base_dir: str,
    dest_config,
    dt: datetime,
    timezone: str = "UTC"
) -> Path:
    """
    Build destination path for a download.
    
    Args:
        base_dir: Base data directory
        dest_config: DestinationConfig object
        dt: Datetime for path substitution
        timezone: Timezone string (e.g., "UTC", "Asia/Hong_Kong")
        
    Returns:
        Path object for the destination directory
    """
    # Convert to UTC for path if timezone is specified
    if timezone and timezone != "UTC":
        tz = ZoneInfo(timezone)
        utc_dt = dt.astimezone(tz)
    else:
        utc_dt = dt
    
    # Apply datetime formatting to date_dir_pattern
    date_dir = dest_config.date_dir_pattern
    
    # Replace datetime placeholders
    replacements = {
        'YYYY': utc_dt.strftime('%Y'),
        'MM': utc_dt.strftime('%m'),
        'DD': utc_dt.strftime('%d'),
        'HH': utc_dt.strftime('%H'),
        'MI': utc_dt.strftime('%M'),
        'YYYYMMDD': utc_dt.strftime('%Y%m%d'),
        'YYYYMMDDHH': utc_dt.strftime('%Y%m%d%H'),
        'YYYYMMDDHHMI': utc_dt.strftime('%Y%m%d%H%M'),
        'YYYYMMDDHHMISS': utc_dt.strftime('%Y%m%d%H%M%S'),
    }
    
    for placeholder, value in replacements.items():
        date_dir = date_dir.replace(f'{{{placeholder}}}', value)
    
    # Replace {dataDir} placeholder with base_dir
    date_dir = date_dir.replace('{dataDir}', base_dir)
    
    # Handle subdir
    subdir = dest_config.subdir
    if subdir:
        path = Path(base_dir) / subdir / date_dir
    else:
        path = Path(base_dir) / date_dir
    
    return path
