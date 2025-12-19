"""
Detection Manager - Handles YOLO detection and tracking
Shared across all viewer modes
"""

import cv2
import numpy as np
from typing import Optional, Dict, List
import os
import sys
from pathlib import Path

# Try to import YOLO and supervision
YOLO_AVAILABLE = False
SUPERVISION_AVAILABLE = False
try:
    from ultralytics import YOLO
    import supervision as sv
    YOLO_AVAILABLE = True
    SUPERVISION_AVAILABLE = True
except ImportError:
    pass

# Try to import OC-SORT tracker
OCSORT_AVAILABLE = False
try:
    # Try multiple import paths
    current_file = Path(__file__).resolve()
    parent_dir = current_file.parent.parent.parent.parent  # SoccerID -> soccer_analysis
    ocsort_path = os.path.join(parent_dir, 'ocsort_tracker.py')
    if os.path.exists(ocsort_path):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ocsort_tracker", ocsort_path)
        ocsort_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ocsort_module)
        OCSortTracker = ocsort_module.OCSortTracker
        OCSORT_AVAILABLE = True
    else:
        from ocsort_tracker import OCSortTracker
        OCSORT_AVAILABLE = True
except ImportError:
    pass


class DetectionManager:
    """Manages YOLO detection and tracking"""
    
    def __init__(self):
        self.model = None
        self.tracker = None
        self.detections_history = {}  # frame_num -> detections
        self.initialized = False
        
    def initialize(self, model_path: str = 'yolo11n.pt'):
        """Initialize YOLO model and tracker"""
        if not YOLO_AVAILABLE or not SUPERVISION_AVAILABLE:
            print("Warning: YOLO/supervision not available")
            return False
        
        try:
            # Try YOLOv11 first, fallback to YOLOv8
            try:
                self.model = YOLO(model_path)
                print(f"✓ YOLO model loaded: {model_path}")
            except:
                self.model = YOLO('yolov8n.pt')
                print("✓ YOLOv8 loaded (fallback)")
            
            # Initialize tracker - prefer OC-SORT
            if OCSORT_AVAILABLE:
                self.tracker = OCSortTracker(
                    track_activation_threshold=0.20,
                    minimum_matching_threshold=0.8,
                    lost_track_buffer=50,
                    min_track_length=3,
                    max_age=150,
                    iou_threshold=0.8
                )
                print("✓ OC-SORT tracker initialized")
            else:
                self.tracker = sv.ByteTrack(
                    track_activation_threshold=0.20,
                    minimum_matching_threshold=0.8,
                    lost_track_buffer=50
                )
                print("✓ ByteTrack tracker initialized (OC-SORT not available)")
            
            self.initialized = True
            return True
        except Exception as e:
            print(f"Error initializing detection: {e}")
            return False
    
    def detect_frame(self, frame: np.ndarray, frame_num: int, classes: List[int] = [0]) -> Optional:
        """Run detection on a frame and update tracker"""
        if not self.initialized or self.model is None:
            return None
        
        try:
            # Run YOLO detection
            results = self.model(frame, classes=classes, verbose=False)
            detections = sv.Detections.from_ultralytics(results[0])
            
            # Update tracker
            if self.tracker:
                if hasattr(self.tracker, 'update_with_detections'):
                    detections = self.tracker.update_with_detections(detections)
                else:
                    detections = self.tracker.update(detections)
            
            # Store in history
            self.detections_history[frame_num] = detections
            
            return detections
        except Exception as e:
            print(f"Error detecting frame {frame_num}: {e}")
            return None
    
    def get_detections(self, frame_num: int) -> Optional:
        """Get detections for a frame (from history or detect on demand)"""
        if frame_num in self.detections_history:
            return self.detections_history[frame_num]
        return None
    
    def clear_history(self):
        """Clear detection history"""
        self.detections_history.clear()
    
    def is_initialized(self) -> bool:
        """Check if detection is initialized"""
        return self.initialized

