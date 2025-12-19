"""
Overlay Metadata System
Stores and manages visualization overlays separately from base video
OPTIMIZED: Supports both JSON and pickle formats for faster serialization
"""

import json
import pickle
import os
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import numpy as np
import math


class SafeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles NaN, inf, numpy types, and other invalid values."""
    def encode(self, o):
        # Recursively clean the object before encoding
        cleaned = self._clean_value(o)
        return super().encode(cleaned)
    
    def default(self, obj):
        """Fallback for objects that can't be serialized by the default encoder."""
        return self._clean_value(obj)
    
    def _clean_value(self, obj):
        """Recursively clean values to ensure JSON serializability."""
        if isinstance(obj, dict):
            return {k: self._clean_value(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._clean_value(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return self._clean_value(obj.tolist())
        # Check for numpy types BEFORE checking for Python types
        # numpy.float32 is NOT a subclass of float, so it needs explicit checking
        elif hasattr(obj, 'dtype'):
            # This catches numpy scalars that have a dtype attribute
            obj_item = obj.item() if hasattr(obj, 'item') else obj
            if isinstance(obj_item, float):
                if math.isnan(obj_item) or math.isinf(obj_item):
                    return None
                return float(obj_item)
            elif isinstance(obj_item, (int, bool)):
                return int(obj_item) if not isinstance(obj_item, bool) else bool(obj_item)
            else:
                return obj_item
        elif isinstance(obj, (np.floating, np.float32, np.float64, np.float16)):
            # Handle all numpy float types
            fval = float(obj)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        elif isinstance(obj, (np.integer, np.int32, np.int64, np.int16, np.int8, np.uint32, np.uint64, np.uint16, np.uint8)):
            # Handle all numpy integer types
            return int(obj)
        elif isinstance(obj, np.generic):
            # Catch any other numpy scalar types
            obj_item = obj.item() if hasattr(obj, 'item') else obj
            if isinstance(obj_item, float):
                fval = float(obj_item)
                if math.isnan(fval) or math.isinf(fval):
                    return None
                return fval
            elif isinstance(obj_item, int):
                return int(obj_item)
            else:
                return obj_item
        elif isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return obj
        elif isinstance(obj, (int, bool)):
            return obj
        else:
            return obj


class OverlayMetadata:
    """Manages overlay metadata for video analysis."""
    
    def __init__(self, video_path: str, fps: float, total_frames: int):
        """
        Initialize overlay metadata.
        
        Args:
            video_path: Path to base video
            fps: Video frame rate
            total_frames: Total number of frames
        """
        self.video_path = video_path
        self.fps = fps
        self.total_frames = total_frames
        self.overlays = {}  # frame_num -> overlay data
        self.visualization_settings = {}
        self.analytics_data = {}  # frame_num -> {player_id: analytics}
        
    def add_frame_overlay(self, frame_num: int, players: List[Dict], ball: Optional[Dict] = None,
                          analytics: Optional[Dict] = None, predicted_boxes: Optional[List[Dict]] = None,
                          raw_yolo_detections: Optional[Dict] = None):
        """
        Add overlay data for a frame.
        
        Args:
            frame_num: Frame number
            players: List of player overlay data
            ball: Ball overlay data (optional)
            analytics: Analytics data for players (optional)
            predicted_boxes: List of predicted box data for lost tracks (optional)
            raw_yolo_detections: Raw YOLO detection boxes before tracking (optional)
        """
        self.overlays[frame_num] = {
            "players": players,
            "ball": ball
        }
        
        if predicted_boxes:
            self.overlays[frame_num]["predicted_boxes"] = predicted_boxes
        
        if raw_yolo_detections:
            self.overlays[frame_num]["raw_yolo_detections"] = raw_yolo_detections
        
        if analytics:
            self.analytics_data[frame_num] = analytics
    
    def set_visualization_settings(self, settings: Dict):
        """Set visualization settings."""
        self.visualization_settings = settings
    
    def save(self, output_path: str, use_pickle: bool = True):
        """
        Save overlay metadata to file (pickle or JSON).
        
        OPTIMIZATION: Pickle is faster for large metadata files (3-5x faster).
        JSON is more portable and human-readable but slower for large files.
        
        Args:
            output_path: Path to save file
            use_pickle: If True, use pickle format (.pkl), else use JSON (.json)
        """
        # Determine format from extension or use_pickle flag
        if use_pickle or output_path.endswith('.pkl'):
            pickle_path = output_path.replace('.json', '.pkl') if output_path.endswith('.json') else output_path
            if not pickle_path.endswith('.pkl'):
                pickle_path += '.pkl'
            try:
                metadata = {
                    "video_path": self.video_path,
                    "fps": self.fps,
                    "total_frames": self.total_frames,
                    "overlays": self.overlays,  # Keep as dict, pickle handles it natively
                    "analytics": self.analytics_data,
                    "visualization_settings": self.visualization_settings
                }
                with open(pickle_path, 'wb') as f:
                    pickle.dump(metadata, f, protocol=pickle.HIGHEST_PROTOCOL)
                return pickle_path
            except Exception as e:
                print(f"⚠ Pickle save failed: {e}. Falling back to JSON...")
                # Fall through to JSON save
        
        # JSON fallback (or if use_pickle=False)
        json_path = output_path.replace('.pkl', '.json') if output_path.endswith('.pkl') else output_path
        if not json_path.endswith('.json'):
            json_path += '.json'
        try:
            metadata = {
                "video_path": self.video_path,
                "fps": float(self.fps) if not (math.isnan(self.fps) or math.isinf(self.fps)) else 30.0,
                "total_frames": int(self.total_frames),
                "overlays": {str(k): v for k, v in self.overlays.items()},
                "analytics": {str(k): v for k, v in self.analytics_data.items()},
                "visualization_settings": self.visualization_settings
            }
            
            # Use custom encoder to handle NaN/inf values
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False, cls=SafeJSONEncoder)
            return json_path
        except Exception as e:
            # If save fails, try with minimal data
            try:
                minimal_metadata = {
                    "video_path": str(self.video_path),
                    "fps": 30.0,
                    "total_frames": int(self.total_frames),
                    "overlays": {},
                    "analytics": {},
                    "visualization_settings": {}
                }
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(minimal_metadata, f, indent=2, ensure_ascii=False)
                print(f"⚠ Overlay metadata save error: {e}. Saved minimal metadata instead.")
                return json_path
            except Exception as e2:
                print(f"⚠ Critical: Could not save overlay metadata: {e2}")
                raise
    
    @staticmethod
    def load(metadata_path: str) -> 'OverlayMetadata':
        """
        Load overlay metadata from file (pickle or JSON).
        
        OPTIMIZATION: Automatically detects format and uses pickle if available (3-5x faster).
        
        Args:
            metadata_path: Path to metadata file (.pkl or .json)
            
        Returns:
            OverlayMetadata instance
        """
        # Try pickle first (faster)
        pickle_path = metadata_path.replace('.json', '.pkl') if metadata_path.endswith('.json') else metadata_path
        if not pickle_path.endswith('.pkl'):
            pickle_path = metadata_path + '.pkl'
        
        if os.path.exists(pickle_path):
            try:
                with open(pickle_path, 'rb') as f:
                    data = pickle.load(f)
                
                metadata = OverlayMetadata(
                    data['video_path'],
                    data['fps'],
                    data['total_frames']
                )
                
                # Pickle preserves types, so overlays are already dict[int, ...]
                metadata.overlays = data.get('overlays', {})
                metadata.analytics_data = data.get('analytics', {})
                metadata.visualization_settings = data.get('visualization_settings', {})
                
                return metadata
            except Exception as e:
                print(f"⚠ Pickle load failed: {e}. Trying JSON...")
        
        # Fallback to JSON
        json_path = metadata_path.replace('.pkl', '.json') if metadata_path.endswith('.pkl') else metadata_path
        if not json_path.endswith('.json'):
            json_path = metadata_path + '.json'
        
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"Metadata file not found: {metadata_path} (tried .pkl and .json)")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        metadata = OverlayMetadata(
            data['video_path'],
            data['fps'],
            data['total_frames']
        )
        
        metadata.overlays = {int(k): v for k, v in data.get('overlays', {}).items()}
        metadata.analytics_data = {int(k): v for k, v in data.get('analytics', {}).items()}
        metadata.visualization_settings = data.get('visualization_settings', {})
        
        return metadata


def create_player_overlay_data(track_id: int, bbox: Tuple[float, float, float, float],
                              center: Tuple[float, float], player_name: str = None,
                              team: str = None, jersey_number: str = None,
                              confidence: float = 1.0, color: Tuple[int, int, int] = None,
                              speed: float = None, distance_to_ball: float = None,
                              has_ball: bool = False, velocity: Tuple[float, float] = None,
                              direction_angle: float = None, position_history: List[Tuple[float, float]] = None) -> Dict:
    """
    Create player overlay data structure.
    
    Args:
        track_id: Track ID
        bbox: Bounding box (x1, y1, x2, y2)
        center: Center point (x, y)
        player_name: Player name (optional)
        team: Team name (optional)
        jersey_number: Jersey number (optional)
        confidence: Detection confidence
        color: BGR color tuple
        speed: Player speed (optional)
        distance_to_ball: Distance to ball (optional)
    
    Returns:
        Player overlay data dictionary
    """
    def safe_float(value):
        """Convert value to float, handling NaN, inf, and numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            fval = float(value)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        except (ValueError, TypeError, AttributeError):
            return None
    
    def safe_int(value):
        """Convert value to int, handling numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            return int(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    return {
        "track_id": safe_int(track_id),
        "bbox": [safe_float(x) for x in bbox],
        "center": [safe_float(x) for x in center],
        "player_name": player_name,
        "team": team,
        "jersey_number": jersey_number,
        "confidence": safe_float(confidence),
        "color": [safe_int(c) for c in color] if color else None,
        "speed": safe_float(speed),
        "distance_to_ball": safe_float(distance_to_ball),
        "has_ball": bool(has_ball),  # Ball possession indicator
        # ENHANCEMENT: Direction arrow and trail data
        "velocity": [safe_float(v) for v in velocity] if velocity else None,  # (vx, vy) in pixels per frame
        "direction_angle": safe_float(direction_angle),  # Angle in radians (0 = right, π/2 = down)
        "position_history": [[safe_float(p[0]), safe_float(p[1])] for p in position_history] if position_history else None  # Recent positions for trail
    }


def create_ball_overlay_data(center: Tuple[float, float], detected: bool = True,
                            trail: List[Tuple[float, float]] = None,
                            speed: float = None) -> Dict:
    """
    Create ball overlay data structure.
    
    Args:
        center: Ball center (x, y)
        detected: Whether ball was detected
        trail: List of recent ball positions
        speed: Ball speed (optional)
    
    Returns:
        Ball overlay data dictionary
    """
    def safe_float(value):
        """Convert value to float, handling NaN, inf, and numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            fval = float(value)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        except (ValueError, TypeError, AttributeError):
            return None
    
    return {
        "center": [safe_float(x) for x in center] if center else None,
        "detected": bool(detected),
        "trail": [[safe_float(x), safe_float(y)] for x, y in trail] if trail else [],
        "speed": safe_float(speed)
    }


def create_predicted_box_data(track_id: int, bbox: Tuple[float, float, float, float],
                              center: Tuple[float, float], color: Tuple[int, int, int] = None,
                              style: str = "dot", size: int = 5) -> Dict:
    """
    Create predicted box overlay data structure for lost tracks.
    
    Args:
        track_id: Track ID
        bbox: Bounding box (x1, y1, x2, y2) - last known position
        center: Center point (x, y)
        color: BGR color tuple
        style: Prediction style ("dot", "box", "cross", "x", "arrow", "diamond")
        size: Prediction marker size
    
    Returns:
        Predicted box overlay data dictionary
    """
    def safe_float(value):
        """Convert value to float, handling NaN, inf, and numpy types."""
        if value is None:
            return None
        try:
            if hasattr(value, 'dtype'):
                value = value.item()
            fval = float(value)
            if math.isnan(fval) or math.isinf(fval):
                return None
            return fval
        except (ValueError, TypeError, AttributeError):
            return None
    
    def safe_int(value):
        """Convert value to int, handling numpy types."""
        if value is None:
            return None
        try:
            if hasattr(value, 'dtype'):
                value = value.item()
            return int(value)
        except (ValueError, TypeError):
            return None
    
    return {
        "track_id": safe_int(track_id),
        "bbox": [safe_float(x) for x in bbox],
        "center": [safe_float(x) for x in center],
        "color": [safe_int(c) for c in color] if color else None,
        "style": str(style),
        "size": safe_int(size)
    }


def create_trajectory_data(track_id: int, points: List[Tuple[float, float]],
                          color: Tuple[int, int, int] = None) -> Dict:
    """
    Create trajectory data structure for player movement.
    
    Args:
        track_id: Track ID
        points: List of (x, y) positions over time
        color: Trajectory color (BGR)
    
    Returns:
        Trajectory data dictionary
    """
    def safe_float(value):
        """Convert value to float, handling numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            return float(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    def safe_int(value):
        """Convert value to int, handling numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            return int(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    return {
        "track_id": safe_int(track_id),
        "points": [[safe_float(x), safe_float(y)] for x, y in points],
        "color": [safe_int(c) for c in color] if color else None
    }


def create_field_zone_data(zone_name: str, bounds: List[Tuple[float, float]],
                          color: Tuple[int, int, int] = None) -> Dict:
    """
    Create field zone data structure.
    
    Args:
        zone_name: Zone name (e.g., "defensive", "midfield", "attacking")
        bounds: List of (x, y) points defining zone polygon
        color: Zone color (BGR)
    
    Returns:
        Field zone data dictionary
    """
    def safe_float(value):
        """Convert value to float, handling numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            return float(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    def safe_int(value):
        """Convert value to int, handling numpy types."""
        if value is None:
            return None
        try:
            # Handle numpy types explicitly using .item() for proper conversion
            if hasattr(value, 'dtype'):
                # This is a numpy scalar
                value = value.item()
            return int(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    return {
        "zone_name": zone_name,
        "bounds": [[safe_float(x), safe_float(y)] for x, y in bounds],
        "color": [safe_int(c) for c in color] if color else None
    }

