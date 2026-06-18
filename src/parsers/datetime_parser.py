"""Datetime parser for generating file timestamps and calculating datetime intervals."""

import re
from datetime import datetime, timedelta
from typing import List, Tuple
from zoneinfo import ZoneInfo
from dateutil import parser as dateutil_parser

from ..config_loader import DatetimeConfig


class DatetimeParser:
    """Parses and generates datetime values for file downloads."""

    # Pattern to find datetime format specifiers in filename
    DATETIME_PATTERN = re.compile(r'\{(YYYYMMDDHHMM|YYYYMMDDHH|YYYYMMDD|YYYYMM|YYYY|YYYYMMDDHHMMSS)\}')

    def __init__(self, config: DatetimeConfig):
        self.config = config
        self.source_tz = ZoneInfo(config.timezone)

    def get_datetime_for_now(self, reference_time: datetime = None) -> datetime:
        """
        Get the reference datetime for current download cycle.
        
        Args:
            reference_time: Optional reference time, defaults to now
            
        Returns:
            datetime in source timezone
        """
        if reference_time is None:
            now = datetime.now(ZoneInfo('UTC')).replace(tzinfo=self.source_tz)
        else:
            now = reference_time
        return now

    def calculate_datetime_list(self, reference_time: datetime = None) -> List[datetime]:
        """
        Calculate list of datetime values to download based on configuration.
        
        The algorithm:
        1. Start from reference_time minus lookback_minutes
        2. Calculate datetime slots with interval_minutes spacing
        3. Apply offset_minutes adjustment
        4. Generate datetimes going backwards from reference_time
        
        Example: if current time is 202606181648, interval=10, offset=1, lookback=60
        We want datetimes: 202606181646, 202606181636, 202606181626, 202606181616, 
                          202606181606, 202606181556
        
        Returns:
            List of datetime objects to generate filenames for
        """
        if reference_time is None:
            reference_time = datetime.now(ZoneInfo('UTC')).replace(tzinfo=self.source_tz)
        
        # Apply offset to reference time
        ref_with_offset = reference_time - timedelta(minutes=self.config.offset_minutes)
        
        # Calculate how many slots to go back
        num_slots = self.config.lookback_minutes // self.config.interval_minutes
        
        datetimes = []
        for i in range(num_slots):
            # Go back in steps of interval
            slot_time = ref_with_offset - timedelta(minutes=i * self.config.interval_minutes)
            datetimes.append(slot_time)
        
        return datetimes

    def format_datetime(self, dt: datetime, pattern: str = None) -> str:
        """
        Format a datetime according to the pattern.
        
        Args:
            dt: datetime to format
            pattern: Format pattern (uses config pattern if not provided)
            
        Returns:
            Formatted datetime string
        """
        if pattern is None:
            pattern = self.config.pattern
        return dt.strftime(pattern)

    def generate_filename(self, base_pattern: str, dt: datetime) -> str:
        """
        Generate a filename by substituting datetime placeholders.
        
        Args:
            base_pattern: Pattern like "radar_{var1}_{YYYYMMDDHHMM}.jpg"
            dt: datetime to substitute
            
        Returns:
            Generated filename string
        """
        # Find and replace datetime patterns
        result = base_pattern
        
        # Replace full patterns
        replacements = {
            '{YYYYMMDDHHMMSS}': dt.strftime('%Y%m%d%H%M%S'),
            '{YYYYMMDDHHMM}': dt.strftime('%Y%m%d%H%M'),
            '{YYYYMMDDHH}': dt.strftime('%Y%m%d%H'),
            '{YYYYMMDD}': dt.strftime('%Y%m%d'),
            '{YYYYMM}': dt.strftime('%Y%m'),
            '{YYYY}': dt.strftime('%Y'),
        }
        
        for placeholder, value in replacements.items():
            result = result.replace(placeholder, value)
        
        return result

    def parse_datetime_from_string(self, date_string: str) -> datetime:
        """
        Parse datetime from a string using the configured pattern.
        
        Args:
            date_string: String containing datetime like "202606181648"
            
        Returns:
            Parsed datetime in source timezone
        """
        try:
            dt = datetime.strptime(date_string, self.config.pattern)
            return dt.replace(tzinfo=self.source_tz)
        except ValueError as e:
            raise ValueError(f"Failed to parse datetime '{date_string}' with pattern '{self.config.pattern}': {e}")

    def convert_to_utc(self, dt: datetime) -> datetime:
        """Convert a datetime to UTC."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.source_tz)
        return dt.astimezone(ZoneInfo('UTC'))

    def convert_timezone(self, dt: datetime, target_tz: str) -> datetime:
        """Convert a datetime to a target timezone."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.source_tz)
        target_zone = ZoneInfo(target_tz)
        return dt.astimezone(target_zone)

    def get_utc_date_path(self, dt: datetime) -> str:
        """
        Get the UTC date path component for directory structure.
        
        Args:
            dt: datetime to convert
            
        Returns:
            YYYYMMDD string in UTC
        """
        utc_dt = self.convert_to_utc(dt)
        return utc_dt.strftime('%Y%m%d')

    @staticmethod
    def extract_datetime_from_filename(filename: str, patterns: List[str] = None) -> Tuple[str, datetime, str]:
        """
        Extract datetime from a filename.
        
        Args:
            filename: Filename to parse
            patterns: List of regex patterns to try
            
        Returns:
            Tuple of (original_filename, datetime, matched_pattern)
        """
        if patterns is None:
            patterns = [
                r'(\d{14})',  # YYYYMMDDHHMMSS
                r'(\d{12})',  # YYYYMMDDHHMM
                r'(\d{10})',  # YYYYMMDDHH
                r'(\d{8})',   # YYYYMMDD
                r'(\d{6})',   # YYYYMM
            ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                date_str = match.group(1)
                try:
                    if len(date_str) == 14:
                        dt = datetime.strptime(date_str, '%Y%m%d%H%M%S')
                    elif len(date_str) == 12:
                        dt = datetime.strptime(date_str, '%Y%m%d%H%M')
                    elif len(date_str) == 10:
                        dt = datetime.strptime(date_str, '%Y%m%d%H')
                    elif len(date_str) == 8:
                        dt = datetime.strptime(date_str, '%Y%m%d')
                    elif len(date_str) == 6:
                        dt = datetime.strptime(date_str, '%Y%m')
                    else:
                        continue
                    return filename, dt, pattern
                except ValueError:
                    continue
        
        raise ValueError(f"Could not extract datetime from filename: {filename}")
