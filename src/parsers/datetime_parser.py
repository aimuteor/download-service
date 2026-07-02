"""Datetime parsing and calculation for download scheduling."""

from datetime import datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo
import re

from ..config_loader import DatetimeConfig


class DatetimeParser:
    """Handles datetime calculations for download scheduling."""

    def __init__(self, config: DatetimeConfig):
        """
        Initialize datetime parser.
        
        Args:
            config: DatetimeConfig with timezone, interval, offset, lookback
        """
        self.config = config

    def calculate_datetime_list(self, reference_time: datetime = None) -> List[datetime]:
        """
        Calculate list of datetimes to attempt downloads.
        
        Uses interval-based lookback from reference time.
        
        Args:
            reference_time: Optional reference time, defaults to current time
            
        Returns:
            List of datetimes to attempt
        """
        if reference_time is None:
            reference_time = self._calculate_reference_time()
        
        # Calculate lookback start time
        lookback_delta = timedelta(minutes=self.config.lookback_minutes)
        lookback_start = reference_time - lookback_delta
        
        # Apply offset
        if self.config.offset_minutes > 0:
            lookback_start = lookback_start - timedelta(minutes=self.config.offset_minutes)
            reference_time = reference_time - timedelta(minutes=self.config.offset_minutes)
        
        # Generate interval slots
        datetimes = []
        interval_delta = timedelta(minutes=self.config.interval_minutes)
        
        # Align to interval boundary
        current = self._align_to_interval(lookback_start, interval_delta)
        
        while current <= reference_time:
            datetimes.append(current)
            current = current + interval_delta
        
        return datetimes

    def _align_to_interval(self, dt: datetime, interval: timedelta) -> datetime:
        """
        Align datetime to the previous interval boundary.
        
        For example, with 10-minute interval:
        - 11:23 -> 11:20
        - 11:20 -> 11:20
        - 11:09 -> 11:00
        """
        total_minutes = dt.hour * 60 + dt.minute
        interval_minutes = interval.total_seconds() / 60
        aligned_minutes = int(total_minutes / interval_minutes) * interval_minutes
        
        from datetime import time
        aligned_time = time(
            hour=int(aligned_minutes // 60),
            minute=int(aligned_minutes % 60)
        )
        
        return dt.replace(hour=aligned_time.hour, minute=aligned_time.minute, second=0, microsecond=0)

    def _calculate_reference_time(self) -> datetime:
        """
        Calculate the reference datetime for calculating lookback slots.
        Uses current UTC time converted to the configured timezone.
        
        Returns:
            datetime with timezone info set
        """
        now = datetime.now(ZoneInfo("UTC"))
        return now.astimezone(ZoneInfo(self.config.timezone))

    def generate_filename(self, pattern: str, dt: datetime) -> str:
        """
        Generate filename by replacing datetime placeholders.
        
        Placeholders: {YYYY}, {MM}, {DD}, {HH}, {MI}, {SS}, {YYYYMMDD}, {YYYYMMDDHH}, {YYYYMMDDHHMI}, {YYYYMMDDHHMISS}
        
        Args:
            pattern: Filename pattern with placeholders
            dt: Datetime to use for replacement
            
        Returns:
            Filename with placeholders replaced
        """
        # Convert to target timezone for formatting if datetime is naive
        if dt.tzinfo is None:
            dt = dt.astimezone(ZoneInfo(self.config.timezone))
        
        # Replace placeholders
        result = pattern
        result = result.replace('{YYYY}', dt.strftime('%Y'))
        result = result.replace('{MM}', dt.strftime('%m'))
        result = result.replace('{DD}', dt.strftime('%d'))
        result = result.replace('{HH}', dt.strftime('%H'))
        result = result.replace('{MI}', dt.strftime('%M'))
        result = result.replace('{SS}', dt.strftime('%S'))
        result = result.replace('{YYYYMMDD}', dt.strftime('%Y%m%d'))
        result = result.replace('{YYYYMMDDHH}', dt.strftime('%Y%m%d%H'))
        result = result.replace('{YYYYMMDDHHMI}', dt.strftime('%Y%m%d%H%M'))
        result = result.replace('{YYYYMMDDHHMISS}', dt.strftime('%Y%m%d%H%M%S'))
        
        return result

    def parse_datetime_from_filename(self, filename: str) -> datetime:
        """
        Extract datetime from filename.
        
        Supports formats: YYYYMMDDHHMISS, YYYYMMDDHHMI, YYYYMMDDHH, YYYYMMDD
        
        Args:
            filename: Filename to parse
            
        Returns:
            Datetime extracted from filename
            
        Raises:
            ValueError: If no datetime pattern found in filename
        """
        # Try different datetime patterns
        patterns = [
            (r'(\d{14})', '%Y%m%d%H%M%S'),  # YYYYMMDDHHMISS
            (r'(\d{12})', '%Y%m%d%H%M'),    # YYYYMMDDHHMI
            (r'(\d{10})', '%Y%m%d%H'),        # YYYYMMDDHH
            (r'(\d{8})', '%Y%m%d'),          # YYYYMMDD
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    dt = datetime.strptime(match.group(1), fmt)
                    # Convert to target timezone
                    return dt.replace(tzinfo=ZoneInfo(self.config.timezone))
                except ValueError:
                    continue
        
        raise ValueError(f"No valid datetime pattern found in filename: {filename}")

    def format_datetime(self, dt: datetime, pattern: str) -> str:
        """
        Format datetime with pattern.
        
        Args:
            dt: Datetime to format
            pattern: Format pattern
            
        Returns:
            Formatted datetime string
        """
        return self.generate_filename(pattern, dt)

    def get_utc_offset_hours(self) -> float:
        """
        Get UTC offset in hours for the configured timezone.
        
        Returns:
            UTC offset in hours (e.g., 8.0 for HKT, -5.0 for EST)
        """
        ref_time = self._calculate_reference_time()
        utc_time = ref_time.astimezone(ZoneInfo("UTC"))
        delta = ref_time - utc_time
        return delta.total_seconds() / 3600

    def convert_to_utc(self, dt: datetime) -> datetime:
        """
        Convert datetime to UTC.
        
        Args:
            dt: Datetime to convert (in configured timezone)
            
        Returns:
            UTC datetime
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(self.config.timezone))
        return dt.astimezone(ZoneInfo("UTC"))
