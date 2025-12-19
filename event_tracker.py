"""
Event Tracking Module
Allows marking events during video playback with keyboard shortcuts
Stores events in CSV/JSON with timestamps and frame numbers
"""

import json
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

@dataclass
class GameEvent:
    """Represents a game event"""
    event_type: str  # "goal", "pass", "shot", "foul", "corner", "free_kick", "save", "tackle", "substitution", "custom"
    frame_num: int
    timestamp: float  # seconds from video start
    player_id: Optional[int] = None  # track_id of player involved
    player_name: Optional[str] = None
    team: Optional[str] = None
    description: Optional[str] = None  # Custom description
    video_path: Optional[str] = None
    x_position: Optional[float] = None  # Field position (normalized 0-1)
    y_position: Optional[float] = None
    metadata: Optional[Dict] = None  # Additional data

class EventTracker:
    def __init__(self, video_path: str, fps: float = 30.0):
        self.video_path = video_path
        self.fps = fps
        self.events: List[GameEvent] = []
        self.event_file_json = None
        self.event_file_csv = None
        
    def add_event(self, event_type: str, frame_num: int, 
                  player_id: Optional[int] = None, 
                  player_name: Optional[str] = None,
                  team: Optional[str] = None,
                  description: Optional[str] = None,
                  x_position: Optional[float] = None,
                  y_position: Optional[float] = None,
                  metadata: Optional[Dict] = None):
        """Add a new event"""
        timestamp = frame_num / self.fps if self.fps > 0 else 0
        
        event = GameEvent(
            event_type=event_type,
            frame_num=frame_num,
            timestamp=timestamp,
            player_id=player_id,
            player_name=player_name,
            team=team,
            description=description,
            video_path=self.video_path,
            x_position=x_position,
            y_position=y_position,
            metadata=metadata or {}
        )
        self.events.append(event)
        return event
    
    def save_events(self, output_dir: Optional[str] = None):
        """Save events to JSON and CSV files"""
        if not output_dir:
            output_dir = os.path.dirname(self.video_path) or "."
        
        base_name = os.path.splitext(os.path.basename(self.video_path))[0]
        
        # Save JSON
        json_path = os.path.join(output_dir, f"{base_name}_events.json")
        events_data = {
            "video_path": self.video_path,
            "fps": self.fps,
            "total_events": len(self.events),
            "created_at": datetime.now().isoformat(),
            "events": [asdict(event) for event in self.events]
        }
        with open(json_path, 'w') as f:
            json.dump(events_data, f, indent=2)
        self.event_file_json = json_path
        
        # Save CSV
        csv_path = os.path.join(output_dir, f"{base_name}_events.csv")
        if self.events:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "event_type", "frame_num", "timestamp", "player_id", "player_name",
                    "team", "description", "x_position", "y_position"
                ])
                writer.writeheader()
                for event in self.events:
                    writer.writerow({
                        "event_type": event.event_type,
                        "frame_num": event.frame_num,
                        "timestamp": f"{event.timestamp:.3f}",
                        "player_id": event.player_id or "",
                        "player_name": event.player_name or "",
                        "team": event.team or "",
                        "description": event.description or "",
                        "x_position": f"{event.x_position:.3f}" if event.x_position else "",
                        "y_position": f"{event.y_position:.3f}" if event.y_position else ""
                    })
        else:
            # Create empty CSV with headers
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "event_type", "frame_num", "timestamp", "player_id", "player_name",
                    "team", "description", "x_position", "y_position"
                ])
                writer.writeheader()
        self.event_file_csv = csv_path
        
        return json_path, csv_path
    
    def load_events(self, json_path: Optional[str] = None, csv_path: Optional[str] = None):
        """Load events from file"""
        if json_path and os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.events = [GameEvent(**event) for event in data.get("events", [])]
                return len(self.events)
        elif csv_path and os.path.exists(csv_path):
            self.events = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        event = GameEvent(
                            event_type=row["event_type"],
                            frame_num=int(row["frame_num"]),
                            timestamp=float(row["timestamp"]),
                            player_id=int(row["player_id"]) if row.get("player_id") and row["player_id"].strip() else None,
                            player_name=row["player_name"] or None,
                            team=row["team"] or None,
                            description=row.get("description") or None,
                            x_position=float(row["x_position"]) if row.get("x_position") and row["x_position"].strip() else None,
                            y_position=float(row["y_position"]) if row.get("y_position") and row["y_position"].strip() else None
                        )
                        self.events.append(event)
                    except (ValueError, KeyError) as e:
                        print(f"Warning: Skipping invalid event row: {e}")
                        continue
            return len(self.events)
        return 0
    
    def get_events_by_type(self, event_type: str) -> List[GameEvent]:
        """Get all events of a specific type"""
        return [e for e in self.events if e.event_type == event_type]
    
    def get_events_in_range(self, start_frame: int, end_frame: int) -> List[GameEvent]:
        """Get events within a frame range"""
        return [e for e in self.events if start_frame <= e.frame_num <= end_frame]
    
    def get_events_for_player(self, player_name: str) -> List[GameEvent]:
        """Get all events for a specific player"""
        return [e for e in self.events if e.player_name == player_name]
    
    def delete_event(self, event_index: int):
        """Delete an event by index"""
        if 0 <= event_index < len(self.events):
            del self.events[event_index]
            return True
        return False

