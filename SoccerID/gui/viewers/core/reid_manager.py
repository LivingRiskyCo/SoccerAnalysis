"""
Re-ID Manager - Handles Re-ID feature extraction and matching
Shared across all viewer modes
"""

from typing import Optional, Dict, List, Tuple
import numpy as np
import sys
import os
from pathlib import Path

# Try to import Re-ID tracker
REID_AVAILABLE = False
try:
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent  # SoccerID -> soccer_analysis
    reid_path = os.path.join(parent_dir, 'reid_tracker.py')
    if os.path.exists(reid_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("reid_tracker", reid_path)
        reid_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reid_module)
        ReIDTracker = reid_module.ReIDTracker
        REID_AVAILABLE = True
    else:
        from reid_tracker import ReIDTracker
        REID_AVAILABLE = True
except ImportError:
    pass


class ReIDManager:
    """Manages Re-ID feature extraction and matching"""
    
    def __init__(self):
        self.reid_tracker = None
        self.frame_reid_features = {}  # frame_num -> {track_id: features}
        self.frame_foot_features = {}  # frame_num -> {track_id: foot_features}
        self.initialized = False
        
    def initialize(self):
        """Initialize Re-ID tracker"""
        if not REID_AVAILABLE:
            print("Warning: Re-ID tracker not available")
            return False
        
        try:
            self.reid_tracker = ReIDTracker()
            self.initialized = True
            print("✓ Re-ID tracker initialized")
            return True
        except Exception as e:
            print(f"Warning: Could not initialize Re-ID tracker: {e}")
            return False
    
    def extract_features(self, frame: np.ndarray, detections, frame_num: int):
        """Extract Re-ID features for detections in a frame"""
        if not self.initialized or self.reid_tracker is None:
            return
        
        try:
            if detections is None or len(detections) == 0:
                return
            
            # Extract features for each detection
            features_dict = {}
            foot_features_dict = {}
            
            for i, (xyxy, track_id) in enumerate(zip(detections.xyxy, detections.tracker_id)):
                if track_id is None:
                    continue
                
                # Extract bounding box
                x1, y1, x2, y2 = map(int, xyxy)
                bbox = [x1, y1, x2, y2]
                
                # Extract Re-ID features (upper body)
                try:
                    features = self.reid_tracker.extract_features(frame, bbox)
                    if features is not None:
                        features_dict[track_id] = features
                except:
                    pass
                
                # Extract foot features (if available)
                try:
                    if hasattr(self.reid_tracker, 'extract_foot_features'):
                        foot_features = self.reid_tracker.extract_foot_features(frame, bbox)
                        if foot_features is not None:
                            foot_features_dict[track_id] = foot_features
                except:
                    pass
            
            # Store features
            if features_dict:
                self.frame_reid_features[frame_num] = features_dict
            if foot_features_dict:
                self.frame_foot_features[frame_num] = foot_features_dict
                
        except Exception as e:
            print(f"Error extracting Re-ID features: {e}")
    
    def get_features(self, frame_num: int, track_id: int) -> Optional[np.ndarray]:
        """Get Re-ID features for a track at a frame"""
        if frame_num in self.frame_reid_features:
            return self.frame_reid_features[frame_num].get(track_id)
        return None
    
    def get_foot_features(self, frame_num: int, track_id: int) -> Optional[np.ndarray]:
        """Get foot features for a track at a frame"""
        if frame_num in self.frame_foot_features:
            return self.frame_foot_features[frame_num].get(track_id)
        return None
    
    def clear_features(self):
        """Clear all stored features"""
        self.frame_reid_features.clear()
        self.frame_foot_features.clear()
    
    def is_initialized(self) -> bool:
        """Check if Re-ID is initialized"""
        return self.initialized

