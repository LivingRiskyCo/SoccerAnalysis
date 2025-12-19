"""
Video Manager - Handles video loading, frame navigation, and video properties
Shared across all viewer modes
"""

import cv2
import os
import numpy as np
from typing import Optional, Tuple
from collections import OrderedDict
import threading


class VideoManager:
    """Manages video loading, frame access, and video properties"""
    
    def __init__(self, video_path: Optional[str] = None):
        self.video_path = video_path
        self.cap: Optional[cv2.VideoCapture] = None
        self.fps = 30.0
        self.total_frames = 0
        self.width = 0
        self.height = 0
        self.original_width = 0
        self.original_height = 0
        
        # Frame buffering for performance
        self.frame_buffer = OrderedDict()
        self.buffer_size = 320
        self.buffer_thread = None
        self.buffer_active = False
        self.buffer_lock = threading.Lock()
        self.buffer_cap = None  # Separate VideoCapture for buffer thread
        
        if video_path:
            self.load_video(video_path)
    
    def load_video(self, video_path: str) -> bool:
        """Load video file"""
        if not os.path.exists(video_path):
            print(f"Error: Video file not found: {video_path}")
            return False
        
        # Close existing video if open
        if self.cap:
            self.cap.release()
        if self.buffer_cap:
            self.buffer_cap.release()
        
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)
        
        if not self.cap.isOpened():
            print(f"Error: Could not open video: {video_path}")
            return False
        
        # Get video properties
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.total_frames = int(frame_count) if frame_count and not np.isnan(frame_count) else 0
        width_val = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height_val = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.width = int(width_val) if width_val and not np.isnan(width_val) else 0
        self.height = int(height_val) if height_val and not np.isnan(height_val) else 0
        self.original_width = self.width
        self.original_height = self.height
        
        # Create separate VideoCapture for buffering thread
        self.buffer_cap = cv2.VideoCapture(video_path)
        
        print(f"✓ Loaded video: {os.path.basename(video_path)} ({self.total_frames} frames, {self.width}x{self.height}, {self.fps:.1f} fps)")
        return True
    
    def get_frame(self, frame_num: int) -> Optional[np.ndarray]:
        """Get frame at specified frame number"""
        if not self.cap or not self.cap.isOpened():
            return None
        
        # Check buffer first
        with self.buffer_lock:
            if frame_num in self.frame_buffer:
                return self.frame_buffer[frame_num].copy()
        
        # Fallback to direct read
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = self.cap.read()
        if ret:
            return frame
        return None
    
    def start_buffering(self, current_frame: int = 0):
        """Start background frame buffering"""
        if self.buffer_active:
            return
        
        self.buffer_active = True
        self.buffer_thread = threading.Thread(target=self._buffer_worker, args=(current_frame,), daemon=True)
        self.buffer_thread.start()
    
    def stop_buffering(self):
        """Stop background frame buffering"""
        self.buffer_active = False
        if self.buffer_thread:
            self.buffer_thread.join(timeout=1.0)
    
    def _buffer_worker(self, start_frame: int):
        """Background worker for frame buffering"""
        if not self.buffer_cap or not self.buffer_cap.isOpened():
            return
        
        # Buffer frames ahead of current position
        for i in range(start_frame, min(start_frame + self.buffer_size, self.total_frames)):
            if not self.buffer_active:
                break
            
            self.buffer_cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = self.buffer_cap.read()
            if ret:
                with self.buffer_lock:
                    self.frame_buffer[i] = frame
                    # Limit buffer size
                    if len(self.frame_buffer) > self.buffer_size:
                        self.frame_buffer.popitem(last=False)  # Remove oldest
    
    def release(self):
        """Release video resources"""
        if self.cap:
            self.cap.release()
        if self.buffer_cap:
            self.buffer_cap.release()
        self.stop_buffering()
        self.frame_buffer.clear()
    
    def get_properties(self) -> dict:
        """Get video properties"""
        return {
            'fps': self.fps,
            'total_frames': self.total_frames,
            'width': self.width,
            'height': self.height,
            'original_width': self.original_width,
            'original_height': self.original_height,
        }

