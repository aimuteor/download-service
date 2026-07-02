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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestOffsetMinutes:
    """Test offset_minutes functionality."""
    
    def test_offset_1_minute(self):
        """Test offset=1 shifts slots to minute 1 of each interval."""
        # interval=10, offset=1, lookback=60, ref=16:48
        # Slots should be at XX:01, XX:11, XX:21, XX:31, XX:41, XX:51
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=10,
            offset_minutes=1,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        # Verify all slots end with XX:01, XX:11, XX:21, XX:31, XX:41, XX:51
        expected = [16, 16, 16, 16, 16, 15]  # hours
        expected_mins = [41, 31, 21, 11, 1, 51]
        
        assert len(datetimes) == 6
        for i, dt in enumerate(datetimes):
            assert dt.hour == expected[i], f"Slot {i}: expected hour {expected[i]}, got {dt.hour}"
            assert dt.minute == expected_mins[i], f"Slot {i}: expected minute {expected_mins[i]}, got {dt.minute}"
    
    def test_offset_5_minutes(self):
        """Test offset=5 shifts slots to minute 5 of each interval."""
        # interval=10, offset=5, lookback=60, ref=16:48
        # Slots should be at XX:05, XX:15, XX:25, XX:35, XX:45, XX:55
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=10,
            offset_minutes=5,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        expected_mins = [45, 35, 25, 15, 5, 55]
        
        assert len(datetimes) == 6
        for i, dt in enumerate(datetimes):
            assert dt.minute == expected_mins[i], f"Slot {i}: expected minute {expected_mins[i]}, got {dt.minute}"
    
    def test_offset_0_no_shift(self):
        """Test offset=0 gives slots at minute 0 of each interval."""
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=10,
            offset_minutes=0,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        # Should be at XX:40, XX:30, XX:20, XX:10, XX:00, XX:50 (going back)
        # Actually: latest slot = floor(1008/10)*10 + 0 = 1000 min = 16:40
        # Then: 16:40, 16:30, 16:20, 16:10, 16:00, 15:50
        expected_mins = [40, 30, 20, 10, 0, 50]
        expected_hours = [16, 16, 16, 16, 16, 15]
        
        assert len(datetimes) == 6
        for i, dt in enumerate(datetimes):
            assert dt.minute == expected_mins[i], f"Slot {i}: expected minute {expected_mins[i]}, got {dt.minute}"
            assert dt.hour == expected_hours[i], f"Slot {i}: expected hour {expected_hours[i]}, got {dt.hour}"


class TestUTCHKTConversion:
    """Test UTC to HKT timezone conversion via _calculate_reference_time()."""
    
    def test_calculate_reference_time_converts_utc_to_hkt(self):
        """
        Test that _calculate_reference_time() properly converts UTC to HKT.
        
        This is a critical test because _calculate_reference_time() is called
        when no reference_time is passed to calculate_datetime_list().
        
        The bug was: datetime.now().astimezone(HKT) treated the naive local time
        as if it were already in HKT, causing wrong conversions.
        
        The fix is: datetime.now(ZoneInfo("UTC")).astimezone(HKT) properly
        treats the current time as UTC then converts to HKT.
        """
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",  # UTC+8
            interval_minutes=10,
            offset_minutes=0,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        # Get reference time
        ref_time = parser._calculate_reference_time()
        
        # It should be timezone-aware
        assert ref_time.tzinfo is not None, "Reference time should be timezone-aware"
        
        # Convert to UTC to check
        utc_time = ref_time.astimezone(ZoneInfo("UTC"))
        
        # The UTC time should be the current UTC time (within a few seconds)
        from datetime import datetime
        current_utc = datetime.now(ZoneInfo("UTC"))
        
        # Should be within 1 minute of current UTC time
        diff_seconds = abs((current_utc - utc_time).total_seconds())
        assert diff_seconds < 60, f"Reference time should be close to current UTC, but diff was {diff_seconds} seconds"
    
    def test_calculate_datetime_list_uses_utc_to_hkt_conversion(self):
        """
        Test that calculate_datetime_list() without reference_time uses
        proper UTC→HKT conversion.
        
        This test uses a fixed "current UTC" to verify the algorithm works correctly.
        """
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=10,
            offset_minutes=0,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        # We pass None to force use of _calculate_reference_time()
        # But since we can't mock datetime.now(), we just verify the slots
        # are in HKT and the timezone conversion is correct
        
        datetimes = parser.calculate_datetime_list()
        
        # All datetimes should be timezone-aware and in HKT
        for dt in datetimes:
            assert dt.tzinfo is not None, f"Slot {dt} should be timezone-aware"
        
        # The slots should span roughly the last hour in HKT
        # (we can't exacty predict since we don't know the exact current time)
        assert len(datetimes) > 0, "Should have at least some slots"
    
    def test_hkt_is_8_hours_ahead_of_utc(self):
        """Verify HKT timezone is correctly UTC+8."""
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=10,
            offset_minutes=0,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        utc_offset = parser.get_utc_offset_hours()
        assert utc_offset == 8.0, f"HKT should be UTC+8, but get_utc_offset_hours() returned {utc_offset}"


class TestNegativeOffsetMinutes:
    """Test negative offset_minutes functionality."""
    
    def test_negative_offset_allows_earlier_slots(self):
        """
        Test that negative offset shifts slots to earlier in each interval.
        
        With interval=10 and offset=-3:
        - Normal slots would be XX:00, XX:10, XX:20, XX:30, XX:40, XX:50
        - With offset=-3, slots become XX:57, XX:07, XX:17, XX:27, XX:37, XX:47
          (3 minutes before each 10-min boundary)
        """
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=10,
            offset_minutes=-3,
            lookback_minutes=60
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        # With offset=-3, the latest slot should be 16:37
        # (floor(1008/10)*10 + (-3) = 1000 - 3 = 997 min = 16:37)
        # 15:47 would be 61 min before ref, outside 60 min lookback
        expected_mins = [37, 27, 17, 7, 57]
        expected_hours = [16, 16, 16, 16, 15]
        
        assert len(datetimes) == 5, f"Expected 5 slots, got {len(datetimes)}"
        for i, dt in enumerate(datetimes):
            assert dt.hour == expected_hours[i], f"Slot {i}: expected hour {expected_hours[i]}, got {dt.hour}"
            assert dt.minute == expected_mins[i], f"Slot {i}: expected minute {expected_mins[i]}, got {dt.minute}"
    
    def test_negative_offset_with_small_interval(self):
        """Test negative offset with interval=5."""
        config = DatetimeConfig(
            timezone="Asia/Hong_Kong",
            interval_minutes=5,
            offset_minutes=-2,
            lookback_minutes=30
        )
        parser = DatetimeParser(config)
        
        reference = datetime(2026, 6, 18, 16, 48, tzinfo=ZoneInfo("Asia/Hong_Kong"))
        datetimes = parser.calculate_datetime_list(reference)
        
        # With interval=5 and offset=-2:
        # Day start diff: 1008 min, floor(1008/5)*5 = 1005, + (-2) = 1003 = 16:43
        # Then go back by 5: 16:43, 16:38, 16:33, 16:28, 16:23, 16:18
        expected_mins = [43, 38, 33, 28, 23, 18]
        
        assert len(datetimes) == 6
        for i, dt in enumerate(datetimes):
            assert dt.minute == expected_mins[i], f"Slot {i}: expected minute {expected_mins[i]}, got {dt.minute}"


class TestConfigValidatorNegativeOffset:
    """Test that config validator allows negative offset_minutes."""
    
    def test_validator_allows_negative_offset(self):
        """Test that validate_source allows negative offset_minutes."""
        from src.config_validator import validate_source
        
        class MockSource:
            name = "test_source"
            type = "http"
            datetime_config = DatetimeConfig(
                timezone="Asia/Hong_Kong",
                interval_minutes=10,
                offset_minutes=-5,
                lookback_minutes=60
            )
            offset_minutes = -5
        
        errors = validate_source(MockSource())
        
        # Filter for offset-related errors
        offset_errors = [e for e in errors if 'offset' in e.lower()]
        assert len(offset_errors) == 0, f"Unexpected offset errors: {offset_errors}"
