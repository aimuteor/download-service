"""Datetime parsing and calculation for download scheduling."""

from datetime import datetime, timedelta
from typing import List, Tuple
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
        
        Algorithm (aligns to day start + offset):
        1. Find today's day start (00:00) in source timezone
        2. Calculate diff in minutes from day start to reference_time
        3. Round down diff to nearest interval boundary
        4. Add offset_minutes to get the first (latest) slot minute
        5. Go backwards by interval for lookback
        
        Example: interval=10, offset=1, lookback=60, ref=16:48 HKT
        - Day start: 00:00, Diff: 1008 min
        - floor(1008/10)*10 = 1000 (aligned to interval)
        - + offset(1) = 1001 min = 16:41 (latest slot)
        - Go back: 16:41, 16:31, 16:21, 16:11, 16:01, 15:51
        
        Args:
            reference_time: Optional reference time, defaults to current time
            
        Returns:
            List of datetimes to attempt
        """
        if reference_time is None:
            reference_time = self._calculate_reference_time()
        
        # Ensure reference_time is timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=ZoneInfo(self.config.timezone))
        
        # Step 1: Find today's day start (00:00) in source timezone
        today_start = reference_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Step 2: Calculate diff in minutes from day start to reference_time
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
        
        max_lookback_minutes = self.config.lookback_minutes
        
        while True:
            minutes_since_slot = (reference_time - current_slot).total_seconds() / 60
            
            if minutes_since_slot > max_lookback_minutes:
                break
            
            if current_slot <= reference_time:
                datetimes.append(current_slot)
            
            current_slot = current_slot - timedelta(minutes=self.config.interval_minutes)
            
            # Safety break
            if len(datetimes) > 1000:
                break
        
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
        tz = ZoneInfo(self.config.timezone)
        # Get the UTC offset for this timezone at a reference point
        ref_point = datetime(2026, 7, 2, 12, 0, tzinfo=tz)  # noon on a specific date
        utc_point = ref_point.astimezone(ZoneInfo("UTC"))
        offset = ref_point.utcoffset()
        return offset.total_seconds() / 3600 if offset else 0.0

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
    def extract_datetime_from_filename(filename: str) -> Tuple[str, datetime, str]:
        """
        Extract datetime from a filename.
        
        Args:
            filename: Filename to parse
            
        Returns:
            Tuple of (original_filename, datetime, matched_pattern)
        """
        patterns = [
            (r'(\d{14})', '%Y%m%d%H%M%S'),  # YYYYMMDDHHMISS
            (r'(\d{12})', '%Y%m%d%H%M'),    # YYYYMMDDHHMI
            (r'(\d{10})', '%Y%m%d%H'),      # YYYYMMDDHH
            (r'(\d{8})', '%Y%m%d'),         # YYYYMMDD
        ]
        
        for pattern, fmt in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    dt = datetime.strptime(match.group(1), fmt)
                    return filename, dt, pattern
                except ValueError:
                    continue
        
        raise ValueError(f"No valid datetime pattern found in filename: {filename}")
