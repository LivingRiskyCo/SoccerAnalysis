"""
Predictive Analytics
Predict player positions, movements, and events
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import pandas as pd

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

logger = get_logger("predictive_analytics")


class PredictiveAnalytics:
    """
    Predicts player positions, movements, and events
    """
    
    def __init__(self, history_length: int = 30):
        """
        Initialize predictive analytics
        
        Args:
            history_length: Number of frames to keep in history
        """
        self.history_length = history_length
        self.position_history = {}  # track_id -> deque of positions
        self.velocity_history = {}  # track_id -> deque of velocities
    
    def update_track(self, track_id: int, x: float, y: float, frame_num: int):
        """
        Update track history for prediction
        
        Args:
            track_id: Track identifier
            x: X position
            y: Y position
            frame_num: Frame number
        """
        if track_id not in self.position_history:
            self.position_history[track_id] = deque(maxlen=self.history_length)
            self.velocity_history[track_id] = deque(maxlen=self.history_length)
        
        self.position_history[track_id].append((x, y, frame_num))
        
        # Calculate velocity
        if len(self.position_history[track_id]) >= 2:
            prev_pos = self.position_history[track_id][-2]
            curr_pos = self.position_history[track_id][-1]
            
            dt = curr_pos[2] - prev_pos[2]
            if dt > 0:
                vx = (curr_pos[0] - prev_pos[0]) / dt
                vy = (curr_pos[1] - prev_pos[1]) / dt
                self.velocity_history[track_id].append((vx, vy))
    
    def predict_position(self, track_id: int, frames_ahead: int = 5) -> Optional[Tuple[float, float]]:
        """
        Predict future position of a track
        
        Args:
            track_id: Track identifier
            frames_ahead: Number of frames to predict ahead
            
        Returns:
            Predicted (x, y) position or None
        """
        if track_id not in self.position_history or len(self.position_history[track_id]) < 2:
            return None
        
        positions = list(self.position_history[track_id])
        velocities = list(self.velocity_history[track_id])
        
        if len(velocities) == 0:
            return None
        
        # Get current position and average velocity
        current_pos = positions[-1]
        avg_velocity = np.mean(velocities, axis=0) if len(velocities) > 0 else np.array([0.0, 0.0])
        
        # Simple linear prediction
        predicted_x = current_pos[0] + avg_velocity[0] * frames_ahead
        predicted_y = current_pos[1] + avg_velocity[1] * frames_ahead
        
        return (float(predicted_x), float(predicted_y))
    
    def predict_movement_direction(self, track_id: int) -> Optional[float]:
        """
        Predict movement direction (angle in degrees)
        
        Args:
            track_id: Track identifier
            
        Returns:
            Direction angle in degrees (0-360) or None
        """
        if track_id not in self.velocity_history or len(self.velocity_history[track_id]) == 0:
            return None
        
        velocities = list(self.velocity_history[track_id])
        avg_velocity = np.mean(velocities, axis=0)
        
        # Calculate angle
        angle_rad = np.arctan2(avg_velocity[1], avg_velocity[0])
        angle_deg = np.degrees(angle_rad)
        
        # Normalize to 0-360
        if angle_deg < 0:
            angle_deg += 360
        
        return float(angle_deg)
    
    def predict_event_probability(self,
                                 track_id: int,
                                 event_type: str,
                                 context: Dict[str, Any]) -> float:
        """
        Predict probability of an event occurring
        
        Args:
            track_id: Track identifier
            event_type: Type of event ('shot', 'pass', 'goal', etc.)
            context: Context information (ball position, goal position, etc.)
            
        Returns:
            Probability (0-1) of event occurring
        """
        if track_id not in self.position_history:
            return 0.0
        
        positions = list(self.position_history[track_id])
        if len(positions) < 5:
            return 0.0
        
        current_pos = positions[-1]
        current_x, current_y = current_pos[0], current_pos[1]
        
        # Simple heuristics for event prediction
        if event_type == 'shot':
            # Predict shot based on proximity to goal and speed
            goal_x = context.get('goal_x', 0)
            goal_y = context.get('goal_y', 0)
            distance_to_goal = np.sqrt((current_x - goal_x)**2 + (current_y - goal_y)**2)
            
            # Closer to goal = higher probability
            if distance_to_goal < 20:
                return 0.8
            elif distance_to_goal < 50:
                return 0.5
            else:
                return 0.2
        
        elif event_type == 'pass':
            # Predict pass based on proximity to other players
            other_players = context.get('other_players', [])
            if len(other_players) > 0:
                min_distance = min([
                    np.sqrt((current_x - p[0])**2 + (current_y - p[1])**2)
                    for p in other_players
                ])
                
                if min_distance < 10:
                    return 0.7
                elif min_distance < 30:
                    return 0.4
                else:
                    return 0.1
        
        return 0.0
    
    def analyze_trajectory(self, track_id: int) -> Dict[str, Any]:
        """
        Analyze trajectory patterns for a track
        
        Args:
            track_id: Track identifier
            
        Returns:
            Dictionary with trajectory analysis
        """
        if track_id not in self.position_history or len(self.position_history[track_id]) < 5:
            return {}
        
        positions = list(self.position_history[track_id])
        velocities = list(self.velocity_history[track_id])
        
        # Calculate statistics
        total_distance = 0.0
        for i in range(len(positions) - 1):
            dx = positions[i+1][0] - positions[i][0]
            dy = positions[i+1][1] - positions[i][1]
            total_distance += np.sqrt(dx**2 + dy**2)
        
        avg_speed = np.mean([np.sqrt(v[0]**2 + v[1]**2) for v in velocities]) if velocities else 0.0
        max_speed = np.max([np.sqrt(v[0]**2 + v[1]**2) for v in velocities]) if velocities else 0.0
        
        return {
            'total_distance': float(total_distance),
            'avg_speed': float(avg_speed),
            'max_speed': float(max_speed),
            'num_frames': len(positions),
            'trajectory_type': self._classify_trajectory(positions)
        }
    
    def _classify_trajectory(self, positions: List[Tuple[float, float, int]]) -> str:
        """Classify trajectory type"""
        if len(positions) < 3:
            return "unknown"
        
        # Calculate movement pattern
        total_movement = 0.0
        for i in range(len(positions) - 1):
            dx = positions[i+1][0] - positions[i][0]
            dy = positions[i+1][1] - positions[i][1]
            total_movement += np.sqrt(dx**2 + dy**2)
        
        avg_movement = total_movement / (len(positions) - 1)
        
        if avg_movement < 1.0:
            return "stationary"
        elif avg_movement < 5.0:
            return "slow_movement"
        elif avg_movement < 15.0:
            return "moderate_movement"
        else:
            return "fast_movement"

