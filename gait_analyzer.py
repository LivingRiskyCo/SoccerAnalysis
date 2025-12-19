"""
Gait Analysis Module
Analyzes player movement patterns (stride, cadence, running style) from pose keypoints and movement data.

Gait features are unique to each player and help with recognition even when appearance is similar.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import deque
import cv2


class GaitAnalyzer:
    """
    Analyzes gait patterns from pose keypoints and movement data.
    
    Extracts features like:
    - Stride length
    - Cadence (steps per second)
    - Running style (upright, forward lean, etc.)
    - Limb proportions
    - Movement rhythm
    """
    
    def __init__(self, 
                 history_length: int = 30,  # Frames to keep for analysis
                 min_samples_for_gait: int = 10):  # Minimum samples needed
        """
        Initialize Gait Analyzer
        
        Args:
            history_length: Number of frames to keep in history
            min_samples_for_gait: Minimum samples needed to compute gait features
        """
        self.history_length = history_length
        self.min_samples_for_gait = min_samples_for_gait
        
        # Store gait history per track
        # Format: track_id -> {
        #   'keypoints': deque of keypoint arrays,
        #   'positions': deque of (x, y) positions,
        #   'velocities': deque of velocity magnitudes,
        #   'timestamps': deque of frame numbers
        # }
        self.track_gait_history: Dict[int, Dict] = {}
        
        # COCO pose keypoint indices (YOLO pose uses COCO format)
        # 0: nose, 1: left_eye, 2: right_eye, 3: left_ear, 4: right_ear,
        # 5: left_shoulder, 6: right_shoulder, 7: left_elbow, 8: right_elbow,
        # 9: left_wrist, 10: right_wrist, 11: left_hip, 12: right_hip,
        # 13: left_knee, 14: right_knee, 15: left_ankle, 16: right_ankle
        self.KEYPOINT_NAMES = [
            'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow',
            'left_wrist', 'right_wrist', 'left_hip', 'right_hip',
            'left_knee', 'right_knee', 'left_ankle', 'right_ankle'
        ]
        
        # Key indices for gait analysis
        self.ANKLE_LEFT = 15
        self.ANKLE_RIGHT = 16
        self.KNEE_LEFT = 13
        self.KNEE_RIGHT = 14
        self.HIP_LEFT = 11
        self.HIP_RIGHT = 12
        self.SHOULDER_LEFT = 5
        self.SHOULDER_RIGHT = 6
    
    def update_track(self, 
                    track_id: int,
                    keypoints: Optional[np.ndarray] = None,  # Shape: (17, 3) or (17, 2) - (x, y, confidence)
                    position: Optional[Tuple[float, float]] = None,  # (x, y) center position
                    velocity: Optional[float] = None,  # Velocity magnitude
                    frame_num: int = 0):
        """
        Update gait history for a track
        
        Args:
            track_id: Track identifier
            keypoints: Pose keypoints array
            position: Player center position
            velocity: Velocity magnitude
            frame_num: Current frame number
        """
        if track_id not in self.track_gait_history:
            self.track_gait_history[track_id] = {
                'keypoints': deque(maxlen=self.history_length),
                'positions': deque(maxlen=self.history_length),
                'velocities': deque(maxlen=self.history_length),
                'timestamps': deque(maxlen=self.history_length)
            }
        
        history = self.track_gait_history[track_id]
        
        if keypoints is not None:
            history['keypoints'].append(keypoints.copy())
        if position is not None:
            history['positions'].append(position)
        if velocity is not None:
            history['velocities'].append(velocity)
        history['timestamps'].append(frame_num)
    
    def extract_gait_features(self, track_id: int) -> Optional[Dict[str, float]]:
        """
        Extract gait features for a track
        
        Args:
            track_id: Track identifier
            
        Returns:
            Dict with gait features or None if insufficient data
        """
        if track_id not in self.track_gait_history:
            return None
        
        history = self.track_gait_history[track_id]
        
        # Need minimum samples
        if len(history['keypoints']) < self.min_samples_for_gait:
            return None
        
        keypoints_list = list(history['keypoints'])
        positions_list = list(history['positions'])
        velocities_list = list(history['velocities'])
        
        features = {}
        
        # 1. STRIDE LENGTH: Distance between consecutive foot placements
        stride_lengths = []
        if len(positions_list) >= 2:
            for i in range(1, len(positions_list)):
                # Calculate distance between ankle positions
                if len(keypoints_list[i]) > self.ANKLE_LEFT and len(keypoints_list[i-1]) > self.ANKLE_LEFT:
                    # Get ankle positions (average of left and right)
                    curr_ankles = self._get_ankle_center(keypoints_list[i])
                    prev_ankles = self._get_ankle_center(keypoints_list[i-1])
                    
                    if curr_ankles is not None and prev_ankles is not None:
                        stride = np.linalg.norm(np.array(curr_ankles) - np.array(prev_ankles))
                        stride_lengths.append(stride)
        
        if stride_lengths:
            features['avg_stride_length'] = np.mean(stride_lengths)
            features['std_stride_length'] = np.std(stride_lengths)
            features['max_stride_length'] = np.max(stride_lengths)
        else:
            features['avg_stride_length'] = 0.0
            features['std_stride_length'] = 0.0
            features['max_stride_length'] = 0.0
        
        # 2. CADENCE: Steps per second (frequency of foot placements)
        if len(positions_list) >= 3:
            # Count significant position changes (potential steps)
            step_count = 0
            for i in range(1, len(positions_list)):
                if len(keypoints_list[i]) > self.ANKLE_LEFT and len(keypoints_list[i-1]) > self.ANKLE_LEFT:
                    curr_ankles = self._get_ankle_center(keypoints_list[i])
                    prev_ankles = self._get_ankle_center(keypoints_list[i-1])
                    
                    if curr_ankles is not None and prev_ankles is not None:
                        step_distance = np.linalg.norm(np.array(curr_ankles) - np.array(prev_ankles))
                        if step_distance > 5.0:  # Threshold for significant movement
                            step_count += 1
            
            # Estimate cadence (assuming ~30 fps, adjust if different)
            time_span = len(positions_list) / 30.0  # seconds
            if time_span > 0:
                features['cadence'] = (step_count / 2.0) / time_span  # Divide by 2 (left + right = 1 step)
            else:
                features['cadence'] = 0.0
        else:
            features['cadence'] = 0.0
        
        # 3. RUNNING STYLE: Body lean angle (forward/backward, upright)
        lean_angles = []
        for keypoints in keypoints_list:
            if len(keypoints) > self.SHOULDER_RIGHT:
                # Calculate angle between shoulders and hips
                shoulder_center = self._get_shoulder_center(keypoints)
                hip_center = self._get_hip_center(keypoints)
                
                if shoulder_center is not None and hip_center is not None:
                    # Calculate angle from vertical
                    dx = shoulder_center[0] - hip_center[0]
                    dy = shoulder_center[1] - hip_center[1]
                    angle = np.arctan2(dx, abs(dy)) * 180 / np.pi  # Degrees
                    lean_angles.append(angle)
        
        if lean_angles:
            features['avg_lean_angle'] = np.mean(lean_angles)
            features['std_lean_angle'] = np.std(lean_angles)
        else:
            features['avg_lean_angle'] = 0.0
            features['std_lean_angle'] = 0.0
        
        # 4. LIMB PROPORTIONS: Leg length, arm length, torso length
        if len(keypoints_list) > 0:
            # Use most recent keypoints
            kp = keypoints_list[-1]
            
            # Leg length (hip to ankle, average of left and right)
            leg_lengths = []
            if len(kp) > self.ANKLE_LEFT:
                left_leg = self._distance(kp, self.HIP_LEFT, self.ANKLE_LEFT)
                right_leg = self._distance(kp, self.HIP_RIGHT, self.ANKLE_RIGHT)
                if left_leg is not None:
                    leg_lengths.append(left_leg)
                if right_leg is not None:
                    leg_lengths.append(right_leg)
            
            features['avg_leg_length'] = np.mean(leg_lengths) if leg_lengths else 0.0
            
            # Torso length (shoulder to hip)
            torso_lengths = []
            if len(kp) > self.SHOULDER_LEFT:
                left_torso = self._distance(kp, self.SHOULDER_LEFT, self.HIP_LEFT)
                right_torso = self._distance(kp, self.SHOULDER_RIGHT, self.HIP_RIGHT)
                if left_torso is not None:
                    torso_lengths.append(left_torso)
                if right_torso is not None:
                    torso_lengths.append(right_torso)
            
            features['avg_torso_length'] = np.mean(torso_lengths) if torso_lengths else 0.0
            
            # Leg-to-torso ratio (unique body proportion)
            if features['avg_torso_length'] > 0:
                features['leg_torso_ratio'] = features['avg_leg_length'] / features['avg_torso_length']
            else:
                features['leg_torso_ratio'] = 0.0
        else:
            features['avg_leg_length'] = 0.0
            features['avg_torso_length'] = 0.0
            features['leg_torso_ratio'] = 0.0
        
        # 5. MOVEMENT RHYTHM: Consistency of movement patterns
        if len(velocities_list) >= 3:
            # Calculate velocity variation (lower = more consistent rhythm)
            velocity_array = np.array(velocities_list)
            features['velocity_std'] = np.std(velocity_array)
            features['velocity_cv'] = np.std(velocity_array) / (np.mean(velocity_array) + 1e-8)  # Coefficient of variation
        else:
            features['velocity_std'] = 0.0
            features['velocity_cv'] = 0.0
        
        # 6. STEP SYMMETRY: Left vs right step consistency
        if len(keypoints_list) >= 4:
            left_steps = []
            right_steps = []
            
            for i in range(1, len(keypoints_list)):
                if len(keypoints_list[i]) > self.ANKLE_LEFT:
                    # Left ankle movement
                    if len(keypoints_list[i-1]) > self.ANKLE_LEFT:
                        left_step = self._distance_between_keypoints(
                            keypoints_list[i-1], keypoints_list[i], 
                            self.ANKLE_LEFT, self.ANKLE_LEFT
                        )
                        if left_step is not None:
                            left_steps.append(left_step)
                    
                    # Right ankle movement
                    if len(keypoints_list[i-1]) > self.ANKLE_RIGHT:
                        right_step = self._distance_between_keypoints(
                            keypoints_list[i-1], keypoints_list[i],
                            self.ANKLE_RIGHT, self.ANKLE_RIGHT
                        )
                        if right_step is not None:
                            right_steps.append(right_step)
            
            if left_steps and right_steps:
                avg_left = np.mean(left_steps)
                avg_right = np.mean(right_steps)
                features['step_symmetry'] = 1.0 - abs(avg_left - avg_right) / (max(avg_left, avg_right) + 1e-8)
            else:
                features['step_symmetry'] = 0.0
        else:
            features['step_symmetry'] = 0.0
        
        return features
    
    def get_gait_signature(self, track_id: int) -> Optional[np.ndarray]:
        """
        Get normalized gait signature vector for matching
        
        Args:
            track_id: Track identifier
            
        Returns:
            Normalized feature vector or None
        """
        features = self.extract_gait_features(track_id)
        if features is None:
            return None
        
        # Create feature vector (normalized)
        feature_vector = np.array([
            features.get('avg_stride_length', 0.0),
            features.get('std_stride_length', 0.0),
            features.get('cadence', 0.0),
            features.get('avg_lean_angle', 0.0),
            features.get('leg_torso_ratio', 0.0),
            features.get('velocity_cv', 0.0),
            features.get('step_symmetry', 0.0)
        ])
        
        # Normalize (L2 norm)
        norm = np.linalg.norm(feature_vector)
        if norm > 0:
            feature_vector = feature_vector / norm
        
        return feature_vector
    
    def _get_ankle_center(self, keypoints: np.ndarray) -> Optional[Tuple[float, float]]:
        """Get center point between left and right ankles"""
        if len(keypoints) <= max(self.ANKLE_LEFT, self.ANKLE_RIGHT):
            return None
        
        left_ankle = keypoints[self.ANKLE_LEFT]
        right_ankle = keypoints[self.ANKLE_RIGHT]
        
        # Check confidence (if available)
        if len(left_ankle) >= 3 and left_ankle[2] < 0.3:
            return None
        if len(right_ankle) >= 3 and right_ankle[2] < 0.3:
            return None
        
        center_x = (left_ankle[0] + right_ankle[0]) / 2.0
        center_y = (left_ankle[1] + right_ankle[1]) / 2.0
        
        return (center_x, center_y)
    
    def _get_shoulder_center(self, keypoints: np.ndarray) -> Optional[Tuple[float, float]]:
        """Get center point between left and right shoulders"""
        if len(keypoints) <= max(self.SHOULDER_LEFT, self.SHOULDER_RIGHT):
            return None
        
        left_shoulder = keypoints[self.SHOULDER_LEFT]
        right_shoulder = keypoints[self.SHOULDER_RIGHT]
        
        if len(left_shoulder) >= 3 and left_shoulder[2] < 0.3:
            return None
        if len(right_shoulder) >= 3 and right_shoulder[2] < 0.3:
            return None
        
        center_x = (left_shoulder[0] + right_shoulder[0]) / 2.0
        center_y = (left_shoulder[1] + right_shoulder[1]) / 2.0
        
        return (center_x, center_y)
    
    def _get_hip_center(self, keypoints: np.ndarray) -> Optional[Tuple[float, float]]:
        """Get center point between left and right hips"""
        if len(keypoints) <= max(self.HIP_LEFT, self.HIP_RIGHT):
            return None
        
        left_hip = keypoints[self.HIP_LEFT]
        right_hip = keypoints[self.HIP_RIGHT]
        
        if len(left_hip) >= 3 and left_hip[2] < 0.3:
            return None
        if len(right_hip) >= 3 and right_hip[2] < 0.3:
            return None
        
        center_x = (left_hip[0] + right_hip[0]) / 2.0
        center_y = (left_hip[1] + right_hip[1]) / 2.0
        
        return (center_x, center_y)
    
    def _distance(self, keypoints: np.ndarray, idx1: int, idx2: int) -> Optional[float]:
        """Calculate distance between two keypoints"""
        if len(keypoints) <= max(idx1, idx2):
            return None
        
        kp1 = keypoints[idx1]
        kp2 = keypoints[idx2]
        
        # Check confidence
        if len(kp1) >= 3 and kp1[2] < 0.3:
            return None
        if len(kp2) >= 3 and kp2[2] < 0.3:
            return None
        
        dx = kp1[0] - kp2[0]
        dy = kp1[1] - kp2[1]
        return np.sqrt(dx*dx + dy*dy)
    
    def _distance_between_keypoints(self, 
                                    kp1_array: np.ndarray, 
                                    kp2_array: np.ndarray,
                                    idx1: int, 
                                    idx2: int) -> Optional[float]:
        """Calculate distance between same keypoint in two frames"""
        if len(kp1_array) <= idx1 or len(kp2_array) <= idx2:
            return None
        
        kp1 = kp1_array[idx1]
        kp2 = kp2_array[idx2]
        
        if len(kp1) >= 3 and kp1[2] < 0.3:
            return None
        if len(kp2) >= 3 and kp2[2] < 0.3:
            return None
        
        dx = kp1[0] - kp2[0]
        dy = kp1[1] - kp2[1]
        return np.sqrt(dx*dx + dy*dy)
    
    def clear_track(self, track_id: int):
        """Clear gait history for a track"""
        if track_id in self.track_gait_history:
            del self.track_gait_history[track_id]
    
    def clear_all(self):
        """Clear all gait history"""
        self.track_gait_history.clear()

