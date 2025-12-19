"""
Anchor Frame Manager - Handles anchor frame creation and management
Shared across all viewer modes
"""

from typing import Dict, List, Optional
import json
import os
from pathlib import Path


class AnchorFrameManager:
    """Manages anchor frames (frame-level player tags with 1.00 confidence)"""
    
    def __init__(self):
        # Format: {frame_num: [{track_id, player_name, bbox: [x1, y1, x2, y2], confidence: 1.00, team, jersey_number}]}
        self.anchor_frames: Dict[int, List[Dict]] = {}
        self.video_path: Optional[str] = None
    
    def add_anchor(self, frame_num: int, track_id: Optional[int], player_name: str, 
                   bbox: List[float], team: str = "", jersey_number: str = ""):
        """Add an anchor frame tag"""
        if frame_num not in self.anchor_frames:
            self.anchor_frames[frame_num] = []
        
        anchor = {
            'track_id': track_id,
            'player_name': player_name,
            'bbox': bbox,
            'confidence': 1.00,
            'team': team,
            'jersey_number': jersey_number
        }
        
        # Check if anchor already exists for this track_id in this frame
        for existing in self.anchor_frames[frame_num]:
            if existing.get('track_id') == track_id:
                # Update existing
                existing.update(anchor)
                return
        
        # Add new anchor
        self.anchor_frames[frame_num].append(anchor)
    
    def remove_anchor(self, frame_num: int, track_id: Optional[int]):
        """Remove an anchor frame tag"""
        if frame_num not in self.anchor_frames:
            return
        
        self.anchor_frames[frame_num] = [
            a for a in self.anchor_frames[frame_num] 
            if a.get('track_id') != track_id
        ]
        
        # Remove frame entry if empty
        if not self.anchor_frames[frame_num]:
            del self.anchor_frames[frame_num]
    
    def get_anchors(self, frame_num: int) -> List[Dict]:
        """Get anchor frames for a specific frame"""
        return self.anchor_frames.get(frame_num, [])
    
    def get_all_anchors(self) -> Dict[int, List[Dict]]:
        """Get all anchor frames"""
        return self.anchor_frames.copy()
    
    def clear_anchors(self):
        """Clear all anchor frames"""
        self.anchor_frames.clear()
    
    def load_from_seed_config(self, seed_file_path: str) -> bool:
        """Load anchor frames from seed config file"""
        if not os.path.exists(seed_file_path):
            return False
        
        try:
            with open(seed_file_path, 'r') as f:
                config = json.load(f)
            
            anchor_frames_dict = config.get('anchor_frames', {})
            
            # Convert string keys to int
            self.anchor_frames = {}
            for frame_key, anchors in anchor_frames_dict.items():
                frame_num = int(frame_key) if isinstance(frame_key, str) else frame_key
                self.anchor_frames[frame_num] = anchors
            
            print(f"✓ Loaded {len(self.anchor_frames)} anchor frames from seed config")
            return True
        except Exception as e:
            print(f"Error loading anchor frames: {e}")
            return False
    
    def save_to_seed_config(self, seed_file_path: str, additional_data: Optional[Dict] = None) -> bool:
        """Save anchor frames to seed config file"""
        try:
            # Convert int keys to string for JSON
            anchor_frames_dict = {
                str(frame_num): anchors 
                for frame_num, anchors in self.anchor_frames.items()
            }
            
            config = {
                'anchor_frames': anchor_frames_dict,
                **(additional_data or {})
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(seed_file_path) if os.path.dirname(seed_file_path) else '.', exist_ok=True)
            
            with open(seed_file_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            print(f"✓ Saved {len(self.anchor_frames)} anchor frames to seed config")
            return True
        except Exception as e:
            print(f"Error saving anchor frames: {e}")
            return False
    
    def get_approved_mappings(self) -> Dict[str, tuple]:
        """Convert anchor frames to approved_mappings format: track_id -> (player_name, team, jersey_number)"""
        mappings = {}
        
        for frame_num, anchors in self.anchor_frames.items():
            for anchor in anchors:
                track_id = anchor.get('track_id')
                if track_id is not None:
                    tid_str = str(int(track_id))
                    player_name = anchor.get('player_name', '')
                    team = anchor.get('team', '')
                    jersey_number = anchor.get('jersey_number', '')
                    
                    if player_name:
                        mappings[tid_str] = (player_name, team, jersey_number)
        
        return mappings
    
    def count_anchors(self) -> int:
        """Get total number of anchor tags"""
        return sum(len(anchors) for anchors in self.anchor_frames.values())

