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
            if detections is None:
                return
            
            # Handle supervision Detections object
            if hasattr(detections, 'xyxy') and hasattr(detections, 'tracker_id'):
                # Supervision Detections object
                if len(detections) == 0:
                    return
                
                # Extract features using reid_tracker's method
                try:
                    features = self.reid_tracker.extract_features(frame, detections, None, None)
                    
                    # Extract foot features if available
                    foot_features = None
                    if hasattr(self.reid_tracker, 'extract_foot_features'):
                        try:
                            foot_features = self.reid_tracker.extract_foot_features(frame, detections)
                        except:
                            pass
                    
                    # Store features indexed by track_id
                    if frame_num not in self.frame_reid_features:
                        self.frame_reid_features[frame_num] = {}
                    if frame_num not in self.frame_foot_features:
                        self.frame_foot_features[frame_num] = {}
                    
                    if features is not None and len(features) > 0:
                        for i, track_id in enumerate(detections.tracker_id):
                            if track_id is not None and i < len(features):
                                feature_vector = features[i]
                                # Flatten if needed
                                if isinstance(feature_vector, np.ndarray) and len(feature_vector.shape) > 1:
                                    feature_vector = feature_vector.flatten()
                                self.frame_reid_features[frame_num][track_id] = feature_vector
                    
                    if foot_features is not None and len(foot_features) > 0:
                        for i, track_id in enumerate(detections.tracker_id):
                            if track_id is not None and i < len(foot_features):
                                foot_feature_vector = foot_features[i]
                                if isinstance(foot_feature_vector, np.ndarray) and len(foot_feature_vector.shape) > 1:
                                    foot_feature_vector = foot_feature_vector.flatten()
                                self.frame_foot_features[frame_num][track_id] = foot_feature_vector
                except Exception as e:
                    print(f"Error extracting features with reid_tracker: {e}")
            else:
                # Handle bbox list format (legacy)
                if len(detections) == 0:
                    return
                
                features_dict = {}
                foot_features_dict = {}
                
                for i, bbox in enumerate(detections):
                    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        x1, y1, x2, y2 = map(int, bbox[:4])
                        track_id = i  # Use index as track_id
                        
                        # Extract Re-ID features (upper body)
                        try:
                            features = self.reid_tracker.extract_features(frame, [bbox])
                            if features is not None and len(features) > 0:
                                features_dict[track_id] = features[0]
                        except:
                            pass
                        
                        # Extract foot features (if available)
                        try:
                            if hasattr(self.reid_tracker, 'extract_foot_features'):
                                foot_features = self.reid_tracker.extract_foot_features(frame, [bbox])
                                if foot_features is not None and len(foot_features) > 0:
                                    foot_features_dict[track_id] = foot_features[0]
                        except:
                            pass
                
                # Store features
                if features_dict:
                    if frame_num not in self.frame_reid_features:
                        self.frame_reid_features[frame_num] = {}
                    self.frame_reid_features[frame_num].update(features_dict)
                if foot_features_dict:
                    if frame_num not in self.frame_foot_features:
                        self.frame_foot_features[frame_num] = {}
                    self.frame_foot_features[frame_num].update(foot_features_dict)
                
        except Exception as e:
            print(f"Error extracting Re-ID features: {e}")
            import traceback
            traceback.print_exc()
    
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

