"""
HOTA (Higher Order Tracking Accuracy) Evaluation Module

HOTA is a comprehensive metric that evaluates:
- Detection Accuracy (DetA): How well objects are detected
- Association Accuracy (AssA): How well objects are tracked over time
- Overall HOTA Score: Balanced combination of both

This module integrates HOTA evaluation into the soccer analysis pipeline.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
import os
from collections import defaultdict


class HOTAEvaluator:
    """
    HOTA (Higher Order Tracking Accuracy) evaluator for multi-object tracking.
    
    HOTA provides a more balanced evaluation than traditional metrics like MOTA,
    as it considers both detection and association accuracy simultaneously.
    """
    
    def __init__(self, alpha: float = 0.0):
        """
        Initialize HOTA evaluator.
        
        Args:
            alpha: Alpha parameter for HOTA (0.0 = equal weight, higher = more weight on association)
        """
        self.alpha = alpha
        self.results = {}
    
    def calculate_hota(
        self,
        pred_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        gt_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        frame_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, float]:
        """
        Calculate HOTA metrics.
        
        Args:
            pred_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            gt_tracks: Dictionary of {track_id: [(frame, x1, y1, x2, y2), ...]}
            frame_range: Optional (start_frame, end_frame) to limit evaluation
        
        Returns:
            Dictionary with HOTA metrics:
            - HOTA: Overall HOTA score (0-1, higher is better)
            - DetA: Detection Accuracy (0-1)
            - AssA: Association Accuracy (0-1)
            - DetRe: Detection Recall
            - DetPr: Detection Precision
            - AssRe: Association Recall
            - AssPr: Association Precision
        """
        if frame_range:
            start_frame, end_frame = frame_range
            pred_tracks = self._filter_frames(pred_tracks, start_frame, end_frame)
            gt_tracks = self._filter_frames(gt_tracks, start_frame, end_frame)
        
        # Calculate detection accuracy
        det_metrics = self._calculate_detection_accuracy(pred_tracks, gt_tracks)
        
        # Calculate association accuracy
        ass_metrics = self._calculate_association_accuracy(pred_tracks, gt_tracks)
        
        # Calculate overall HOTA
        deta = det_metrics['accuracy']
        assa = ass_metrics['accuracy']
        
        # HOTA formula: sqrt(DetA * AssA)
        hota = np.sqrt(deta * assa) if deta > 0 and assa > 0 else 0.0
        
        return {
            'HOTA': float(hota),
            'DetA': float(deta),
            'AssA': float(assa),
            'DetRe': float(det_metrics['recall']),
            'DetPr': float(det_metrics['precision']),
            'AssRe': float(ass_metrics['recall']),
            'AssPr': float(ass_metrics['precision']),
            'DetTP': int(det_metrics['tp']),
            'DetFP': int(det_metrics['fp']),
            'DetFN': int(det_metrics['fn']),
            'AssTP': int(ass_metrics['tp']),
            'AssFP': int(ass_metrics['fp']),
            'AssFN': int(ass_metrics['fn']),
        }
    
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
    
    def _calculate_detection_accuracy(
        self,
        pred_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        gt_tracks: Dict[int, List[Tuple[int, float, float, float, float]]]
    ) -> Dict[str, float]:
        """Calculate detection accuracy metrics."""
        # Flatten all detections
        pred_dets = []
        for track_id, detections in pred_tracks.items():
            for det in detections:
                # Handle both 5-tuple (frame, x1, y1, x2, y2) and 6-tuple (frame, x1, y1, x2, y2, player_name)
                # Extract only bbox coordinates (x1, y1, x2, y2) - first 4 elements after frame
                if len(det) >= 5:
                    frame = det[0]
                    bbox = (det[1], det[2], det[3], det[4])  # Only take first 4 bbox coordinates
                    pred_dets.append((frame, bbox))
        
        gt_dets = []
        for track_id, detections in gt_tracks.items():
            for det in detections:
                # Handle both 5-tuple (frame, x1, y1, x2, y2) and 6-tuple (frame, x1, y1, x2, y2, player_name)
                # Extract only bbox coordinates (x1, y1, x2, y2) - first 4 elements after frame
                if len(det) >= 5:
                    frame = det[0]
                    bbox = (det[1], det[2], det[3], det[4])  # Only take first 4 bbox coordinates
                    gt_dets.append((frame, bbox))
        
        # Group by frame
        pred_by_frame = defaultdict(list)
        gt_by_frame = defaultdict(list)
        
        for frame, bbox in pred_dets:
            pred_by_frame[frame].append(bbox)
        for frame, bbox in gt_dets:
            gt_by_frame[frame].append(bbox)
        
        # Calculate IoU-based matching
        all_frames = set(pred_by_frame.keys()) | set(gt_by_frame.keys())
        tp = 0
        fp = 0
        fn = 0
        
        for frame in all_frames:
            pred_boxes = pred_by_frame.get(frame, [])
            gt_boxes = gt_by_frame.get(frame, [])
            
            # Match predictions to ground truth using IoU
            matched_gt = set()
            for pred_box in pred_boxes:
                best_iou = 0.0
                best_gt_idx = -1
                for i, gt_box in enumerate(gt_boxes):
                    if i in matched_gt:
                        continue
                    iou = self._calculate_iou(pred_box, gt_box)
                    if iou > best_iou:
                        best_iou = iou
                        best_gt_idx = i
                
                if best_iou >= 0.5:  # IoU threshold for detection match
                    tp += 1
                    matched_gt.add(best_gt_idx)
                else:
                    fp += 1
            
            # Unmatched ground truth = false negatives
            fn += len(gt_boxes) - len(matched_gt)
        
        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        accuracy = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return {
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'precision': precision,
            'recall': recall,
            'accuracy': accuracy
        }
    
    def _calculate_association_accuracy(
        self,
        pred_tracks: Dict[int, List[Tuple[int, float, float, float, float]]],
        gt_tracks: Dict[int, List[Tuple[int, float, float, float, float]]]
    ) -> Dict[str, float]:
        """Calculate association accuracy metrics."""
        # For association, we need to match tracks over time
        # This is simplified - full HOTA uses more complex matching
        
        # Count track fragments (how many times a track is broken)
        pred_fragments = sum(1 for track_id, detections in pred_tracks.items() if len(detections) > 0)
        gt_fragments = len(gt_tracks)
        
        # Count track switches (simplified - would need temporal matching)
        # For now, use a simplified metric based on track persistence
        pred_track_lengths = [len(dets) for dets in pred_tracks.values()]
        gt_track_lengths = [len(dets) for dets in gt_tracks.values()]
        
        avg_pred_length = np.mean(pred_track_lengths) if pred_track_lengths else 0
        avg_gt_length = np.mean(gt_track_lengths) if gt_track_lengths else 0
        
        # Simplified association accuracy based on track persistence
        if avg_gt_length > 0:
            persistence_ratio = min(avg_pred_length / avg_gt_length, 1.0)
        else:
            persistence_ratio = 0.0
        
        # Simplified metrics (full HOTA would use more complex temporal matching)
        tp = int(sum(pred_track_lengths))
        fp = int(sum(max(0, len(dets) - avg_gt_length) for dets in pred_tracks.values()))
        fn = int(sum(max(0, avg_gt_length - len(dets)) for dets in pred_tracks.values()))
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        accuracy = persistence_ratio  # Simplified association accuracy
        
        return {
            'tp': tp,
            'fp': fp,
            'fn': fn,
            'precision': precision,
            'recall': recall,
            'accuracy': accuracy
        }
    
    def _calculate_iou(
        self,
        box1: Tuple[float, float, float, float],
        box2: Tuple[float, float, float, float]
    ) -> float:
        """Calculate Intersection over Union (IoU) between two bounding boxes."""
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
    
    def evaluate_from_csv(
        self,
        pred_csv_path: str,
        gt_csv_path: Optional[str] = None,
        frame_range: Optional[Tuple[int, int]] = None
    ) -> Dict[str, float]:
        """
        Evaluate HOTA metrics from CSV files.
        
        Args:
            pred_csv_path: Path to predicted tracking CSV
            gt_csv_path: Optional path to ground truth CSV (if None, uses anchor frames)
            frame_range: Optional (start_frame, end_frame) to limit evaluation
        
        Returns:
            Dictionary with HOTA metrics
        """
        # Load predicted tracks from CSV
        pred_tracks = self._load_tracks_from_csv(pred_csv_path)
        
        # Load ground truth tracks
        if gt_csv_path and os.path.exists(gt_csv_path):
            gt_tracks = self._load_tracks_from_csv(gt_csv_path)
        else:
            # Use anchor frames as ground truth if available
            gt_tracks = self._load_anchor_frames_as_gt()
        
        if not pred_tracks:
            return {'error': 'No predicted tracks found'}
        
        if not gt_tracks:
            return {'error': 'No ground truth tracks found'}
        
        # Calculate HOTA
        return self.calculate_hota(pred_tracks, gt_tracks, frame_range)
    
    def _load_tracks_from_csv(self, csv_path: str) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
        """Load tracks from CSV file."""
        if not os.path.exists(csv_path):
            return {}
        
        try:
            df = pd.read_csv(csv_path, comment='#')
            
            # Expected columns: frame, track_id, x1, y1, x2, y2 (or similar)
            # Adjust based on your CSV format
            tracks = defaultdict(list)
            
            for _, row in df.iterrows():
                frame = int(row.get('frame', row.get('frame_num', 0)))
                track_id = int(row.get('track_id', row.get('player_id', 0)))
                
                # Try different column name variations
                if 'x1' in row and 'y1' in row and 'x2' in row and 'y2' in row:
                    x1, y1, x2, y2 = row['x1'], row['y1'], row['x2'], row['y2']
                elif 'x' in row and 'y' in row:
                    # Assume center point and size
                    x, y = row['x'], row['y']
                    w = row.get('width', 50)
                    h = row.get('height', 100)
                    x1, y1 = x - w/2, y - h/2
                    x2, y2 = x + w/2, y + h/2
                else:
                    continue
                
                tracks[track_id].append((frame, float(x1), float(y1), float(x2), float(y2)))
            
            return dict(tracks)
        except Exception as e:
            print(f"⚠ Error loading tracks from CSV: {e}")
            return {}
    
    def _load_anchor_frames_as_gt(self) -> Dict[int, List[Tuple[int, float, float, float, float]]]:
        """Load anchor frames as ground truth."""
        # This would load from PlayerTagsSeed JSON files
        # For now, return empty dict
        return {}


def evaluate_tracking_hota(
    csv_path: str,
    anchor_frames_path: Optional[str] = None,
    frame_range: Optional[Tuple[int, int]] = None
) -> Dict[str, float]:
    """
    Convenience function to evaluate HOTA metrics.
    
    Args:
        csv_path: Path to tracking CSV file
        anchor_frames_path: Optional path to anchor frames JSON
        frame_range: Optional (start_frame, end_frame) to limit evaluation
    
    Returns:
        Dictionary with HOTA metrics
    """
    evaluator = HOTAEvaluator()
    return evaluator.evaluate_from_csv(csv_path, anchor_frames_path, frame_range)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python hota_evaluator.py <tracking_csv_path> [anchor_frames_json]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    anchor_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    results = evaluate_tracking_hota(csv_path, anchor_path)
    
    print("\n" + "="*60)
    print("HOTA (Higher Order Tracking Accuracy) Evaluation")
    print("="*60)
    print(f"\nOverall HOTA Score: {results.get('HOTA', 0):.4f}")
    print(f"Detection Accuracy (DetA): {results.get('DetA', 0):.4f}")
    print(f"Association Accuracy (AssA): {results.get('AssA', 0):.4f}")
    print(f"\nDetection Metrics:")
    print(f"  Recall: {results.get('DetRe', 0):.4f}")
    print(f"  Precision: {results.get('DetPr', 0):.4f}")
    print(f"  TP: {results.get('DetTP', 0)}, FP: {results.get('DetFP', 0)}, FN: {results.get('DetFN', 0)}")
    print(f"\nAssociation Metrics:")
    print(f"  Recall: {results.get('AssRe', 0):.4f}")
    print(f"  Precision: {results.get('AssPr', 0):.4f}")
    print(f"  TP: {results.get('AssTP', 0)}, FP: {results.get('AssFP', 0)}, FN: {results.get('AssFN', 0)}")
    print("="*60)

