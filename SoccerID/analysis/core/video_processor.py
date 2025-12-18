"""
Video Processing Module
Handles video I/O, frame reading, and basic video operations with caching and threading
"""

import cv2
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
import os
import sys
import threading
from queue import Queue
from collections import deque

# Try new structure imports first, fallback to legacy
try:
    from ...utils.logger_config import get_logger
    from ...utils.performance import FrameCache
except ImportError:
    try:
        from SoccerID.utils.logger_config import get_logger
        from SoccerID.utils.performance import FrameCache
    except ImportError:
        # Legacy fallback
        try:
            from logger_config import get_logger
            FrameCache = None
        except ImportError:
            import logging
            get_logger = lambda name: logging.getLogger(name)
            FrameCache = None

logger = get_logger("video_processor")


class VideoProcessor:
    """Handles video processing operations with caching and background loading"""
    
    def __init__(self, video_path: str, 
                 enable_caching: bool = True,
                 cache_size_mb: int = 512,
                 enable_prefetch: bool = True,
                 prefetch_buffer: int = 10):
        """
        Initialize video processor
        
        Args:
            video_path: Path to input video file
            enable_caching: Enable frame caching
            cache_size_mb: Cache size in MB
            enable_prefetch: Enable background frame prefetching
            prefetch_buffer: Number of frames to prefetch ahead
        """
        self.video_path = video_path
        self.cap = None
        self.fps = 30.0
        self.total_frames = 0
        self.width = 0
        self.height = 0
        self.frame_count = 0
        
        # Caching
        self.enable_caching = enable_caching and FrameCache is not None
        if self.enable_caching:
            self.cache = FrameCache(max_size_mb=cache_size_mb)
        else:
            self.cache = None
        
        # Prefetching
        self.enable_prefetch = enable_prefetch
        self.prefetch_buffer = prefetch_buffer
        self.prefetch_queue = Queue(maxsize=prefetch_buffer * 2)
        self.prefetch_thread = None
        self.prefetch_stop = threading.Event()
        self.current_read_position = 0
        
        self._open_video()
        
        if self.enable_prefetch:
            self._start_prefetch_thread()
    
    def _open_video(self):
        """Open video file and get properties"""
        try:
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                raise ValueError(f"Could not open video: {self.video_path}")
            
            # Get video properties
            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
            self.total_frames = int(frame_count) if frame_count and not np.isnan(frame_count) else 0
            width_val = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            height_val = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.width = int(width_val) if width_val and not np.isnan(width_val) else 0
            self.height = int(height_val) if height_val and not np.isnan(height_val) else 0
            
            logger.info(f"Opened video: {self.video_path}")
            logger.info(f"Properties: {self.width}x{self.height} @ {self.fps:.2f} fps, {self.total_frames} frames")
            
        except Exception as e:
            logger.error(f"Error opening video: {e}", exc_info=True)
            raise
    
    def read_frame(self, frame_num: Optional[int] = None) -> Optional[Tuple[np.ndarray, int]]:
        """
        Read a frame from video (with caching and prefetching)
        
        Args:
            frame_num: Frame number to read (None = next frame)
            
        Returns:
            Tuple of (frame, frame_number) or None if error
        """
        if self.cap is None:
            return None
        
        try:
            # Determine target frame number
            if frame_num is not None:
                target_frame = frame_num
            else:
                target_frame = self.current_read_position
            
            # Check cache first
            if self.enable_caching:
                cache_key = f"frame_{target_frame}"
                cached_frame = self.cache.get(cache_key)
                if cached_frame is not None:
                    self.frame_count = target_frame
                    self.current_read_position = target_frame + 1
                    return (cached_frame, target_frame)
            
            # Read from video
            if frame_num is not None:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            
            ret, frame = self.cap.read()
            if ret:
                current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                self.frame_count = current_frame
                self.current_read_position = current_frame + 1
                
                # Cache frame
                if self.enable_caching and frame is not None:
                    try:
                        import sys
                        frame_size = frame.nbytes if hasattr(frame, 'nbytes') else sys.getsizeof(frame)
                        self.cache.put(f"frame_{current_frame}", frame.copy(), frame_size)
                    except:
                        pass
                
                return (frame, current_frame)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error reading frame: {e}", exc_info=True)
            return None
    
    def read_frames_batch(self, frame_nums: List[int]) -> List[Optional[Tuple[np.ndarray, int]]]:
        """
        Read multiple frames in batch (optimized for sequential access)
        
        Args:
            frame_nums: List of frame numbers to read (should be sorted for best performance)
            
        Returns:
            List of (frame, frame_number) tuples
        """
        if not frame_nums:
            return []
        
        # Sort frame numbers for sequential reading
        sorted_frames = sorted(set(frame_nums))
        results = {}
        
        # Check cache first
        cached_frames = {}
        uncached_frames = []
        
        for frame_num in sorted_frames:
            if self.enable_caching:
                cache_key = f"frame_{frame_num}"
                cached_frame = self.cache.get(cache_key)
                if cached_frame is not None:
                    cached_frames[frame_num] = (cached_frame, frame_num)
                else:
                    uncached_frames.append(frame_num)
            else:
                uncached_frames.append(frame_num)
        
        # Read uncached frames sequentially (more efficient than random access)
        if uncached_frames and self.cap:
            try:
                # Read frames in order
                for frame_num in uncached_frames:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, frame = self.cap.read()
                    if ret:
                        current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
                        results[current_frame] = (frame, current_frame)
                        
                        # Cache frame
                        if self.enable_caching:
                            try:
                                frame_size = frame.nbytes if hasattr(frame, 'nbytes') else sys.getsizeof(frame)
                                self.cache.put(f"frame_{current_frame}", frame.copy(), frame_size)
                            except:
                                pass
            except Exception as e:
                logger.warning(f"Batch read error: {e}")
        
        # Combine cached and newly read frames
        all_results = {}
        all_results.update(cached_frames)
        all_results.update(results)
        
        # Return in original order
        return [all_results.get(fn) for fn in frame_nums]
    
    def _start_prefetch_thread(self):
        """Start background thread for prefetching frames"""
        if not self.enable_prefetch:
            return
        
        def prefetch_worker():
            """Background worker to prefetch frames"""
            prefetch_cap = cv2.VideoCapture(self.video_path)
            if not prefetch_cap.isOpened():
                return
            
            prefetch_position = 0
            
            while not self.prefetch_stop.is_set():
                try:
                    # Check if we need to prefetch
                    if self.prefetch_queue.qsize() < self.prefetch_buffer:
                        # Prefetch next frame
                        prefetch_cap.set(cv2.CAP_PROP_POS_FRAMES, prefetch_position)
                        ret, frame = prefetch_cap.read()
                        
                        if ret:
                            # Try to add to queue (non-blocking)
                            try:
                                self.prefetch_queue.put_nowait((prefetch_position, frame))
                                prefetch_position += 1
                            except:
                                pass  # Queue full, skip
                        else:
                            # End of video
                            break
                    else:
                        # Queue is full, wait a bit
                        self.prefetch_stop.wait(0.1)
                except Exception as e:
                    logger.warning(f"Prefetch error: {e}")
                    break
            
            prefetch_cap.release()
        
        self.prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        self.prefetch_thread.start()
    
    def _stop_prefetch_thread(self):
        """Stop prefetch thread"""
        if self.prefetch_thread:
            self.prefetch_stop.set()
            self.prefetch_thread.join(timeout=1.0)
    
    def get_frame(self, frame_num: int) -> Optional[np.ndarray]:
        """
        Get specific frame by number
        
        Args:
            frame_num: Frame number to get
            
        Returns:
            Frame array or None if error
        """
        result = self.read_frame(frame_num)
        if result:
            return result[0]
        return None
    
    def close(self):
        """Close video file and cleanup"""
        # Stop prefetch thread
        if self.enable_prefetch:
            self._stop_prefetch_thread()
        
        # Close video
        if self.cap:
            self.cap.release()
            self.cap = None
        
        # Clear cache
        if self.cache:
            self.cache.clear()
    
    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics"""
        if self.cache:
            return self.cache.get_stats()
        return None
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

