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
    # Note: MM = month, MI = minute (to distinguish them)
    DATETIME_PATTERN = re.compile(r'\{(YYYYMMDDHHMI|YYYYMMDDHH|YYYYMMDD|YYYYMM|YYYYMMDDHHMISS|YYYY|MM|DD|HH|MI)\}')

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
        
        The algorithm (aligns to day start):
        1. Find the datetime of day start time (00:00) in the specified timezone
        2. Find the diff in minutes from the current time to the today start time
        3. Round down the diff by the interval_minutes
        4. Add the offset_minutes to get the latest slot
        5. For lookback: subtract interval_minutes from latest and check within lookback
        
        Example: interval=10, offset=1, lookback=60, current=16:48 HKT
        - Day start: 00:00, Diff: 1008 min
        - floor(1008/10)*10 + offset = 1001 min = 16:41
        - Slots: 16:41, 16:31, 16:21, 16:11, 16:01, 15:51
        
        Returns:
            List of datetime objects to generate filenames for
        """
        if reference_time is None:
            reference_time = datetime.now(ZoneInfo('UTC')).replace(tzinfo=self.source_tz)
        
        # Ensure reference_time is in source timezone
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=self.source_tz)
        else:
            reference_time = reference_time.astimezone(self.source_tz)
        
        # Step 1: Find today's day start (00:00) in source timezone
        today_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Step 2: Calculate diff in minutes from today start to current time
        diff_minutes = (reference_time - today_start).total_seconds() / 60
        
        # Step 3: Round down diff to nearest interval
        rounded_diff = (diff_minutes // self.config.interval_minutes) * self.config.interval_minutes
        
        # Step 4: Add offset to get the first (latest) slot
        latest_slot_minutes = rounded_diff + self.config.offset_minutes
        
        # Calculate latest slot datetime
        latest_slot = today_start + timedelta(minutes=latest_slot_minutes)
        
        # If latest_slot is after reference_time (due to offset), go back one interval
        if latest_slot > reference_time:
            latest_slot = latest_slot - timedelta(minutes=self.config.interval_minutes)
        
        # Step 5: Generate slots by subtracting interval, checking lookback
        datetimes = []
        current_slot = latest_slot
        
        # Calculate total minutes we can go back based on lookback
        max_lookback_minutes = self.config.lookback_minutes
        
        while True:
            # Check if this slot is within lookback range
            minutes_since_slot = (reference_time - current_slot).total_seconds() / 60
            
            if minutes_since_slot > max_lookback_minutes:
                break
            
            # Only add slots that are in the past (not future)
            if current_slot <= reference_time:
                datetimes.append(current_slot)
            
            # Move to previous slot
            current_slot = current_slot - timedelta(minutes=self.config.interval_minutes)
            
            # Safety break: don't go back more than 7 days worth of slots
            if len(datetimes) > 1000:
                break
        
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
            base_pattern: Pattern like "radar_{var1}_{YYYY}_{MM}_{DD}_{HH}_{MI}.jpg"
            dt: datetime to substitute
            
        Returns:
            Generated filename string
        """
        # Find and replace datetime patterns
        result = base_pattern
        
        # Replace patterns (MI = minute, MM = month)
        replacements = {
            # Combined patterns
            '{YYYYMMDDHHMISS}': dt.strftime('%Y%m%d%H%M%S'),
            '{YYYYMMDDHHMI}': dt.strftime('%Y%m%d%H%M'),  # MI = minute
            '{YYYYMMDDHH}': dt.strftime('%Y%m%d%H'),
            '{YYYYMMDD}': dt.strftime('%Y%m%d'),
            '{YYYYMM}': dt.strftime('%Y%m'),
            # Individual patterns
            '{YYYY}': dt.strftime('%Y'),
            '{MM}': dt.strftime('%m'),   # Month (not minute!)
            '{DD}': dt.strftime('%d'),
            '{HH}': dt.strftime('%H'),
            '{MI}': dt.strftime('%M'),   # Minute (MI to distinguish from MM)
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
