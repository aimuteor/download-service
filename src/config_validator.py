"""Configuration validator for download service."""

import re
from typing import List, Tuple
from zoneinfo import ZoneInfo


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__(f"Configuration validation failed: {'; '.join(errors)}")


def validate_sources(sources: List) -> List[str]:
    """
    Validate a list of source configurations.
    
    Args:
        sources: List of SourceConfig objects
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    for source in sources:
        source_errors = validate_source(source)
        for err in source_errors:
            errors.append(f"[{source.name}] {err}")
    
    return errors


def validate_source(source) -> List[str]:
    """
    Validate a single source configuration.
    
    Args:
        source: SourceConfig object
        
    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    
    # ========== Level 1: Basic validation ==========
    
    # Required string fields
    if not hasattr(source, 'name') or not source.name:
        errors.append("name is required")
        return errors  # Can't continue without name
    
    if not hasattr(source, 'type') or not source.type:
        errors.append("type is required")
    elif source.type not in ['http', 'https', 'ftp', 'sftp']:
        errors.append(f"type must be one of: http, https, ftp, sftp")
    
    if not hasattr(source, 'path') or not source.path:
        errors.append("path is required")
    
    if not hasattr(source, 'filename_pattern') or not source.filename_pattern:
        errors.append("filename_pattern is required")
    
    # ========== Level 2: Numeric range validation ==========
    
    if hasattr(source, 'interval_minutes'):
        if not isinstance(source.interval_minutes, int):
            errors.append("interval_minutes must be integer")
        elif source.interval_minutes < 1:
            errors.append("interval_minutes must be >= 1")
        elif source.interval_minutes > 1440:
            errors.append("interval_minutes seems too large (>24 hours)")
    
    if hasattr(source, 'timeout'):
        if not isinstance(source.timeout, int):
            errors.append("timeout must be integer")
        elif source.timeout < 1:
            errors.append("timeout must be >= 1")
    
    if hasattr(source, 'lookback_minutes'):
        if not isinstance(source.lookback_minutes, int):
            errors.append("lookback_minutes must be integer")
        elif source.lookback_minutes < 0:
            errors.append("lookback_minutes cannot be negative")
    
    if hasattr(source, 'offset_minutes'):
        if not isinstance(source.offset_minutes, int):
            errors.append("offset_minutes must be integer")
        elif source.offset_minutes < 0:
            errors.append("offset_minutes cannot be negative")
    
    # ========== Level 3: Timezone validation ==========
    
    if hasattr(source, 'datetime_config') and source.datetime_config:
        dt_config = source.datetime_config
        if hasattr(dt_config, 'timezone') and dt_config.timezone:
            try:
                ZoneInfo(dt_config.timezone)
            except KeyError:
                errors.append(f"Invalid timezone: {dt_config.timezone}")
    
    # ========== Level 4: VAR reference validation ==========
    
    if hasattr(source, 'filename_pattern') and source.filename_pattern:
        # Extract all {VAR} patterns from filename_pattern
        used_vars = set(re.findall(r'\{(\w+)\}', source.filename_pattern))
        
        # Remove datetime placeholders (these are built-in)
        datetime_placeholders = {'YYYY', 'MM', 'DD', 'HH', 'MI', 'SS', 
                                'YYYYMMDD', 'YYYYMMDDHH', 'YYYYMMDDHHMI', 'YYYYMMDDHHMISS',
                                'dataDir'}
        used_vars = used_vars - datetime_placeholders
        
        if hasattr(source, 'var_arrays') and source.var_arrays:
            defined_vars = set(source.var_arrays.keys())
            undefined = used_vars - defined_vars
            if undefined:
                errors.append(f"Undefined vars in filename_pattern: {undefined}")
        elif used_vars:
            errors.append(f"var_arrays required for vars: {used_vars}")
    
    # Validate var_arrays values
    if hasattr(source, 'var_arrays') and source.var_arrays:
        for var_name, values in source.var_arrays.items():
            if not isinstance(values, list):
                errors.append(f"var_arrays.{var_name} must be a list")
            elif len(values) == 0:
                errors.append(f"var_arrays.{var_name} cannot be empty")
    
    return errors


def is_config_changed(config_path: str, new_content: str) -> bool:
    """
    Check if config content has changed from stored hash.
    Returns True if changed, False if same.
    """
    import hashlib
    
    new_hash = hashlib.sha256(new_content.encode()).hexdigest()
    
    try:
        with open(config_path, 'r') as f:
            old_content = f.read()
        old_hash = hashlib.sha256(old_content.encode()).hexdigest()
        return new_hash != old_hash
    except Exception:
        return True  # If can't read, assume changed
