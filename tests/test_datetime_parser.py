"""Tests for datetime parser."""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.parsers.datetime_parser import DatetimeParser
from src.config_loader import DatetimeConfig


class TestDatetimeParser:
    """Test DatetimeParser functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = DatetimeConfig(
            pattern="%Y%m%d%H%M",
            timezone="Asia/Hong_Kong",  # UTC+8
            interval_minutes=10,
            offset_minutes=1,
            lookback_minutes=60
        )
        self.parser = DatetimeParser(self.config)

    def test_calculate_datetime_list(self):
        """Test calculation of datetime list for downloads with day-start alignment."""
        # Reference time: 2026-06-18 16:48:00 HKT
        # Algorithm:
        # 1. Day start: 00:00, Diff: 1008 min
        # 2. floor(1008/10)*10 + offset(1) = 1001 min = 16:41
        # 3. Slots: 16:41, 16:31, 16:21, 16:11, 16:01, 15:51
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        datetimes = self.parser.calculate_datetime_list(reference)
        
        # Should have 6 datetimes (60 / 10 = 6)
        assert len(datetimes) == 6
        
        # First slot should be 16:41 HKT (aligned to day start + offset)
        expected_first = datetime(2026, 6, 18, 16, 41, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        assert datetimes[0] == expected_first
        
        # Verify spacing (10 minutes between slots)
        for i in range(1, len(datetimes)):
            diff = (datetimes[i-1] - datetimes[i]).total_seconds() / 60
            assert diff == 10
        
        # Verify all slots
        expected_slots = [
            datetime(2026, 6, 18, 16, 41, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            datetime(2026, 6, 18, 16, 31, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            datetime(2026, 6, 18, 16, 21, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            datetime(2026, 6, 18, 16, 11, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            datetime(2026, 6, 18, 16, 1, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            datetime(2026, 6, 18, 15, 51, tzinfo=ZoneInfo("Asia/Hong_Kong")),
        ]
        for i, expected in enumerate(expected_slots):
            assert datetimes[i] == expected, f"Slot {i}: expected {expected}, got {datetimes[i]}"

    def test_generate_filename(self):
        """Test filename generation with datetime substitution."""
        dt = datetime(2026, 6, 18, 16, 46, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        pattern = "radar_{var1}_{YYYYMMDDHHMI}.jpg"  # Use HHMI for minute
        result = self.parser.generate_filename(pattern, dt)
        
        assert result == "radar_{var1}_202606181646.jpg"

    def test_generate_filename_with_var1(self):
        """Test filename generation with datetime substitution."""
        dt = datetime(2026, 6, 18, 16, 46, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        pattern = "radar_{var1}_{YYYYMMDDHHMI}.jpg"  # Use HHMI for minute
        filename = self.parser.generate_filename(pattern, dt)
        filename = filename.replace("{var1}", "tcr")
        
        assert filename == "radar_tcr_202606181646.jpg"

    def test_get_utc_date_path(self):
        """Test UTC date path extraction."""
        # 16:48 HKT = 08:48 UTC
        dt_hkt = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        utc_date = self.parser.get_utc_date_path(dt_hkt)
        
        assert utc_date == "20260618"

    def test_convert_to_utc(self):
        """Test timezone conversion to UTC."""
        dt_hkt = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        dt_utc = self.parser.convert_to_utc(dt_hkt)
        
        assert dt_utc.hour == 8
        assert dt_utc.minute == 48

    def test_extract_datetime_from_filename(self):
        """Test datetime extraction from filename."""
        filename = "radar_tcr_202606181646.jpg"
        
        original, dt, pattern = DatetimeParser.extract_datetime_from_filename(filename)
        
        assert original == filename
        assert dt.year == 2026
        assert dt.month == 6
        assert dt.day == 18
        assert dt.hour == 16
        assert dt.minute == 46


class TestDatetimeParserInterval180:
    """Test datetime parser with interval=180 (3 hours)."""
    
    def test_interval_180_aligned_to_day_start(self):
        """Test interval=180 with lookback=180, current=10:05."""
        # Current: 10:05, interval=180, offset=0, lookback=180
        # Day start: 00:00, Diff: 605 min
        # floor(605/180)*180 = 540, + offset(0) = 540 min = 09:00
        # Latest slot: 09:00, diff from current = 65 min ≤ 180 ✓
        # Next slot: 09:00 - 180 = 06:00, diff = 245 min > 180 ✗
        # Result: only 09:00
        config = DatetimeConfig(
            pattern="%Y%m%d%H%M",
            timezone="Asia/Hong_Kong",
            interval_minutes=180,
            offset_minutes=0,
            lookback_minutes=180
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 22, 10, 5, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        expected_slots = [
            datetime(2026, 6, 22, 9, 0, tzinfo=ZoneInfo("Asia/Hong_Kong")),
        ]
        
        assert len(datetimes) == 1
        assert datetimes[0] == expected_slots[0]


class TestDatetimeParserInterval720:
    """Test datetime parser with interval=720 (12 hours)."""
    
    def test_interval_720_aligned_to_day_start(self):
        """Test interval=720 with lookback=1440, current=09:08."""
        # Current: 09:08, interval=720, offset=0, lookback=1440
        # Day start: 00:00, Diff: 548 min
        # floor(548/720)*720 = 0, + offset(0) = 0 min = 00:00
        # Latest slot: 00:00, diff from current = 548 min ≤ 1440 ✓
        # Next slot: 00:00 - 720 = prev day 12:00, diff = 1268 min ≤ 1440 ✓
        # Next slot: prev day 12:00 - 720 = prev day 00:00, diff = ... > 1440 ✗
        # Result: 00:00 and prev day 12:00
        config = DatetimeConfig(
            pattern="%Y%m%d%H%M",
            timezone="Asia/Hong_Kong",
            interval_minutes=720,
            offset_minutes=0,
            lookback_minutes=1440
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 22, 9, 8, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        expected_slots = [
            datetime(2026, 6, 22, 0, 0, tzinfo=ZoneInfo("Asia/Hong_Kong")),
            datetime(2026, 6, 21, 12, 0, tzinfo=ZoneInfo("Asia/Hong_Kong")),
        ]
        
        assert len(datetimes) == 2
        assert datetimes[0] == expected_slots[0]
        assert datetimes[1] == expected_slots[1]


class TestDatetimeParserVariousPatterns:
    """Test various datetime patterns."""

    def test_YYYYMMDDHH(self):
        """Test YYYYMMDDHH pattern."""
        config = DatetimeConfig(pattern="%Y%m%d%H")
        parser = DatetimeParser(config)
        
        dt = datetime(2026, 6, 18, 16)
        result = parser.format_datetime(dt)
        
        assert result == "2026061816"

    def test_YYYYMMDD(self):
        """Test YYYYMMDD pattern."""
        config = DatetimeConfig(pattern="%Y%m%d")
        parser = DatetimeParser(config)
        
        dt = datetime(2026, 6, 18)
        result = parser.format_datetime(dt)
        
        assert result == "20260618"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
