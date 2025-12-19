"""
Identity Tracker: Comprehensive system for tracking player identity across track ID changes
This ensures that anchor frame assignments persist even when track IDs change
"""

import numpy as np
from collections import deque
from typing import Dict, Tuple, Optional, List

class IdentityTracker:
    """
    Tracks player identity across track ID changes using bbox position matching.
    This ensures anchor frame assignments persist even when the tracker assigns new IDs.
    """
    
    def __init__(self, position_tolerance_px: float = 200.0, iou_threshold: float = 0.3):
        """
        Initialize identity tracker.
        
        Args:
            position_tolerance_px: Maximum distance (pixels) to consider a match
            iou_threshold: Minimum IoU to consider a match
        """
        self.position_tolerance_px = position_tolerance_px
        self.iou_threshold = iou_threshold
        
        # Track identity assignments: track_id -> (player_name, confidence, frame_assigned, bbox)
        self.track_identity: Dict[int, Tuple[str, float, int, List[float]]] = {}
        
        # Track bbox history for each track: track_id -> deque of (frame, bbox)
        self.track_bbox_history: Dict[int, deque] = {}
        
        # Track player position history: player_name -> deque of (frame, bbox, track_id)
        self.player_position_history: Dict[str, deque] = {}
        
        # Maximum history length
        self.max_history = 30  # Keep last 30 frames
        
    def update_track(self, track_id: int, bbox: List[float], frame_num: int):
        """
        Update bbox history for a track.
        
        Args:
            track_id: Track ID
            bbox: Bounding box [x1, y1, x2, y2]
            frame_num: Current frame number
        """
        if track_id not in self.track_bbox_history:
            self.track_bbox_history[track_id] = deque(maxlen=self.max_history)
        self.track_bbox_history[track_id].append((frame_num, bbox))
    
    def assign_identity(self, track_id: int, player_name: str, confidence: float, 
                       frame_num: int, bbox: List[float]):
        """
        Assign identity to a track (from anchor frame or Re-ID).
        
        Args:
            track_id: Track ID
            player_name: Player name
            confidence: Confidence score (1.00 for anchor frames)
            frame_num: Frame number where assignment occurred
            bbox: Bounding box at assignment time
        """
        self.track_identity[track_id] = (player_name, confidence, frame_num, bbox)
        
        # Update player position history
        if player_name not in self.player_position_history:
            self.player_position_history[player_name] = deque(maxlen=self.max_history)
        self.player_position_history[player_name].append((frame_num, bbox, track_id))
    
    def find_player_by_position(self, bbox: List[float], frame_num: int, 
                               exclude_track_ids: Optional[List[int]] = None) -> Optional[Tuple[int, str, float]]:
        """
        Find a player by bbox position (for reconnection when track ID changes).
        
        Args:
            bbox: Current bounding box [x1, y1, x2, y2]
            frame_num: Current frame number
            exclude_track_ids: Track IDs to exclude from matching
            
        Returns:
            (track_id, player_name, confidence) if match found, None otherwise
        """
        if exclude_track_ids is None:
            exclude_track_ids = []
        
        best_match = None
        best_score = 0.0
        
        bbox_center_x = (bbox[0] + bbox[2]) / 2
        bbox_center_y = (bbox[1] + bbox[3]) / 2
        bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        
        # Check all tracks with assigned identities
        for track_id, (player_name, confidence, assign_frame, assign_bbox) in self.track_identity.items():
            if track_id in exclude_track_ids:
                continue
            
            # Get most recent bbox for this track
            if track_id in self.track_bbox_history and len(self.track_bbox_history[track_id]) > 0:
                last_frame, last_bbox = self.track_bbox_history[track_id][-1]
                
                # Calculate distance
                last_center_x = (last_bbox[0] + last_bbox[2]) / 2
                last_center_y = (last_bbox[1] + last_bbox[3]) / 2
                distance = np.sqrt((bbox_center_x - last_center_x)**2 + (bbox_center_y - last_center_y)**2)
                
                # Calculate IoU
                iou = self._calculate_iou(bbox, last_bbox)
                
                # Score based on distance and IoU
                if distance < self.position_tolerance_px and iou > self.iou_threshold:
                    # Weighted score: IoU is more important than distance
                    score = iou * 0.7 + (1.0 - min(distance / self.position_tolerance_px, 1.0)) * 0.3
                    
                    if score > best_score:
                        best_score = score
                        best_match = (track_id, player_name, confidence)
        
        return best_match
    
    def get_identity(self, track_id: int) -> Optional[Tuple[str, float, int]]:
        """
        Get identity for a track.
        
        Args:
            track_id: Track ID
            
        Returns:
            (player_name, confidence, frame_assigned) if found, None otherwise
        """
        if track_id in self.track_identity:
            player_name, confidence, frame_num, _ = self.track_identity[track_id]
            return (player_name, confidence, frame_num)
        return None
    
    def clear_inactive_tracks(self, active_track_ids: List[int], frame_num: int):
        """
        Clear identity for tracks that are no longer active.
        
        Args:
            active_track_ids: List of currently active track IDs
            frame_num: Current frame number
        """
        active_set = set(active_track_ids)
        tracks_to_clear = []
        
        for track_id in self.track_identity:
            if track_id not in active_set:
                tracks_to_clear.append(track_id)
        
        for track_id in tracks_to_clear:
            del self.track_identity[track_id]
            if track_id in self.track_bbox_history:
                del self.track_bbox_history[track_id]
    
    def _calculate_iou(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate Intersection over Union (IoU) between two bboxes."""
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2
        
        # Calculate intersection
        inter_x1 = max(x1_1, x1_2)
        inter_y1 = max(y1_1, y1_2)
        inter_x2 = min(x2_1, x2_2)
        inter_y2 = min(y2_1, y2_2)
        
        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return 0.0
        
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        
        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - inter_area
        
        if union_area <= 0:
            return 0.0
        
        return inter_area / union_area

