"""
Config backup manager for maintaining rolling backups of successful configs.
"""

import os
import shutil
from pathlib import Path
from typing import Optional
import hashlib


class ConfigBackupManager:
    """
    Manages rolling backups of successful config files.
    Keeps last N successful configs.
    """
    
    MAX_BACKUPS = 5
    
    def __init__(self, config_path: str):
        """
        Args:
            config_path: Path to the main config file (e.g., config/config.yaml)
        """
        self.config_path = Path(config_path)
        self.config_dir = self.config_path.parent
        self.backup_name = self.config_path.name + ".last_good"
        self.backup_path = self.config_dir / self.backup_name
        
        # Rolling backups: config.yaml.last_good.1, .2, .3, .4, .5
        self.rolling_backups = [
            self.config_dir / f"{self.backup_name}.{i}" 
            for i in range(1, self.MAX_BACKUPS + 1)
        ]
    
    def save_successful_config(self) -> bool:
        """
        Save current config as successful backup.
        Only saves if config content has changed.
        
        Returns:
            True if saved, False if skipped (no change)
        """
        if not self.config_path.exists():
            return False
        
        # Read current config
        try:
            with open(self.config_path, 'r') as f:
                current_content = f.read()
        except Exception as e:
            print(f"[WARN] Cannot read config for backup: {e}")
            return False
        
        # Check if changed from last backup
        if self.backup_path.exists():
            try:
                with open(self.backup_path, 'r') as f:
                    last_content = f.read()
                if current_content == last_content:
                    return False  # No change, don't save
            except Exception:
                pass  # If can't read, proceed with save
        
        # Shift rolling backups (5 -> 4 -> 3 -> 2 -> 1)
        self._shift_backups()
        
        # Save current as last_good
        try:
            with open(self.backup_path, 'w') as f:
                f.write(current_content)
            print(f"[INFO] Saved successful config backup: {self.backup_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Cannot save config backup: {e}")
            return False
    
    def _shift_backups(self):
        """Shift rolling backups down (5 -> 4, 4 -> 3, etc.)"""
        # Remove oldest (5)
        if self.rolling_backups[-1].exists():
            self.rolling_backups[-1].unlink()
        
        # Shift existing numbered backups down first (.1 -> .2, .2 -> .3, etc.)
        for i in range(len(self.rolling_backups) - 1, 0, -1):
            src = self.rolling_backups[i - 1]
            dst = self.rolling_backups[i]
            if src.exists():
                shutil.copy2(src, dst)
        
        # Then copy current last_good to .1
        if self.backup_path.exists():
            shutil.copy2(self.backup_path, self.rolling_backups[0])
    
    def restore_last_good(self) -> bool:
        """
        Restore from the last good backup.
        
        Returns:
            True if restored, False if no backup available
        """
        if not self.backup_path.exists():
            print(f"[WARN] No backup config found at: {self.backup_path}")
            return False
        
        try:
            # Read backup
            with open(self.backup_path, 'r') as f:
                content = f.read()
            
            # Write to main config
            with open(self.config_path, 'w') as f:
                f.write(content)
            
            print(f"[INFO] Restored config from backup: {self.backup_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Cannot restore config from backup: {e}")
            return False
    
    def has_backup(self) -> bool:
        """Check if a backup exists."""
        return self.backup_path.exists()
    
    def get_backup_info(self) -> dict:
        """Get info about available backups."""
        info = {
            "has_backup": self.has_backup(),
            "main_config": str(self.config_path),
            "backup_path": str(self.backup_path),
            "rolling_backups": []
        }
        
        for bp in self.rolling_backups:
            if bp.exists():
                stat = bp.stat()
                info["rolling_backups"].append({
                    "path": str(bp),
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })
        
        return info
