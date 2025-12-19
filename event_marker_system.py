"""
Event Marker System
Allows marking events (passes, shots, goals, etc.) on the timeline as anchor points
for the event detection system. Can be used in playback viewer, setup wizard, and seeder.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class EventType(Enum):
    """Types of events that can be marked"""
    PASS = "pass"
    SHOT = "shot"
    GOAL = "goal"
    TACKLE = "tackle"
    SAVE = "save"
    CORNER = "corner"
    FREE_KICK = "free_kick"
    PENALTY = "penalty"
    OFFSIDE = "offside"
    CUSTOM = "custom"


@dataclass
class EventMarker:
    """Represents a single event marker on the timeline"""
    frame_num: int
    event_type: EventType
    timestamp: float  # In seconds
    player_name: Optional[str] = None
    player_id: Optional[int] = None
    team: Optional[str] = None
    confidence: float = 1.0  # Manual markers have 1.0 confidence
    position: Optional[Tuple[float, float]] = None  # (x, y) in normalized coordinates
    metadata: Optional[Dict] = None  # Additional event-specific data
    notes: Optional[str] = None  # User notes
    created_at: Optional[str] = None  # ISO timestamp
    
    def __post_init__(self):
        if isinstance(self.event_type, str):
            self.event_type = EventType(self.event_type)
        if self.metadata is None:
            self.metadata = {}
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        if self.position:
            data['position'] = list(self.position)
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'EventMarker':
        """Create from dictionary"""
        if 'position' in data and data['position']:
            data['position'] = tuple(data['position'])
        return cls(**data)


class EventMarkerSystem:
    """Manages event markers for a video"""
    
    def __init__(self, video_path: Optional[str] = None):
        self.video_path = video_path
        self.markers: List[EventMarker] = []
        self._markers_by_frame: Dict[int, List[EventMarker]] = {}  # Cache for fast lookup
        
    def add_marker(self, marker: EventMarker) -> None:
        """Add a new event marker"""
        self.markers.append(marker)
        self._update_frame_index(marker.frame_num)
        # Sort markers by frame number
        self.markers.sort(key=lambda m: m.frame_num)
    
    def remove_marker(self, frame_num: int, event_type: Optional[EventType] = None) -> bool:
        """Remove marker(s) at a specific frame. If event_type is specified, only remove that type."""
        removed = False
        markers_to_remove = []
        
        for marker in self.markers:
            if marker.frame_num == frame_num:
                if event_type is None or marker.event_type == event_type:
                    markers_to_remove.append(marker)
                    removed = True
        
        for marker in markers_to_remove:
            self.markers.remove(marker)
        
        if removed:
            self._rebuild_frame_index()
        
        return removed
    
    def get_markers_at_frame(self, frame_num: int) -> List[EventMarker]:
        """Get all markers at a specific frame"""
        return self._markers_by_frame.get(frame_num, [])
    
    def get_markers_in_range(self, start_frame: int, end_frame: int) -> List[EventMarker]:
        """Get all markers in a frame range"""
        return [m for m in self.markers if start_frame <= m.frame_num <= end_frame]
    
    def get_markers_by_type(self, event_type: EventType) -> List[EventMarker]:
        """Get all markers of a specific type"""
        return [m for m in self.markers if m.event_type == event_type]
    
    def get_all_markers(self) -> List[EventMarker]:
        """Get all markers, sorted by frame number"""
        return sorted(self.markers, key=lambda m: m.frame_num)
    
    def clear_markers(self, event_type: Optional[EventType] = None) -> None:
        """Clear all markers, or markers of a specific type"""
        if event_type is None:
            self.markers.clear()
        else:
            self.markers = [m for m in self.markers if m.event_type != event_type]
        self._rebuild_frame_index()
    
    def _update_frame_index(self, frame_num: int) -> None:
        """Update the frame index cache"""
        if frame_num not in self._markers_by_frame:
            self._markers_by_frame[frame_num] = []
        # Rebuild for this frame
        self._markers_by_frame[frame_num] = [
            m for m in self.markers if m.frame_num == frame_num
        ]
    
    def _rebuild_frame_index(self) -> None:
        """Rebuild the entire frame index"""
        self._markers_by_frame = {}
        for marker in self.markers:
            if marker.frame_num not in self._markers_by_frame:
                self._markers_by_frame[marker.frame_num] = []
            self._markers_by_frame[marker.frame_num].append(marker)
    
    def save_to_file(self, file_path: Optional[str] = None) -> str:
        """Save markers to JSON file"""
        if file_path is None:
            if self.video_path:
                video_dir = os.path.dirname(os.path.abspath(self.video_path))
                video_basename = os.path.splitext(os.path.basename(self.video_path))[0]
                file_path = os.path.join(video_dir, f"{video_basename}_event_markers.json")
            else:
                file_path = "event_markers.json"
        
        data = {
            'video_path': self.video_path,
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'markers': [m.to_dict() for m in self.markers]
        }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        return file_path
    
    def load_from_file(self, file_path: str) -> bool:
        """Load markers from JSON file"""
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            self.video_path = data.get('video_path', self.video_path)
            self.markers = [EventMarker.from_dict(m) for m in data.get('markers', [])]
            self._rebuild_frame_index()
            return True
        except Exception as e:
            print(f"Error loading event markers: {e}")
            return False
    
    def export_to_event_detection_format(self) -> List[Dict]:
        """Export markers in format compatible with event detection system"""
        events = []
        for marker in self.markers:
            event = {
                'event_type': marker.event_type.value,
                'frame_num': marker.frame_num,
                'timestamp': marker.timestamp,
                'confidence': marker.confidence,
                'player_name': marker.player_name,
                'player_id': marker.player_id,
                'team': marker.team,
                'start_pos': marker.position,
                'end_pos': marker.position,  # Manual markers typically have same start/end
                'metadata': marker.metadata or {},
                'is_manual': True,  # Flag to indicate this is a manual marker
                'notes': marker.notes
            }
            events.append(event)
        return events
    
    def merge_with_detected_events(self, detected_events: List[Dict], 
                                   merge_threshold_frames: int = 5) -> List[Dict]:
        """
        Merge manual markers with detected events.
        If a detected event is within merge_threshold_frames of a manual marker,
        prefer the manual marker (higher confidence).
        """
        merged = []
        used_markers = set()
        
        # Convert markers to event format
        marker_events = {m.frame_num: m for m in self.markers}
        
        for detected_event in detected_events:
            frame_num = detected_event.get('frame_num', 0)
            
            # Check if there's a manual marker nearby
            nearby_marker = None
            for marker_frame, marker in marker_events.items():
                if abs(marker_frame - frame_num) <= merge_threshold_frames:
                    if marker.event_type.value == detected_event.get('event_type'):
                        nearby_marker = marker
                        break
            
            if nearby_marker:
                # Use manual marker instead
                event = nearby_marker.to_dict()
                event['is_manual'] = True
                event['detected_confidence'] = detected_event.get('confidence', 0)
                merged.append(event)
                used_markers.add(nearby_marker.frame_num)
            else:
                # Use detected event
                detected_event['is_manual'] = False
                merged.append(detected_event)
        
        # Add any unused manual markers
        for marker_frame, marker in marker_events.items():
            if marker_frame not in used_markers:
                event = marker.to_dict()
                event['is_manual'] = True
                merged.append(event)
        
        # Sort by frame number
        merged.sort(key=lambda e: e.get('frame_num', 0))
        return merged
    
    def get_statistics(self) -> Dict:
        """Get statistics about markers"""
        stats = {
            'total_markers': len(self.markers),
            'by_type': {},
            'frame_range': None
        }
        
        if self.markers:
            stats['frame_range'] = (
                min(m.frame_num for m in self.markers),
                max(m.frame_num for m in self.markers)
            )
        
        for event_type in EventType:
            count = len([m for m in self.markers if m.event_type == event_type])
            if count > 0:
                stats['by_type'][event_type.value] = count
        
        return stats

