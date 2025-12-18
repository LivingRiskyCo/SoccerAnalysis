"""
Tracking Module
Handles multi-object tracking
"""

import numpy as np
from typing import List, Dict, Any, Optional
import os

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("tracker")

# Conditional imports
try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    logger.warning("Supervision not available - tracking will be limited")

# BoxMOT tracker import
try:
    from boxmot_tracker_wrapper import create_tracker
    BOXMOT_AVAILABLE = True
except ImportError:
    BOXMOT_AVAILABLE = False
    logger.warning("BoxMOT not available - will use basic tracking")


class Tracker:
    """Handles multi-object tracking"""
    
    def __init__(self, tracker_type: str = "deepocsort",
                 track_thresh: float = 0.25,
                 match_thresh: float = 0.7,  # Increased from 0.6 for better accuracy
                 track_buffer_seconds: float = 7.0,  # Increased from 5.0 for better occlusion handling
                 fps: float = 30.0,
                 use_velocity: bool = True,
                 use_appearance: bool = True):
        """
        Initialize tracker with enhanced settings for better accuracy
        
        Args:
            tracker_type: Tracker type (bytetrack, ocsort, deepocsort, etc.)
            track_thresh: Detection threshold
            match_thresh: Matching threshold (increased to 0.7 for stricter matching)
            track_buffer_seconds: Track buffer time in seconds (increased to 7.0 for better occlusion handling)
            fps: Video FPS for buffer calculation
            use_velocity: Whether to use velocity prediction (default True)
            use_appearance: Whether to use appearance features (default True, deepocsort uses this)
        """
        self.tracker_type = tracker_type
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh  # Higher = more strict matching, reduces ID switches
        self.track_buffer_seconds = track_buffer_seconds  # Longer buffer = better occlusion recovery
        self.fps = fps
        self.use_velocity = use_velocity
        self.use_appearance = use_appearance
        self.tracker = None
        
        # Ensure deepocsort is used if appearance is desired (it has built-in appearance features)
        if use_appearance and tracker_type not in ["deepocsort", "strongsort"]:
            logger.info(f"Switching to deepocsort for appearance-based tracking (requested: {tracker_type})")
            self.tracker_type = "deepocsort"
        
        self._create_tracker()
    
    def _create_tracker(self):
        """Create tracker instance"""
        try:
            if BOXMOT_AVAILABLE:
                # Calculate track buffer in frames
                track_buffer_frames = int(self.track_buffer_seconds * self.fps)
                
                self.tracker = create_tracker(
                    tracker_type=self.tracker_type,
                    track_thresh=self.track_thresh,
                    match_thresh=self.match_thresh,
                    track_buffer=track_buffer_frames
                )
                logger.info(f"Created {self.tracker_type} tracker")
            elif SUPERVISION_AVAILABLE:
                # Fallback to supervision trackers
                if self.tracker_type == "bytetrack":
                    self.tracker = sv.ByteTrack()
                elif self.tracker_type == "ocsort":
                    self.tracker = sv.OCSORT()
                else:
                    self.tracker = sv.ByteTrack()  # Default
                logger.info(f"Created {self.tracker_type} tracker (supervision)")
            else:
                logger.warning("No tracking library available")
                
        except Exception as e:
            logger.error(f"Error creating tracker: {e}", exc_info=True)
            self.tracker = None
    
    def update(self, detections: List[Dict[str, Any]], frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Update tracker with new detections
        
        Args:
            detections: List of detection dictionaries
            frame: Current frame
            
        Returns:
            List of tracked objects with track IDs
        """
        if self.tracker is None:
            return []
        
        try:
            # Convert detections to supervision format
            if SUPERVISION_AVAILABLE:
                boxes = []
                confidences = []
                class_ids = []
                
                for det in detections:
                    boxes.append(det['bbox'])
                    confidences.append(det['confidence'])
                    class_ids.append(det.get('class_id', 0))
                
                if not boxes:
                    return []
                
                detections_sv = sv.Detections(
                    xyxy=np.array(boxes),
                    confidence=np.array(confidences),
                    class_id=np.array(class_ids)
                )
                
                # Update tracker
                tracked_detections = self.tracker.update_with_detections(detections_sv)
                
                # Convert back to dictionary format
                tracks = []
                for i, track_id in enumerate(tracked_detections.tracker_id):
                    if track_id is not None:
                        tracks.append({
                            'track_id': int(track_id),
                            'bbox': tracked_detections.xyxy[i].tolist(),
                            'confidence': float(tracked_detections.confidence[i]),
                            'class_id': int(tracked_detections.class_id[i])
                        })
                
                return tracks
            else:
                # Fallback: return detections with sequential IDs
                tracks = []
                for i, det in enumerate(detections):
                    tracks.append({
                        'track_id': i + 1,
                        'bbox': det['bbox'],
                        'confidence': det['confidence'],
                        'class_id': det.get('class_id', 0)
                    })
                return tracks
                
        except Exception as e:
            logger.error(f"Error updating tracker: {e}", exc_info=True)
            return []

