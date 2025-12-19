"""
Anomaly Detection
Detects impossible movements, unrealistic speeds, and other anomalies
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from scipy import stats

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("anomaly_detector")


class AnomalyDetector:
    """
    Detects anomalies in tracking data (impossible movements, unrealistic speeds, etc.)
    """
    
    def __init__(self,
                 max_speed: float = 12.0,  # m/s (about 43 km/h, reasonable for soccer)
                 max_acceleration: float = 10.0,  # m/s²
                 max_jump_distance: float = 5.0,  # meters per frame
                 z_score_threshold: float = 3.0):
        """
        Initialize anomaly detector
        
        Args:
            max_speed: Maximum reasonable speed in m/s
            max_acceleration: Maximum reasonable acceleration in m/s²
            max_jump_distance: Maximum reasonable position jump in meters per frame
            z_score_threshold: Z-score threshold for statistical anomaly detection
        """
        self.max_speed = max_speed
        self.max_acceleration = max_acceleration
        self.max_jump_distance = max_jump_distance
        self.z_score_threshold = z_score_threshold
    
    def detect_anomalies(self, csv_path: str) -> Dict[str, Any]:
        """
        Detect all types of anomalies in tracking data
        
        Args:
            csv_path: Path to tracking CSV file
            
        Returns:
            Dictionary with detected anomalies
        """
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.error(f"Error reading CSV: {e}")
            return {'error': str(e)}
        
        anomalies = {
            'impossible_movements': [],
            'unrealistic_speeds': [],
            'unrealistic_accelerations': [],
            'statistical_anomalies': [],
            'position_jumps': []
        }
        
        if 'track_id' not in df.columns:
            return {'error': 'Missing track_id column'}
        
        # Detect anomalies per track
        for track_id in df['track_id'].dropna().unique():
            track_df = df[df['track_id'] == track_id].sort_values('frame_num')
            
            # Check for impossible movements
            impossible = self._detect_impossible_movements(track_id, track_df)
            anomalies['impossible_movements'].extend(impossible)
            
            # Check for unrealistic speeds
            speeds = self._detect_unrealistic_speeds(track_id, track_df)
            anomalies['unrealistic_speeds'].extend(speeds)
            
            # Check for unrealistic accelerations
            accelerations = self._detect_unrealistic_accelerations(track_id, track_df)
            anomalies['unrealistic_accelerations'].extend(accelerations)
            
            # Check for position jumps
            jumps = self._detect_position_jumps(track_id, track_df)
            anomalies['position_jumps'].extend(jumps)
        
        # Statistical anomaly detection
        statistical = self._detect_statistical_anomalies(df)
        anomalies['statistical_anomalies'].extend(statistical)
        
        # Summary
        anomalies['summary'] = {
            'total_impossible_movements': len(anomalies['impossible_movements']),
            'total_unrealistic_speeds': len(anomalies['unrealistic_speeds']),
            'total_unrealistic_accelerations': len(anomalies['unrealistic_accelerations']),
            'total_position_jumps': len(anomalies['position_jumps']),
            'total_statistical_anomalies': len(anomalies['statistical_anomalies'])
        }
        
        return anomalies
    
    def _detect_impossible_movements(self, track_id: int, track_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect impossible movements (teleportation, etc.)"""
        anomalies = []
        
        if 'x' not in track_df.columns or 'y' not in track_df.columns:
            return anomalies
        
        if 'frame_num' not in track_df.columns:
            return anomalies
        
        # Calculate frame-to-frame distances
        frames = track_df['frame_num'].values
        x_values = track_df['x'].values
        y_values = track_df['y'].values
        
        for i in range(len(frames) - 1):
            dx = x_values[i + 1] - x_values[i]
            dy = y_values[i + 1] - y_values[i]
            distance = np.sqrt(dx**2 + dy**2)
            
            # Assuming 60 fps, max reasonable movement per frame
            # Soccer field is ~100m, so max jump should be reasonable
            if distance > self.max_jump_distance:
                anomalies.append({
                    'track_id': int(track_id),
                    'frame': int(frames[i]),
                    'next_frame': int(frames[i + 1]),
                    'distance': float(distance),
                    'type': 'impossible_movement',
                    'severity': 'high'
                })
        
        return anomalies
    
    def _detect_unrealistic_speeds(self, track_id: int, track_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect unrealistic speeds"""
        anomalies = []
        
        if 'speed' not in track_df.columns:
            return anomalies
        
        speeds = track_df['speed'].values
        frames = track_df['frame_num'].values
        
        for i, speed in enumerate(speeds):
            if speed > self.max_speed:
                anomalies.append({
                    'track_id': int(track_id),
                    'frame': int(frames[i]),
                    'speed': float(speed),
                    'max_allowed': self.max_speed,
                    'type': 'unrealistic_speed',
                    'severity': 'medium'
                })
        
        return anomalies
    
    def _detect_unrealistic_accelerations(self, track_id: int, track_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect unrealistic accelerations"""
        anomalies = []
        
        if 'speed' not in track_df.columns or 'frame_num' not in track_df.columns:
            return anomalies
        
        speeds = track_df['speed'].values
        frames = track_df['frame_num'].values
        
        # Calculate acceleration (change in speed per frame)
        # Assuming 60 fps, convert to m/s²
        fps = 60.0
        for i in range(len(speeds) - 1):
            if frames[i + 1] - frames[i] == 1:  # Consecutive frames
                delta_speed = speeds[i + 1] - speeds[i]
                acceleration = delta_speed * fps  # m/s²
                
                if abs(acceleration) > self.max_acceleration:
                    anomalies.append({
                        'track_id': int(track_id),
                        'frame': int(frames[i]),
                        'acceleration': float(acceleration),
                        'max_allowed': self.max_acceleration,
                        'type': 'unrealistic_acceleration',
                        'severity': 'medium'
                    })
        
        return anomalies
    
    def _detect_position_jumps(self, track_id: int, track_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect sudden position jumps"""
        return self._detect_impossible_movements(track_id, track_df)  # Same logic
    
    def _detect_statistical_anomalies(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect statistical anomalies using Z-score"""
        anomalies = []
        
        numeric_columns = ['x', 'y', 'speed', 'confidence']
        for col in numeric_columns:
            if col in df.columns:
                values = df[col].dropna().values
                if len(values) > 10:  # Need enough data
                    z_scores = np.abs(stats.zscore(values))
                    outliers = np.where(z_scores > self.z_score_threshold)[0]
                    
                    for idx in outliers:
                        anomalies.append({
                            'column': col,
                            'row_index': int(df.index[idx]),
                            'value': float(values[idx]),
                            'z_score': float(z_scores[idx]),
                            'type': 'statistical_anomaly',
                            'severity': 'low'
                        })
        
        return anomalies

