"""
Advanced Tracking Utilities
Based on academic research (Deep HM-SORT, SoccerNet Tracking Challenge)

Features:
1. Harmonic Mean association
2. Expansion IOU with motion prediction
3. Soccer-specific Re-ID training support
"""

import numpy as np
from typing import Tuple, Optional, Dict, List
from collections import defaultdict


def harmonic_mean(a: float, b: float) -> float:
    """
    Calculate Harmonic Mean of two values.
    
    Harmonic Mean is better than arithmetic mean for combining metrics
    because it penalizes extreme values more.
    
    Formula: HM = 2 × (a × b) / (a + b)
    
    Args:
        a: First value
        b: Second value
    
    Returns:
        Harmonic mean of a and b
    """
    if a == 0 and b == 0:
        return 0.0
    if a == 0 or b == 0:
        return 0.0
    return 2.0 * (a * b) / (a + b)


def calculate_expansion_iou(
    box1: Tuple[float, float, float, float],
    box2: Tuple[float, float, float, float],
    velocity1: Optional[Tuple[float, float]] = None,
    velocity2: Optional[Tuple[float, float]] = None,
    expansion_factor: float = 0.1,
    time_delta: float = 1.0
) -> float:
    """
    Calculate Expansion IOU with motion prediction.
    
    Expansion IOU considers predicted motion of objects, making it better
    for fast-moving players. Based on Deep HM-SORT paper.
    
    Args:
        box1: First bounding box (x1, y1, x2, y2)
        box2: Second bounding box (x1, y1, x2, y2)
        velocity1: Optional velocity of box1 (vx, vy) in pixels per frame
        velocity2: Optional velocity of box2 (vx, vy) in pixels per frame
        expansion_factor: How much to expand boxes based on motion (default: 0.1)
        time_delta: Time difference between frames (default: 1.0)
    
    Returns:
        Expansion IOU value (0.0 to 1.0)
    """
    x1_1, y1_1, x2_1, y2_1 = box1
    x1_2, y1_2, x2_2, y2_2 = box2
    
    # Calculate center and size
    cx1 = (x1_1 + x2_1) / 2.0
    cy1 = (y1_1 + y2_1) / 2.0
    w1 = x2_1 - x1_1
    h1 = y2_1 - y1_1
    
    cx2 = (x1_2 + x2_2) / 2.0
    cy2 = (y1_2 + y2_2) / 2.0
    w2 = x2_2 - x1_2
    h2 = y2_2 - y1_2
    
    # Predict future positions based on velocity
    if velocity1 is not None:
        vx1, vy1 = velocity1
        # Predict center position after time_delta
        cx1_pred = cx1 + vx1 * time_delta
        cy1_pred = cy1 + vy1 * time_delta
        # Expand box based on motion magnitude
        motion_mag1 = np.sqrt(vx1**2 + vy1**2)
        expansion1 = motion_mag1 * expansion_factor * time_delta
        w1_expanded = w1 + expansion1
        h1_expanded = h1 + expansion1
    else:
        cx1_pred = cx1
        cy1_pred = cy1
        w1_expanded = w1
        h1_expanded = h1
    
    if velocity2 is not None:
        vx2, vy2 = velocity2
        cx2_pred = cx2 + vx2 * time_delta
        cy2_pred = cy2 + vy2 * time_delta
        motion_mag2 = np.sqrt(vx2**2 + vy2**2)
        expansion2 = motion_mag2 * expansion_factor * time_delta
        w2_expanded = w2 + expansion2
        h2_expanded = h2 + expansion2
    else:
        cx2_pred = cx2
        cy2_pred = cy2
        w2_expanded = w2
        h2_expanded = h2
    
    # Create expanded boxes
    box1_expanded = (
        cx1_pred - w1_expanded / 2.0,
        cy1_pred - h1_expanded / 2.0,
        cx1_pred + w1_expanded / 2.0,
        cy1_pred + h1_expanded / 2.0
    )
    
    box2_expanded = (
        cx2_pred - w2_expanded / 2.0,
        cy2_pred - h2_expanded / 2.0,
        cx2_pred + w2_expanded / 2.0,
        cy2_pred + h2_expanded / 2.0
    )
    
    # Calculate standard IOU on expanded boxes
    return calculate_iou(box1_expanded, box2_expanded)


def calculate_iou(
    box1: Tuple[float, float, float, float],
    box2: Tuple[float, float, float, float]
) -> float:
    """
    Calculate standard Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        box1: First bounding box (x1, y1, x2, y2)
        box2: Second bounding box (x1, y1, x2, y2)
    
    Returns:
        IoU value (0.0 to 1.0)
    """
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


def harmonic_mean_association(
    detection_score: float,
    association_score: float,
    detection_weight: float = 0.5,
    association_weight: float = 0.5
) -> float:
    """
    Calculate Harmonic Mean association score.
    
    Uses Harmonic Mean to combine detection and association scores,
    which is better than arithmetic mean for tracking decisions.
    Based on Deep HM-SORT paper.
    
    Args:
        detection_score: Detection confidence (0.0 to 1.0)
        association_score: Association/Re-ID similarity (0.0 to 1.0)
        detection_weight: Weight for detection score (default: 0.5)
        association_weight: Weight for association score (default: 0.5)
    
    Returns:
        Combined score using Harmonic Mean (0.0 to 1.0)
    """
    # Weighted harmonic mean
    if detection_score == 0 and association_score == 0:
        return 0.0
    if detection_score == 0 or association_score == 0:
        return 0.0
    
    # Weighted harmonic mean: HM = (w1 + w2) / (w1/a + w2/b)
    weighted_hm = (detection_weight + association_weight) / (
        detection_weight / detection_score + association_weight / association_score
    )
    
    return weighted_hm


def calculate_track_velocity(
    current_box: Tuple[float, float, float, float],
    previous_box: Tuple[float, float, float, float],
    frame_delta: int = 1
) -> Tuple[float, float]:
    """
    Calculate velocity (motion) of a track between two frames.
    
    Args:
        current_box: Current bounding box (x1, y1, x2, y2)
        previous_box: Previous bounding box (x1, y1, x2, y2)
        frame_delta: Number of frames between boxes (default: 1)
    
    Returns:
        Velocity tuple (vx, vy) in pixels per frame
    """
    if frame_delta == 0:
        return (0.0, 0.0)
    
    # Calculate centers
    cx1 = (current_box[0] + current_box[2]) / 2.0
    cy1 = (current_box[1] + current_box[3]) / 2.0
    
    cx2 = (previous_box[0] + previous_box[2]) / 2.0
    cy2 = (previous_box[1] + previous_box[3]) / 2.0
    
    # Calculate velocity
    vx = (cx1 - cx2) / frame_delta
    vy = (cy1 - cy2) / frame_delta
    
    return (vx, vy)


class SoccerReIDTrainer:
    """
    Soccer-specific Re-ID training infrastructure.
    
    Supports fine-tuning Re-ID models on soccer player data for better
    feature extraction. Based on SoccerNet Re-ID task best practices.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize soccer Re-ID trainer.
        
        Args:
            model_path: Optional path to pre-trained model
        """
        self.model_path = model_path
        self.training_data = []
        self.validation_data = []
        
    def add_training_sample(
        self,
        player_id: str,
        frame: np.ndarray,
        bbox: Tuple[float, float, float, float],
        camera_id: Optional[str] = None
    ):
        """
        Add a training sample for soccer-specific Re-ID.
        
        Args:
            player_id: Player identifier
            frame: Video frame (numpy array)
            bbox: Bounding box (x1, y1, x2, y2)
            camera_id: Optional camera identifier for multi-camera training
        """
        self.training_data.append({
            'player_id': player_id,
            'frame': frame,
            'bbox': bbox,
            'camera_id': camera_id
        })
    
    def prepare_training_data(self, min_samples_per_player: int = 10):
        """
        Prepare training data for fine-tuning.
        
        Args:
            min_samples_per_player: Minimum samples per player to include
        
        Returns:
            Dictionary with prepared training data
        """
        # Group by player
        player_samples = defaultdict(list)
        for sample in self.training_data:
            player_samples[sample['player_id']].append(sample)
        
        # Filter players with enough samples
        valid_players = {
            pid: samples for pid, samples in player_samples.items()
            if len(samples) >= min_samples_per_player
        }
        
        return {
            'players': valid_players,
            'total_samples': sum(len(s) for s in valid_players.values()),
            'num_players': len(valid_players)
        }
    
    def export_for_training(
        self,
        output_dir: str,
        format: str = 'soccernet'
    ):
        """
        Export training data in format compatible with SoccerNet or other frameworks.
        
        Args:
            output_dir: Directory to save training data
            format: Export format ('soccernet', 'torchreid', 'custom')
        """
        import os
        import json
        
        os.makedirs(output_dir, exist_ok=True)
        
        prepared_data = self.prepare_training_data()
        
        if format == 'soccernet':
            # Export in SoccerNet format
            annotations = []
            for player_id, samples in prepared_data['players'].items():
                for idx, sample in enumerate(samples):
                    annotations.append({
                        'player_id': player_id,
                        'frame_path': f"{player_id}_{idx}.jpg",
                        'bbox': sample['bbox'],
                        'camera_id': sample.get('camera_id', 'default')
                    })
            
            with open(os.path.join(output_dir, 'annotations.json'), 'w') as f:
                json.dump(annotations, f, indent=2)
        
        elif format == 'torchreid':
            # Export for torchreid training
            # Create directory structure: output_dir/player_id/image.jpg
            for player_id, samples in prepared_data['players'].items():
                player_dir = os.path.join(output_dir, player_id)
                os.makedirs(player_dir, exist_ok=True)
                
                for idx, sample in enumerate(samples):
                    # Extract ROI from frame
                    x1, y1, x2, y2 = [int(coord) for coord in sample['bbox']]
                    roi = sample['frame'][y1:y2, x1:x2]
                    
                    # Save image
                    import cv2
                    image_path = os.path.join(player_dir, f"{idx:04d}.jpg")
                    cv2.imwrite(image_path, roi)
        
        print(f"✓ Exported {prepared_data['total_samples']} samples for {prepared_data['num_players']} players to {output_dir}")


def match_tracks_with_harmonic_mean(
    detections: List[Dict],
    tracks: List[Dict],
    use_expansion_iou: bool = True,
    track_velocities: Optional[Dict[int, Tuple[float, float]]] = None
) -> List[Tuple[int, int, float]]:
    """
    Match detections to tracks using Harmonic Mean association and Expansion IOU.
    
    Based on Deep HM-SORT methodology.
    
    Args:
        detections: List of detection dicts with 'bbox', 'confidence', 'reid_similarity'
        tracks: List of track dicts with 'track_id', 'bbox', 'last_frame'
        use_expansion_iou: Whether to use Expansion IOU (default: True)
        track_velocities: Optional dict of {track_id: (vx, vy)} for motion prediction
    
    Returns:
        List of (detection_idx, track_id, match_score) tuples
    """
    matches = []
    
    for det_idx, det in enumerate(detections):
        best_score = 0.0
        best_track_id = None
        
        det_bbox = det['bbox']
        det_conf = det.get('confidence', 1.0)
        det_reid = det.get('reid_similarity', 0.0)
        
        for track in tracks:
            track_id = track['track_id']
            track_bbox = track['bbox']
            
            # Calculate IOU (with expansion if enabled)
            if use_expansion_iou and track_velocities and track_id in track_velocities:
                velocity = track_velocities[track_id]
                iou = calculate_expansion_iou(det_bbox, track_bbox, velocity2=velocity)
            else:
                iou = calculate_iou(det_bbox, track_bbox)
            
            # Get Re-ID similarity if available
            track_reid = track.get('reid_similarity', 0.0)
            reid_sim = max(det_reid, track_reid) if det_reid > 0 or track_reid > 0 else 0.0
            
            # Use Harmonic Mean to combine detection confidence and association score
            # Association score combines IOU and Re-ID similarity
            association_score = harmonic_mean(iou, reid_sim) if reid_sim > 0 else iou
            match_score = harmonic_mean_association(det_conf, association_score)
            
            if match_score > best_score:
                best_score = match_score
                best_track_id = track_id
        
        if best_track_id is not None and best_score > 0.3:  # Minimum threshold
            matches.append((det_idx, best_track_id, best_score))
    
    return matches

