"""
Enhanced Tracking Utilities
- Enhanced Kalman filtering for smoother tracking
- Improved temporal smoothing (EMA with confidence weighting)
- Confidence-based filtering
"""

import numpy as np
from collections import deque
from typing import Optional, Tuple, Dict
import cv2


class EnhancedKalmanFilter:
    """
    Enhanced Kalman filter for player position smoothing
    Works on top of ByteTrack's internal Kalman filter for additional smoothing
    """
    
    def __init__(self, process_noise=0.03, measurement_noise=0.3, initial_velocity=(0, 0)):
        """
        Initialize Kalman filter
        
        Args:
            process_noise: Process noise covariance (how much we trust the model)
            measurement_noise: Measurement noise covariance (how much we trust detections)
            initial_velocity: Initial velocity estimate (vx, vy)
        """
        # State: [x, y, vx, vy] (position and velocity)
        self.state = np.zeros(4, dtype=np.float32)
        self.covariance = np.eye(4, dtype=np.float32) * 1000  # Large initial uncertainty
        
        # Process noise (Q) - how much we trust the motion model
        self.Q = np.eye(4, dtype=np.float32) * process_noise
        self.Q[2, 2] = process_noise * 0.5  # Less noise in velocity
        self.Q[3, 3] = process_noise * 0.5
        
        # Measurement noise (R) - how much we trust detections
        self.R = np.eye(2, dtype=np.float32) * measurement_noise
        
        # State transition matrix (constant velocity model)
        # x' = x + vx*dt, y' = y + vy*dt, vx' = vx, vy' = vy
        self.F = np.eye(4, dtype=np.float32)
        
        # Measurement matrix (we only observe position, not velocity)
        self.H = np.zeros((2, 4), dtype=np.float32)
        self.H[0, 0] = 1  # x
        self.H[1, 1] = 1  # y
        
        self.dt = 1.0  # Time step (1 frame)
        self.initialized = False
    
    def predict(self, dt: float = 1.0) -> Tuple[float, float]:
        """
        Predict next state
        
        Args:
            dt: Time step (default: 1.0 for 1 frame)
        
        Returns:
            Predicted (x, y) position
        """
        if not self.initialized:
            return (0, 0)
        
        self.dt = dt
        
        # Update state transition matrix with dt
        self.F[0, 2] = dt  # x' = x + vx*dt
        self.F[1, 3] = dt  # y' = y + vy*dt
        
        # Predict state
        self.state = self.F @ self.state
        
        # Predict covariance
        self.covariance = self.F @ self.covariance @ self.F.T + self.Q
        
        return (float(self.state[0]), float(self.state[1]))
    
    def update(self, measurement: Tuple[float, float], confidence: float = 1.0):
        """
        Update filter with new measurement
        
        Args:
            measurement: (x, y) position measurement
            confidence: Detection confidence (0-1), used to adjust measurement noise
        """
        if not self.initialized:
            # Initialize with first measurement
            self.state[0] = measurement[0]
            self.state[1] = measurement[1]
            self.state[2] = 0  # Initial velocity
            self.state[3] = 0
            self.initialized = True
            return
        
        # Adjust measurement noise based on confidence
        # Lower confidence = higher noise = less trust in measurement
        adaptive_R = self.R * (2.0 - confidence)  # Scale noise inversely with confidence
        
        # Innovation (measurement residual)
        z = np.array([measurement[0], measurement[1]], dtype=np.float32)
        y = z - self.H @ self.state
        
        # Innovation covariance
        S = self.H @ self.covariance @ self.H.T + adaptive_R
        
        # Kalman gain
        K = self.covariance @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        self.state = self.state + K @ y
        
        # Update covariance
        I = np.eye(4, dtype=np.float32)
        self.covariance = (I - K @ self.H) @ self.covariance
    
    def get_state(self) -> Tuple[float, float, float, float]:
        """
        Get current state: (x, y, vx, vy)
        """
        return (float(self.state[0]), float(self.state[1]), 
                float(self.state[2]), float(self.state[3]))
    
    def get_position(self) -> Tuple[float, float]:
        """
        Get current position: (x, y)
        """
        return (float(self.state[0]), float(self.state[1]))
    
    def get_velocity(self) -> Tuple[float, float]:
        """
        Get current velocity: (vx, vy)
        """
        return (float(self.state[2]), float(self.state[3]))
    
    def reset(self):
        """Reset filter to uninitialized state"""
        self.initialized = False
        self.state = np.zeros(4, dtype=np.float32)
        self.covariance = np.eye(4, dtype=np.float32) * 1000


class EMASmoother:
    """
    Exponential Moving Average (EMA) smoother with confidence weighting
    Better than simple moving average - responds faster to changes while still smoothing
    """
    
    def __init__(self, alpha=0.3, min_history=3):
        """
        Initialize EMA smoother
        
        Args:
            alpha: Smoothing factor (0-1). Lower = more smoothing, higher = more responsive
            min_history: Minimum number of samples before applying smoothing
        """
        self.alpha = alpha
        self.min_history = min_history
        self.history = deque(maxlen=10)  # Store recent (position, confidence) tuples
        self.smoothed_position = None
    
    def update(self, position: Tuple[float, float], confidence: float = 1.0) -> Tuple[float, float]:
        """
        Update smoother with new position
        
        Args:
            position: (x, y) position
            confidence: Detection confidence (0-1), used for weighting
        
        Returns:
            Smoothed (x, y) position
        """
        self.history.append((position, confidence))
        
        if len(self.history) < self.min_history:
            # Not enough history yet, return current position
            self.smoothed_position = position
            return position
        
        # Calculate weighted average with confidence
        if self.smoothed_position is None:
            # Initialize with first position
            self.smoothed_position = position
        else:
            # EMA update with confidence weighting
            # Higher confidence = use more of new measurement
            # Lower confidence = use more of smoothed value
            confidence_weight = 0.5 + (confidence * 0.5)  # Scale confidence to 0.5-1.0
            adaptive_alpha = self.alpha * confidence_weight
            
            x_new = adaptive_alpha * position[0] + (1 - adaptive_alpha) * self.smoothed_position[0]
            y_new = adaptive_alpha * position[1] + (1 - adaptive_alpha) * self.smoothed_position[1]
            self.smoothed_position = (x_new, y_new)
        
        return self.smoothed_position
    
    def reset(self):
        """Reset smoother"""
        self.history.clear()
        self.smoothed_position = None


def filter_by_confidence(detections, min_confidence: float = 0.25, 
                         adaptive_threshold: bool = True,
                         confidence_history: Optional[Dict] = None) -> np.ndarray:
    """
    Filter detections by confidence with adaptive threshold
    
    Args:
        detections: Supervision Detections object
        min_confidence: Minimum confidence threshold
        adaptive_threshold: Whether to use adaptive threshold based on frame-to-frame consistency
        confidence_history: Dictionary to store confidence history for adaptive threshold
    
    Returns:
        Boolean mask of detections to keep
    """
    if len(detections) == 0:
        return np.array([], dtype=bool)
    
    confidences = detections.confidence
    
    if not adaptive_threshold:
        # Simple threshold
        return confidences >= min_confidence
    
    # Adaptive threshold: adjust based on detection consistency
    # If we have many high-confidence detections, be stricter
    # If we have few detections, be more lenient
    high_conf_count = np.sum(confidences >= min_confidence + 0.1)
    total_count = len(confidences)
    
    if total_count > 0:
        high_conf_ratio = high_conf_count / total_count
        
        # If most detections are high confidence, use stricter threshold
        if high_conf_ratio > 0.7:
            adaptive_thresh = min_confidence + 0.05
        # If few detections are high confidence, use more lenient threshold
        elif high_conf_ratio < 0.3:
            adaptive_thresh = max(0.15, min_confidence - 0.05)
        else:
            adaptive_thresh = min_confidence
    else:
        adaptive_thresh = min_confidence
    
    return confidences >= adaptive_thresh


def filter_by_size(detections, min_height: float = 40, max_height: float = 500,
                   min_area: float = 1500, max_area: float = 50000,
                   width: int = 1920, height: int = 1080) -> np.ndarray:
    """
    Filter detections by size (remove too small or too large)
    
    Args:
        detections: Supervision Detections object
        min_height: Minimum bounding box height (scaled with resolution)
        max_height: Maximum bounding box height (scaled with resolution)
        min_area: Minimum bounding box area (scaled with resolution)
        max_area: Maximum bounding box area (scaled with resolution)
        width: Video width (for scaling)
        height: Video height (for scaling)
    
    Returns:
        Boolean mask of detections to keep
    """
    if len(detections) == 0:
        return np.array([], dtype=bool)
    
    # Scale thresholds with resolution
    scale_factor = width / 1920.0
    scaled_min_height = min_height * scale_factor
    scaled_max_height = max_height * scale_factor
    scaled_min_area = min_area * scale_factor * scale_factor
    scaled_max_area = max_area * scale_factor * scale_factor
    
    keep_mask = np.ones(len(detections), dtype=bool)
    
    for i, (x1, y1, x2, y2) in enumerate(detections.xyxy):
        box_height = y2 - y1
        box_width = x2 - x1
        box_area = box_width * box_height
        
        # Filter by height
        if box_height < scaled_min_height or box_height > scaled_max_height:
            keep_mask[i] = False
            continue
        
        # Filter by area
        if box_area < scaled_min_area or box_area > scaled_max_area:
            keep_mask[i] = False
            continue
    
    return keep_mask

