"""
Video Clip Manager
Creates video clips from events and manages highlight clips for players
"""

import cv2
import os
import json
import threading
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np


@dataclass
class VideoClip:
    """Represents a video clip"""
    clip_id: str
    event_type: str
    frame_start: int
    frame_end: int
    video_path: str
    clip_path: str
    player_id: Optional[int] = None
    player_name: Optional[str] = None
    team: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    duration: Optional[float] = None  # seconds
    thumbnail_path: Optional[str] = None
    metadata: Optional[Dict] = None


class ClipManager:
    """Manages video clip creation and storage"""
    
    def __init__(self, clips_dir: str = "clips"):
        self.clips_dir = clips_dir
        self.clips: Dict[str, VideoClip] = {}  # clip_id -> VideoClip
        self._ensure_clips_dir()
        self.load_clips()
    
    def _ensure_clips_dir(self):
        """Ensure clips directory exists"""
        if not os.path.exists(self.clips_dir):
            os.makedirs(self.clips_dir, exist_ok=True)
    
    def create_clip(self, video_path: str, frame_start: int, frame_end: int,
                   event_type: str, player_id: Optional[int] = None,
                   player_name: Optional[str] = None, team: Optional[str] = None,
                   description: Optional[str] = None, fps: float = 30.0,
                   include_overlays: bool = True, overlay_renderer=None,
                   progress_callback=None) -> Optional[VideoClip]:
        """Create a video clip from frame range"""
        if not os.path.exists(video_path):
            return None
        
        # Generate clip ID
        clip_id = f"{event_type}_{frame_start}_{frame_end}_{int(time.time())}"
        
        # Generate clip filename
        video_basename = os.path.splitext(os.path.basename(video_path))[0]
        clip_filename = f"{video_basename}_{clip_id}.mp4"
        clip_path = os.path.join(self.clips_dir, clip_filename)
        
        # Open input video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return None
        
        # Get video properties
        video_fps = cap.get(cv2.CAP_PROP_FPS) or fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Validate frame range
        frame_start = max(0, min(frame_start, total_frames - 1))
        frame_end = max(frame_start + 1, min(frame_end, total_frames))
        
        # Calculate duration
        duration = (frame_end - frame_start) / video_fps
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(clip_path, fourcc, video_fps, (width, height))
        
        if not out.isOpened():
            cap.release()
            return None
        
        # Seek to start frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)
        
        # Create thumbnail from first frame
        ret, thumbnail_frame = cap.read()
        thumbnail_path = None
        if ret:
            thumbnail_filename = f"{clip_id}_thumb.jpg"
            thumbnail_path = os.path.join(self.clips_dir, thumbnail_filename)
            cv2.imwrite(thumbnail_path, thumbnail_frame)
            # Reset to start
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)
        
        # Write frames
        frames_written = 0
        total_frames_to_write = frame_end - frame_start
        
        for frame_num in range(frame_start, frame_end):
            ret, frame = cap.read()
            if not ret:
                break
            
            # Apply overlays if requested
            if include_overlays and overlay_renderer:
                try:
                    frame = overlay_renderer.render_frame(frame, frame_num)
                except:
                    pass  # Continue without overlays if rendering fails
            
            out.write(frame)
            frames_written += 1
            
            # Update progress
            if progress_callback and frame_num % 10 == 0:
                progress = (frames_written / total_frames_to_write) * 100
                progress_callback(progress)
        
        cap.release()
        out.release()
        
        # Create clip object
        clip = VideoClip(
            clip_id=clip_id,
            event_type=event_type,
            frame_start=frame_start,
            frame_end=frame_end,
            video_path=video_path,
            clip_path=clip_path,
            player_id=player_id,
            player_name=player_name,
            team=team,
            description=description,
            created_at=datetime.now().isoformat(),
            duration=duration,
            thumbnail_path=thumbnail_path,
            metadata={}
        )
        
        # Save clip
        self.clips[clip_id] = clip
        self.save_clips()
        
        return clip
    
    def create_clip_from_event(self, video_path: str, event, fps: float = 30.0,
                              clip_duration_before: float = 2.0,
                              clip_duration_after: float = 3.0,
                              include_overlays: bool = True,
                              overlay_renderer=None,
                              progress_callback=None) -> Optional[VideoClip]:
        """Create clip from an event with context before/after"""
        frame_num = event.frame_num
        
        # Calculate frame range
        frames_before = int(clip_duration_before * fps)
        frames_after = int(clip_duration_after * fps)
        
        frame_start = max(0, frame_num - frames_before)
        frame_end = frame_num + frames_after
        
        return self.create_clip(
            video_path=video_path,
            frame_start=frame_start,
            frame_end=frame_end,
            event_type=event.event_type,
            player_id=event.player_id,
            player_name=event.player_name,
            team=event.team,
            description=event.description,
            fps=fps,
            include_overlays=include_overlays,
            overlay_renderer=overlay_renderer,
            progress_callback=progress_callback
        )
    
    def get_clips_for_player(self, player_name: str) -> List[VideoClip]:
        """Get all clips for a specific player"""
        return [clip for clip in self.clips.values() 
                if clip.player_name == player_name]
    
    def get_clips_by_event_type(self, event_type: str) -> List[VideoClip]:
        """Get all clips of a specific event type"""
        return [clip for clip in self.clips.values() 
                if clip.event_type == event_type]
    
    def delete_clip(self, clip_id: str) -> bool:
        """Delete a clip and its files"""
        if clip_id not in self.clips:
            return False
        
        clip = self.clips[clip_id]
        
        # Delete clip file
        if os.path.exists(clip.clip_path):
            try:
                os.remove(clip.clip_path)
            except:
                pass
        
        # Delete thumbnail
        if clip.thumbnail_path and os.path.exists(clip.thumbnail_path):
            try:
                os.remove(clip.thumbnail_path)
            except:
                pass
        
        # Remove from dictionary
        del self.clips[clip_id]
        self.save_clips()
        
        return True
    
    def save_clips(self):
        """Save clips metadata to JSON"""
        clips_file = os.path.join(self.clips_dir, "clips_metadata.json")
        clips_data = {
            "clips": [asdict(clip) for clip in self.clips.values()],
            "updated_at": datetime.now().isoformat()
        }
        with open(clips_file, 'w') as f:
            json.dump(clips_data, f, indent=2)
    
    def load_clips(self):
        """Load clips metadata from JSON"""
        clips_file = os.path.join(self.clips_dir, "clips_metadata.json")
        if os.path.exists(clips_file):
            try:
                with open(clips_file, 'r') as f:
                    data = json.load(f)
                    for clip_data in data.get("clips", []):
                        clip = VideoClip(**clip_data)
                        # Verify clip file exists
                        if os.path.exists(clip.clip_path):
                            self.clips[clip.clip_id] = clip
                        else:
                            # Clip file missing, skip it
                            pass
            except Exception as e:
                print(f"Warning: Could not load clips metadata: {e}")
    
    def export_clip(self, clip_id: str, output_path: str) -> bool:
        """Export clip to a specific location"""
        if clip_id not in self.clips:
            return False
        
        clip = self.clips[clip_id]
        if not os.path.exists(clip.clip_path):
            return False
        
        try:
            import shutil
            shutil.copy2(clip.clip_path, output_path)
            return True
        except Exception as e:
            print(f"Error exporting clip: {e}")
            return False
    
    def get_clip_info(self, clip_id: str) -> Optional[VideoClip]:
        """Get clip information"""
        return self.clips.get(clip_id)

