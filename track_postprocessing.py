"""
Track Post-Processing Utilities
- Track interpolation: Fill gaps when detection is temporarily lost
- Track NMS: Remove duplicate tracks tracking the same player
- Enhanced occlusion recovery with motion prediction
- Works with both ByteTrack and OC-SORT
"""

import numpy as np
from collections import defaultdict, deque
from typing import Dict, Tuple

try:
    import supervision as sv
    SUPERVISION_AVAILABLE = True
except ImportError:
    SUPERVISION_AVAILABLE = False


class TrackPostProcessor:
    """
    Post-processing utilities for track smoothing and cleanup
    Works with any tracker (ByteTrack, OC-SORT, etc.)
    Enhanced with motion prediction for occlusion recovery
    """
    
    def __init__(self, max_gap_frames=10, nms_iou_threshold=0.9, 
                 occlusion_recovery_seconds=3.0, occlusion_recovery_distance=250, fps=30.0):
        """
        Initialize post-processor
        
        Args:
            max_gap_frames: Maximum gap size to interpolate (default: 10 frames)
            nms_iou_threshold: IoU threshold for NMS (default: 0.9, very high overlap)
            occlusion_recovery_seconds: Maximum time (seconds) to recover lost tracks (default: 3.0s)
            occlusion_recovery_distance: Maximum pixel distance for recovery (default: 250px)
            fps: Video frame rate for time-based calculations (default: 30.0)
        """
        self.max_gap_frames = max_gap_frames
        self.nms_iou_threshold = nms_iou_threshold
        self.occlusion_recovery_frames = int(occlusion_recovery_seconds * fps)
        self.occlusion_recovery_distance = occlusion_recovery_distance
        self.fps = fps
        
        # Track history for interpolation
        self.track_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        self.track_last_frame: Dict[int, int] = {}  # track_id -> last frame seen
        self.track_last_position: Dict[int, Tuple[float, float]] = {}  # track_id -> (x, y) last position
        self.track_last_bbox: Dict[int, Tuple[float, float, float, float]] = {}  # track_id -> (x1, y1, x2, y2) last bbox
        self.track_velocity: Dict[int, Tuple[float, float]] = {}  # track_id -> (dx, dy) velocity in pixels/frame
        self.track_bbox_size: Dict[int, Tuple[float, float]] = {}  # track_id -> (width, height) last bbox size
        self.track_id_mapping: Dict[int, int] = {}  # Map new track IDs to older ones for merging across frames
        
        # Lost tracks with predicted positions
        self.lost_tracks: Dict[int, Dict] = {}  # track_id -> {last_frame, last_pos, velocity, bbox_size, predicted_positions}
        
        print(f"✓ Track Post-Processor initialized")
        print(f"  Max gap for interpolation: {max_gap_frames} frames")
        print(f"  NMS IoU threshold: {nms_iou_threshold}")
        print(f"  Occlusion recovery: {occlusion_recovery_seconds}s ({self.occlusion_recovery_frames} frames)")
        print(f"  Recovery distance: {occlusion_recovery_distance}px")
    
    def interpolate_tracks(self, detections, current_frame):
        """
        Interpolate positions for tracks with gaps
        
        Args:
            detections: Supervision Detections object
            current_frame: Current frame number
            
        Returns:
            Detections with interpolated positions added (if gaps detected)
        """
        if not SUPERVISION_AVAILABLE or len(detections) == 0:
            return detections
        
        # Update track history and velocity
        current_track_ids = set()
        for i, track_id in enumerate(detections.tracker_id):
            if track_id is not None:
                current_track_ids.add(track_id)
                bbox = detections.xyxy[i]
                center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
                bbox_size = (bbox[2] - bbox[0], bbox[3] - bbox[1])  # (width, height)
                
                # Calculate velocity if we have previous position
                if track_id in self.track_last_frame and track_id in self.track_last_position:
                    prev_frame = self.track_last_frame[track_id]
                    prev_pos = self.track_last_position[track_id]
                    frames_diff = current_frame - prev_frame
                    
                    if frames_diff > 0:
                        # Calculate velocity (pixels per frame)
                        dx = (center[0] - prev_pos[0]) / frames_diff
                        dy = (center[1] - prev_pos[1]) / frames_diff
                        self.track_velocity[track_id] = (dx, dy)
                
                # Update history
                self.track_history[track_id].append((center[0], center[1], current_frame))
                self.track_last_frame[track_id] = current_frame
                self.track_last_position[track_id] = (center[0], center[1])
                self.track_last_bbox[track_id] = tuple(bbox)
                self.track_bbox_size[track_id] = bbox_size
                
                # Remove from lost tracks if it was lost
                if track_id in self.lost_tracks:
                    del self.lost_tracks[track_id]
        
        # Update lost tracks and predict positions
        self._update_lost_tracks(current_frame, current_track_ids)
        
        return detections
    
    def _update_lost_tracks(self, current_frame, active_track_ids):
        """Update lost tracks and predict their positions"""
        # Find tracks that were active but are now lost
        for track_id in list(self.track_last_frame.keys()):
            if track_id not in active_track_ids and track_id not in self.lost_tracks:
                # Track was just lost - initialize lost track entry
                if track_id in self.track_last_position and track_id in self.track_last_bbox:
                    velocity = self.track_velocity.get(track_id, (0.0, 0.0))
                    bbox_size = self.track_bbox_size.get(track_id, (50.0, 100.0))
                    
                    self.lost_tracks[track_id] = {
                        'last_frame': self.track_last_frame[track_id],
                        'last_position': self.track_last_position[track_id],
                        'last_bbox': self.track_last_bbox[track_id],
                        'velocity': velocity,
                        'bbox_size': bbox_size,
                        'predicted_positions': {}
                    }
        
        # Update predicted positions for lost tracks
        for track_id, lost_data in list(self.lost_tracks.items()):
            frames_since_lost = current_frame - lost_data['last_frame']
            
            # Remove if too old
            if frames_since_lost > self.occlusion_recovery_frames:
                del self.lost_tracks[track_id]
                continue
            
            # Predict position based on velocity
            velocity = lost_data['velocity']
            last_pos = lost_data['last_position']
            predicted_x = last_pos[0] + velocity[0] * frames_since_lost
            predicted_y = last_pos[1] + velocity[1] * frames_since_lost
            
            lost_data['predicted_positions'][current_frame] = (predicted_x, predicted_y)
    
    def apply_track_nms(self, detections, current_frame=None):
        """
        Apply Non-Maximum Suppression to remove duplicate tracks
        
        Removes tracks that are tracking the same player (high IoU overlap or close position)
        
        Args:
            detections: Supervision Detections object
            current_frame: Current frame number (optional, for cross-frame merging)
            
        Returns:
            Detections with duplicate tracks removed (keeps older track IDs)
        """
        if not SUPERVISION_AVAILABLE or len(detections) < 2:
            return detections
        
        # Group detections by track ID
        track_groups = defaultdict(list)
        for i, track_id in enumerate(detections.tracker_id):
            if track_id is not None:
                track_groups[track_id].append(i)
        
        # Enhanced occlusion recovery: Check if any new tracks should be merged with recently lost tracks
        # Uses motion prediction and bbox size consistency
        current_track_ids = set(track_groups.keys())
        for new_tid in current_track_ids:
            if new_tid in self.track_id_mapping:
                # This track was already mapped to an older ID, skip
                continue
            
            indices = track_groups[new_tid]
            if len(indices) == 0:
                continue
            
            new_box = detections.xyxy[indices[0]]
            new_center = ((new_box[0] + new_box[2]) / 2, (new_box[1] + new_box[3]) / 2)
            new_box_size = (new_box[2] - new_box[0], new_box[3] - new_box[1])  # (width, height)
            new_box_area = new_box_size[0] * new_box_size[1]
            
            best_match = None
            best_match_score = 0.0
            
            # Check against lost tracks with motion prediction
            for old_tid, lost_data in list(self.lost_tracks.items()):
                if old_tid in current_track_ids:
                    continue  # Old track is still active
                
                frames_since_lost = current_frame - lost_data['last_frame']
                if frames_since_lost > self.occlusion_recovery_frames:
                    continue  # Too old to recover
                
                # Get predicted position for this frame
                predicted_pos = lost_data['predicted_positions'].get(current_frame)
                if predicted_pos is None:
                    # Calculate predicted position
                    velocity = lost_data['velocity']
                    last_pos = lost_data['last_position']
                    predicted_pos = (
                        last_pos[0] + velocity[0] * frames_since_lost,
                        last_pos[1] + velocity[1] * frames_since_lost
                    )
                
                # Calculate distance to predicted position
                distance_to_predicted = np.sqrt(
                    (new_center[0] - predicted_pos[0])**2 + 
                    (new_center[1] - predicted_pos[1])**2
                )
                
                # Also check distance to last known position (fallback)
                last_pos = lost_data['last_position']
                distance_to_last = np.sqrt(
                    (new_center[0] - last_pos[0])**2 + 
                    (new_center[1] - last_pos[1])**2
                )
                
                # Use the minimum distance (predicted or last)
                distance = min(distance_to_predicted, distance_to_last)
                
                # Check bbox size consistency
                old_bbox_size = lost_data['bbox_size']
                old_box_area = old_bbox_size[0] * old_bbox_size[1]
                size_ratio = min(new_box_area, old_box_area) / max(new_box_area, old_box_area) if max(new_box_area, old_box_area) > 0 else 0
                
                # Calculate match score (lower distance and higher size ratio = better match)
                # Normalize distance by box size
                avg_box_size = np.sqrt((new_box_size[0] + new_box_size[1]) / 2)
                normalized_distance = distance / max(avg_box_size, 1.0)
                
                # Match if:
                # 1. Distance is within recovery threshold AND size is similar (> 60%)
                # 2. OR distance is very close (< 30% of box size) regardless of size
                if (distance <= self.occlusion_recovery_distance and size_ratio > 0.6) or \
                   (normalized_distance < 0.3 and size_ratio > 0.4):
                    # Calculate match score (higher is better)
                    match_score = size_ratio * (1.0 / (1.0 + normalized_distance))
                    
                    if match_score > best_match_score:
                        best_match = old_tid
                        best_match_score = match_score
            
            # If we found a good match, merge the tracks
            if best_match is not None and best_match_score > 0.3 and current_frame is not None:  # Minimum confidence threshold
                old_tid = best_match
                # Map new track to old track ID
                self.track_id_mapping[new_tid] = old_tid
                # Update the new track's ID in detections
                for idx in indices:
                    detections.tracker_id[idx] = old_tid
                # Update track history to reflect the merge
                if old_tid in self.track_history:
                    self.track_history[old_tid].append((new_center[0], new_center[1], current_frame))
                self.track_last_frame[old_tid] = current_frame
                self.track_last_position[old_tid] = (new_center[0], new_center[1])
                self.track_last_bbox[old_tid] = tuple(new_box)
                self.track_bbox_size[old_tid] = new_box_size
                # Remove from lost tracks
                if old_tid in self.lost_tracks:
                    del self.lost_tracks[old_tid]
                # Rebuild track_groups since we changed IDs
                track_groups = defaultdict(list)
                for i, track_id in enumerate(detections.tracker_id):
                    if track_id is not None:
                        track_groups[track_id].append(i)
                current_track_ids = set(track_groups.keys())
        
        # Find duplicate tracks (tracks with high IoU overlap or very close positions)
        tracks_to_remove = set()
        track_ids_list = list(track_groups.keys())
        
        for i, tid1 in enumerate(track_ids_list):
            if tid1 in tracks_to_remove:
                continue
            
            indices1 = track_groups[tid1]
            if len(indices1) == 0:
                continue
            
            box1 = detections.xyxy[indices1[0]]
            conf1 = detections.confidence[indices1[0]]
            age1 = len(self.track_history.get(tid1, []))
            center1 = ((box1[0] + box1[2]) / 2, (box1[1] + box1[3]) / 2)
            
            for tid2 in track_ids_list[i+1:]:
                if tid2 in tracks_to_remove:
                    continue
                
                indices2 = track_groups[tid2]
                if len(indices2) == 0:
                    continue
                
                box2 = detections.xyxy[indices2[0]]
                conf2 = detections.confidence[indices2[0]]
                age2 = len(self.track_history.get(tid2, []))
                center2 = ((box2[0] + box2[2]) / 2, (box2[1] + box2[3]) / 2)
                
                # Calculate IoU
                iou = self._calculate_iou(box1, box2)
                
                # Calculate center distance (for detecting same player with different boxes)
                center_distance = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)
                box1_size = np.sqrt((box1[2] - box1[0])**2 + (box1[3] - box1[1])**2)
                normalized_distance = center_distance / max(box1_size, 1.0)  # Normalize by box size
                
                # If IoU is very high OR centers are very close, they're likely the same player
                # Also check if boxes are similar size (same player should have similar box size)
                box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
                box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
                size_ratio = min(box1_area, box2_area) / max(box1_area, box2_area) if max(box1_area, box2_area) > 0 else 0
                
                is_duplicate = False
                if iou > self.nms_iou_threshold:
                    is_duplicate = True
                elif normalized_distance < 0.3 and size_ratio > 0.7:
                    # Centers are very close (< 30% of box size) and boxes are similar size (> 70% ratio)
                    # This catches cases where boxes don't overlap but are clearly the same player
                    is_duplicate = True
                
                if is_duplicate:
                    # Keep the track with longer history (older ID) or higher confidence if same age
                    # Prefer keeping the older track ID to maintain consistency
                    if age1 < age2 or (age1 == age2 and conf1 < conf2):
                        tracks_to_remove.add(tid1)
                        break  # tid1 is removed, move to next
                    else:
                        tracks_to_remove.add(tid2)
        
        # Remove duplicate tracks from detections
        if tracks_to_remove:
            mask = np.array([tid not in tracks_to_remove if tid is not None else True 
                            for tid in detections.tracker_id])
            
            # Filter all detection attributes
            detections.xyxy = detections.xyxy[mask]
            detections.confidence = detections.confidence[mask]
            detections.tracker_id = detections.tracker_id[mask]
            if hasattr(detections, 'class_id') and detections.class_id is not None:
                detections.class_id = detections.class_id[mask]
        
        return detections
    
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
    
    def cleanup_inactive_tracks(self, active_track_ids):
        """Clean up history for tracks that are no longer active"""
        inactive_tracks = set(self.track_history.keys()) - set(active_track_ids)
        for track_id in inactive_tracks:
            if track_id in self.track_history:
                del self.track_history[track_id]
            if track_id in self.track_last_frame:
                del self.track_last_frame[track_id]
            if track_id in self.track_last_position:
                del self.track_last_position[track_id]
            if track_id in self.track_last_bbox:
                del self.track_last_bbox[track_id]
            if track_id in self.track_velocity:
                del self.track_velocity[track_id]
            if track_id in self.track_bbox_size:
                del self.track_bbox_size[track_id]

