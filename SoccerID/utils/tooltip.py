"""
Tooltip System for GUI Controls
Provides contextual help and "Why?" explanations for all controls
"""

import tkinter as tk
from typing import Optional, Callable


class ToolTip:
    """
    Create a tooltip for a given widget
    
    Usage:
        tooltip = ToolTip(widget, "This is a helpful tooltip")
        tooltip = ToolTip(widget, "Short tip", detailed_text="Long explanation here")
    """
    
    def __init__(self, widget, text: str, detailed_text: Optional[str] = None, 
                 delay: int = 500, wrap_length: int = 300):
        """
        Initialize tooltip
        
        Args:
            widget: Tkinter widget to attach tooltip to
            text: Short tooltip text (shown on hover)
            detailed_text: Optional detailed explanation (shown with "Why?" button)
            delay: Delay in milliseconds before showing tooltip
            wrap_length: Maximum width for text wrapping
        """
        self.widget = widget
        self.text = text
        self.detailed_text = detailed_text
        self.delay = delay
        self.wrap_length = wrap_length
        self.tipwindow = None
        self.detailed_window = None
        self.id = None
        self.x = self.y = 0
        
        # Bind events
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)
        self.widget.bind('<ButtonPress>', self.leave)
    
    def enter(self, event=None):
        """Show tooltip after delay"""
        self.schedule()
    
    def leave(self, event=None):
        """Hide tooltip"""
        self.unschedule()
        self.hidetip()
    
    def schedule(self):
        """Schedule tooltip to appear"""
        self.unschedule()
        self.id = self.widget.after(self.delay, self.showtip)
    
    def unschedule(self):
        """Cancel scheduled tooltip"""
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
    
    def showtip(self, event=None):
        """Display the tooltip"""
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        # Create tooltip window
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        # Create frame with text
        frame = tk.Frame(tw, background="#ffffe0", relief=tk.SOLID, borderwidth=1)
        frame.pack(ipadx=1)
        
        label = tk.Label(frame, text=self.text, justify=tk.LEFT,
                        background="#ffffe0", relief=tk.FLAT, borderwidth=0,
                        font=("Arial", 9), wraplength=self.wrap_length)
        label.pack(ipadx=4, ipady=2)
        
        # Add "Why?" button if detailed text exists
        if self.detailed_text:
            why_button = tk.Button(frame, text="Why?", command=self.show_detailed,
                                  font=("Arial", 8), bg="#ffffe0", relief=tk.FLAT,
                                  cursor="hand2")
            why_button.pack(pady=2)
    
    def show_detailed(self):
        """Show detailed explanation window"""
        if self.detailed_window:
            return
        
        # Create detailed explanation window
        self.detailed_window = dw = tk.Toplevel(self.widget)
        dw.title("Explanation")
        dw.geometry("500x300")
        dw.transient(self.widget)
        
        # Center on screen
        dw.update_idletasks()
        x = (dw.winfo_screenwidth() // 2) - (dw.winfo_width() // 2)
        y = (dw.winfo_screenheight() // 2) - (dw.winfo_height() // 2)
        dw.geometry(f"+{x}+{y}")
        
        # Create frame
        frame = tk.Frame(dw, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(frame, text="Why?", font=("Arial", 12, "bold"))
        title.pack(anchor=tk.W, pady=(0, 10))
        
        # Detailed text
        text_widget = tk.Text(frame, wrap=tk.WORD, font=("Arial", 9),
                             bg="#fafafa", relief=tk.FLAT, padx=5, pady=5)
        text_widget.insert("1.0", self.detailed_text)
        text_widget.config(state=tk.DISABLED)
        text_widget.pack(fill=tk.BOTH, expand=True)
        
        # Close button
        close_btn = tk.Button(frame, text="Close", command=self.close_detailed)
        close_btn.pack(pady=10)
        
        # Close on window close
        dw.protocol("WM_DELETE_WINDOW", self.close_detailed)
    
    def close_detailed(self):
        """Close detailed explanation window"""
        if self.detailed_window:
            self.detailed_window.destroy()
            self.detailed_window = None
    
    def hidetip(self):
        """Hide tooltip"""
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()
        self.close_detailed()


def create_tooltip(widget, text: str, detailed_text: Optional[str] = None) -> ToolTip:
    """
    Convenience function to create a tooltip
    
    Args:
        widget: Tkinter widget
        text: Tooltip text
        detailed_text: Optional detailed explanation
    
    Returns:
        ToolTip instance
    """
    return ToolTip(widget, text, detailed_text)


# Tooltip text database for common controls
TOOLTIP_DATABASE = {
    "input_file": {
        "text": "Select the video file to analyze",
        "detailed": "Choose your recorded soccer video file. Supported formats: MP4, AVI, MOV. "
                   "The video should be recorded with a stable camera position for best results."
    },
    "output_file": {
        "text": "Output file path for analyzed video",
        "detailed": "The analyzed video with tracking overlays will be saved here. "
                   "If left empty, a default name will be generated based on the input filename."
    },
    "ball_tracking": {
        "text": "Enable ball detection and tracking",
        "detailed": "When enabled, the system will detect and track the soccer ball throughout the video. "
                   "This enables ball trajectory visualization, speed calculations, and possession tracking."
    },
    "player_tracking": {
        "text": "Enable player detection and tracking",
        "detailed": "When enabled, YOLO will detect players and track their movements. "
                   "This is required for player analytics, heatmaps, and team statistics."
    },
    "dewarp_enabled": {
        "text": "Correct fisheye distortion from ultra-wide lens",
        "detailed": "If your video was recorded with an ultra-wide lens (120° FOV), enable this to "
                   "correct the fisheye distortion and get straight field lines. This improves tracking accuracy."
    },
    "use_imperial_units": {
        "text": "Display measurements in feet and mph",
        "detailed": "When enabled, distances will be shown in feet instead of meters, and speeds in mph "
                   "instead of m/s. Useful for US-based users."
    },
    "yolo_confidence": {
        "text": "YOLO detection confidence threshold",
        "detailed": "Lower values (0.1-0.3) detect more objects but may include false positives. "
                   "Higher values (0.4-0.6) are more conservative. Default: 0.25"
    },
    "track_thresh": {
        "text": "Tracking confidence threshold",
        "detailed": "Minimum confidence required to maintain a track. Lower values keep tracks longer "
                   "but may include noise. Higher values are stricter but may drop valid tracks."
    },
    "use_reid": {
        "text": "Enable Re-ID for player recognition",
        "detailed": "Re-identification uses appearance features to recognize players across frames. "
                   "This improves tracking consistency, especially when players are occluded or leave the frame."
    },
    "gallery_similarity_threshold": {
        "text": "Player gallery matching threshold",
        "detailed": "Confidence threshold for matching detected players to known players in the gallery. "
                   "Lower values (0.3-0.4) match more aggressively. Higher values (0.5-0.6) are more conservative."
    },
    "dewarp_enabled": {
        "text": "Correct fisheye distortion from ultra-wide lens",
        "detailed": "If your video was recorded with an ultra-wide lens (120° FOV), enable this to "
                   "correct the fisheye distortion and get straight field lines. This improves tracking accuracy."
    },
    "remove_net_enabled": {
        "text": "Remove net from detection",
        "detailed": "When enabled, the system will attempt to mask out the goal net to prevent it from "
                   "being detected as players. Useful for videos with visible goal nets."
    },
    "preserve_audio": {
        "text": "Keep original audio in output video",
        "detailed": "When enabled, the original audio track from the input video will be preserved in "
                   "the output analyzed video. Disable to create silent videos (faster processing)."
    },
    "yolo_iou_threshold": {
        "text": "YOLO IoU threshold for non-maximum suppression",
        "detailed": "Intersection over Union threshold for filtering overlapping detections. "
                   "Lower values (0.3-0.4) keep more detections. Higher values (0.5-0.7) are more strict. "
                   "Default: 0.45"
    },
    "yolo_resolution": {
        "text": "YOLO processing resolution",
        "detailed": "Resolution at which YOLO processes frames. 'full' uses original resolution (most accurate but slower). "
                   "Lower resolutions are faster but may miss small players or reduce accuracy."
    },
    "track_thresh": {
        "text": "Tracking confidence threshold",
        "detailed": "Minimum confidence required to maintain a track. Lower values keep tracks longer "
                   "but may include noise. Higher values are stricter but may drop valid tracks."
    },
    "match_thresh": {
        "text": "Track matching threshold",
        "detailed": "Confidence threshold for matching new detections to existing tracks. "
                   "Lower values allow more matches (good for crowded scenes). Higher values are more conservative."
    },
    "use_reid": {
        "text": "Enable Re-ID for player recognition",
        "detailed": "Re-identification uses appearance features to recognize players across frames. "
                   "This improves tracking consistency, especially when players are occluded or leave the frame."
    },
    "reid_similarity_threshold": {
        "text": "Re-ID similarity threshold",
        "detailed": "Confidence threshold for Re-ID matching. Lower values match more aggressively. "
                   "Higher values require stronger appearance similarity."
    },
    "foot_based_tracking": {
        "text": "Use foot position for tracking",
        "detailed": "When enabled, tracking focuses on player foot positions rather than bounding box centers. "
                   "This provides more accurate ground position for distance and speed calculations."
    },
    "temporal_smoothing": {
        "text": "Apply temporal smoothing to tracks",
        "detailed": "Smooths player positions over time to reduce jitter and improve visual quality. "
                   "May slightly reduce responsiveness to sudden movements."
    },
    "show_bounding_boxes": {
        "text": "Display bounding boxes around players",
        "detailed": "Shows rectangular boxes around detected players in the output video. "
                   "Useful for debugging or when you want to see detection boundaries."
    },
    "show_circles_at_feet": {
        "text": "Show circles at player foot positions",
        "detailed": "Displays circular markers at each player's foot position. "
                   "This is the primary visualization for player tracking."
    },
    "show_player_labels": {
        "text": "Display player names/labels",
        "detailed": "Shows player names or track IDs above each player in the output video. "
                   "Useful for identifying players during playback."
    },
    "show_ball_trail": {
        "text": "Display ball trajectory trail",
        "detailed": "Shows a trail behind the ball indicating its path. "
                   "The trail length can be adjusted to show more or less history."
    },
    "show_heat_map": {
        "text": "Display player heat map overlay",
        "detailed": "Shows a heat map indicating where players have spent the most time on the field. "
                   "Warmer colors indicate more time spent in that area."
    },
    "preview_analysis": {
        "text": "Preview analysis on first 15 seconds",
        "detailed": "Runs a quick analysis on the first 15 seconds of video to test settings before "
                   "processing the entire video. Useful for verifying configuration."
    },
    "start_analysis": {
        "text": "Start full video analysis",
        "detailed": "Begins processing the entire video with current settings. This may take a while "
                   "depending on video length and resolution. Progress will be shown in the status area."
    },
    "setup_wizard": {
        "text": "Open Interactive Setup Wizard",
        "detailed": "Launches the step-by-step setup wizard to guide you through video setup, field calibration, "
                   "player tagging, and team color configuration. Recommended for first-time users."
    },
    "calibrate_field": {
        "text": "Calibrate field boundaries and dimensions",
        "detailed": "Opens the field calibration tool to mark field corners and define field dimensions. "
                   "This enables accurate distance measurements and field-based analytics."
    },
    "playback_viewer": {
        "text": "Open playback viewer for analyzed video",
        "detailed": "Opens a video player to review the analyzed video with all overlays and tracking data. "
                   "You can scrub through frames, adjust overlays, and view analytics."
    }
}

