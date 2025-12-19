"""
Player Path Animations
Animate player movement paths over time
"""

import cv2
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import pandas as pd

# Try to import logger
try:
    from ...utils.logger_config import get_logger
except ImportError:
    try:
        from soccer_analysis.utils.logger_config import get_logger
    except ImportError:
        try:
            from utils.logger_config import get_logger
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)

logger = get_logger("path_animations")


class PathAnimator:
    """
    Creates animated visualizations of player movement paths
    """
    
    def __init__(self,
                 trail_length: int = 100,
                 fade_trail: bool = True,
                 show_direction: bool = True,
                 show_speed_color: bool = True):
        """
        Initialize path animator
        
        Args:
            trail_length: Number of frames to show in trail
            fade_trail: Whether to fade trail over time
            show_direction: Whether to show direction arrows
            show_speed_color: Whether to color-code by speed
        """
        self.trail_length = trail_length
        self.fade_trail = fade_trail
        self.show_direction = show_direction
        self.show_speed_color = show_speed_color
        
        # Player path history: track_id -> deque of (frame_num, x, y, speed)
        self.path_history = {}  # track_id -> deque
    
    def update_path(self, track_id: int, x: float, y: float, frame_num: int, speed: Optional[float] = None):
        """
        Update path history for a track
        
        Args:
            track_id: Track identifier
            x: X position
            y: Y position
            frame_num: Frame number
            speed: Optional speed value
        """
        if track_id not in self.path_history:
            self.path_history[track_id] = deque(maxlen=self.trail_length)
        
        self.path_history[track_id].append((frame_num, x, y, speed or 0.0))
    
    def draw_path_animation(self,
                           frame: np.ndarray,
                           track_id: int,
                           color: Tuple[int, int, int] = (255, 255, 255),
                           thickness: int = 2) -> np.ndarray:
        """
        Draw animated path for a track
        
        Args:
            frame: Frame to draw on
            track_id: Track identifier
            color: Base color for path
            thickness: Line thickness
            
        Returns:
            Frame with path drawn
        """
        if track_id not in self.path_history or len(self.path_history[track_id]) < 2:
            return frame
        
        path_points = list(self.path_history[track_id])
        
        # Draw path segments
        for i in range(len(path_points) - 1):
            point1 = path_points[i]
            point2 = path_points[i + 1]
            
            x1, y1 = int(point1[1]), int(point1[2])
            x2, y2 = int(point2[1]), int(point2[2])
            
            # Calculate fade alpha if enabled
            alpha = 1.0
            if self.fade_trail:
                # Fade based on position in trail (newer = more opaque)
                position_in_trail = i / len(path_points)
                alpha = position_in_trail
            
            # Calculate color based on speed if enabled
            line_color = color
            if self.show_speed_color:
                speed = point2[3] if len(point2) > 3 else 0.0
                line_color = self._speed_to_color(speed)
            
            # Apply alpha
            if alpha < 1.0:
                line_color = tuple(int(c * alpha) for c in line_color)
            
            # Draw line segment
            cv2.line(frame, (x1, y1), (x2, y2), line_color, thickness)
        
        # Draw direction arrow if enabled
        if self.show_direction and len(path_points) >= 2:
            self._draw_direction_arrow(frame, path_points[-2], path_points[-1], color)
        
        return frame
    
    def _speed_to_color(self, speed: float) -> Tuple[int, int, int]:
        """
        Convert speed to color (blue = slow, red = fast)
        
        Args:
            speed: Speed in m/s
            
        Returns:
            BGR color tuple
        """
        # Normalize speed (0-15 m/s range)
        normalized = min(1.0, max(0.0, speed / 15.0))
        
        # Blue (slow) to Red (fast)
        if normalized < 0.5:
            # Blue to Cyan
            blue = 255
            green = int(255 * normalized * 2)
            red = 0
        else:
            # Cyan to Red
            blue = int(255 * (1.0 - (normalized - 0.5) * 2))
            green = 255
            red = int(255 * (normalized - 0.5) * 2)
        
        return (int(blue), int(green), int(red))
    
    def _draw_direction_arrow(self,
                             frame: np.ndarray,
                             point1: Tuple,
                             point2: Tuple,
                             color: Tuple[int, int, int]):
        """Draw direction arrow"""
        x1, y1 = int(point1[1]), int(point1[2])
        x2, y2 = int(point2[1]), int(point2[2])
        
        # Calculate angle
        dx = x2 - x1
        dy = y2 - y1
        angle = np.arctan2(dy, dx)
        
        # Arrow parameters
        arrow_length = 15
        arrow_head_size = 8
        
        # Calculate arrow end point
        arrow_x = int(x2 - arrow_length * np.cos(angle))
        arrow_y = int(y2 - arrow_length * np.sin(angle))
        
        # Draw arrow
        cv2.arrowedLine(
            frame,
            (arrow_x, arrow_y),
            (x2, y2),
            color,
            2,
            tipLength=0.3
        )
    
    def create_path_video(self,
                         video_path: str,
                         csv_path: str,
                         output_path: str,
                         track_ids: Optional[List[int]] = None,
                         fps: float = 30.0) -> bool:
        """
        Create animated path video from tracking data
        
        Args:
            video_path: Input video path
            csv_path: Tracking CSV path
            output_path: Output video path
            track_ids: Optional list of track IDs to animate
            fps: Video FPS
            
        Returns:
            True if successful
        """
        try:
            # Load tracking data
            df = pd.read_csv(csv_path)
            
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                logger.error(f"Could not open video: {video_path}")
                return False
            
            # Get video properties
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            video_fps = cap.get(cv2.CAP_PROP_FPS) or fps
            
            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, video_fps, (width, height))
            
            frame_num = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Get tracking data for this frame
                frame_data = df[df['frame_num'] == frame_num]
                
                # Update paths and draw
                for _, row in frame_data.iterrows():
                    track_id = int(row.get('track_id', 0))
                    if track_ids and track_id not in track_ids:
                        continue
                    
                    x = float(row.get('x', 0))
                    y = float(row.get('y', 0))
                    speed = float(row.get('speed', 0))
                    
                    # Update path
                    self.update_path(track_id, x, y, frame_num, speed)
                    
                    # Draw path
                    player_color = self._get_player_color(track_id)
                    frame = self.draw_path_animation(frame, track_id, player_color)
                
                # Write frame
                out.write(frame)
                frame_num += 1
            
            # Cleanup
            cap.release()
            out.release()
            
            logger.info(f"Created path animation video: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create path video: {e}")
            return False
    
    def _get_player_color(self, track_id: int) -> Tuple[int, int, int]:
        """Get color for a player track"""
        # Generate consistent color based on track ID
        np.random.seed(track_id)
        color = np.random.randint(0, 255, 3).tolist()
        return tuple(int(c) for c in color)
    
    def clear_paths(self, track_id: Optional[int] = None):
        """Clear path history"""
        if track_id is not None:
            self.path_history.pop(track_id, None)
        else:
            self.path_history.clear()

