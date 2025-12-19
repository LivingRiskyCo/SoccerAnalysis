"""
Event detection and tracking for Soccer Analysis Tool
"""

from .detector import EventDetector, DetectedEvent
from .marker_system import EventMarkerSystem, EventMarker

__all__ = [
    'EventDetector',
    'DetectedEvent',
    'EventMarkerSystem',
    'EventMarker'
]

