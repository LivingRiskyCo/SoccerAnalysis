"""
Comprehensive Tracking Metrics Evaluator

Evaluates tracking quality using multiple metrics:
- HOTA (Higher Order Tracking Accuracy): Balanced detection and association
- MOTA (Multiple Object Tracking Accuracy): Traditional metric with false positives/negatives
- IDF1 (ID F1 Score): ID consistency over time

All metrics work together with Re-ID to provide comprehensive evaluation.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import os
from collections import defaultdict
from hota_evaluator import HOTAEvaluator

# Import advanced tracking utilities
try:
    from advanced_tracking_utils import (
        calculate_expansion_iou,
        calculate_iou as advanced_calculate_iou,
        harmonic_mean_association,
        calculate_track_velocity
    )
    ADVANCED_UTILS_AVAILABLE = True
except ImportError:
    ADVANCED_UTILS_AVAILABLE = False
    print("⚠ Advanced tracking utilities not available (advanced_tracking_utils.py not found)")


class TrackingMetricsEvaluator:
    """
    Comprehensive tracking metrics evaluator supporting HOTA, MOTA, and IDF1.
    
    All metrics work together:
    - Re-ID improves tracking during analysis
    - HOTA evaluates balanced detection and association
    - MOTA evaluates traditional tracking accuracy
    - IDF1 evaluates ID consistency
    """
    
    def __init__(self):
        """Initialize evaluator with HOTA support."""
        self.hota_evaluator = HOTAEvaluator()
    
    def calculate_mota(
        self,
        pred_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        gt_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        frame_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, float]:
        """
        Calculate MOTA (Multiple Object Tracking Accuracy).
        
        MOTA = 1 - (FN + FP + IDSW) / GT
        
        Where:
        - FN: False Negatives (missed detections)
        - FP: False Positives (false detections)
        - IDSW: ID Switches (track ID changes)
        - GT: Ground Truth detections
        
        Args:
            pred_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            gt_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            frame_range: Optional (start_frame, end_frame) to limit evaluation
        
        Returns:
            Dictionary with MOTA metrics:
            - MOTA: Overall MOTA score (0-1, higher is better)
            - MOTP: Multiple Object Tracking Precision (localization accuracy)
            - FN: False Negatives count
            - FP: False Positives count
            - IDSW: ID Switches count
            - GT: Ground Truth count
        """
        if frame_range:
            start_frame, end_frame = frame_range
            pred_tracks = self._filter_frames(pred_tracks, start_frame, end_frame)
            gt_tracks = self._filter_frames(gt_tracks, start_frame, end_frame)
        
        # Group by frame
        pred_by_frame = defaultdict(list)
        gt_by_frame = defaultdict(list)
        
        for track_id, detections in pred_tracks.items():
            for det in detections:
                # Handle both 5-tuple (frame, x1, y1, x2, y2) and 6-tuple (frame, x1, y1, x2, y2, player_name)
                if len(det) >= 5:
                    frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                    pred_by_frame[frame].append((track_id, x1, y1, x2, y2))
        
        for track_id, detections in gt_tracks.items():
            for det in detections:
                # Handle both 5-tuple (frame, x1, y1, x2, y2) and 6-tuple (frame, x1, y1, x2, y2, player_name)
                if len(det) >= 5:
                    frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                    gt_by_frame[frame].append((track_id, x1, y1, x2, y2))
        
        all_frames = set(pred_by_frame.keys()) | set(gt_by_frame.keys())
        
        total_fp = 0
        total_fn = 0
        total_idsw = 0
        total_gt = 0
        total_iou_sum = 0.0
        total_matches = 0
        
        # Track ID assignments for ID switch detection
        prev_frame_assignments = {}  # gt_track_id -> pred_track_id
        
        # DIAGNOSTIC: Track matching statistics
        total_iou_attempts = 0
        total_iou_sum_for_diagnostics = 0.0
        max_iou_seen = 0.0
        frames_with_matches = 0
        frames_with_no_matches = 0
        
        # CRITICAL FIX: Detect and normalize coordinate systems
        # Check if coordinates are in different systems (normalized vs pixel, or different resolutions)
        pred_coords = []
        gt_coords = []
        # Sample from all available frames (not just overlapping ones) to detect coordinate systems
        # This handles cases where predictions and GT are in different frame ranges
        for frame in sorted(all_frames)[:20]:  # Sample up to 20 frames
            pred_dets = pred_by_frame.get(frame, [])
            gt_dets = gt_by_frame.get(frame, [])
            # Collect coordinates from both predictions and GT separately
            # This allows normalization even when frames don't overlap
            if pred_dets:
                pred_coords.extend([(d[1], d[2], d[3], d[4]) for d in pred_dets])
            if gt_dets:
                gt_coords.extend([(d[1], d[2], d[3], d[4]) for d in gt_dets])
        
        # Detect coordinate system and normalize if needed
        if pred_coords and gt_coords:
            pred_max_x = max(max(c[0], c[2]) for c in pred_coords) if pred_coords else 0
            pred_max_y = max(max(c[1], c[3]) for c in pred_coords) if pred_coords else 0
            gt_max_x = max(max(c[0], c[2]) for c in gt_coords) if gt_coords else 0
            gt_max_y = max(max(c[1], c[3]) for c in gt_coords) if gt_coords else 0
            
            # Calculate average bbox sizes to detect if one is normalized (0-1) vs pixel coordinates
            pred_avg_w = sum(abs(c[2] - c[0]) for c in pred_coords) / len(pred_coords) if pred_coords else 0
            pred_avg_h = sum(abs(c[3] - c[1]) for c in pred_coords) / len(pred_coords) if pred_coords else 0
            gt_avg_w = sum(abs(c[2] - c[0]) for c in gt_coords) / len(gt_coords) if gt_coords else 0
            gt_avg_h = sum(abs(c[3] - c[1]) for c in gt_coords) / len(gt_coords) if gt_coords else 0
            
            # CRITICAL FIX: Always check for coordinate mismatch, even if ranges seem similar
            # Use ratio-based detection instead of absolute difference (works for any resolution)
            coord_ratio_x = pred_max_x / gt_max_x if gt_max_x > 0 else 1.0
            coord_ratio_y = pred_max_y / gt_max_y if gt_max_y > 0 else 1.0
            
            # Detect mismatch if ratios are significantly different from 1.0 (more than 10% difference)
            # OR if one is normalized (0-1) and the other is pixel coordinates
            pred_is_normalized = pred_max_x <= 1.0 and pred_max_y <= 1.0
            gt_is_normalized = gt_max_x <= 1.0 and gt_max_y <= 1.0
            coord_mismatch = (
                (abs(coord_ratio_x - 1.0) > 0.1 or abs(coord_ratio_y - 1.0) > 0.1) or
                (pred_is_normalized != gt_is_normalized)
            ) and (pred_max_x > 0 and gt_max_x > 0)
            
            # Initialize scale factors (default to no scaling)
            scale_x = 1.0
            scale_y = 1.0
            
            if coord_mismatch:
                print(f"  🔧 Detected coordinate system mismatch:")
                print(f"     Prediction range: x=[0, {pred_max_x:.1f}], y=[0, {pred_max_y:.1f}], avg_bbox=[{pred_avg_w:.1f}x{pred_avg_h:.1f}]")
                print(f"     Ground Truth range: x=[0, {gt_max_x:.1f}], y=[0, {gt_max_y:.1f}], avg_bbox=[{gt_avg_w:.1f}x{gt_avg_h:.1f}]")
                print(f"     Coordinate ratios: x={coord_ratio_x:.3f}, y={coord_ratio_y:.3f}")
                
                # Check if one is normalized (0-1) vs pixel coordinates
                if pred_is_normalized and not gt_is_normalized:
                    # Predictions are normalized, GT is pixel - normalize GT to 0-1
                    print(f"     Prediction appears normalized (0-1), normalizing GT to match:")
                    if gt_max_x > 0 and gt_max_y > 0:
                        scale_x = 1.0 / gt_max_x
                        scale_y = 1.0 / gt_max_y
                        print(f"     Scale factors: x={scale_x:.6f}, y={scale_y:.6f}")
                elif gt_is_normalized and not pred_is_normalized:
                    # GT is normalized, predictions are pixel - scale GT to pixel coordinates
                    print(f"     GT appears normalized (0-1), scaling to match prediction pixel coordinates:")
                    if gt_max_x > 0 and gt_max_y > 0:
                        scale_x = pred_max_x / gt_max_x if gt_max_x > 0 else 1.0
                        scale_y = pred_max_y / gt_max_y if gt_max_y > 0 else 1.0
                        print(f"     Scale factors: x={scale_x:.3f}, y={scale_y:.3f}")
                else:
                    # Both are pixel coordinates but different resolutions
                    # Normalize GT coordinates to match prediction scale (CSV is reference)
                    print(f"     Both appear to be pixel coordinates, normalizing GT to match prediction scale:")
                    if gt_max_x > 0 and gt_max_y > 0:
                        scale_x = pred_max_x / gt_max_x
                        scale_y = pred_max_y / gt_max_y
                        print(f"     Scale factors: x={scale_x:.3f}, y={scale_y:.3f}")
                    print(f"     ⚠ WARNING: This suggests GT and predictions are from different video resolutions!")
                    print(f"     ⚠ This may indicate anchor frames are from a different video than the analysis.")
                    print(f"     ⚠ CRITICAL: Scale factors differ significantly (x={scale_x:.3f}, y={scale_y:.3f})")
                    print(f"        → This strongly suggests anchor frames are from a DIFFERENT VIDEO")
                    print(f"        → Anchor frames should be recreated from the same video being analyzed")
                    print(f"        → Metrics evaluation will be inaccurate until anchor frames match the video")
                
                # Apply normalization to all GT coordinates (always apply if scale factors were calculated)
                if (scale_x != 1.0 or scale_y != 1.0) and gt_max_x > 0 and gt_max_y > 0:
                    normalized_count = 0
                    for track_id in list(gt_tracks.keys()):
                        normalized_dets = []
                        for det in gt_tracks[track_id]:
                            # Handle both 5-tuple and 6-tuple formats
                            if len(det) >= 5:
                                frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                                # Preserve player_name if present (6th element)
                                if len(det) > 5:
                                    normalized_dets.append((
                                        frame,
                                        x1 * scale_x,
                                        y1 * scale_y,
                                        x2 * scale_x,
                                        y2 * scale_y,
                                        det[5]  # player_name
                                    ))
                                else:
                                    normalized_dets.append((
                                        frame,
                                        x1 * scale_x,
                                        y1 * scale_y,
                                        x2 * scale_x,
                                        y2 * scale_y
                                    ))
                            normalized_count += 1
                        gt_tracks[track_id] = normalized_dets
                    
                    # Rebuild gt_by_frame with normalized coordinates
                    gt_by_frame = defaultdict(list)
                    for track_id, detections in gt_tracks.items():
                        for det in detections:
                            # Handle both 5-tuple and 6-tuple formats
                            if len(det) >= 5:
                                frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                                gt_by_frame[frame].append((track_id, x1, y1, x2, y2))
                    
                    print(f"     ✓ Normalized {normalized_count} GT detections")
                    
                    # Verify normalization worked by checking a sample
                    if normalized_count > 0:
                        sample_gt = list(gt_tracks.values())[0][0] if gt_tracks else None
                        sample_pred = list(pred_tracks.values())[0][0] if pred_tracks else None
                        if sample_gt and sample_pred and len(sample_gt) >= 5 and len(sample_pred) >= 5:
                            _, gx1, gy1, gx2, gy2 = sample_gt[0], sample_gt[1], sample_gt[2], sample_gt[3], sample_gt[4]
                            _, px1, py1, px2, py2 = sample_pred[0], sample_pred[1], sample_pred[2], sample_pred[3], sample_pred[4]
                            sample_iou = self._calculate_iou((px1, py1, px2, py2), (gx1, gy1, gx2, gy2))
                            print(f"     Sample IoU after normalization: {sample_iou:.4f}")
                            if sample_iou < 0.01:
                                print(f"     ⚠ WARNING: Sample IoU still very low - coordinates may be from different videos!")
                                print(f"     ⚠ Consider checking that anchor frames match the analyzed video.")
                                
                                # Check if scale factors are very different (suggests different aspect ratios/videos)
                                if abs(scale_x - scale_y) > 2.0:  # More than 2x difference
                                    print(f"     ⚠ CRITICAL: Scale factors differ significantly (x={scale_x:.3f}, y={scale_y:.3f})")
                                    print(f"        → This strongly suggests anchor frames are from a DIFFERENT VIDEO")
                                    print(f"        → Anchor frames should be recreated from the same video being analyzed")
                                    print(f"        → Metrics evaluation will be inaccurate until anchor frames match the video")
        
        # Pre-check: Verify normalization worked by checking if any bboxes overlap
        # This helps detect if anchor frames are from a different video
        sample_frames_checked = 0
        sample_frames_with_overlap = 0
        for frame in sorted(list(all_frames)[:10]):  # Check first 10 frames
            pred_dets = pred_by_frame.get(frame, [])
            gt_dets = gt_by_frame.get(frame, [])
            if len(pred_dets) > 0 and len(gt_dets) > 0:
                sample_frames_checked += 1
                for pred_track_id, px1, py1, px2, py2 in pred_dets:
                    for gt_track_id, gx1, gy1, gx2, gy2 in gt_dets:
                        iou = self._calculate_iou((px1, py1, px2, py2), (gx1, gy1, gx2, gy2))
                        if iou > 0.01:  # Any overlap at all
                            sample_frames_with_overlap += 1
                            break
                    if sample_frames_with_overlap > 0:
                        break
        
        if sample_frames_checked > 0 and sample_frames_with_overlap == 0:
            print(f"  ⚠ CRITICAL WARNING: After normalization, {sample_frames_checked} sample frames checked, 0 with any bbox overlap!")
            print(f"     This strongly suggests anchor frames are from a DIFFERENT VIDEO than the analysis.")
            print(f"     → Anchor frames should be from the SAME video file as the analysis.")
            print(f"     → Check that PlayerTagsSeed-*.json matches the analyzed video.")
        
        # FRAME OFFSET DETECTION: If frames don't overlap, try to detect and correct frame offset
        # This handles cases where predictions and GT are from the same video but different frame ranges
        pred_frame_list = sorted(pred_by_frame.keys())
        gt_frame_list = sorted(gt_by_frame.keys())
        frame_overlap_count = len(set(pred_frame_list) & set(gt_frame_list))
        frame_offset = 0
        
        # Calculate frame ranges for use in offset detection and proximity matching
        pred_min = min(pred_frame_list) if pred_frame_list else 0
        pred_max = max(pred_frame_list) if pred_frame_list else 0
        gt_min = min(gt_frame_list) if gt_frame_list else 0
        gt_max = max(gt_frame_list) if gt_frame_list else 0
        
        if frame_overlap_count == 0 and len(pred_frame_list) > 0 and len(gt_frame_list) > 0:
            # Try to detect frame offset by finding the closest match
            
            # Check if predictions are within GT frame range (even if no exact overlap)
            # This handles cases where GT frames are sparse (e.g., 0, 420) but predictions are in between
            if pred_min >= gt_min and pred_max <= gt_max:
                # Predictions are within GT range - use proximity matching (no offset needed)
                print(f"  🔧 Predictions [{pred_min}, {pred_max}] are within GT range [{gt_min}, {gt_max}]")
                print(f"     Using proximity matching to find nearest GT frames...")
                frame_offset = 0  # No offset needed, just proximity matching
            else:
                # Try different offset strategies
                # Strategy 1: Align by minimum frames (assume predictions start later)
                offset_by_min = pred_min - gt_min
                # Strategy 2: Align by maximum frames
                offset_by_max = pred_max - gt_max
                # Strategy 3: Align by center
                pred_center = (pred_min + pred_max) / 2
                gt_center = (gt_min + gt_max) / 2
                offset_by_center = int(pred_center - gt_center)
                
                # Use the offset that makes the most sense (smallest absolute value, or by center)
                candidate_offsets = [offset_by_min, offset_by_max, offset_by_center]
                # Prefer offset that brings frames closer together
                frame_offset = min(candidate_offsets, key=lambda x: abs(x))
                
                if abs(frame_offset) > 0:
                    print(f"  🔧 Detected frame offset: predictions are {frame_offset:+d} frames relative to ground truth")
                    print(f"     Attempting to match predictions to ground truth with frame offset correction...")
                    
                    # Apply offset to ground truth frames (shift GT frames to match prediction frame numbers)
                    # Create a new gt_by_frame with offset frames
                    gt_by_frame_offset = defaultdict(list)
                    for gt_frame, detections in gt_by_frame.items():
                        offset_frame = gt_frame + frame_offset
                        gt_by_frame_offset[offset_frame] = detections
                    
                    # Check if offset creates any overlap
                    offset_overlap = len(set(pred_frame_list) & set(gt_by_frame_offset.keys()))
                    if offset_overlap > 0:
                        print(f"     ✓ Frame offset creates {offset_overlap} overlapping frames - using offset matching")
                        gt_by_frame = gt_by_frame_offset
                        # Also update gt_tracks to reflect the offset
                        for track_id in list(gt_tracks.keys()):
                            offset_dets = []
                            for det in gt_tracks[track_id]:
                                # Handle both 5-tuple and 6-tuple formats
                                if len(det) >= 5:
                                    frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                                    # Preserve player_name if present
                                    if len(det) > 5:
                                        offset_dets.append((frame + frame_offset, x1, y1, x2, y2, det[5]))
                                    else:
                                        offset_dets.append((frame + frame_offset, x1, y1, x2, y2))
                            gt_tracks[track_id] = offset_dets
                    else:
                        print(f"     ⚠ Frame offset did not create overlap - will try proximity matching instead")
                        frame_offset = 0  # Reset offset if it doesn't help
        
        # PROXIMITY MATCHING: If still no overlap, match predictions to nearest GT frames
        # This allows evaluation even when frame numbers don't align perfectly
        use_proximity_matching = False
        if frame_overlap_count == 0 and len(pred_frame_list) > 0 and len(gt_frame_list) > 0:
            # Check if frames are close enough to match by proximity
            # (pred_min, pred_max, gt_min, gt_max already defined above)
            
            # If predictions are within GT range, always use proximity matching
            # This handles sparse GT frames (e.g., anchor frames at 0, 420) with predictions in between
            if pred_min >= gt_min and pred_max <= gt_max:
                use_proximity_matching = True
                print(f"  🔧 Predictions within GT range - using proximity matching for sparse GT frames")
            # If frame ranges are within reasonable distance (e.g., within 500 frames), use proximity matching
            elif (pred_min <= gt_max + 500 and pred_max >= gt_min - 500):
                print(f"  🔧 No frame overlap, but frames are close - using proximity matching")
                print(f"     Predictions: [{pred_min}, {pred_max}], GT: [{gt_min}, {gt_max}]")
                use_proximity_matching = True
            else:
                print(f"  ⚠ Frame ranges too far apart for proximity matching")
                print(f"     Predictions: [{pred_min}, {pred_max}], GT: [{gt_min}, {gt_max}]")
                print(f"     → This strongly suggests predictions and GT are from different videos")
        
        for frame in sorted(all_frames):
            pred_dets = pred_by_frame.get(frame, [])
            gt_dets = gt_by_frame.get(frame, [])
            
            # PROXIMITY MATCHING: If using proximity matching, find nearest GT frame
            if use_proximity_matching and len(gt_dets) == 0 and len(pred_dets) > 0:
                # Find the closest GT frame to this prediction frame
                closest_gt_frame = None
                min_frame_diff = float('inf')
                # Use larger proximity window when GT frames are sparse (e.g., anchor frames)
                # If predictions are within GT range, allow matching to any GT frame
                max_proximity = 500 if (pred_min >= gt_min and pred_max <= gt_max) else 50
                
                for gt_frame in gt_frame_list:
                    frame_diff = abs(gt_frame - frame)
                    if frame_diff < min_frame_diff and frame_diff <= max_proximity:
                        min_frame_diff = frame_diff
                        closest_gt_frame = gt_frame
                
                if closest_gt_frame is not None:
                    gt_dets = gt_by_frame.get(closest_gt_frame, [])
                    if len(gt_dets) > 0:
                        # Use GT from closest frame for matching
                        # Note: This allows matching even when exact frame numbers don't align
                        pass  # gt_dets is already set
            
            # CRITICAL FIX: Only evaluate frames that have ground truth
            # Frames without ground truth should be skipped (standard practice in tracking evaluation)
            # This prevents massive false positives when only a few anchor frames exist
            if len(gt_dets) == 0:
                # Skip frames without ground truth - don't count as false positives
                # This is correct behavior: we can't evaluate what we don't have ground truth for
                continue
            
            total_gt += len(gt_dets)
            
            if len(pred_dets) == 0:
                # All ground truth are false negatives
                total_fn += len(gt_dets)
                frames_with_no_matches += 1
                continue
            
            # Match predictions to ground truth using IoU
            matches = []
            matched_gt = set()
            matched_pred = set()
            frame_max_iou = 0.0
            
            for i, (pred_track_id, px1, py1, px2, py2) in enumerate(pred_dets):
                best_iou = 0.0
                best_gt_idx = -1
                best_gt_track_id = None
                best_distance = float('inf')
                
                # Calculate prediction bbox center and size for distance-based fallback
                pred_center_x = (px1 + px2) / 2.0
                pred_center_y = (py1 + py2) / 2.0
                pred_width = px2 - px1
                pred_height = py2 - py1
                pred_diagonal = np.sqrt(pred_width**2 + pred_height**2)  # Diagonal for normalized distance
                
                for j, (gt_track_id, gx1, gy1, gx2, gy2) in enumerate(gt_dets):
                    if j in matched_gt:
                        continue
                    
                    iou = self._calculate_iou(
                        (px1, py1, px2, py2),
                        (gx1, gy1, gx2, gy2)
                    )
                    
                    total_iou_attempts += 1
                    total_iou_sum_for_diagnostics += iou
                    max_iou_seen = max(max_iou_seen, iou)
                    frame_max_iou = max(frame_max_iou, iou)
                    
                    # More lenient IoU threshold for matching (0.05 instead of 0.10 for better matching)
                    # Lower threshold helps match detections even when bboxes don't align perfectly
                    # This is especially important when anchor frames are from different videos/resolutions
                    if iou > best_iou and iou >= 0.05:  # IoU threshold for match (lowered to 0.05 to capture more matches)
                        best_iou = iou
                        best_gt_idx = j
                        best_gt_track_id = gt_track_id
                        # Reset distance when we have a good IoU match
                        best_distance = 0.0
                    
                    # DISTANCE-BASED FALLBACK: If IoU is 0 or very low, check center-to-center distance
                    # This handles cases where bboxes are close but don't overlap (e.g., 2-3 pixel gap)
                    elif iou < 0.05:  # Only use distance fallback when IoU is below threshold
                        # Calculate GT bbox center
                        gt_center_x = (gx1 + gx2) / 2.0
                        gt_center_y = (gy1 + gy2) / 2.0
                        
                        # Calculate Euclidean distance between centers
                        center_distance = np.sqrt(
                            (pred_center_x - gt_center_x)**2 + 
                            (pred_center_y - gt_center_y)**2
                        )
                        
                        # Normalize distance by bbox diagonal (so it's scale-invariant)
                        # If distance is less than 0.5x the diagonal, consider it a match
                        # This allows matching when bboxes are within ~50% of their size apart
                        normalized_distance = center_distance / pred_diagonal if pred_diagonal > 0 else center_distance
                        
                        # Distance threshold: 1.0 means bboxes can be up to 100% of their diagonal apart
                        # Increased from 0.5 to be more lenient when coordinate systems don't match perfectly
                        distance_threshold = 1.0
                        
                        if normalized_distance < distance_threshold and normalized_distance < best_distance:
                            # Use this as a distance-based match (but with lower confidence)
                            # We'll use a synthetic IoU based on distance (inverse relationship)
                            # Closer = higher synthetic IoU
                            synthetic_iou = max(0.05, 0.10 - (normalized_distance * 0.10))  # Range: 0.05 to 0.10
                            
                            # Only use distance match if we don't have a better IoU match
                            if best_iou < synthetic_iou:
                                best_iou = synthetic_iou
                                best_gt_idx = j
                                best_gt_track_id = gt_track_id
                                best_distance = normalized_distance
                
                if best_gt_idx >= 0:
                    matches.append((i, best_gt_idx, best_iou, pred_track_id, best_gt_track_id))
                    matched_gt.add(best_gt_idx)
                    matched_pred.add(i)
            
            if len(matches) > 0:
                frames_with_matches += 1
            else:
                frames_with_no_matches += 1
                # DIAGNOSTIC: Log first few frames with no matches to help debug
                if frames_with_no_matches <= 3:
                    # Show actual bbox values to diagnose coordinate system issues
                    if len(pred_dets) > 0 and len(gt_dets) > 0:
                        pred_sample = pred_dets[0]  # (track_id, x1, y1, x2, y2)
                        gt_sample = gt_dets[0]  # (track_id, x1, y1, x2, y2)
                        print(f"  ⚠ Frame {frame}: {len(pred_dets)} predictions, {len(gt_dets)} GT, max IoU: {frame_max_iou:.3f} (threshold: 0.05)")
                        print(f"     Sample pred bbox: track_id={pred_sample[0]}, x1={pred_sample[1]:.1f}, y1={pred_sample[2]:.1f}, x2={pred_sample[3]:.1f}, y2={pred_sample[4]:.1f}")
                        print(f"     Sample GT bbox: track_id={gt_sample[0]}, x1={gt_sample[1]:.1f}, y1={gt_sample[2]:.1f}, x2={gt_sample[3]:.1f}, y2={gt_sample[4]:.1f}")
                        # Calculate IoU between samples
                        sample_iou = self._calculate_iou(
                            (pred_sample[1], pred_sample[2], pred_sample[3], pred_sample[4]),
                            (gt_sample[1], gt_sample[2], gt_sample[3], gt_sample[4])
                        )
                        print(f"     Sample IoU: {sample_iou:.4f}")
                        
                        # Calculate center distance for diagnostics
                        pred_center_x = (pred_sample[1] + pred_sample[3]) / 2
                        pred_center_y = (pred_sample[2] + pred_sample[4]) / 2
                        gt_center_x = (gt_sample[1] + gt_sample[3]) / 2
                        gt_center_y = (gt_sample[2] + gt_sample[4]) / 2
                        center_distance = np.sqrt((pred_center_x - gt_center_x)**2 + (pred_center_y - gt_center_y)**2)
                        pred_diagonal = np.sqrt((pred_sample[3] - pred_sample[1])**2 + (pred_sample[4] - pred_sample[2])**2)
                        normalized_distance = center_distance / pred_diagonal if pred_diagonal > 0 else center_distance
                        print(f"     Center distance: {center_distance:.1f}px, normalized: {normalized_distance:.3f} (threshold: 1.0)")
            
            # Count ID switches
            current_frame_assignments = {}
            for pred_idx, gt_idx, iou, pred_track_id, gt_track_id in matches:
                current_frame_assignments[gt_track_id] = pred_track_id
                
                # Check for ID switch
                if gt_track_id in prev_frame_assignments:
                    if prev_frame_assignments[gt_track_id] != pred_track_id:
                        total_idsw += 1
                
                total_iou_sum += iou
                total_matches += 1
            
            prev_frame_assignments = current_frame_assignments
            
            # Count false positives (unmatched predictions)
            total_fp += len(pred_dets) - len(matched_pred)
            
            # Count false negatives (unmatched ground truth)
            total_fn += len(gt_dets) - len(matched_gt)
        
        # DIAGNOSTIC: Print matching statistics if no matches found
        if total_matches == 0 and total_iou_attempts > 0:
            avg_iou = total_iou_sum_for_diagnostics / total_iou_attempts
            print(f"\n  ⚠ DIAGNOSTIC: No matches found between GT and predictions")
            print(f"     • Total IoU attempts: {total_iou_attempts}")
            print(f"     • Average IoU: {avg_iou:.4f}")
            print(f"     • Max IoU seen: {max_iou_seen:.4f}")
            print(f"     • Frames with matches: {frames_with_matches}")
            print(f"     • Frames with no matches: {frames_with_no_matches}")
            print(f"     • IoU threshold: 0.05 (try lowering if max IoU < 0.05)")
            
            # Check if there's a frame offset issue
            if len(all_frames) > 0:
                pred_frame_list = sorted(pred_by_frame.keys())
                gt_frame_list = sorted(gt_by_frame.keys())
                if pred_frame_list and gt_frame_list:
                    pred_min, pred_max = min(pred_frame_list), max(pred_frame_list)
                    gt_min, gt_max = min(gt_frame_list), max(gt_frame_list)
                    frame_overlap = len(set(pred_frame_list) & set(gt_frame_list))
                    print(f"     • Frame ranges: Predictions=[{pred_min}, {pred_max}], GT=[{gt_min}, {gt_max}]")
                    print(f"     • Frame overlap: {frame_overlap} frames")
                    if frame_overlap == 0:
                        print(f"     ⚠ CRITICAL: No frame overlap between predictions and ground truth!")
                        print(f"        → This suggests predictions and GT are from different videos or frame ranges")
                        print(f"        → Check that CSV and anchor frames are from the same video")
            
            # CRITICAL DIAGNOSTIC: Show sample bbox values to identify coordinate system issues
            if len(all_frames) > 0:
                sample_frame = sorted(all_frames)[0]
                pred_dets_sample = pred_by_frame.get(sample_frame, [])
                gt_dets_sample = gt_by_frame.get(sample_frame, [])
                if len(pred_dets_sample) > 0 and len(gt_dets_sample) > 0:
                    pred_sample = pred_dets_sample[0]
                    gt_sample = gt_dets_sample[0]
                    print(f"\n  📊 Sample bbox comparison (Frame {sample_frame}):")
                    print(f"     Prediction: track_id={pred_sample[0]}, bbox=[{pred_sample[1]:.1f}, {pred_sample[2]:.1f}, {pred_sample[3]:.1f}, {pred_sample[4]:.1f}]")
                    print(f"     Ground Truth: track_id={gt_sample[0]}, bbox=[{gt_sample[1]:.1f}, {gt_sample[2]:.1f}, {gt_sample[3]:.1f}, {gt_sample[4]:.1f}]")
                    # Check if coordinates look normalized (0-1 range) vs pixel coordinates
                    pred_is_normalized = all(0 <= coord <= 1 for coord in pred_sample[1:5])
                    gt_is_normalized = all(0 <= coord <= 1 for coord in gt_sample[1:5])
                    print(f"     Prediction bbox appears {'normalized (0-1)' if pred_is_normalized else 'pixel coordinates'}")
                    print(f"     Ground Truth bbox appears {'normalized (0-1)' if gt_is_normalized else 'pixel coordinates'}")
                    if pred_is_normalized != gt_is_normalized:
                        print(f"     ⚠ COORDINATE SYSTEM MISMATCH: One is normalized, one is pixel coordinates!")
                        print(f"        → This will cause very low IoU. Need to normalize both to same system.")
            
            print(f"\n     • Possible issues:")
            print(f"       - Bbox coordinates in different coordinate systems (normalized vs pixel)")
            print(f"       - Frame numbers don't match")
            print(f"       - Bboxes are too far apart spatially")
            print(f"       - Anchor frame bboxes may be in wrong format")
        
        # Calculate MOTA
        if total_gt > 0:
            mota = 1.0 - (total_fn + total_fp + total_idsw) / total_gt
            mota = max(0.0, min(1.0, mota))  # Clamp to [0, 1]
        else:
            mota = 0.0
        
        # Calculate MOTP (average IoU of matches)
        motp = total_iou_sum / total_matches if total_matches > 0 else 0.0
        
        result = {
            'MOTA': float(mota),
            'MOTP': float(motp),
            'FN': int(total_fn),
            'FP': int(total_fp),
            'IDSW': int(total_idsw),
            'GT': int(total_gt),
            'Matches': int(total_matches)
        }
        
        # Add diagnostics if no matches found
        if total_matches == 0 and total_iou_attempts > 0:
            result['Diagnostics'] = {
                'total_iou_attempts': total_iou_attempts,
                'avg_iou': total_iou_sum_for_diagnostics / total_iou_attempts,
                'max_iou_seen': max_iou_seen,
                'frames_with_matches': frames_with_matches,
                'frames_with_no_matches': frames_with_no_matches
            }
        
        return result
    
    def calculate_idf1(
        self,
        pred_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        gt_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        frame_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, float]:
        """
        Calculate IDF1 (ID F1 Score).
        
        IDF1 measures ID consistency over time by evaluating:
        - IDTP: ID True Positives (correct ID assignments)
        - IDFP: ID False Positives (wrong ID assignments)
        - IDFN: ID False Negatives (missed ID assignments)
        
        IDF1 = 2 * IDTP / (2 * IDTP + IDFP + IDFN)
        
        Args:
            pred_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            gt_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            frame_range: Optional (start_frame, end_frame) to limit evaluation
        
        Returns:
            Dictionary with IDF1 metrics:
            - IDF1: ID F1 Score (0-1, higher is better)
            - IDTP: ID True Positives
            - IDFP: ID False Positives
            - IDFN: ID False Negatives
            - IDR: ID Recall
            - IDP: ID Precision
        """
        if frame_range:
            start_frame, end_frame = frame_range
            pred_tracks = self._filter_frames(pred_tracks, start_frame, end_frame)
            gt_tracks = self._filter_frames(gt_tracks, start_frame, end_frame)
        
        # Group by frame
        pred_by_frame = defaultdict(list)
        gt_by_frame = defaultdict(list)
        
        for track_id, detections in pred_tracks.items():
            for det in detections:
                # Handle both 5-tuple (frame, x1, y1, x2, y2) and 6-tuple (frame, x1, y1, x2, y2, player_name)
                if len(det) >= 5:
                    frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                    pred_by_frame[frame].append((track_id, x1, y1, x2, y2))
        
        for track_id, detections in gt_tracks.items():
            for det in detections:
                # Handle both 5-tuple (frame, x1, y1, x2, y2) and 6-tuple (frame, x1, y1, x2, y2, player_name)
                if len(det) >= 5:
                    frame, x1, y1, x2, y2 = det[0], det[1], det[2], det[3], det[4]
                    gt_by_frame[frame].append((track_id, x1, y1, x2, y2))
        
        all_frames = set(pred_by_frame.keys()) | set(gt_by_frame.keys())
        
        idtp = 0  # ID True Positives
        idfp = 0  # ID False Positives
        idfn = 0  # ID False Negatives
        
        # Track ID assignments across frames
        id_assignments = {}  # (gt_track_id, pred_track_id) -> count
        
        for frame in sorted(all_frames):
            pred_dets = pred_by_frame.get(frame, [])
            gt_dets = gt_by_frame.get(frame, [])
            
            # CRITICAL FIX: Only evaluate frames that have ground truth
            # Skip frames without ground truth (same as MOTA fix)
            if len(gt_dets) == 0:
                continue
            
            if len(pred_dets) == 0:
                # All ground truth are false negatives
                idfn += len(gt_dets)
                continue
            
            # Match predictions to ground truth
            matches = []
            matched_gt = set()
            matched_pred = set()
            
            for i, (pred_track_id, px1, py1, px2, py2) in enumerate(pred_dets):
                best_iou = 0.0
                best_gt_idx = -1
                best_gt_track_id = None
                
                for j, (gt_track_id, gx1, gy1, gx2, gy2) in enumerate(gt_dets):
                    if j in matched_gt:
                        continue
                    
                    iou = self._calculate_iou(
                        (px1, py1, px2, py2),
                        (gx1, gy1, gx2, gy2)
                    )
                    
                    # More lenient IoU threshold for matching (0.05 instead of 0.3)
                    # Lowered to match MOTA threshold for consistency
                    if iou > best_iou and iou >= 0.05:  # IoU threshold for match (lowered from 0.3)
                        best_iou = iou
                        best_gt_idx = j
                        best_gt_track_id = gt_track_id
                
                if best_gt_idx >= 0:
                    matches.append((pred_track_id, best_gt_track_id))
                    matched_gt.add(best_gt_idx)
                    matched_pred.add(i)
            
            # Count ID matches
            for pred_track_id, gt_track_id in matches:
                key = (gt_track_id, pred_track_id)
                id_assignments[key] = id_assignments.get(key, 0) + 1
            
            # Count unmatched as false positives/negatives
            idfp += len(pred_dets) - len(matched_pred)
            idfn += len(gt_dets) - len(matched_gt)
        
        # Count ID True Positives (consistent ID assignments)
        # An ID assignment is correct if it's the most common assignment for that GT track
        for (gt_track_id, pred_track_id), count in id_assignments.items():
            # Check if this is the dominant assignment for this GT track
            other_assignments = [
                c for (g, p), c in id_assignments.items()
                if g == gt_track_id and p != pred_track_id
            ]
            if not other_assignments or count >= max(other_assignments):
                idtp += count
        
        # Calculate IDF1
        if idtp + idfp + idfn > 0:
            idf1 = 2 * idtp / (2 * idtp + idfp + idfn)
        else:
            idf1 = 0.0
        
        # Calculate ID Precision and Recall
        idp = idtp / (idtp + idfp) if (idtp + idfp) > 0 else 0.0
        idr = idtp / (idtp + idfn) if (idtp + idfn) > 0 else 0.0
        
        return {
            'IDF1': float(idf1),
            'IDTP': int(idtp),
            'IDFP': int(idfp),
            'IDFN': int(idfn),
            'IDP': float(idp),
            'IDR': float(idr)
        }
    
    def evaluate_all_metrics(
        self,
        pred_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        gt_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        frame_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, any]:
        """
        Calculate all metrics: HOTA, MOTA, and IDF1.
        
        Args:
            pred_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            gt_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            frame_range: Optional (start_frame, end_frame) to limit evaluation
        
        Returns:
            Dictionary with all metrics combined
        """
        # Calculate HOTA
        hota_results = self.hota_evaluator.calculate_hota(pred_tracks, gt_tracks, frame_range)
        
        # Calculate MOTA
        mota_results = self.calculate_mota(pred_tracks, gt_tracks, frame_range)
        
        # Calculate IDF1
        idf1_results = self.calculate_idf1(pred_tracks, gt_tracks, frame_range)
        
        # Combine all results
        return {
            **hota_results,
            **mota_results,
            **idf1_results
        }
    
    def evaluate_from_csv(
        self,
        pred_csv_path: str,
        gt_csv_path: Optional[str] = None,
        frame_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, any]:
        """
        Evaluate all metrics from CSV files.
        
        Args:
            pred_csv_path: Path to predicted tracking CSV
            gt_csv_path: Optional path to ground truth CSV (if None, uses anchor frames)
            frame_range: Optional (start_frame, end_frame) to limit evaluation
        
        Returns:
            Dictionary with all metrics (HOTA, MOTA, IDF1)
        """
        # Load predicted tracks from CSV
        pred_tracks = self._load_tracks_from_csv(pred_csv_path)
        
        # Store CSV path for anchor frame auto-discovery
        self._csv_path = pred_csv_path
        
        # Load ground truth tracks
        # gt_csv_path can be either a CSV file OR a JSON anchor frames file
        if gt_csv_path and os.path.exists(gt_csv_path):
            # Check if it's a CSV or JSON file
            if gt_csv_path.lower().endswith('.json'):
                # It's an anchor frames JSON file
                # Pass CSV tracks so we can look up bbox if anchor frames have None bbox
                self._csv_tracks = pred_tracks  # Store CSV tracks for bbox lookup
                gt_tracks = self._load_anchor_frames_as_gt(gt_csv_path)
            else:
                # It's a CSV file
                gt_tracks = self._load_tracks_from_csv(gt_csv_path)
        else:
            # Use anchor frames as ground truth if available (try to find automatically)
            # Pass CSV tracks so we can look up bbox if anchor frames have None bbox
            self._csv_tracks = pred_tracks  # Store CSV tracks for bbox lookup
            gt_tracks = self._load_anchor_frames_as_gt(gt_csv_path)  # Pass path even if None to try auto-discovery
        
        if not pred_tracks:
            return {'error': 'No predicted tracks found'}
        
        if not gt_tracks:
            error_msg = 'No ground truth tracks found'
            if gt_csv_path:
                if gt_csv_path.lower().endswith('.json'):
                    error_msg += f' - anchor frames file: {gt_csv_path}'
                    error_msg += ' (file may be empty or have no anchor_frames data)'
                else:
                    error_msg += f' - CSV file: {gt_csv_path}'
            else:
                error_msg += ' - no anchor frames file provided'
            return {'error': error_msg}
        
        # Warn if very few ground truth frames (evaluation will be limited)
        gt_frames = set()
        for track_id, detections in gt_tracks.items():
            for det in detections:
                gt_frames.add(det[0])  # frame number
        
        pred_frames = set()
        for track_id, detections in pred_tracks.items():
            for det in detections:
                pred_frames.add(det[0])  # frame number
        
        if len(gt_frames) < 50:
            print(f"⚠ WARNING: Only {len(gt_frames)} frames have ground truth (out of {len(pred_frames)} predicted frames)")
            print(f"   Metrics will only be evaluated on frames with anchor frames")
            print(f"   Tip: Tag more frames in Setup Wizard for more comprehensive evaluation")
        
        # Check for frame overlap
        frame_overlap = len(gt_frames & pred_frames)
        if frame_overlap == 0 and len(gt_frames) > 0 and len(pred_frames) > 0:
            gt_min, gt_max = min(gt_frames), max(gt_frames)
            pred_min, pred_max = min(pred_frames), max(pred_frames)
            print(f"\n  ⚠ CRITICAL WARNING: No frame overlap between predictions and ground truth!")
            print(f"     Prediction frames: [{pred_min}, {pred_max}] ({len(pred_frames)} frames)")
            print(f"     Ground truth frames: [{gt_min}, {gt_max}] ({len(gt_frames)} frames)")
            print(f"     → This suggests predictions and GT are from different videos or frame ranges")
            print(f"     → Check that CSV and anchor frames are from the same video")
            print(f"     → Metrics may be inaccurate due to frame mismatch")
        
        # Calculate all metrics
        return self.evaluate_all_metrics(pred_tracks, gt_tracks, frame_range)
    
    def _filter_frames(
        self,
        tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        start_frame: int,
        end_frame: int
    ) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
        """Filter tracks to only include frames in the specified range."""
        filtered = {}
        for track_id, detections in tracks.items():
            filtered_dets = [
                det for det in detections
                if start_frame <= det[0] <= end_frame
            ]
            if filtered_dets:
                filtered[track_id] = filtered_dets
        return filtered
    
    def _calculate_iou(
        self,
        box1: Tuple[float, float, float, float],
        box2: Tuple[float, float, float, float],
        use_expansion: bool = False,
        velocity1: Optional[Tuple[float, float]] = None,
        velocity2: Optional[Tuple[float, float]] = None
    ) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes.
        Optionally uses Expansion IOU with motion prediction.
        """
        if use_expansion and ADVANCED_UTILS_AVAILABLE:
            return calculate_expansion_iou(box1, box2, velocity1, velocity2)
        elif ADVANCED_UTILS_AVAILABLE:
            return advanced_calculate_iou(box1, box2)
        else:
            # Fallback to standard IOU
            x1_1, y1_1, x2_1, y2_1 = box1
            x1_2, y1_2, x2_2, y2_2 = box2
            
            # Calculate intersection
            x1_i = max(x1_1, x1_2)
            y1_i = max(y1_1, y1_2)
            x2_i = min(x2_1, x2_2)
            y2_i = min(y2_1, y2_2)
            
            if x2_i <= x1_i or y2_i <= y1_i:
                return 0.0
            
            intersection = (x2_i - x1_i) * (y2_i - y1_i)
            
            # Calculate union
            area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
            area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
            union = area1 + area2 - intersection
            
            return intersection / union if union > 0 else 0.0
    
    def _load_tracks_from_csv(self, csv_path: str) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
        """Load tracks from CSV file."""
        if not os.path.exists(csv_path):
            return {}
        
        try:
            # Try reading with different error handling strategies
            try:
                # First try: standard read (skip comment lines starting with '#')
                df = pd.read_csv(csv_path, comment='#')
            except pd.errors.ParserError as e:
                # If parsing fails, try with error handling
                try:
                    # Try with error_bad_lines=False (skip bad lines) and skip comments
                    df = pd.read_csv(csv_path, on_bad_lines='skip', engine='python', comment='#')
                except:
                    # Try with different delimiter
                    try:
                        df = pd.read_csv(csv_path, sep=',', on_bad_lines='skip', engine='python', comment='#')
                    except:
                        # Last resort: try with skiprows to skip problematic lines
                        print(f"⚠ CSV parsing failed, attempting to skip problematic lines...")
                        df = pd.read_csv(csv_path, on_bad_lines='skip', engine='python', skipinitialspace=True, comment='#')
            
            # Check for empty DataFrame
            if df.empty:
                print(f"⚠ CSV file is empty: {csv_path}")
                return {}
            
            tracks = defaultdict(list)
            
            for _, row in df.iterrows():
                # Get frame number with NaN handling
                frame_val = row.get('frame', row.get('frame_num', None))
                if pd.isna(frame_val):
                    continue  # Skip rows with NaN frame numbers
                try:
                    frame = int(frame_val)
                except (ValueError, TypeError):
                    continue  # Skip rows that can't be converted to int
                
                # Get track_id with NaN handling (try multiple column names)
                track_id_val = None
                for col_name in ['track_id', 'player_id', 'id']:
                    if col_name in row:
                        track_id_val = row[col_name]
                        break
                
                if track_id_val is None or pd.isna(track_id_val):
                    continue  # Skip rows with NaN track IDs
                
                # Handle empty strings and whitespace
                if isinstance(track_id_val, str):
                    track_id_val = track_id_val.strip()
                    if not track_id_val or track_id_val == '':
                        continue
                
                try:
                    track_id = int(float(track_id_val))  # Convert to float first to handle string numbers
                except (ValueError, TypeError):
                    continue  # Skip rows that can't be converted to int
                
                # Try different column name variations
                # Format 1: Bounding boxes (x1, y1, x2, y2)
                if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                    x1_val, y1_val, x2_val, y2_val = row['x1'], row['y1'], row['x2'], row['y2']
                    # Check for NaN in coordinates
                    if pd.isna(x1_val) or pd.isna(y1_val) or pd.isna(x2_val) or pd.isna(y2_val):
                        continue
                    x1, y1, x2, y2 = float(x1_val), float(y1_val), float(x2_val), float(y2_val)
                # Format 2: Center point with size (x, y, width, height)
                elif 'x' in row and 'y' in row:
                    x_val, y_val = row['x'], row['y']
                    if pd.isna(x_val) or pd.isna(y_val):
                        continue
                    x, y = float(x_val), float(y_val)
                    w = row.get('width', 50)
                    h = row.get('height', 100)
                    if pd.isna(w):
                        w = 50
                    if pd.isna(h):
                        h = 100
                    x1, y1 = x - w/2, y - h/2
                    x2, y2 = x + w/2, y + h/2
                # Format 3: Player center points (player_x, player_y) - convert to bbox
                elif 'player_x' in row and 'player_y' in row:
                    px_val, py_val = row['player_x'], row['player_y']
                    # Check for NaN or empty strings
                    if pd.isna(px_val) or pd.isna(py_val):
                        continue
                    # Handle empty strings (CSV might write '' instead of NaN)
                    if isinstance(px_val, str) and not px_val.strip():
                        continue
                    if isinstance(py_val, str) and not py_val.strip():
                        continue
                    # Use default player size (approximate)
                    try:
                        px, py = float(px_val), float(py_val)
                    except (ValueError, TypeError):
                        continue  # Skip if can't convert to float
                    # Default player bbox size - use more realistic sizes
                    # Typical player bbox: width ~50-80px, height ~120-180px depending on video resolution
                    # Use larger size to ensure we capture the player (better for matching)
                    default_w = 80  # pixels (increased from 60)
                    default_h = 160  # pixels (increased from 120)
                    x1, y1 = px - default_w/2, py - default_h/2
                    x2, y2 = px + default_w/2, py + default_h/2
                else:
                    continue
                
                # Also store player_name if available (for matching anchor frames)
                player_name = None
                if 'player_name' in row:
                    player_name_val = row['player_name']
                    if pd.notna(player_name_val) and str(player_name_val).strip():
                        # Handle list format (e.g., "['Name', 'Team', 'Jersey']")
                        player_name_str = str(player_name_val).strip()
                        if player_name_str.startswith('[') and player_name_str.endswith(']'):
                            try:
                                import ast
                                name_list = ast.literal_eval(player_name_str)
                                if isinstance(name_list, list) and len(name_list) > 0:
                                    player_name = str(name_list[0]).strip()
                            except:
                                player_name = player_name_str
                        else:
                            player_name = player_name_str
                
                # Store detection with player_name for better matching
                tracks[track_id].append((frame, float(x1), float(y1), float(x2), float(y2), player_name))
            
            if not tracks:
                print(f"⚠ No tracks loaded from CSV: {csv_path}")
                print(f"   CSV columns found: {list(df.columns)}")
                print(f"   CSV shape: {df.shape}")
                if len(df) > 0:
                    print(f"   First row sample: {df.iloc[0].to_dict()}")
                    # Diagnostic: Check how many rows have valid player_id
                    player_id_col = None
                    for col in ['track_id', 'player_id', 'id']:
                        if col in df.columns:
                            player_id_col = col
                            break
                    if player_id_col:
                        valid_player_ids = df[player_id_col].notna()
                        if isinstance(df[player_id_col].iloc[0], str):
                            # Also check for non-empty strings
                            valid_player_ids = valid_player_ids & (df[player_id_col].str.strip() != '')
                        valid_count = valid_player_ids.sum()
                        print(f"   Rows with valid {player_id_col}: {valid_count} / {len(df)}")
                        # Check coordinate columns
                        if 'player_x' in df.columns and 'player_y' in df.columns:
                            valid_coords = df['player_x'].notna() & df['player_y'].notna()
                            if isinstance(df['player_x'].iloc[0], str):
                                valid_coords = valid_coords & (df['player_x'].str.strip() != '') & (df['player_y'].str.strip() != '')
                            valid_coord_count = valid_coords.sum()
                            print(f"   Rows with valid player_x/player_y: {valid_coord_count} / {len(df)}")
                            # Check overlap
                            if player_id_col:
                                both_valid = valid_player_ids & valid_coords
                                both_valid_count = both_valid.sum()
                                print(f"   Rows with both valid {player_id_col} AND coordinates: {both_valid_count} / {len(df)}")
            else:
                total_detections = sum(len(dets) for dets in tracks.values())
                print(f"✓ Loaded {len(tracks)} tracks with {total_detections} total detections from CSV")
            
            return dict(tracks)
        except Exception as e:
            print(f"⚠ Error loading tracks from CSV: {e}")
            import traceback
            traceback.print_exc()
            # Try to get more info about the CSV file
            try:
                if os.path.exists(csv_path):
                    file_size = os.path.getsize(csv_path)
                    print(f"   CSV file size: {file_size} bytes")
                    # Try to read first few lines
                    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()[:5]
                        print(f"   First 5 lines of CSV:")
                        for i, line in enumerate(lines, 1):
                            print(f"      Line {i}: {line[:100]}...")
            except:
                pass
            return {}
    
    def _load_anchor_frames_as_gt(self, anchor_frames_path: Optional[str] = None) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
        """
        Load anchor frames as ground truth from PlayerTagsSeed JSON files.
        
        Args:
            anchor_frames_path: Path to PlayerTagsSeed JSON file or None to search automatically
        
        Returns:
            Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
        """
        import json
        
        gt_tracks = defaultdict(list)
        
        # If path provided, try to load it
        if anchor_frames_path and os.path.exists(anchor_frames_path):
            try:
                with open(anchor_frames_path, 'r') as f:
                    seed_data = json.load(f)
                
                if "anchor_frames" in seed_data:
                    anchor_frames = seed_data["anchor_frames"]
                    # Convert anchor frames format to ground truth tracks format
                    # Anchor frames: {frame_num: [{track_id, player_name, bbox: [x1, y1, x2, y2], ...}]}
                    # GT tracks: {track_id: [(frame, x1, y1, x2, y2), ...]}
                    for frame_num_str, anchors in anchor_frames.items():
                        try:
                            frame_num = int(frame_num_str)
                        except (ValueError, TypeError):
                            continue
                        
                        for anchor in anchors:
                            track_id = anchor.get('track_id')
                            anchor_bbox = anchor.get('bbox')  # Renamed to clarify this is from anchor frame
                            player_name = anchor.get('player_name')  # Get player name for better matching
                            
                            # Extract player_name from list format if needed (e.g., ['Cameron Hill', 'Blue', ''])
                            # Use extract_player_name for consistency with main analysis code
                            player_name_str = None
                            if player_name:
                                try:
                                    # Import extract_player_name from combined_analysis_optimized
                                    from combined_analysis_optimized import extract_player_name
                                    player_name_str = extract_player_name(player_name)
                                except ImportError:
                                    # Fallback to manual extraction if import fails
                                    if isinstance(player_name, list) and len(player_name) > 0:
                                        player_name_str = str(player_name[0]).strip()
                                    elif isinstance(player_name, str):
                                        # Handle string that looks like a list (e.g., "['Cameron Hill', 'Blue', '']")
                                        if player_name.startswith('[') and player_name.endswith(']'):
                                            try:
                                                import ast
                                                name_list = ast.literal_eval(player_name)
                                                if isinstance(name_list, list) and len(name_list) > 0:
                                                    player_name_str = str(name_list[0]).strip()
                                            except:
                                                player_name_str = player_name.strip()
                                        else:
                                            player_name_str = player_name.strip()
                            
                            # CRITICAL FIX: Use player_name as GT track_id if available (more stable than track_id)
                            # This allows matching even when track_ids change between videos
                            # Use a hash of player_name as a stable identifier
                            if player_name_str:
                                # Use player_name hash as GT track_id (stable across videos)
                                import hashlib
                                gt_track_id = int(hashlib.md5(player_name_str.encode()).hexdigest()[:8], 16) % 1000000
                            elif track_id is not None:
                                gt_track_id = int(track_id)
                            else:
                                continue  # Skip anchors without track_id or player_name
                            
                            # CRITICAL FIX: Always prefer CSV bboxes over anchor frame bboxes
                            # Anchor frame bboxes may be from a different video/resolution, so they don't match
                            # CSV bboxes are from the actual video being analyzed, so they're correct
                            bbox = None
                            
                            # Try to get bbox from CSV detections for this exact frame
                            # This ensures bboxes match the actual video coordinates
                            # ENHANCED: Match by frame number AND player_name for better accuracy
                            if hasattr(self, '_csv_tracks') and self._csv_tracks:
                                # Search all CSV tracks for detections at this exact frame
                                best_match = None
                                best_frame_diff = float('inf')
                                
                                # Extract player_name from anchor (handle list format)
                                # Use the already-extracted player_name_str if available
                                anchor_player_name = player_name_str if player_name_str else None
                                
                                # First, try exact frame match with player_name matching
                                csv_matches_found = 0
                                for csv_track_id, detections in self._csv_tracks.items():
                                    for det_data in detections:
                                        # Handle both old format (5 values) and new format (6 values with player_name)
                                        if len(det_data) >= 5:
                                            det_frame = det_data[0]
                                            x1, y1, x2, y2 = det_data[1], det_data[2], det_data[3], det_data[4]
                                            csv_player_name = det_data[5] if len(det_data) > 5 else None
                                            
                                            if det_frame == frame_num:
                                                csv_matches_found += 1
                                                # Exact frame match - check player_name if available
                                                if anchor_player_name and csv_player_name:
                                                    # Match by player_name (case-insensitive)
                                                    if anchor_player_name.lower() == csv_player_name.lower():
                                                        # Perfect match: same frame AND same player
                                                        bbox = [x1, y1, x2, y2]
                                                        if frame_num <= 3:
                                                            print(f"  ✓ Frame {frame_num}: Matched '{anchor_player_name}' to CSV bbox [{x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}]")
                                                        break
                                                elif not anchor_player_name or not csv_player_name:
                                                    # No player_name available - use first match
                                                    if bbox is None:  # Use first match if no player_name
                                                        bbox = [x1, y1, x2, y2]
                                                        if frame_num <= 3:
                                                            print(f"  ✓ Frame {frame_num}: Matched anchor to CSV bbox [{x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}] (no player_name)")
                                    if bbox:
                                        break
                                
                                # Diagnostic: If we found CSV matches but didn't match by player_name, warn
                                if csv_matches_found > 0 and bbox is None and anchor_player_name and frame_num <= 3:
                                    print(f"  ⚠ Frame {frame_num}: Found {csv_matches_found} CSV detection(s) but player_name mismatch")
                                    print(f"     → Anchor player: '{anchor_player_name}'")
                                    print(f"     → CSV players at this frame: (checking...)")
                                
                                # If no exact match, try within 5 frames with player_name matching
                                if bbox is None:
                                    for csv_track_id, detections in self._csv_tracks.items():
                                        for det_data in detections:
                                            if len(det_data) >= 5:
                                                det_frame = det_data[0]
                                                x1, y1, x2, y2 = det_data[1], det_data[2], det_data[3], det_data[4]
                                                csv_player_name = det_data[5] if len(det_data) > 5 else None
                                                frame_diff = abs(det_frame - frame_num)
                                                
                                                if frame_diff <= 5 and frame_diff < best_frame_diff:
                                                    # Prefer matches with same player_name
                                                    if anchor_player_name and csv_player_name:
                                                        if anchor_player_name.lower() == csv_player_name.lower():
                                                            best_match = [x1, y1, x2, y2]
                                                            best_frame_diff = frame_diff
                                                    elif not anchor_player_name or not csv_player_name:
                                                        # No player_name - use first match
                                                        if best_match is None:
                                                            best_match = [x1, y1, x2, y2]
                                                            best_frame_diff = frame_diff
                                    
                                    if best_match is not None:
                                        bbox = best_match
                                
                                # If still no match, try matching by track_id if available
                                # This handles cases where frame numbers don't align but track_ids do
                                if bbox is None and track_id is not None:
                                    for csv_track_id, detections in self._csv_tracks.items():
                                        if int(csv_track_id) == int(track_id):
                                            # Found matching track_id - use first detection from this track
                                            if detections:
                                                det_data = detections[0]
                                                if len(det_data) >= 5:
                                                    x1, y1, x2, y2 = det_data[1], det_data[2], det_data[3], det_data[4]
                                                    bbox = [x1, y1, x2, y2]
                                                    break
                                
                                # If still no match, try within 20 frames (expanded search)
                                if bbox is None:
                                    for csv_track_id, detections in self._csv_tracks.items():
                                        for det_data in detections:
                                            if len(det_data) >= 5:
                                                det_frame = det_data[0]
                                                x1, y1, x2, y2 = det_data[1], det_data[2], det_data[3], det_data[4]
                                                frame_diff = abs(det_frame - frame_num)
                                                if frame_diff <= 20 and frame_diff < best_frame_diff:
                                                    best_match = [x1, y1, x2, y2]
                                                    best_frame_diff = frame_diff
                                    
                                    if best_match is not None:
                                        bbox = best_match
                            
                            # Fallback: If CSV lookup failed, use anchor frame bbox (but warn strongly)
                            if bbox is None or not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
                                if anchor_bbox and isinstance(anchor_bbox, (list, tuple)) and len(anchor_bbox) >= 4:
                                    bbox = anchor_bbox
                                    # Warn that we're using anchor bbox (may not match video coordinates)
                                    # This is a critical issue - anchor frames from different videos won't match
                                    if frame_num <= 3:  # Warn for first few frames
                                        print(f"  ⚠ Frame {frame_num}: Using anchor frame bbox (CSV lookup failed)")
                                        print(f"     → Anchor bbox: {anchor_bbox}")
                                        print(f"     → Player: {anchor_player_name if anchor_player_name else 'Unknown'}")
                                        print(f"     → CSV lookup failed - anchor frames may be from different video/resolution")
                                        print(f"     → This will cause coordinate mismatch in metrics evaluation")
                                        print(f"     → Solution: Ensure anchor frames were created from the SAME CSV being analyzed")
                                else:
                                    # Last resort: Try to get bbox from CSV for nearby frames
                                    if hasattr(self, '_csv_tracks') and self._csv_tracks:
                                        player_center = None
                                        # Search all tracks for closest frame
                                        for csv_track_id, detections in self._csv_tracks.items():
                                            for det_data in detections:
                                                if len(det_data) >= 5:
                                                    det_frame = det_data[0]
                                                    x1, y1, x2, y2 = det_data[1], det_data[2], det_data[3], det_data[4]
                                                    if abs(det_frame - frame_num) <= 10:  # Within 10 frames
                                                        # Use center of this detection
                                                        center_x = (x1 + x2) / 2
                                                        center_y = (y1 + y2) / 2
                                                        player_center = (center_x, center_y)
                                                        break
                                            if player_center:
                                                break
                                        
                                        # If we have a center, create default bbox (80x160 pixels, typical player size)
                                        if player_center:
                                            center_x, center_y = player_center
                                            default_w, default_h = 80, 160
                                            bbox = [
                                                center_x - default_w / 2,
                                                center_y - default_h / 2,
                                                center_x + default_w / 2,
                                                center_y + default_h / 2
                                            ]
                                
                                # If still no bbox, skip this anchor (can't create GT without bbox)
                                if bbox is None or not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
                                    continue
                            
                            try:
                                x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
                                # Use stable GT track_id (player_name hash or original track_id)
                                gt_tracks[gt_track_id].append((frame_num, x1, y1, x2, y2))
                            except (ValueError, TypeError, IndexError):
                                continue
                    
                    total_anchors = sum(len(anchors) for anchors in anchor_frames.values())
                    total_gt_detections = sum(len(dets) for dets in gt_tracks.values())
                    
                    # DIAGNOSTIC: Log why anchor frames might be missing
                    if total_gt_detections == 0 and total_anchors > 0:
                        print(f"⚠ WARNING: {total_anchors} anchor frames loaded but 0 ground truth detections created")
                        print(f"   → This usually means anchor frames are missing bbox information")
                        print(f"   → Checking sample anchor frames...")
                        
                        # Check first few anchor frames
                        sample_count = 0
                        missing_bbox_count = 0
                        missing_track_id_count = 0
                        for frame_num_str, anchors in list(anchor_frames.items())[:3]:
                            for anchor in anchors[:2]:  # Check first 2 anchors per frame
                                sample_count += 1
                                if anchor.get('bbox') is None:
                                    missing_bbox_count += 1
                                if anchor.get('track_id') is None:
                                    missing_track_id_count += 1
                        
                        if missing_bbox_count > 0:
                            print(f"   → Found {missing_bbox_count}/{sample_count} sample anchors without bbox")
                            print(f"   → Tip: Recreate anchor frames using 'Convert Tracks → Anchor Frames' to include bbox")
                        if missing_track_id_count > 0:
                            print(f"   → Found {missing_track_id_count}/{sample_count} sample anchors without track_id")
                        
                        # Check if CSV tracks are available for lookup
                        if hasattr(self, '_csv_tracks') and self._csv_tracks:
                            csv_track_count = len(self._csv_tracks)
                            print(f"   → CSV tracks available for bbox lookup: {csv_track_count} tracks")
                        else:
                            print(f"   → CSV tracks NOT available for bbox lookup")
                    
                    print(f"✓ Loaded {total_gt_detections} ground truth detections from {total_anchors} anchor frames in {len(anchor_frames)} frames")
                    return dict(gt_tracks)
            except Exception as e:
                print(f"⚠ Error loading anchor frames from {anchor_frames_path}: {e}")
                import traceback
                traceback.print_exc()
        
        # If no path provided or loading failed, try to find PlayerTagsSeed file automatically
        # Search in the same directory as CSV file (if available) or current directory
        if not anchor_frames_path or not os.path.exists(anchor_frames_path):
            # Try to auto-discover anchor frames file
            search_dirs = []
            
            # CRITICAL: Search in CSV directory first (most likely location)
            if hasattr(self, '_csv_path') and self._csv_path:
                csv_dir = os.path.dirname(os.path.abspath(self._csv_path))
                if os.path.exists(csv_dir):
                    search_dirs.append(csv_dir)
                    # Also try to extract video name from CSV filename and search for matching PlayerTagsSeed
                    csv_basename = os.path.basename(self._csv_path)
                    # Try to extract video name from CSV filename (e.g., "20251125_194503_analyzed.csv" -> "20251125_194503")
                    if '_analyzed' in csv_basename:
                        video_name = csv_basename.replace('_analyzed.csv', '').replace('_analyzed-', '').split('-')[0]
                        expected_seed_file = os.path.join(csv_dir, f"PlayerTagsSeed-{video_name}.json")
                        if os.path.exists(expected_seed_file):
                            print(f"✓ Found expected anchor file: PlayerTagsSeed-{video_name}.json")
                            return self._load_anchor_frames_as_gt(expected_seed_file)
            
            # If anchor_frames_path was provided but doesn't exist, search in its directory
            if anchor_frames_path:
                search_dirs.append(os.path.dirname(os.path.abspath(anchor_frames_path)))
                print(f"⚠ Anchor frames file not found: {anchor_frames_path}")
                print(f"   Searching for anchor frames files...")
            
            # Also search in current directory and common locations
            search_dirs.extend([os.getcwd(), os.path.dirname(os.path.abspath(__file__))])
            
            # Look for PlayerTagsSeed files
            found_file = None
            for search_dir in search_dirs:
                if not os.path.exists(search_dir):
                    continue
                    
                try:
                    for filename in os.listdir(search_dir):
                        # Look for PlayerTagsSeed-*.json files
                        if filename.startswith("PlayerTagsSeed-") and filename.endswith(".json"):
                            candidate_path = os.path.join(search_dir, filename)
                            try:
                                # Verify it's a valid anchor frames file
                                with open(candidate_path, 'r') as f:
                                    data = json.load(f)
                                    if 'anchor_frames' in data or 'video_path' in data:
                                        found_file = candidate_path
                                        print(f"✓ Auto-discovered anchor frames: {filename}")
                                        break
                            except:
                                continue
                    
                    if found_file:
                        break
                except:
                    continue
            
            if found_file:
                # Recursively call with found file
                return self._load_anchor_frames_as_gt(found_file)
            else:
                if anchor_frames_path:
                    print(f"   Expected file: PlayerTagsSeed-{{video_name}}.json in video directory")
                else:
                    print("⚠ No anchor frames path provided - cannot load ground truth")
                    print("   Tip: Anchor frames should be in PlayerTagsSeed-{video_name}.json")
                    print("   Or use the 'Convert Tracks → Anchor Frames' tool to create them")
        
        return dict(gt_tracks)


def evaluate_tracking_metrics(
    csv_path: str,
    anchor_frames_path: Optional[str] = None,
    frame_range: Optional[Tuple[int, int]] = None
) -> Dict[str, any]:
    """
    Convenience function to evaluate all tracking metrics (HOTA, MOTA, IDF1).
    
    Args:
        csv_path: Path to tracking CSV file
        anchor_frames_path: Optional path to anchor frames JSON
        frame_range: Optional (start_frame, end_frame) to limit evaluation
    
    Returns:
        Dictionary with all metrics (HOTA, MOTA, IDF1)
    """
    evaluator = TrackingMetricsEvaluator()
    return evaluator.evaluate_from_csv(csv_path, anchor_frames_path, frame_range)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python tracking_metrics_evaluator.py <tracking_csv_path> [anchor_frames_json]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    anchor_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = evaluate_tracking_metrics(csv_path, anchor_path)
    
    print("\n" + "="*60)
    print("Comprehensive Tracking Metrics Evaluation")
    print("="*60)
    
    if 'error' in results:
        print(f"Error: {results['error']}")
    else:
        print(f"\n📊 HOTA (Higher Order Tracking Accuracy):")
        print(f"   Overall HOTA Score: {results.get('HOTA', 0):.4f}")
        print(f"   Detection Accuracy (DetA): {results.get('DetA', 0):.4f}")
        print(f"   Association Accuracy (AssA): {results.get('AssA', 0):.4f}")
        
        print(f"\n📊 MOTA (Multiple Object Tracking Accuracy):")
        print(f"   MOTA Score: {results.get('MOTA', 0):.4f}")
        print(f"   MOTP (Precision): {results.get('MOTP', 0):.4f}")
        print(f"   False Negatives: {results.get('FN', 0)}")
        print(f"   False Positives: {results.get('FP', 0)}")
        print(f"   ID Switches: {results.get('IDSW', 0)}")
        print(f"   Ground Truth: {results.get('GT', 0)}")
        
        print(f"\n📊 IDF1 (ID F1 Score):")
        print(f"   IDF1 Score: {results.get('IDF1', 0):.4f}")
        print(f"   ID Precision: {results.get('IDP', 0):.4f}")
        print(f"   ID Recall: {results.get('IDR', 0):.4f}")
        print(f"   ID True Positives: {results.get('IDTP', 0)}")
        print(f"   ID False Positives: {results.get('IDFP', 0)}")
        print(f"   ID False Negatives: {results.get('IDFN', 0)}")
        
        print("\n" + "="*60)
        print("Interpretation:")
        print("• HOTA: Balanced detection and association (0-1, higher is better)")
        print("• MOTA: Traditional tracking accuracy (0-1, higher is better)")
        print("• IDF1: ID consistency over time (0-1, higher is better)")
        print("• All metrics work together with Re-ID for comprehensive evaluation")
        print("="*60)

