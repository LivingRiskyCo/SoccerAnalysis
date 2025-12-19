"""
Core Analysis Module
Video processing, detection, and tracking
"""

from .video_processor import VideoProcessor
from .detector import Detector
from .tracker import Tracker
from .utils import (
    meters_to_feet, mps_to_mph, mps2_to_fts2, draw_direction_arrow,
    load_field_calibration, load_ball_color_config,
    is_point_in_field, transform_point_to_field, transform_field_to_point,
    calculate_possession
)

__all__ = [
    'VideoProcessor', 'Detector', 'Tracker',
    'meters_to_feet', 'mps_to_mph', 'mps2_to_fts2', 'draw_direction_arrow',
    'load_field_calibration', 'load_ball_color_config',
    'is_point_in_field', 'transform_point_to_field', 'transform_field_to_point',
    'calculate_possession'
]
