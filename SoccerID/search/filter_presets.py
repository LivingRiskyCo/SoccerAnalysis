"""
Filter Presets Module
Save and load custom filter presets
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("filter_presets")


class FilterPresets:
    """
    Manage custom filter presets
    """
    
    def __init__(self, presets_file: str = "filter_presets.json"):
        """
        Initialize filter presets
        
        Args:
            presets_file: Path to presets storage file
        """
        self.presets_file = presets_file
        self.presets = {}  # preset_name -> filter_config
        self.load_presets()
    
    def save_preset(self,
                   name: str,
                   filters: Dict[str, Any],
                   description: Optional[str] = None) -> bool:
        """
        Save a filter preset
        
        Args:
            name: Preset name
            filters: Filter configuration dictionary
            description: Optional description
            
        Returns:
            True if successful
        """
        self.presets[name] = {
            'filters': filters,
            'description': description or "",
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.save_presets()
        logger.info(f"Saved filter preset: {name}")
        return True
    
    def load_preset(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a filter preset"""
        if name in self.presets:
            return self.presets[name]['filters'].copy()
        return None
    
    def delete_preset(self, name: str) -> bool:
        """Delete a filter preset"""
        if name in self.presets:
            del self.presets[name]
            self.save_presets()
            logger.info(f"Deleted filter preset: {name}")
            return True
        return False
    
    def list_presets(self) -> List[Dict[str, Any]]:
        """List all presets"""
        return [
            {
                'name': name,
                'description': preset['description'],
                'created_at': preset['created_at'],
                'updated_at': preset['updated_at']
            }
            for name, preset in self.presets.items()
        ]
    
    def save_presets(self):
        """Save presets to file"""
        try:
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save presets: {e}")
    
    def load_presets(self):
        """Load presets from file"""
        if not os.path.exists(self.presets_file):
            return
        
        try:
            with open(self.presets_file, 'r') as f:
                self.presets = json.load(f)
            logger.info(f"Loaded {len(self.presets)} filter presets")
        except Exception as e:
            logger.error(f"Failed to load presets: {e}")

