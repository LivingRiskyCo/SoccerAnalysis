"""
Progress Integration Helper
Connects progress tracker with analysis pipeline
"""

import threading
import time
from typing import Optional, Callable
try:
    from .progress_tracker import ProgressTracker
except ImportError:
    try:
        from soccer_analysis.utils.progress_tracker import ProgressTracker
    except ImportError:
        ProgressTracker = None


class ProgressIntegration:
    """
    Integrates ProgressTracker with analysis pipeline
    
    Provides callbacks and helpers for updating progress from analysis thread
    """
    
    def __init__(self, progress_tracker: Optional[ProgressTracker] = None,
                 gui_update_callback: Optional[Callable] = None):
        """
        Initialize progress integration
        
        Args:
            progress_tracker: ProgressTracker instance
            gui_update_callback: Function to call for GUI updates (main thread)
        """
        self.progress_tracker = progress_tracker
        self.gui_update_callback = gui_update_callback
        self.is_running = False
        self.update_thread = None
        self.last_frame = 0
        self.last_total = 0
    
    def start(self, total_items: int, item_name: str = "items"):
        """Start progress tracking"""
        if self.progress_tracker:
            self.progress_tracker.start(total_items)
        self.is_running = True
        self.last_frame = 0
        self.last_total = total_items
        
        # Start update thread if GUI callback provided
        if self.gui_update_callback:
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
    
    def update(self, current: int, status: str = "", details: str = "", phase: str = ""):
        """
        Update progress (can be called from any thread)
        
        Args:
            current: Current item number
            status: Status message
            details: Detailed status
            phase: Processing phase
        """
        self.last_frame = current
        if self.progress_tracker:
            self.progress_tracker.update(current, status, details, phase)
    
    def _update_loop(self):
        """Background thread to update GUI periodically"""
        while self.is_running:
            if self.progress_tracker and self.gui_update_callback:
                summary = self.progress_tracker.get_status_summary()
                # Schedule GUI update on main thread
                try:
                    self.gui_update_callback(
                        summary.get("current", 0),
                        summary.get("total", 0),
                        summary.get("status", ""),
                        summary.get("details", ""),
                        summary.get("phase", "")
                    )
                except:
                    pass  # GUI might be closed
            time.sleep(0.1)  # Update every 100ms
    
    def finish(self):
        """Mark progress as complete"""
        self.is_running = False
        if self.progress_tracker:
            self.progress_tracker.finish()
        if self.update_thread:
            self.update_thread.join(timeout=1.0)
    
    def is_cancelled(self) -> bool:
        """Check if cancelled"""
        if self.progress_tracker:
            return self.progress_tracker.is_cancelled()
        return False


def create_progress_callback(progress_integration: ProgressIntegration):
    """
    Create a callback function for use in analysis pipeline
    
    Args:
        progress_integration: ProgressIntegration instance
    
    Returns:
        Callback function that can be called from analysis code
    """
    def progress_callback(current: int, total: int, status: str = "", 
                         details: str = "", phase: str = ""):
        """Progress callback for analysis pipeline"""
        progress_integration.update(current, status, details, phase)
    
    return progress_callback

