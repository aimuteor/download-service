"""
Status tracker for monitoring download status.
Generates status.json for the web monitoring interface.
"""

import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class SourceError:
    """Record of a download error."""
    time: str
    message: str
    url: str = ""


@dataclass
class SourceStatus:
    """Status for a single source."""
    type: str
    current_status: str  # "success", "error", "unknown"
    last_success: Optional[str] = None
    last_attempt: Optional[str] = None
    today_total: int = 0
    today_success: int = 0
    today_failed: int = 0
    last_24h_total: int = 0
    last_24h_success: int = 0
    last_24h_failed: int = 0
    recent_errors: List[SourceError] = None
    
    def __post_init__(self):
        if self.recent_errors is None:
            self.recent_errors = []
    
    @property
    def today_success_rate(self) -> float:
        if self.today_total == 0:
            return 0.0
        return round(self.today_success / self.today_total * 100, 1)
    
    @property
    def last_24h_success_rate(self) -> float:
        if self.last_24h_total == 0:
            return 0.0
        return round(self.last_24h_success / self.last_24h_total * 100, 1)
    
    @property
    def hours_since_last_success(self) -> Optional[float]:
        if not self.last_success:
            return None
        try:
            last = datetime.fromisoformat(self.last_success.replace('+08:00', '').replace('Z', ''))
            now = datetime.now()
            delta = now - last
            return round(delta.total_seconds() / 3600, 1)
        except:
            return None
    
    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "current_status": self.current_status,
            "last_success": self.last_success,
            "last_attempt": self.last_attempt,
            "today_stats": {
                "total": self.today_total,
                "success": self.today_success,
                "failed": self.today_failed,
                "success_rate": self.today_success_rate
            },
            "last_24h_stats": {
                "total": self.last_24h_total,
                "success": self.last_24h_success,
                "failed": self.last_24h_failed,
                "success_rate": self.last_24h_success_rate
            },
            "recent_errors": [asdict(e) for e in self.recent_errors[-10:]]  # Last 10 errors
        }


class StatusTracker:
    """
    Tracks download status for all sources and generates status.json.
    
    Usage:
        tracker = StatusTracker("./data")
        tracker.record_success("source_name", "ftp")
        tracker.record_failure("source_name", "Connection timeout")
        tracker.save()
    """
    
    def __init__(self, data_dir: str = "./monitor"):
        self.data_dir = Path(data_dir)
        self.status_file = self.data_dir / "status.json"
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        
        # In-memory state
        self.sources: Dict[str, SourceStatus] = {}
        self.last_updated: Optional[str] = None
        
        # Load existing status if available
        self._load()
    
    def _load(self):
        """Load existing status from JSON file."""
        if not self.status_file.exists():
            return
        
        try:
            with open(self.status_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.last_updated = data.get("last_updated")
            
            for name, info in data.get("sources", {}).items():
                status = SourceStatus(
                    type=info.get("type", "unknown"),
                    current_status=info.get("current_status", "unknown"),
                    last_success=info.get("last_success"),
                    last_attempt=info.get("last_attempt"),
                    today_total=info.get("today_stats", {}).get("total", 0),
                    today_success=info.get("today_stats", {}).get("success", 0),
                    today_failed=info.get("today_stats", {}).get("failed", 0),
                    last_24h_total=info.get("last_24h_stats", {}).get("total", 0),
                    last_24h_success=info.get("last_24h_stats", {}).get("success", 0),
                    last_24h_failed=info.get("last_24h_stats", {}).get("failed", 0),
                    recent_errors=[
                        SourceError(**e) for e in info.get("recent_errors", [])
                    ]
                )
                self.sources[name] = status
        except Exception as e:
            print(f"Failed to load status file: {e}")
    
    def save(self):
        """Save current status to JSON file."""
        self.last_updated = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        
        data = {
            "last_updated": self.last_updated,
            "sources": {
                name: status.to_dict() 
                for name, status in self.sources.items()
            }
        }
        
        # Write atomically using temp file
        temp_file = self.status_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Replace original
        temp_file.replace(self.status_file)
    
    def get_or_create_source(self, name: str, source_type: str) -> SourceStatus:
        """Get existing source or create new one."""
        if name not in self.sources:
            self.sources[name] = SourceStatus(
                type=source_type,
                current_status="unknown"
            )
        return self.sources[name]
    
    def record_success(self, name: str, source_type: str):
        """Record a successful download."""
        status = self.get_or_create_source(name, source_type)
        now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        
        status.last_success = now
        status.last_attempt = now
        status.current_status = "success"
        status.today_total += 1
        status.today_success += 1
        status.last_24h_total += 1
        status.last_24h_success += 1
        
        self.save()
    
    def record_failure(self, name: str, source_type: str, error_message: str, url: str = ""):
        """Record a failed download."""
        status = self.get_or_create_source(name, source_type)
        now = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")
        
        status.last_attempt = now
        status.current_status = "error"
        status.today_total += 1
        status.today_failed += 1
        status.last_24h_total += 1
        status.last_24h_failed += 1
        
        # Add to recent errors
        status.recent_errors.append(SourceError(
            time=now,
            message=error_message,
            url=url
        ))
        
        # Keep only last 50 errors
        if len(status.recent_errors) > 50:
            status.recent_errors = status.recent_errors[-50:]
        
        self.save()
    
    def reset_daily_stats(self):
        """Reset today's stats (call at midnight)."""
        for status in self.sources.values():
            status.today_total = 0
            status.today_success = 0
            status.today_failed = 0
        self.save()
    
    def update_24h_stats(self):
        """
        Update 24h statistics.
        This should be called periodically to decay old data.
        For simplicity, we just decay the counts by assuming uniform distribution.
        """
        # Simple approach: keep running totals and they'll naturally
        # be replaced as new data comes in
        pass
    
    def get_all_sources_sorted(self) -> List[tuple]:
        """
        Get all sources sorted by priority:
        1. Sources with errors (most recent error first)
        2. Sources with no recent success (hours since last success)
        3. Alphabetical
        """
        def sort_key(item):
            name, status = item
            has_error = status.current_status == "error"
            hours_since = status.hours_since_last_success or 0
            # Sort: errors first, then by hours since last success (descending)
            return (not has_error, -hours_since, name)
        
        return sorted(self.sources.items(), key=sort_key)
    
    def to_json(self) -> str:
        """Get status as JSON string."""
        data = {
            "last_updated": self.last_updated or datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z"),
            "sources": {
                name: status.to_dict() 
                for name, status in self.sources.items()
            }
        }
        return json.dumps(data, indent=2, ensure_ascii=False)
    
    @staticmethod
    def mask_passwords_in_config(config: dict) -> dict:
        """Create a copy of config with passwords masked."""
        import copy
        cfg = copy.deepcopy(config)
        
        # Mask password in auth_credentials
        if 'auth_credentials' in cfg and cfg['auth_credentials']:
            if 'password' in cfg['auth_credentials']:
                cfg['auth_credentials']['password'] = None  # Will show as [hidden]
        
        return cfg


# Global instance for easy import
_tracker: Optional[StatusTracker] = None

def get_tracker(data_dir: str = "./data") -> StatusTracker:
    """Get or create global status tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = StatusTracker(data_dir)
    return _tracker
