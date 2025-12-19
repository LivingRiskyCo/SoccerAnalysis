"""
Metadata Export Module
Handles metadata export for overlays (supports both JSON and Pickle)
"""

import json
import pickle
import os
from typing import Dict, Any, Optional

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ...utils.json_utils import safe_json_save
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
        from soccer_analysis.utils.json_utils import safe_json_save
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
            from json_utils import safe_json_save
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)
            def safe_json_save(data, path):
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

logger = get_logger("metadata_export")


class MetadataExporter:
    """Handles metadata export for overlays"""
    
    def __init__(self):
        """Initialize metadata exporter"""
        pass
    
    def export_overlay_metadata(self, metadata: Any, 
                                output_path: str,
                                use_pickle: bool = True) -> str:
        """
        Export overlay metadata to JSON or Pickle
        
        Args:
            metadata: Overlay metadata object (should have .save() method or be dict)
            output_path: Output file path (will be adjusted for format)
            use_pickle: Use Pickle format (faster) or JSON (portable)
            
        Returns:
            Path to saved file
        """
        try:
            # If metadata has a .save() method (like OverlayMetadata class), use it
            if hasattr(metadata, 'save'):
                saved_path = metadata.save(output_path, use_pickle=use_pickle)
                logger.info(f"Exported overlay metadata: {saved_path}")
                logger.info(f"   → {len(metadata.overlays)} frames with overlay data")
                logger.info(f"   → Format: {'Pickle (fast)' if saved_path.endswith('.pkl') else 'JSON (portable)'}")
                return saved_path
            
            # Otherwise, treat as dictionary
            if use_pickle:
                # Use pickle for faster serialization
                pickle_path = output_path.replace('.json', '_overlay_metadata.pkl')
                if not pickle_path.endswith('.pkl'):
                    pickle_path = output_path + '_overlay_metadata.pkl'
                
                with open(pickle_path, 'wb') as f:
                    pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                logger.info(f"Exported overlay metadata to: {pickle_path}")
                logger.info(f"   → Format: Pickle (fast)")
                return pickle_path
            else:
                # Use JSON for portability
                json_path = output_path.replace('.pkl', '_overlay_metadata.json')
                if not json_path.endswith('.json'):
                    json_path = output_path + '_overlay_metadata.json'
                
                safe_json_save(metadata, json_path)
                
                logger.info(f"Exported overlay metadata to: {json_path}")
                logger.info(f"   → Format: JSON (portable)")
                return json_path
            
        except Exception as e:
            logger.error(f"Error exporting metadata: {e}", exc_info=True)
            raise

