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
        """Test calculation of datetime list for downloads."""
        # Reference time: 2026-06-18 16:48:00 HKT
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        datetimes = self.parser.calculate_datetime_list(reference)
        
        # Should have 6 datetimes (60 / 10 = 6)
        assert len(datetimes) == 6
        
        # First should be reference minus offset minus 0 intervals
        expected_first = reference - timedelta(minutes=1)
        assert datetimes[0] == expected_first
        
        # Verify spacing
        for i in range(1, len(datetimes)):
            diff = (datetimes[i-1] - datetimes[i]).total_seconds() / 60
            assert diff == 10

    def test_generate_filename(self):
        """Test filename generation with datetime substitution."""
        dt = datetime(2026, 6, 18, 16, 46, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        pattern = "radar_{var1}_{YYYYMMDDHHMM}.jpg"
        result = self.parser.generate_filename(pattern, dt)
        
        assert result == "radar_{var1}_202606181646.jpg"

    def test_generate_filename_with_var1(self):
        """Test filename generation with var1 substitution."""
        dt = datetime(2026, 6, 18, 16, 46, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        
        pattern = "radar_{var1}_{YYYYMMDDHHMM}.jpg"
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
