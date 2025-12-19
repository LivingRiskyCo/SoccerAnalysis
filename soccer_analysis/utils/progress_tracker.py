"""
Enhanced Progress Tracking with Time Estimates and Detailed Status
"""

import time
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque


@dataclass
class ProgressUpdate:
    """Single progress update"""
    timestamp: float
    progress: float  # 0.0 to 100.0
    status: str
    details: Optional[str] = None
    frame_num: Optional[int] = None
    total_frames: Optional[int] = None


class ProgressTracker:
    """
    Enhanced progress tracker with time estimates and detailed status
    
    Features:
    - Time remaining estimates
    - Processing speed calculation
    - Detailed status messages
    - Progress history
    - Cancel confirmation
    """
    
    def __init__(self, total_items: int = 0, item_name: str = "items"):
        """
        Initialize progress tracker
        
        Args:
            total_items: Total number of items to process
            item_name: Name of items being processed (e.g., "frames", "videos")
        """
        self.total_items = total_items
        self.item_name = item_name
        self.current_item = 0
        self.start_time: Optional[float] = None
        self.last_update_time: Optional[float] = None
        self.progress_history: deque = deque(maxlen=100)  # Keep last 100 updates
        
        # Status tracking
        self.current_status = "Ready"
        self.current_details = ""
        self.current_phase = "Initializing"
        
        # Time estimation
        self.items_per_second = 0.0
        self.estimated_remaining: Optional[timedelta] = None
        self.estimated_completion: Optional[datetime] = None
        
        # Cancel support
        self.cancelled = False
        self.cancel_callback: Optional[Callable] = None
        
        # Phase tracking
        self.phases: Dict[str, float] = {}  # phase_name -> progress_weight
        self.current_phase_progress = 0.0
    
    def start(self, total_items: Optional[int] = None):
        """Start tracking progress"""
        if total_items is not None:
            self.total_items = total_items
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.current_item = 0
        self.cancelled = False
        self.current_phase = "Starting"
        self._update_estimates()
    
    def update(self, current: int, status: str = "", details: str = "", 
               phase: Optional[str] = None):
        """
        Update progress
        
        Args:
            current: Current item number
            status: Status message
            details: Detailed status information
            phase: Current processing phase
        """
        if self.start_time is None:
            self.start()
        
        self.current_item = current
        if status:
            self.current_status = status
        if details:
            self.current_details = details
        if phase:
            self.current_phase = phase
        
        now = time.time()
        elapsed = now - self.start_time
        
        # Calculate items per second
        if elapsed > 0 and current > 0:
            self.items_per_second = current / elapsed
        
        # Update estimates
        self._update_estimates()
        
        # Record in history
        progress_pct = (current / self.total_items * 100) if self.total_items > 0 else 0.0
        update = ProgressUpdate(
            timestamp=now,
            progress=progress_pct,
            status=self.current_status,
            details=self.current_details,
            frame_num=current if self.item_name == "frames" else None,
            total_frames=self.total_items if self.item_name == "frames" else None
        )
        self.progress_history.append(update)
        
        self.last_update_time = now
    
    def _update_estimates(self):
        """Update time estimates"""
        if self.start_time is None or self.total_items == 0:
            return
        
        if self.current_item > 0 and self.items_per_second > 0:
            remaining_items = self.total_items - self.current_item
            seconds_remaining = remaining_items / self.items_per_second
            self.estimated_remaining = timedelta(seconds=int(seconds_remaining))
            self.estimated_completion = datetime.now() + self.estimated_remaining
        else:
            self.estimated_remaining = None
            self.estimated_completion = None
    
    def get_progress(self) -> float:
        """Get current progress percentage (0.0 to 100.0)"""
        if self.total_items == 0:
            return 0.0
        return min(100.0, (self.current_item / self.total_items) * 100.0)
    
    def get_elapsed_time(self) -> timedelta:
        """Get elapsed time"""
        if self.start_time is None:
            return timedelta(0)
        return timedelta(seconds=int(time.time() - self.start_time))
    
    def get_status_summary(self) -> Dict:
        """Get comprehensive status summary"""
        return {
            "progress": self.get_progress(),
            "current": self.current_item,
            "total": self.total_items,
            "status": self.current_status,
            "details": self.current_details,
            "phase": self.current_phase,
            "elapsed": self.get_elapsed_time(),
            "remaining": self.estimated_remaining,
            "completion": self.estimated_completion,
            "speed": self.items_per_second,
            "item_name": self.item_name
        }
    
    def get_formatted_status(self) -> str:
        """Get formatted status string for display"""
        progress = self.get_progress()
        elapsed = self.get_elapsed_time()
        
        status_parts = [
            f"{self.current_phase}: {progress:.1f}%",
            f"({self.current_item}/{self.total_items} {self.item_name})"
        ]
        
        if self.current_status:
            status_parts.append(f"- {self.current_status}")
        
        if self.estimated_remaining:
            status_parts.append(f" | ETA: {self._format_timedelta(self.estimated_remaining)}")
        
        if self.items_per_second > 0:
            status_parts.append(f" | Speed: {self.items_per_second:.1f} {self.item_name}/s")
        
        return " ".join(status_parts)
    
    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta as human-readable string"""
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def request_cancel(self) -> bool:
        """
        Request cancellation (returns True if confirmed)
        
        Returns:
            True if cancellation confirmed, False if cancelled
        """
        if self.cancel_callback:
            return self.cancel_callback()
        return True  # Default: allow cancellation
    
    def set_cancelled(self, cancelled: bool = True):
        """Set cancelled flag"""
        self.cancelled = cancelled
    
    def is_cancelled(self) -> bool:
        """Check if cancelled"""
        return self.cancelled
    
    def set_cancel_callback(self, callback: Callable[[], bool]):
        """Set callback for cancel confirmation"""
        self.cancel_callback = callback
    
    def finish(self):
        """Mark progress as complete"""
        if self.start_time:
            self.update(self.total_items, "Complete", "Processing finished")
            self.current_phase = "Complete"

