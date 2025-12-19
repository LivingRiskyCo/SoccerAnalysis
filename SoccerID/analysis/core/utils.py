"""
Core Analysis Utilities
Unit conversions, drawing functions, and field calibration utilities
"""

import cv2
import numpy as np
import math
import json
import os
from typing import Optional, Tuple, Dict, Any, List

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ...utils.json_utils import safe_json_load, safe_json_save
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
        from SoccerID.utils.json_utils import safe_json_load, safe_json_save
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
            from json_utils import safe_json_load, safe_json_save
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)
            # Fallback JSON functions
            def safe_json_load(path):
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        return json.load(f)
                return None
            def safe_json_save(data, path):
                with open(path, 'w') as f:
                    json.dump(data, f, indent=2)

logger = get_logger("core_utils")


def meters_to_feet(meters):
    """Convert meters to feet"""
    if meters is None:
        return None
    return meters * 3.28084


def mps_to_mph(mps):
    """Convert meters per second to miles per hour"""
    if mps is None:
        return None
    return mps * 2.23694


def mps2_to_fts2(mps2):
    """Convert meters per second squared to feet per second squared"""
    if mps2 is None:
        return None
    return mps2 * 3.28084


def draw_direction_arrow(frame, center, direction_angle, arrow_length=20, arrow_color=(255, 255, 255), 
                        arrow_thickness=2, arrow_head_size=8):
    """
    Draw direction arrow under feet pointing in direction of travel.
    
    Args:
        frame: Frame to draw on
        center: (x, y) center position
        direction_angle: Angle in radians (0 = right, π/2 = down)
        arrow_length: Length of arrow shaft
        arrow_color: BGR color tuple
        arrow_thickness: Line thickness
        arrow_head_size: Size of arrowhead
    """
    cx, cy = center
    
    # Calculate arrow end point
    end_x = int(cx + arrow_length * math.cos(direction_angle))
    end_y = int(cy + arrow_length * math.sin(direction_angle))
    
    # Draw arrow shaft
    cv2.line(frame, (cx, cy), (end_x, end_y), arrow_color, arrow_thickness, cv2.LINE_AA)
    
    # Draw arrowhead
    arrow_angle1 = direction_angle + math.pi - math.pi / 6  # 150 degrees
    arrow_angle2 = direction_angle + math.pi + math.pi / 6  # 210 degrees
    
    head1_x = int(end_x + arrow_head_size * math.cos(arrow_angle1))
    head1_y = int(end_y + arrow_head_size * math.sin(arrow_angle1))
    head2_x = int(end_x + arrow_head_size * math.cos(arrow_angle2))
    head2_y = int(end_y + arrow_head_size * math.sin(arrow_angle2))
    
    # Draw arrowhead triangle
    arrow_points = np.array([[end_x, end_y], [head1_x, head1_y], [head2_x, head2_y]], np.int32)
    cv2.fillPoly(frame, [arrow_points], arrow_color)
    cv2.polylines(frame, [arrow_points], True, arrow_color, arrow_thickness, cv2.LINE_AA)


def load_field_calibration(calibration_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load field calibration data from JSON file.
    
    Args:
        calibration_path: Path to calibration file (default: field_calibration.json)
        
    Returns:
        Calibration dictionary with 'points' key, or None if not found
    """
    if calibration_path is None:
        calibration_path = "field_calibration.json"
    
    if not os.path.exists(calibration_path):
        return None
    
    try:
        data = safe_json_load(calibration_path)
        if data and "points" in data:
            return data
        return None
    except Exception as e:
        logger.warning(f"Error loading field calibration: {e}")
        return None


def load_ball_color_config(config_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Load ball color configuration from JSON file.
    
    Args:
        config_path: Path to config file (default: ball_color_config.json)
        
    Returns:
        Config dictionary with 'hsv_ranges' key, or None if not found
    """
    if config_path is None:
        config_path = "ball_color_config.json"
    
    if not os.path.exists(config_path):
        return None
    
    try:
        data = safe_json_load(config_path)
        if data and "hsv_ranges" in data:
            return data
        return None
    except Exception as e:
        logger.warning(f"Error loading ball color config: {e}")
        return None


def is_point_in_field(point: Tuple[float, float], 
                      field_calibration: Dict[str, Any],
                      strict_mode: bool = False,
                      margin_pixels: int = 0) -> bool:
    """
    Check if a point is within the calibrated field boundaries.
    
    Args:
        point: (x, y) point to check
        field_calibration: Field calibration dictionary with 'points' key
        strict_mode: If True, use strict boundary checking
        margin_pixels: Margin in pixels for boundary checking
        
    Returns:
        True if point is in field, False otherwise
    """
    if not field_calibration or "points" not in field_calibration:
        return True  # No calibration = assume in field
    
    points = field_calibration["points"]
    if len(points) < 4:
        return True  # Invalid calibration = assume in field
    
    x, y = point
    
    # Convert points to numpy array for easier processing
    pts = np.array(points, dtype=np.float32)
    
    # For 4-point calibration, check if point is inside the quadrilateral
    if len(points) == 4:
        # Use point polygon test
        result = cv2.pointPolygonTest(pts, (x, y), False)
        if strict_mode:
            return result >= 0  # On or inside
        else:
            return result > -margin_pixels  # Within margin
    
    # For 8-point calibration, use outer rectangle
    if len(points) >= 4:
        outer_pts = pts[:4]
        result = cv2.pointPolygonTest(outer_pts, (x, y), False)
        if strict_mode:
            return result >= 0
        else:
            return result > -margin_pixels
    
    return True  # Default: assume in field


def transform_point_to_field(point: Tuple[float, float],
                              homography_matrix: np.ndarray) -> Optional[Tuple[float, float]]:
    """
    Transform a point from image coordinates to field coordinates using homography.
    
    Args:
        point: (x, y) point in image coordinates
        homography_matrix: 3x3 homography matrix
        
    Returns:
        (x, y) point in field coordinates, or None if transformation fails
    """
    if homography_matrix is None or homography_matrix.shape != (3, 3):
        return None
    
    try:
        # Convert to homogeneous coordinates
        pt = np.array([point[0], point[1], 1.0], dtype=np.float32)
        
        # Apply homography
        transformed = homography_matrix @ pt
        
        # Normalize
        if transformed[2] != 0:
            x = transformed[0] / transformed[2]
            y = transformed[1] / transformed[2]
            return (x, y)
        return None
    except Exception as e:
        logger.debug(f"Error transforming point to field: {e}")
        return None


def transform_field_to_point(field_point: Tuple[float, float],
                             homography_inv: np.ndarray) -> Optional[Tuple[float, float]]:
    """
    Transform a point from field coordinates to image coordinates using inverse homography.
    
    Args:
        field_point: (x, y) point in field coordinates
        homography_inv: 3x3 inverse homography matrix
        
    Returns:
        (x, y) point in image coordinates, or None if transformation fails
    """
    if homography_inv is None or homography_inv.shape != (3, 3):
        return None
    
    try:
        # Convert to homogeneous coordinates
        pt = np.array([field_point[0], field_point[1], 1.0], dtype=np.float32)
        
        # Apply inverse homography
        transformed = homography_inv @ pt
        
        # Normalize
        if transformed[2] != 0:
            x = transformed[0] / transformed[2]
            y = transformed[1] / transformed[2]
            return (x, y)
        return None
    except Exception as e:
        logger.debug(f"Error transforming field to point: {e}")
        return None


def calculate_possession(ball_center: Optional[Tuple[float, float]],
                        player_centers: Dict[int, Tuple[float, float]],
                        frame_width: int,
                        frame_height: int) -> Tuple[Optional[int], Optional[float]]:
    """
    Calculate which player is closest to the ball (possession).
    
    Args:
        ball_center: (x, y) ball position, or None
        player_centers: Dictionary of {player_id: (x, y)} positions
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
        
    Returns:
        Tuple of (closest_player_id, distance) or (None, None) if no ball/players
    """
    if ball_center is None or len(player_centers) == 0:
        return None, None
    
    min_distance = float('inf')
    closest_player_id = None
    
    bx, by = ball_center
    
    for player_id, (px, py) in player_centers.items():
        distance = math.sqrt((bx - px)**2 + (by - py)**2)
        if distance < min_distance:
            min_distance = distance
            closest_player_id = player_id
    
    return closest_player_id, min_distance

