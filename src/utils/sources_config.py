"""
Utility to generate sources.json for the monitoring page.
"""

import json
from pathlib import Path
from typing import List
from dataclasses import asdict


def save_sources_config(sources: List, output_path: str = "./monitor/sources.json") -> None:
    """
    Save source configurations (without passwords) to JSON file.
    
    Args:
        sources: List of SourceConfig objects
        output_path: Path to save the JSON file
    """
    configs = []
    for source in sources:
        cfg = {
            "name": source.name,
            "type": source.type,
            "host": source.host,
            "port": source.port,
            "path": source.path,
            "filename_pattern": source.filename_pattern,
            "method": getattr(source, 'method', 'GET'),
        }
        
        # Add auth info (without password)
        if hasattr(source, 'auth_credentials') and source.auth_credentials:
            cfg["auth_credentials"] = {
                "username": getattr(source.auth_credentials, 'username', None)
                # Intentionally omit password for security
            }
        
        # Add datetime_config (convert dataclass to dict)
        if hasattr(source, 'datetime_config') and source.datetime_config:
            cfg["datetime_config"] = asdict(source.datetime_config)
        
        configs.append(cfg)
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(configs, f, indent=2, ensure_ascii=False)
