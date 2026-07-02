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
    # For path components, use the source timezone (HKT) datetime
    # This ensures the date directory matches the observed date locally
    if timezone and timezone != "UTC":
        tz = ZoneInfo(timezone)
        path_dt = dt.astimezone(tz)
    else:
        path_dt = dt
    
    # Apply datetime formatting to date_dir_pattern
    date_dir = dest_config.date_dir_pattern
    
    # Replace datetime placeholders
    replacements = {
        'YYYY': path_dt.strftime('%Y'),
        'MM': path_dt.strftime('%m'),
        'DD': path_dt.strftime('%d'),
        'HH': path_dt.strftime('%H'),
        'MI': path_dt.strftime('%M'),
        'HHMM': path_dt.strftime('%H%M'),
        'HHMI': path_dt.strftime('%H%M'),  # Alias for HHMM
        'YYYYMMDD': path_dt.strftime('%Y%m%d'),
        'YYYYMMDDHH': path_dt.strftime('%Y%m%d%H'),
        'YYYYMMDDHHMI': path_dt.strftime('%Y%m%d%H%M'),
        'YYYYMMDDHHMISS': path_dt.strftime('%Y%m%d%H%M%S'),
        'dataDir': base_dir,
        # dir_array_key support: use the configured key value
        'datatype': getattr(dest_config, 'dir_array_key', 'data'),
    }
    
    for placeholder, value in replacements.items():
        date_dir = date_dir.replace(f'{{{placeholder}}}', value)
    
    # Handle subdir
    subdir = dest_config.subdir
    if subdir:
        path = Path(base_dir) / subdir / date_dir
    else:
        path = Path(base_dir) / date_dir
    
    return path
