"""
OC-SORT (Observation-Centric SORT) Tracker
A simplified implementation of OC-SORT for better occlusion handling

OC-SORT improves upon ByteTrack by:
1. Observation-centric recovery - uses observations to recover lost tracks
2. Better association during occlusions
3. More robust track management

This implementation provides a drop-in replacement for ByteTrack with better occlusion handling.
"""

import numpy as np
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Optional
import cv2

try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False
    print("Warning: supervision not available. OC-SORT will use fallback implementation.")


class OCSortTracker:
    """
    OC-SORT Tracker - Better occlusion handling than ByteTrack
    
    Key improvements:
    - Observation-centric recovery (uses detections to recover lost tracks)
    - Better association during occlusions
    - More robust track lifecycle management
    """
    
    def __init__(self,
                 track_activation_threshold=0.25,
                 minimum_matching_threshold=0.8,
                 lost_track_buffer=30,
                 min_track_length=3,
                 max_age=30,
                 iou_threshold=0.5):
        """
        Initialize OC-SORT Tracker
        
        Args:
            track_activation_threshold: Minimum confidence to start tracking
            minimum_matching_threshold: IoU threshold for matching (lower = more lenient)
            lost_track_buffer: Frames to keep lost tracks before deletion
            min_track_length: Minimum track length before confirming
            max_age: Maximum age of track before deletion
            iou_threshold: IoU threshold for association
        """
        self.track_activation_threshold = track_activation_threshold
        self.minimum_matching_threshold = minimum_matching_threshold
        self.lost_track_buffer = lost_track_buffer
        self.min_track_length = min_track_length
        self.max_age = max_age
        self.iou_threshold = iou_threshold
        
        # Track storage
        self.tracks: Dict[int, Dict] = {}  # track_id -> track info
        self.next_id = 1
        self.frame_count = 0
        
        # Track lifecycle management
        self.track_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))  # track_id -> position history
        self.track_confirmed: Dict[int, bool] = {}  # track_id -> confirmed status
        self.track_confidence_scores: Dict[int, deque] = defaultdict(lambda: deque(maxlen=10))  # track_id -> confidence history
        
        # Observation-centric recovery: store recent observations
        self.recent_observations = deque(maxlen=lost_track_buffer)  # Recent detections
        
        # Track interpolation: store gaps for interpolation
        self.track_gaps: Dict[int, List] = defaultdict(list)  # track_id -> list of gap frames
        
        print(f"✓ OC-SORT Tracker initialized")
        print(f"  Activation threshold: {track_activation_threshold}")
        print(f"  Matching threshold: {minimum_matching_threshold}")
        print(f"  Lost track buffer: {lost_track_buffer} frames")
        print(f"  Min track length: {min_track_length} frames (lifecycle management)")
    
    def update(self, detections):
        """
        Update tracker with new detections
        
        Args:
            detections: Supervision Detections object
            
        Returns:
            Detections with tracker_id assigned
        """
        self.frame_count += 1
        
        if not SUPERVISION_AVAILABLE:
            # Fallback: return detections as-is
            return detections
        
        # Extract detection boxes and confidences
        if len(detections) == 0:
            # No detections - update track ages
            self._update_track_ages()
            return detections
        
        boxes = detections.xyxy
        confidences = detections.confidence
        
        # Filter by confidence threshold
        high_conf_mask = confidences >= self.track_activation_threshold
        high_conf_boxes = boxes[high_conf_mask]
        high_conf_scores = confidences[high_conf_mask]
        
        # Store observations for recovery
        self.recent_observations.append({
            'frame': self.frame_count,
            'boxes': high_conf_boxes.copy() if len(high_conf_boxes) > 0 else np.array([]),
            'scores': high_conf_scores.copy() if len(high_conf_scores) > 0 else np.array([])
        })
        
        # Step 1: Match high-confidence detections to existing tracks
        matched_tracks, unmatched_dets, unmatched_tracks = self._associate(
            high_conf_boxes, high_conf_scores
        )
        
        # Step 2: Update matched tracks (with safety checks)
        # Filter out tracks that were removed before updating
        valid_matched_tracks = {}
        for det_idx, track_id in matched_tracks.items():
            if track_id in self.tracks:
                valid_matched_tracks[det_idx] = track_id
            else:
                # Track was removed, treat as unmatched
                unmatched_dets.append(det_idx)
        
        # Update only valid matched tracks
        for det_idx, track_id in valid_matched_tracks.items():
            box = high_conf_boxes[det_idx]
            score = high_conf_scores[det_idx]
            self._update_track(track_id, box, score, self.frame_count)
        
        # Step 3: Observation-centric recovery
        # Try to recover lost tracks using recent observations
        recovered_tracks = self._observation_centric_recovery(high_conf_boxes, high_conf_scores)
        
        # Step 4: Create new tracks for unmatched detections
        new_track_ids = {}
        for det_idx in unmatched_dets:
            if det_idx not in [r[0] for r in recovered_tracks]:
                box = high_conf_boxes[det_idx]
                score = high_conf_scores[det_idx]
                track_id = self._create_track(box, score, self.frame_count)
                new_track_ids[det_idx] = track_id
        
        # Step 5: Mark unmatched tracks as lost
        for track_id in unmatched_tracks:
            # Safety check: track might have been removed by another process
            if track_id not in self.tracks:
                continue
            self.tracks[track_id]['lost'] = True
            self.tracks[track_id]['lost_frame'] = self.frame_count
        
        # Step 6: Track lifecycle management - confirm tracks that meet minimum length
        for track_id in list(self.tracks.keys()):  # Use list() to avoid modification during iteration
            if track_id not in self.tracks:  # Safety check
                continue
            if not self.track_confirmed.get(track_id, False):
                if self.tracks[track_id]['age'] >= self.min_track_length:
                    self.track_confirmed[track_id] = True
        
        # Step 7: Remove old tracks (with lifecycle management)
        self._remove_old_tracks()
        
        # Step 8: Track interpolation - fill gaps for lost tracks
        # (This happens during observation-centric recovery, but we can also interpolate here)
        
        # Step 9: Assign tracker IDs to detections
        # Initialize all tracker IDs as None
        tracker_ids = np.full(len(detections), None, dtype=object)
        
        # Get mapping from high-conf indices to original indices
        high_conf_indices = np.where(high_conf_mask)[0] if len(high_conf_boxes) > 0 else np.array([])
        
        # Assign IDs to matched high-confidence detections
        for high_conf_idx, track_id in matched_tracks.items():
            if high_conf_idx < len(high_conf_indices):
                original_idx = high_conf_indices[high_conf_idx]
                if original_idx < len(tracker_ids):
                    tracker_ids[original_idx] = track_id
        
        # Assign IDs to recovered tracks
        for high_conf_idx, track_id in recovered_tracks:
            if high_conf_idx < len(high_conf_indices):
                original_idx = high_conf_indices[high_conf_idx]
                if original_idx < len(tracker_ids):
                    tracker_ids[original_idx] = track_id
        
        # Assign IDs to new tracks
        for high_conf_idx, track_id in new_track_ids.items():
            if high_conf_idx < len(high_conf_indices):
                original_idx = high_conf_indices[high_conf_idx]
                if original_idx < len(tracker_ids):
                    tracker_ids[original_idx] = track_id
        
        # Update detections with tracker IDs
        detections.tracker_id = tracker_ids
        
        # Step 10: Apply Track NMS to remove duplicate tracks
        detections = self._apply_track_nms(detections)
        
        return detections
    
    def _associate(self, boxes, scores):
        """
        Associate detections with existing tracks using IoU
        
        Returns:
            matched_tracks: Dict[det_idx, track_id]
            unmatched_dets: List of detection indices
            unmatched_tracks: List of track IDs
        """
        if len(boxes) == 0:
            return {}, [], list(self.tracks.keys())
        
        if len(self.tracks) == 0:
            return {}, list(range(len(boxes))), []
        
        # Get active tracks (not lost or recently lost)
        active_tracks = {
            tid: track for tid, track in self.tracks.items()
            if not track.get('lost', False) or (self.frame_count - track.get('lost_frame', 0)) < 5
        }
        
        if len(active_tracks) == 0:
            return {}, list(range(len(boxes))), []
        
        # Calculate IoU matrix
        iou_matrix = self._calculate_iou_matrix(boxes, active_tracks)
        
        # Hungarian algorithm (simplified greedy matching)
        matched_tracks = {}
        matched_det_indices = set()
        matched_track_ids = set()
        
        # Greedy matching: match highest IoU pairs first
        while True:
            max_iou = -1
            best_det_idx = None
            best_track_id = None
            
            for det_idx in range(len(boxes)):
                if det_idx in matched_det_indices:
                    continue
                
                for track_id in active_tracks.keys():
                    if track_id in matched_track_ids:
                        continue
                    
                    iou = iou_matrix[det_idx, list(active_tracks.keys()).index(track_id)]
                    if iou > max_iou and iou >= self.minimum_matching_threshold:
                        max_iou = iou
                        best_det_idx = det_idx
                        best_track_id = track_id
            
            if best_det_idx is None or best_track_id is None:
                break
            
            matched_tracks[best_det_idx] = best_track_id
            matched_det_indices.add(best_det_idx)
            matched_track_ids.add(best_track_id)
        
        unmatched_dets = [i for i in range(len(boxes)) if i not in matched_det_indices]
        unmatched_tracks = [tid for tid in active_tracks.keys() if tid not in matched_track_ids]
        
        return matched_tracks, unmatched_dets, unmatched_tracks
    
    def _calculate_iou_matrix(self, boxes, tracks):
        """Calculate IoU matrix between detections and tracks"""
        iou_matrix = np.zeros((len(boxes), len(tracks)))
        
        track_list = list(tracks.keys())
        for i, box in enumerate(boxes):
            for j, track_id in enumerate(track_list):
                # Safety check: ensure track_id exists in self.tracks before accessing
                # Track might have been removed between active_tracks creation and this call
                if track_id not in self.tracks:
                    iou_matrix[i, j] = 0.0
                    continue
                track_box = self.tracks[track_id]['box']
                iou_matrix[i, j] = self._calculate_iou(box, track_box)
        
        return iou_matrix
    
    def _calculate_iou(self, box1, box2):
        """Calculate IoU between two boxes"""
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        
        # Calculate intersection
        inter_x_min = max(x1_min, x2_min)
        inter_y_min = max(y1_min, y2_min)
        inter_x_max = min(x1_max, x2_max)
        inter_y_max = min(y1_max, y2_max)
        
        if inter_x_max < inter_x_min or inter_y_max < inter_y_min:
            return 0.0
        
        inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
        
        # Calculate union
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        union_area = box1_area + box2_area - inter_area
        
        if union_area == 0:
            return 0.0
        
        return inter_area / union_area
    
    def _observation_centric_recovery(self, boxes, scores):
        """
        Observation-centric recovery: use recent observations to recover lost tracks
        
        This is the key improvement of OC-SORT over ByteTrack
        """
        recovered = []
        
        if len(self.recent_observations) < 2:
            return recovered
        
        # Get lost tracks that might be recoverable
        lost_tracks = {
            tid: track for tid, track in self.tracks.items()
            if track.get('lost', False) and 
            (self.frame_count - track.get('lost_frame', 0)) <= self.lost_track_buffer
        }
        
        if len(lost_tracks) == 0 or len(boxes) == 0:
            return recovered
        
        # Try to match detections to lost tracks using observation history
        for track_id, track in lost_tracks.items():
            # Get track's last known position
            last_box = track['box']
            
            # Find best matching detection
            best_iou = 0
            best_det_idx = None
            
            for det_idx, box in enumerate(boxes):
                iou = self._calculate_iou(box, last_box)
                if iou > best_iou and iou >= self.minimum_matching_threshold * 0.7:  # More lenient for recovery
                    best_iou = iou
                    best_det_idx = det_idx
            
            if best_det_idx is not None:
                # Recover this track - safety check: track might have been removed
                if track_id not in self.tracks:
                    continue
                self.tracks[track_id]['lost'] = False
                self.tracks[track_id]['lost_frame'] = None
                self._update_track(track_id, boxes[best_det_idx], scores[best_det_idx], self.frame_count)
                recovered.append((best_det_idx, track_id))
        
        return recovered
    
    def _create_track(self, box, score, frame):
        """Create a new track with lifecycle management"""
        track_id = self.next_id
        self.next_id += 1
        
        # Calculate center
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        
        self.tracks[track_id] = {
            'box': box.copy(),
            'center': center,
            'score': score,
            'age': 1,
            'time_since_update': 0,
            'lost': False,
            'lost_frame': None,
            'first_frame': frame,
            'last_frame': frame
        }
        
        # Initialize track history and confidence
        self.track_history[track_id].append((center[0], center[1], frame))
        self.track_confidence_scores[track_id].append(score)
        self.track_confirmed[track_id] = False  # Not confirmed until min_track_length
        
        return track_id
    
    def _update_track(self, track_id, box, score, frame):
        """Update an existing track with history tracking"""
        if track_id not in self.tracks:
            return
        
        center = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        
        # Check for gap and interpolate if needed
        if track_id in self.track_history and len(self.track_history[track_id]) > 0:
            last_pos = self.track_history[track_id][-1]
            last_frame = last_pos[2] if len(last_pos) > 2 else frame - 1
            gap_size = frame - last_frame
            
            # If there's a gap, interpolate intermediate positions
            if gap_size > 1 and gap_size <= self.lost_track_buffer // 2:
                # Interpolate gap frames
                for gap_frame in range(last_frame + 1, frame):
                    interpolated = self._interpolate_track_gaps(track_id, gap_frame)
                    if interpolated:
                        self.track_history[track_id].append((interpolated[0], interpolated[1], gap_frame))
        
        # Safety check: track might have been removed during gap interpolation
        if track_id not in self.tracks:
            return
        
        self.tracks[track_id]['box'] = box.copy()
        self.tracks[track_id]['center'] = center
        self.tracks[track_id]['score'] = score
        self.tracks[track_id]['age'] += 1
        self.tracks[track_id]['time_since_update'] = 0
        self.tracks[track_id]['lost'] = False
        self.tracks[track_id]['lost_frame'] = None
        self.tracks[track_id]['last_frame'] = frame
        
        # Update history and confidence
        if track_id in self.track_history:
            self.track_history[track_id].append((center[0], center[1], frame))
        if track_id in self.track_confidence_scores:
            self.track_confidence_scores[track_id].append(score)
    
    def _update_track_ages(self):
        """Update ages of all tracks when no detections"""
        for track_id in list(self.tracks.keys()):  # Use list() to avoid modification during iteration
            if track_id not in self.tracks:  # Safety check
                continue
            self.tracks[track_id]['time_since_update'] += 1
            self.tracks[track_id]['age'] += 1
    
    def _remove_old_tracks(self):
        """Remove tracks that are too old or lost for too long (with lifecycle management)"""
        tracks_to_remove = []
        
        for track_id, track in self.tracks.items():
            # Track lifecycle management: remove unconfirmed tracks that are too short
            # Only remove if track is old enough to have been confirmed but hasn't been
            # (i.e., age >= min_track_length but still not confirmed - likely false positive)
            if not self.track_confirmed.get(track_id, False):
                if track['age'] >= max(5, self.min_track_length):
                    # Track is old enough to be confirmed but isn't - likely false positive
                    tracks_to_remove.append(track_id)
                    continue
            
            # Remove if lost for too long
            if track.get('lost', False):
                lost_frames = self.frame_count - track.get('lost_frame', self.frame_count)
                if lost_frames > self.lost_track_buffer:
                    tracks_to_remove.append(track_id)
            
            # Remove if too old
            if track['age'] > self.max_age:
                tracks_to_remove.append(track_id)
        
        for track_id in tracks_to_remove:
            del self.tracks[track_id]
            if track_id in self.track_history:
                del self.track_history[track_id]
            if track_id in self.track_confirmed:
                del self.track_confirmed[track_id]
            if track_id in self.track_confidence_scores:
                del self.track_confidence_scores[track_id]
            if track_id in self.track_gaps:
                del self.track_gaps[track_id]
    
    def _interpolate_track_gaps(self, track_id, current_frame):
        """
        Interpolate positions for gaps in track (when detection was temporarily lost)
        
        Args:
            track_id: Track ID to interpolate
            current_frame: Current frame number
            
        Returns:
            Interpolated position (x, y) or None if interpolation not possible
        """
        if track_id not in self.track_history or len(self.track_history[track_id]) < 2:
            return None
        
        history = list(self.track_history[track_id])
        if len(history) < 2:
            return None
        
        # Get last known position
        last_pos = history[-1]
        last_frame = last_pos[2] if len(last_pos) > 2 else current_frame - 1
        
        # Check if there's a gap
        gap_size = current_frame - last_frame
        if gap_size <= 1:
            return None  # No gap or very small gap
        
        # If gap is too large, don't interpolate (likely different object)
        if gap_size > self.lost_track_buffer // 2:
            return None
        
        # Use linear interpolation based on velocity
        if len(history) >= 2:
            # Calculate velocity from last two positions
            prev_pos = history[-2]
            vx = (last_pos[0] - prev_pos[0]) / max(1, last_pos[2] - prev_pos[2]) if len(last_pos) > 2 and len(prev_pos) > 2 else 0
            vy = (last_pos[1] - prev_pos[1]) / max(1, last_pos[2] - prev_pos[2]) if len(last_pos) > 2 and len(prev_pos) > 2 else 0
            
            # Predict position
            predicted_x = last_pos[0] + vx * gap_size
            predicted_y = last_pos[1] + vy * gap_size
            
            return (predicted_x, predicted_y)
        
        return None
    
    def _apply_track_nms(self, detections):
        """
        Apply Non-Maximum Suppression to remove duplicate tracks
        
        This removes tracks that are tracking the same player (high IoU overlap)
        
        Args:
            detections: Supervision Detections object
            
        Returns:
            Detections with duplicate tracks removed
        """
        if len(detections) < 2:
            return detections
        
        # Get all active track IDs and their boxes
        active_tracks = {}
        for i, track_id in enumerate(detections.tracker_id):
            if track_id is not None:
                if track_id not in active_tracks:
                    active_tracks[track_id] = []
                active_tracks[track_id].append(i)
        
        # Find duplicate tracks (tracks with high IoU overlap)
        tracks_to_remove = set()
        track_ids_list = list(active_tracks.keys())
        
        for i, tid1 in enumerate(track_ids_list):
            if tid1 in tracks_to_remove:
                continue
            
            indices1 = active_tracks[tid1]
            if len(indices1) == 0:
                continue
            
            box1 = detections.xyxy[indices1[0]]
            
            for tid2 in track_ids_list[i+1:]:
                if tid2 in tracks_to_remove:
                    continue
                
                indices2 = active_tracks[tid2]
                if len(indices2) == 0:
                    continue
                
                box2 = detections.xyxy[indices2[0]]
                
                # Calculate IoU
                iou = self._calculate_iou(box1, box2)
                
                # If IoU is very high (>0.9), they're likely the same player
                if iou > 0.9:
                    # Keep the track with higher confidence or longer history
                    conf1 = detections.confidence[indices1[0]]
                    conf2 = detections.confidence[indices2[0]]
                    
                    age1 = self.tracks.get(tid1, {}).get('age', 0)
                    age2 = self.tracks.get(tid2, {}).get('age', 0)
                    
                    # Remove the track with lower confidence or shorter history
                    if conf1 < conf2 or (conf1 == conf2 and age1 < age2):
                        tracks_to_remove.add(tid1)
                    else:
                        tracks_to_remove.add(tid2)
        
        # Remove duplicate tracks from detections
        if tracks_to_remove:
            mask = np.array([tid not in tracks_to_remove if tid is not None else True for tid in detections.tracker_id])
            # Filter detections
            detections.xyxy = detections.xyxy[mask]
            detections.confidence = detections.confidence[mask]
            detections.tracker_id = detections.tracker_id[mask]
            if hasattr(detections, 'class_id') and detections.class_id is not None:
                detections.class_id = detections.class_id[mask]
        
        return detections

