"""
Comprehensive Real-Time Tracking Metrics Enhancement

This module uses HOTA, MOTA, and IDF1 concepts to improve tracking DURING analysis,
not just evaluate it afterward.

Key Features:
1. Real-time HOTA, MOTA, and IDF1 monitoring on recent frames
2. Metrics-guided Re-ID threshold adjustment
3. Track merging based on association accuracy
4. Automatic correction of fragmented tracks
5. Real-time route corrections based on all three metrics
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from collections import deque, defaultdict
from hota_evaluator import HOTAEvaluator
try:
    from tracking_metrics_evaluator import TrackingMetricsEvaluator
    METRICS_EVALUATOR_AVAILABLE = True
except ImportError:
    METRICS_EVALUATOR_AVAILABLE = False

# Import advanced tracking utilities
try:
    from advanced_tracking_utils import (
        calculate_expansion_iou,
        harmonic_mean_association,
        calculate_track_velocity,
        match_tracks_with_harmonic_mean
    )
    ADVANCED_UTILS_AVAILABLE = True
except ImportError:
    ADVANCED_UTILS_AVAILABLE = False


class HOTAGuidedTracker:
    """
    Uses HOTA, MOTA, and IDF1 concepts to guide tracking improvements DURING analysis.
    All metrics are calculated in real-time and used for route corrections.
    """
    
    def __init__(self, window_size: int = 100, min_hota_threshold: float = 0.5, 
                 use_harmonic_mean: bool = True, use_expansion_iou: bool = True):
        """
        Initialize comprehensive metrics-guided tracker.
        
        Args:
            window_size: Number of recent frames to evaluate (default: 100)
            min_hota_threshold: Minimum HOTA score before triggering corrections (default: 0.5)
            use_harmonic_mean: Use Harmonic Mean for association (default: True, based on Deep HM-SORT)
            use_expansion_iou: Use Expansion IOU with motion prediction (default: True, based on Deep HM-SORT)
        """
        self.window_size = window_size
        self.min_hota_threshold = min_hota_threshold
        self.use_harmonic_mean = use_harmonic_mean and ADVANCED_UTILS_AVAILABLE
        self.use_expansion_iou = use_expansion_iou and ADVANCED_UTILS_AVAILABLE
        self.recent_tracks = deque(maxlen=window_size)  # Recent track data: (frame_num, track_id, x1, y1, x2, y2)
        self.recent_detections = deque(maxlen=window_size)  # Recent detections
        self.track_velocities = {}  # {track_id: (vx, vy)} for motion prediction
        self.track_history = defaultdict(list)  # {track_id: [(frame, bbox), ...]} for velocity calculation
        self.hota_evaluator = HOTAEvaluator()
        self.reid_threshold_history = deque(maxlen=50)  # Track Re-ID threshold changes
        
        # Comprehensive metrics evaluator for MOTA and IDF1
        if METRICS_EVALUATOR_AVAILABLE:
            self.metrics_evaluator = TrackingMetricsEvaluator()
        else:
            self.metrics_evaluator = None
        
        if self.use_harmonic_mean:
            print("  → Harmonic Mean association enabled (Deep HM-SORT)")
        if self.use_expansion_iou:
            print("  → Expansion IOU enabled (motion prediction)")
        
    def add_frame_data(
        self,
        frame_num: int,
        detections: List[Tuple[int, float, float, float, float]],  # (track_id, x1, y1, x2, y2)
        ground_truth: Optional[List[Tuple[int, float, float, float, float]]] = None
    ):
        """
        Add frame data for comprehensive metrics-guided tracking.
        
        Args:
            frame_num: Frame number
            detections: List of (track_id, x1, y1, x2, y2) detections
            ground_truth: Optional ground truth for evaluation
        """
        self.recent_detections.append((frame_num, detections))
        
        # Store individual track detections for metrics calculation
        for track_id, x1, y1, x2, y2 in detections:
            self.recent_tracks.append((frame_num, track_id, x1, y1, x2, y2))
            
            # Update track history for velocity calculation (if Expansion IOU enabled)
            if self.use_expansion_iou:
                bbox = (x1, y1, x2, y2)
                self.track_history[track_id].append((frame_num, bbox))
                
                # Keep only recent history (last 5 frames for velocity)
                if len(self.track_history[track_id]) > 5:
                    self.track_history[track_id] = self.track_history[track_id][-5:]
                
                # Calculate velocity if we have at least 2 frames
                if len(self.track_history[track_id]) >= 2:
                    current_bbox = self.track_history[track_id][-1][1]
                    previous_bbox = self.track_history[track_id][-2][1]
                    current_frame = self.track_history[track_id][-1][0]
                    previous_frame = self.track_history[track_id][-2][0]
                    frame_delta = current_frame - previous_frame
                    
                    if frame_delta > 0:
                        velocity = calculate_track_velocity(current_bbox, previous_bbox, frame_delta)
                        self.track_velocities[track_id] = velocity
    
    def calculate_recent_metrics(
        self,
        ground_truth: Optional[Dict[int, List[Tuple[int, float, float, float, float]]]] = None
    ) -> Dict[str, float]:
        """
        Calculate HOTA, MOTA, and IDF1 on recent frames IN REAL-TIME.
        This is used DURING analysis for route corrections.
        
        Returns:
            Dictionary with all metrics (HOTA, MOTA, IDF1)
        """
        if len(self.recent_tracks) < 10:
            return {
                'HOTA': 0.0, 'DetA': 0.0, 'AssA': 0.0,
                'MOTA': 0.0, 'MOTP': 0.0, 'FN': 0, 'FP': 0, 'IDSW': 0,
                'IDF1': 0.0, 'IDP': 0.0, 'IDR': 0.0,
                'error': 'Not enough data'
            }
        
        # Convert recent tracks to format: {track_id: [(frame, x1, y1, x2, y2), ...]}
        pred_tracks = defaultdict(list)
        for frame_num, track_id, x1, y1, x2, y2 in self.recent_tracks:
            pred_tracks[track_id].append((frame_num, x1, y1, x2, y2))
        
        # Use ground truth if provided
        gt_tracks = ground_truth if ground_truth else {}
        
        if not gt_tracks:
            return {
                'HOTA': 0.0, 'DetA': 0.0, 'AssA': 0.0,
                'MOTA': 0.0, 'MOTP': 0.0, 'FN': 0, 'FP': 0, 'IDSW': 0,
                'IDF1': 0.0, 'IDP': 0.0, 'IDR': 0.0,
                'error': 'No ground truth available'
            }
        
        # Calculate HOTA
        hota_results = self.hota_evaluator.calculate_hota(pred_tracks, gt_tracks)
        
        # Calculate MOTA and IDF1 if evaluator available
        if self.metrics_evaluator:
            mota_results = self.metrics_evaluator.calculate_mota(pred_tracks, gt_tracks)
            idf1_results = self.metrics_evaluator.calculate_idf1(pred_tracks, gt_tracks)
            
            # Combine all metrics
            return {
                **hota_results,
                **mota_results,
                **idf1_results
            }
        else:
            # Fallback to HOTA only
            return hota_results
    
    def calculate_recent_hota(
        self,
        ground_truth_tracks: Optional[Dict[int, List[Tuple[int, float, float, float, float]]]] = None
    ) -> Dict[str, float]:
        """
        Calculate HOTA on recent frames (backward compatibility).
        
        Returns:
            Dictionary with HOTA metrics
        """
        metrics = self.calculate_recent_metrics(ground_truth_tracks)
        return {
            'HOTA': metrics.get('HOTA', 0.0),
            'DetA': metrics.get('DetA', 0.0),
            'AssA': metrics.get('AssA', 0.0),
            **{k: v for k, v in metrics.items() if k.startswith('Det') or k.startswith('Ass')}
        }
    
    def suggest_reid_threshold_adjustment(
        self,
        current_threshold: float,
        recent_metrics: Optional[Dict[str, float]] = None
    ) -> float:
        """
        Suggest Re-ID threshold adjustment based on ALL metrics (HOTA, MOTA, IDF1).
        Uses all three metrics for better route corrections.
        
        Args:
            current_threshold: Current Re-ID similarity threshold
            recent_metrics: Optional recent metrics (calculated if None)
        
        Returns:
            Suggested new Re-ID threshold
        """
        if recent_metrics is None:
            recent_metrics = self.calculate_recent_metrics()
        
        if 'error' in recent_metrics:
            return current_threshold
        
        assa = recent_metrics.get('AssA', 0.0)
        mota = recent_metrics.get('MOTA', 0.0)
        idf1 = recent_metrics.get('IDF1', 0.0)
        idsw = recent_metrics.get('IDSW', 0)
        hota = recent_metrics.get('HOTA', 0.0)
        
        # Use multiple metrics for better decisions
        # If IDF1 is low, it means ID consistency is poor - lower threshold
        if idf1 < 0.5:
            new_threshold = max(0.25, current_threshold - 0.1)
            self.reid_threshold_history.append(('lowered', new_threshold, f'IDF1={idf1:.2f}'))
            return new_threshold
        
        # If ID switches are high, lower threshold to reconnect tracks
        if idsw > 10:  # More than 10 ID switches in recent window
            new_threshold = max(0.25, current_threshold - 0.08)
            self.reid_threshold_history.append(('lowered', new_threshold, f'IDSW={idsw}'))
            return new_threshold
        
        # If association accuracy is low, lower threshold (more lenient)
        if assa < 0.4:
            new_threshold = max(0.25, current_threshold - 0.1)
            self.reid_threshold_history.append(('lowered', new_threshold, f'AssA={assa:.2f}'))
            return new_threshold
        
        # If MOTA is low but IDF1 is high, might be detection issues (not Re-ID)
        # If both are low, lower Re-ID threshold
        if mota < 0.5 and idf1 < 0.6:
            new_threshold = max(0.25, current_threshold - 0.08)
            self.reid_threshold_history.append(('lowered', new_threshold, f'MOTA={mota:.2f}, IDF1={idf1:.2f}'))
            return new_threshold
        
        # If all metrics are high, raise threshold (stricter matching)
        if assa > 0.7 and mota > 0.7 and idf1 > 0.8:
            new_threshold = min(0.7, current_threshold + 0.05)
            self.reid_threshold_history.append(('raised', new_threshold, f'All metrics high'))
            return new_threshold
        
        # Keep current threshold
        return current_threshold
    
    def suggest_tracking_corrections(
        self,
        recent_metrics: Dict[str, float]
    ) -> List[str]:
        """
        Suggest tracking corrections based on all three metrics (HOTA, MOTA, IDF1).
        These are used for real-time route corrections during analysis.
        
        Returns:
            List of suggestion strings
        """
        suggestions = []
        
        if 'error' in recent_metrics:
            return suggestions
        
        hota = recent_metrics.get('HOTA', 0.0)
        deta = recent_metrics.get('DetA', 0.0)
        assa = recent_metrics.get('AssA', 0.0)
        mota = recent_metrics.get('MOTA', 0.0)
        idf1 = recent_metrics.get('IDF1', 0.0)
        fn = recent_metrics.get('FN', 0)
        fp = recent_metrics.get('FP', 0)
        idsw = recent_metrics.get('IDSW', 0)
        
        # Detection issues (affects HOTA DetA and MOTA FN)
        if deta < 0.6 or fn > 20:
            suggestions.append("Low detection accuracy - consider adjusting YOLO confidence threshold")
        
        # Association issues (affects HOTA AssA and IDF1)
        if assa < 0.5 or idf1 < 0.6:
            suggestions.append("Low association/ID consistency - Re-ID threshold lowered automatically")
        
        # ID switch issues (affects MOTA and IDF1)
        if idsw > 10:
            suggestions.append(f"High ID switches ({idsw}) - track merging may help")
        
        # False positive issues (affects MOTA)
        if fp > 15:
            suggestions.append(f"High false positives ({fp}) - consider stricter detection filtering")
        
        # Overall quality
        if hota < 0.5 and mota < 0.5 and idf1 < 0.5:
            suggestions.append("Overall tracking quality is low - review all tracking parameters")
        
        return suggestions
    
    def identify_fragmented_tracks(
        self,
        min_gap_frames: int = 30,
        max_gap_frames: int = 300
    ) -> List[Tuple[int, int]]:
        """
        Identify tracks that might be fragments of the same player.
        
        Uses HOTA association concepts to find tracks that should be merged.
        
        Args:
            min_gap_frames: Minimum gap between tracks to consider merging
            max_gap_frames: Maximum gap between tracks to consider merging
        
        Returns:
            List of (track_id1, track_id2) pairs that should be merged
        """
        if len(self.recent_tracks) < 20:
            return []
        
        # Analyze track gaps and overlaps
        track_fragments = []
        
        # Get all unique track IDs
        all_track_ids = set()
        for frame_tracks in self.recent_tracks:
            all_track_ids.update(frame_tracks.keys())
        
        # Check for fragmented tracks
        for track_id1 in all_track_ids:
            for track_id2 in all_track_ids:
                if track_id1 >= track_id2:
                    continue
                
                # Check if tracks are close in time and space
                track1_frames = []
                track2_frames = []
                
                for frame_tracks in self.recent_tracks:
                    if track_id1 in frame_tracks:
                        track1_frames.extend(frame_tracks[track_id1])
                    if track_id2 in frame_tracks:
                        track2_frames.extend(frame_tracks[track_id2])
                
                if not track1_frames or not track2_frames:
                    continue
                
                # Check temporal gap
                track1_last = max(f[0] for f in track1_frames)
                track2_first = min(f[0] for f in track2_frames)
                
                if track1_last < track2_first:
                    gap = track2_first - track1_last
                    if min_gap_frames <= gap <= max_gap_frames:
                        # Check spatial proximity
                        last_pos1 = track1_frames[-1][1:3]  # (x1, y1)
                        first_pos2 = track2_frames[0][1:3]  # (x1, y1)
                        
                        distance = np.sqrt(
                            (last_pos1[0] - first_pos2[0])**2 +
                            (last_pos1[1] - first_pos2[1])**2
                        )
                        
                        # If tracks are close in space and time, suggest merge
                        if distance < 200:  # 200 pixels threshold
                            track_fragments.append((track_id1, track_id2))
        
        return track_fragments
    
    def get_tracking_quality_report(self) -> Dict[str, any]:
        """
        Get comprehensive tracking quality report using ALL metrics (HOTA, MOTA, IDF1).
        
        Returns:
            Dictionary with all metrics and suggestions
        """
        recent_metrics = self.calculate_recent_metrics()
        
        report = {
            'recent_metrics': recent_metrics,
            'recent_hota': {k: v for k, v in recent_metrics.items() if 'HOTA' in k or 'DetA' in k or 'AssA' in k},
            'quality_level': 'good' if recent_metrics.get('HOTA', 0) > 0.7 else 'poor',
            'suggestions': self.suggest_tracking_corrections(recent_metrics)
        }
        
        return report
    
    def identify_fragmented_tracks(
        self,
        min_gap_frames: int = 30,
        max_gap_frames: int = 300
    ) -> List[Tuple[int, int]]:
        """
        Identify tracks that might be fragments of the same player.
        
        Uses HOTA association concepts to find tracks that should be merged.
        
        Args:
            min_gap_frames: Minimum gap between tracks to consider merging
            max_gap_frames: Maximum gap between tracks to consider merging
        
        Returns:
            List of (track_id1, track_id2) pairs that should be merged
        """
        if len(self.recent_tracks) < 20:
            return []
        
        # Analyze track gaps and overlaps
        track_fragments = []
        
        # Get all unique track IDs
        all_track_ids = set()
        for frame_num, track_id, x1, y1, x2, y2 in self.recent_tracks:
            all_track_ids.add(track_id)
        
        # Check for fragmented tracks
        for track_id1 in all_track_ids:
            for track_id2 in all_track_ids:
                if track_id1 >= track_id2:
                    continue
                
                # Get frames for each track
                track1_frames = [(f, x1, y1, x2, y2) for f, tid, x1, y1, x2, y2 in self.recent_tracks if tid == track_id1]
                track2_frames = [(f, x1, y1, x2, y2) for f, tid, x1, y1, x2, y2 in self.recent_tracks if tid == track_id2]
                
                if not track1_frames or not track2_frames:
                    continue
                
                # Check temporal gap
                track1_last = max(f[0] for f in track1_frames)
                track2_first = min(f[0] for f in track2_frames)
                
                if track1_last < track2_first:
                    gap = track2_first - track1_last
                    if min_gap_frames <= gap <= max_gap_frames:
                        # Check spatial proximity
                        last_pos1 = track1_frames[-1][1:3]  # (x1, y1)
                        first_pos2 = track2_frames[0][1:3]  # (x1, y1)
                        
                        distance = np.sqrt(
                            (last_pos1[0] - first_pos2[0])**2 +
                            (last_pos1[1] - first_pos2[1])**2
                        )
                        
                        # If tracks are close in space and time, suggest merge
                        if distance < 200:  # 200 pixels threshold
                            track_fragments.append((track_id1, track_id2))
        
        return track_fragments


def integrate_hota_guidance_into_tracking(
    reid_tracker,
    current_reid_threshold: float,
    recent_frame_data: List[Dict],
    hota_guided_tracker: HOTAGuidedTracker
) -> float:
    """
    Integrate HOTA guidance into tracking process.
    
    This function can be called during tracking to adjust Re-ID threshold
    based on recent HOTA performance.
    
    Args:
        reid_tracker: Re-ID tracker instance
        current_reid_threshold: Current Re-ID similarity threshold
        recent_frame_data: List of recent frame tracking data
        hota_guided_tracker: HOTA-guided tracker instance
    
    Returns:
        Adjusted Re-ID threshold
    """
    # Add recent data to HOTA tracker
    for frame_data in recent_frame_data[-100:]:  # Last 100 frames
        detections = frame_data.get('detections', [])
        frame_num = frame_data.get('frame_num', 0)
        
        # Convert to format expected by HOTA tracker
        hota_detections = []
        for det in detections:
            track_id = det.get('track_id', 0)
            bbox = det.get('bbox', [0, 0, 0, 0])
            hota_detections.append((track_id, bbox[0], bbox[1], bbox[2], bbox[3]))
        
        hota_guided_tracker.add_frame_data(frame_num, hota_detections)
    
    # Get suggested threshold adjustment
    new_threshold = hota_guided_tracker.suggest_reid_threshold_adjustment(
        current_reid_threshold
    )
    
    # Update Re-ID tracker if threshold changed significantly
    if abs(new_threshold - current_reid_threshold) > 0.05:
        if hasattr(reid_tracker, 'similarity_threshold'):
            reid_tracker.similarity_threshold = new_threshold
            print(f"📊 HOTA-guided adjustment: Re-ID threshold changed from {current_reid_threshold:.2f} to {new_threshold:.2f}")
    
    return new_threshold

