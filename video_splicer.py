"""
Video Splicer Tool
Splits large video files into smaller chunks for easier upload/download.
Supports time-based, size-based, and manual splitting with resolution/fps controls.
"""

import cv2
import os
import numpy as np
from typing import List, Tuple, Optional, Callable
import shutil


class VideoSplicer:
    """Handles video splitting operations"""
    
    def __init__(self):
        self.video_path: Optional[str] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.video_info: Optional[dict] = None
        self.progress_callback: Optional[Callable] = None
        
    def load_video(self, video_path: str) -> bool:
        """
        Load a video file and extract metadata
        
        Args:
            video_path: Path to video file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.cap:
                self.cap.release()
            
            self.video_path = video_path
            self.cap = cv2.VideoCapture(video_path)
            
            if not self.cap.isOpened():
                return False
            
            # Extract video information
            self.video_info = {
                'fps': self.cap.get(cv2.CAP_PROP_FPS),
                'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'frame_count': int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'duration_seconds': 0.0,
                'file_size_mb': 0.0,
                'codec': self._detect_codec()
            }
            
            # Calculate duration
            if self.video_info['fps'] > 0:
                self.video_info['duration_seconds'] = (
                    self.video_info['frame_count'] / self.video_info['fps']
                )
            
            # Get file size
            if os.path.exists(video_path):
                file_size_bytes = os.path.getsize(video_path)
                self.video_info['file_size_mb'] = file_size_bytes / (1024 * 1024)
            
            return True
            
        except Exception as e:
            print(f"Error loading video: {e}")
            return False
    
    def _detect_codec(self) -> str:
        """Detect video codec from file extension"""
        if not self.video_path:
            return "mp4v"
        
        ext = os.path.splitext(self.video_path)[1].lower()
        codec_map = {
            '.mp4': 'mp4v',
            '.avi': 'XVID',
            '.mov': 'mp4v',
            '.mkv': 'mp4v'
        }
        return codec_map.get(ext, 'mp4v')
    
    def get_video_info(self) -> Optional[dict]:
        """Get video information"""
        return self.video_info.copy() if self.video_info else None
    
    def set_progress_callback(self, callback: Callable):
        """Set callback function for progress updates"""
        self.progress_callback = callback
    
    def _update_progress(self, message: str, percent: float = None):
        """Call progress callback if set"""
        if self.progress_callback:
            self.progress_callback(message, percent)
    
    def split_by_time(self, 
                     chunk_duration_seconds: float,
                     output_dir: str,
                     resolution: Optional[Tuple[int, int]] = None,
                     fps: Optional[float] = None,
                     output_prefix: str = "part") -> List[str]:
        """
        Split video into time-based chunks
        
        Args:
            chunk_duration_seconds: Duration of each chunk in seconds
            output_dir: Directory to save output files
            resolution: Target resolution (width, height) or None for original
            fps: Target frame rate or None for original
            output_prefix: Prefix for output filenames
            
        Returns:
            List of output file paths
        """
        if not self.cap or not self.video_info:
            raise ValueError("Video not loaded. Call load_video() first.")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Get output settings
        out_width = resolution[0] if resolution else self.video_info['width']
        out_height = resolution[1] if resolution else self.video_info['height']
        out_fps = fps if fps else self.video_info['fps']
        
        # Calculate number of chunks
        total_duration = self.video_info['duration_seconds']
        num_chunks = int(np.ceil(total_duration / chunk_duration_seconds))
        
        output_files = []
        base_name = os.path.splitext(os.path.basename(self.video_path))[0]
        ext = os.path.splitext(self.video_path)[1]
        
        self._update_progress(f"Splitting into {num_chunks} chunks...", 0.0)
        
        for chunk_idx in range(num_chunks):
            start_time = chunk_idx * chunk_duration_seconds
            end_time = min((chunk_idx + 1) * chunk_duration_seconds, total_duration)
            
            output_filename = f"{output_prefix}{chunk_idx + 1:03d}{ext}"
            output_path = os.path.join(output_dir, output_filename)
            
            # Calculate overall progress (chunk-level)
            chunk_base_progress = (chunk_idx / num_chunks) * 100.0
            chunk_progress_range = 100.0 / num_chunks  # Progress range for this chunk
            
            self._update_progress(
                f"Processing chunk {chunk_idx + 1}/{num_chunks} ({start_time:.1f}s - {end_time:.1f}s)...",
                chunk_base_progress
            )
            
            # Store progress context for _process_chunk
            self._current_chunk_base = chunk_base_progress
            self._current_chunk_range = chunk_progress_range
            
            success = self._process_chunk(start_time, end_time, output_path, 
                                         out_width, out_height, out_fps)
            
            if success:
                output_files.append(output_path)
                # Update to show chunk is complete
                self._update_progress(
                    f"✓ Completed chunk {chunk_idx + 1}/{num_chunks}",
                    chunk_base_progress + chunk_progress_range
                )
            else:
                self._update_progress(f"⚠ Failed to create chunk {chunk_idx + 1}", None)
        
        self._update_progress(f"✓ Created {len(output_files)} chunks", 100.0)
        return output_files
    
    def split_by_size(self,
                     chunk_size_mb: float,
                     output_dir: str,
                     resolution: Optional[Tuple[int, int]] = None,
                     fps: Optional[float] = None,
                     output_prefix: str = "part") -> List[str]:
        """
        Split video into size-based chunks
        
        Args:
            chunk_size_mb: Target size of each chunk in MB
            output_dir: Directory to save output files
            resolution: Target resolution (width, height) or None for original
            fps: Target frame rate or None for original
            output_prefix: Prefix for output filenames
            
        Returns:
            List of output file paths
        """
        if not self.cap or not self.video_info:
            raise ValueError("Video not loaded. Call load_video() first.")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Estimate chunk duration from target size
        # Rough estimate: assume bitrate scales with resolution and fps
        total_size_mb = self.video_info['file_size_mb']
        total_duration = self.video_info['duration_seconds']
        
        # Estimate bitrate (MB per second)
        mb_per_second = total_size_mb / total_duration if total_duration > 0 else 0.1
        
        # Adjust for resolution/fps changes
        if resolution:
            scale_factor = (resolution[0] * resolution[1]) / (self.video_info['width'] * self.video_info['height'])
            mb_per_second *= scale_factor
        
        if fps:
            scale_factor = fps / self.video_info['fps']
            mb_per_second *= scale_factor
        
        # Calculate chunk duration
        chunk_duration_seconds = chunk_size_mb / mb_per_second if mb_per_second > 0 else 60.0
        
        # Use time-based splitting with calculated duration
        return self.split_by_time(chunk_duration_seconds, output_dir, resolution, fps, output_prefix)
    
    def split_manual(self,
                    split_points: List[float],
                    output_dir: str,
                    resolution: Optional[Tuple[int, int]] = None,
                    fps: Optional[float] = None,
                    output_prefix: str = "part") -> List[str]:
        """
        Split video at manual split points
        
        Args:
            split_points: List of timestamps (seconds) where to split
            output_dir: Directory to save output files
            resolution: Target resolution (width, height) or None for original
            fps: Target frame rate or None for original
            output_prefix: Prefix for output filenames
            
        Returns:
            List of output file paths
        """
        if not self.cap or not self.video_info:
            raise ValueError("Video not loaded. Call load_video() first.")
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Sort and validate split points
        split_points = sorted([float(sp) for sp in split_points])
        total_duration = self.video_info['duration_seconds']
        
        # Remove points outside video duration
        split_points = [sp for sp in split_points if 0 < sp < total_duration]
        
        # Add start and end
        all_points = [0.0] + split_points + [total_duration]
        
        # Get output settings
        out_width = resolution[0] if resolution else self.video_info['width']
        out_height = resolution[1] if resolution else self.video_info['height']
        out_fps = fps if fps else self.video_info['fps']
        
        base_name = os.path.splitext(os.path.basename(self.video_path))[0]
        ext = os.path.splitext(self.video_path)[1]
        
        output_files = []
        num_chunks = len(all_points) - 1
        
        self._update_progress(f"Splitting into {num_chunks} chunks at {len(split_points)} points...", 0.0)
        
        for chunk_idx in range(num_chunks):
            start_time = all_points[chunk_idx]
            end_time = all_points[chunk_idx + 1]
            
            output_filename = f"{output_prefix}{chunk_idx + 1:03d}{ext}"
            output_path = os.path.join(output_dir, output_filename)
            
            # Calculate overall progress (chunk-level)
            chunk_base_progress = (chunk_idx / num_chunks) * 100.0
            chunk_progress_range = 100.0 / num_chunks  # Progress range for this chunk
            
            self._update_progress(
                f"Processing chunk {chunk_idx + 1}/{num_chunks} ({start_time:.1f}s - {end_time:.1f}s)...",
                chunk_base_progress
            )
            
            # Store progress context for _process_chunk
            self._current_chunk_base = chunk_base_progress
            self._current_chunk_range = chunk_progress_range
            
            success = self._process_chunk(start_time, end_time, output_path,
                                         out_width, out_height, out_fps)
            
            if success:
                output_files.append(output_path)
                # Update to show chunk is complete
                self._update_progress(
                    f"✓ Completed chunk {chunk_idx + 1}/{num_chunks}",
                    chunk_base_progress + chunk_progress_range
                )
            else:
                self._update_progress(f"⚠ Failed to create chunk {chunk_idx + 1}", None)
        
        self._update_progress(f"✓ Created {len(output_files)} chunks", 100.0)
        return output_files
    
    def _process_chunk(self,
                      start_time: float,
                      end_time: float,
                      output_path: str,
                      width: int,
                      height: int,
                      fps: float) -> bool:
        """
        Process a single video chunk
        
        Args:
            start_time: Start time in seconds
            end_time: End time in seconds
            output_path: Path to save output file
            width: Output width
            height: Output height
            fps: Output frame rate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Reset to start
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            # Calculate frame numbers
            start_frame = int(start_time * self.video_info['fps'])
            end_frame = int(end_time * self.video_info['fps'])
            
            # Set starting position
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            # Determine codec
            codec = self._detect_codec()
            fourcc = cv2.VideoWriter_fourcc(*codec)
            
            # Create video writer
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            if not out.isOpened():
                # Try alternative codec
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
                if not out.isOpened():
                    return False
            
            frame_count = 0
            current_frame_num = start_frame
            total_frames = end_frame - start_frame
            
            # Calculate frame skip for FPS conversion
            input_fps = self.video_info['fps']
            frame_skip = 1.0
            if fps != input_fps and input_fps > 0:
                frame_skip = input_fps / fps  # How many input frames per output frame
            
            frame_skip_counter = 0.0
            last_progress_update = 0
            
            while current_frame_num < end_frame:
                ret, frame = self.cap.read()
                if not ret:
                    break
                
                # Handle FPS conversion (skip frames if output FPS is lower)
                if fps < input_fps and input_fps > 0:
                    frame_skip_counter += 1.0
                    if frame_skip_counter < frame_skip:
                        current_frame_num += 1
                        continue
                    # Reset counter, preserving fractional remainder for accuracy
                    frame_skip_counter = frame_skip_counter - frame_skip
                
                # If output FPS is higher, we'll duplicate frames (write same frame multiple times)
                # This is handled by writing the frame and then potentially writing it again
                
                # Resize if needed
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
                
                # Write frame (and duplicate if output FPS is higher than input)
                if fps > input_fps and input_fps > 0:
                    # Duplicate frames to match higher output FPS
                    duplicate_count = int(fps / input_fps)
                    for _ in range(duplicate_count):
                        out.write(frame)
                        frame_count += 1
                else:
                    # Normal write (or skip already handled above)
                    out.write(frame)
                    frame_count += 1
                
                current_frame_num += 1
                
                # Update progress every 100 frames or at the end
                if total_frames > 0 and (frame_count % 100 == 0 or current_frame_num >= end_frame):
                    chunk_progress = (frame_count / total_frames) * 100.0
                    # Only update if progress changed significantly (avoid too many updates)
                    if abs(chunk_progress - last_progress_update) >= 1.0 or current_frame_num >= end_frame:
                        # Calculate overall progress (chunk base + chunk progress)
                        if hasattr(self, '_current_chunk_base') and hasattr(self, '_current_chunk_range'):
                            overall_progress = self._current_chunk_base + (chunk_progress / 100.0) * self._current_chunk_range
                        else:
                            overall_progress = chunk_progress
                        self._update_progress(None, overall_progress)
                        last_progress_update = chunk_progress
            
            out.release()
            return True
            
        except Exception as e:
            print(f"Error processing chunk: {e}")
            return False
    
    def close(self):
        """Close video capture"""
        if self.cap:
            self.cap.release()
            self.cap = None

