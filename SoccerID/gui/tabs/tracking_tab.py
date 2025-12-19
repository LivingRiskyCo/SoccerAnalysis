"""
Tracking Tab Component
Extracted from soccer_analysis_gui.py for better organization
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

# Add parent directories to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import tooltip system
try:
    from SoccerID.utils.tooltip import create_tooltip, TOOLTIP_DATABASE
except ImportError:
    try:
        from utils.tooltip import create_tooltip, TOOLTIP_DATABASE
    except ImportError:
        # Fallback: create dummy function
        def create_tooltip(widget, text, detailed_text=None):
            pass
        TOOLTIP_DATABASE = {}


class TrackingTab:
    """Tracking Stability Settings Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize tracking tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks and variables)
            parent_frame: Parent frame to create tab in (should be scrollable canvas frame)
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        self.create_tab()
    
    def create_tab(self):
        """Create the Tracking tab content"""
        # Ensure parent_frame has column configuration
        self.parent_frame.columnconfigure(1, weight=1)
        
        tracking_row = 0
        
        # Player Tracking Stability
        tracking_frame = ttk.LabelFrame(self.parent_frame, text="Player Tracking Stability", padding="10")
        tracking_frame.grid(row=tracking_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=10)
        tracking_frame.columnconfigure(0, weight=0, minsize=180)
        tracking_frame.columnconfigure(1, weight=0, minsize=100)
        tracking_frame.columnconfigure(2, weight=1, minsize=300)
        tracking_row += 1
        
        # Detection Threshold
        ttk.Label(tracking_frame, text="Detection Threshold:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        track_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.1, to=0.5, increment=0.05,
                                           textvariable=self.parent_gui.track_thresh, width=8)
        track_thresh_spinbox.grid(row=0, column=1, padx=5, pady=5)
        create_tooltip(track_thresh_spinbox, 
                      TOOLTIP_DATABASE.get("track_thresh", {}).get("text", "Tracking confidence threshold"),
                      TOOLTIP_DATABASE.get("track_thresh", {}).get("detailed"))
        ttk.Label(tracking_frame, text="(lower = more detections, default: 0.20)", wraplength=280).grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Match Threshold
        ttk.Label(tracking_frame, text="Match Threshold:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        match_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.5, to=1.0, increment=0.1,
                                           textvariable=self.parent_gui.match_thresh, width=8)
        match_thresh_spinbox.grid(row=1, column=1, padx=5, pady=5)
        create_tooltip(match_thresh_spinbox, 
                      TOOLTIP_DATABASE.get("match_thresh", {}).get("text", "Track matching threshold"),
                      TOOLTIP_DATABASE.get("match_thresh", {}).get("detailed"))
        ttk.Label(tracking_frame, text="(higher = stricter matching, default: 0.6)", wraplength=280).grid(row=1, column=2, sticky=tk.W, padx=5)
        
        # Track Buffer Time (seconds)
        ttk.Label(tracking_frame, text="Track Buffer Time (Seconds):", font=("Arial", 9, "bold")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        track_buffer_seconds_spinbox = ttk.Spinbox(tracking_frame, from_=1.0, to=15.0, increment=0.5,
                                                   textvariable=self.parent_gui.track_buffer_seconds, width=10, format="%.1f")
        track_buffer_seconds_spinbox.grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(how long to keep lost tracks alive, higher = less blinking, default: 5.0s)", 
                 foreground="darkgreen", wraplength=280).grid(row=2, column=2, sticky=tk.W, padx=5)
        
        # Legacy Track Buffer (frames)
        ttk.Label(tracking_frame, text="Track Buffer (Frames, Legacy):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        track_buffer_spinbox = ttk.Spinbox(tracking_frame, from_=30, to=500, increment=10,
                                          textvariable=self.parent_gui.track_buffer, width=10)
        track_buffer_spinbox.grid(row=3, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(only used if Buffer Time = 0, otherwise auto-calculated)", 
                 font=("Arial", 7), foreground="gray", wraplength=280).grid(row=3, column=2, sticky=tk.W, padx=5)
        
        # Tracker Type
        ttk.Label(tracking_frame, text="Tracker Type:", font=("Arial", 9, "bold")).grid(row=4, column=0, sticky=tk.W, padx=5, pady=5)
        
        # Check if BoxMOT is available
        boxmot_available = False
        try:
            from boxmot import DeepOcSort
            boxmot_available = True
        except ImportError:
            boxmot_available = False
        
        if boxmot_available:
            tracker_options = ["bytetrack", "ocsort", "deepocsort", "strongsort", "botsort"]
        else:
            tracker_options = ["bytetrack", "ocsort"]
        
        tracker_type_combo = ttk.Combobox(tracking_frame, textvariable=self.parent_gui.tracker_type,
                                         values=tracker_options, state="readonly", width=15)
        tracker_type_combo.grid(row=4, column=1, padx=5, pady=5)
        
        if boxmot_available:
            tracker_help_text = "(DeepOCSORT/StrongSORT: best for occlusions, ByteTrack: fastest, OC-SORT: balanced)"
        else:
            tracker_help_text = "(OC-SORT: better for scrums/bunched players, ByteTrack: faster for open play)"
        ttk.Label(tracking_frame, text=tracker_help_text, 
                 foreground="darkgreen", wraplength=280).grid(row=4, column=2, sticky=tk.W, padx=5)
        
        # Video FPS
        ttk.Label(tracking_frame, text="Video FPS:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=5)
        video_fps_spinbox = ttk.Spinbox(tracking_frame, from_=0, to=240, increment=1,
                                        textvariable=self.parent_gui.video_fps, width=8)
        video_fps_spinbox.grid(row=5, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(0 = auto-detect, set manually if detection is wrong)", wraplength=280).grid(row=5, column=2, sticky=tk.W, padx=5)
        
        # Output FPS
        ttk.Label(tracking_frame, text="Output FPS:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=5)
        output_fps_spinbox = ttk.Spinbox(tracking_frame, from_=0, to=120, increment=1,
                                         textvariable=self.parent_gui.output_fps, width=8)
        output_fps_spinbox.grid(row=6, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(0 = same as input, lower = smaller file)", wraplength=280).grid(row=6, column=2, sticky=tk.W, padx=5)
        
        # Temporal Smoothing
        temporal_smoothing_check = ttk.Checkbutton(tracking_frame, text="Temporal Smoothing",
                                                   variable=self.parent_gui.temporal_smoothing)
        temporal_smoothing_check.grid(row=7, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        create_tooltip(temporal_smoothing_check, 
                      TOOLTIP_DATABASE.get("temporal_smoothing", {}).get("text", "Apply temporal smoothing to tracks"),
                      TOOLTIP_DATABASE.get("temporal_smoothing", {}).get("detailed"))
        ttk.Label(tracking_frame, text="(smooths player positions for better stability)", wraplength=280).grid(row=7, column=2, sticky=tk.W, padx=5)
        
        # Process Every Nth Frame
        ttk.Label(tracking_frame, text="Process Every Nth Frame:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=5)
        process_nth_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=4, increment=1,
                                          textvariable=self.parent_gui.process_every_nth, width=8)
        process_nth_spinbox.grid(row=8, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(1 = all frames, 4 = every 4th frame for 120fps→30fps)", wraplength=280).grid(row=8, column=2, sticky=tk.W, padx=5)
        
        # YOLO Processing Resolution
        ttk.Label(tracking_frame, text="YOLO Resolution:").grid(row=9, column=0, sticky=tk.W, padx=5, pady=5)
        yolo_res_combo = ttk.Combobox(tracking_frame, textvariable=self.parent_gui.yolo_resolution, 
                                     values=["full", "1080p", "720p"], width=10, state="readonly")
        yolo_res_combo.grid(row=9, column=1, padx=5, pady=5)
        ttk.Label(tracking_frame, text="(lower = faster, full = best quality)", wraplength=280).grid(row=9, column=2, sticky=tk.W, padx=5)
        
        # Foot-based tracking
        foot_tracking_check = ttk.Checkbutton(tracking_frame, text="Foot-Based Tracking",
                                             variable=self.parent_gui.foot_based_tracking)
        foot_tracking_check.grid(row=10, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
        create_tooltip(foot_tracking_check, 
                          TOOLTIP_DATABASE.get("foot_based_tracking", {}).get("text", "Use foot position for tracking"),
                          TOOLTIP_DATABASE.get("foot_based_tracking", {}).get("detailed"))
        ttk.Label(tracking_frame, text="(uses foot position as stable anchor)", wraplength=280).grid(row=10, column=2, sticky=tk.W, padx=5)
        
        # Re-ID Settings
        if hasattr(self.parent_gui, 'use_reid'):
            ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=11, column=0, columnspan=3, sticky=tk.EW, pady=10)
            ttk.Label(tracking_frame, text="Re-ID (Re-identification)", font=("Arial", 9, "bold")).grid(row=12, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
            
            reid_check = ttk.Checkbutton(tracking_frame, text="Re-ID (Re-identification)",
                                        variable=self.parent_gui.use_reid)
            reid_check.grid(row=13, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            create_tooltip(reid_check, 
                          TOOLTIP_DATABASE.get("use_reid", {}).get("text", "Enable Re-ID for player recognition"),
                          TOOLTIP_DATABASE.get("use_reid", {}).get("detailed"))
            ttk.Label(tracking_frame, text="(better ID persistence during occlusions)", wraplength=280).grid(row=13, column=2, sticky=tk.W, padx=5)
            
            # Re-ID similarity threshold
            if hasattr(self.parent_gui, 'reid_similarity_threshold'):
                ttk.Label(tracking_frame, text="Re-ID Similarity Threshold:").grid(row=14, column=0, sticky=tk.W, padx=5, pady=5)
                reid_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.25, to=0.9, increment=0.05,
                                                 textvariable=self.parent_gui.reid_similarity_threshold, width=8, format="%.2f")
                reid_thresh_spinbox.grid(row=14, column=1, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(0.25-0.9, higher = stricter matching, default: 0.55)", wraplength=280).grid(row=14, column=2, sticky=tk.W, padx=5)
                
            # Gallery similarity threshold
            if hasattr(self.parent_gui, 'gallery_similarity_threshold'):
                ttk.Label(tracking_frame, text="Gallery Similarity Threshold:").grid(row=15, column=0, sticky=tk.W, padx=5, pady=5)
                gallery_thresh_spinbox = ttk.Spinbox(tracking_frame, from_=0.25, to=0.75, increment=0.05,
                                                     textvariable=self.parent_gui.gallery_similarity_threshold, width=8, format="%.2f")
                gallery_thresh_spinbox.grid(row=15, column=1, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(0.25-0.75, for cross-video player matching, default: 0.40)", wraplength=280).grid(row=15, column=2, sticky=tk.W, padx=5)
        
        # Advanced Tracking Features
        if hasattr(self.parent_gui, 'use_enhanced_kalman'):
            ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=16, column=0, columnspan=3, sticky=tk.EW, pady=10)
            ttk.Label(tracking_frame, text="Advanced Tracking Features", font=("Arial", 9, "bold")).grid(row=17, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
            
            enhanced_kalman_check = ttk.Checkbutton(tracking_frame, text="Enhanced Kalman Filtering",
                                                    variable=self.parent_gui.use_enhanced_kalman)
            enhanced_kalman_check.grid(row=18, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            ttk.Label(tracking_frame, text="(additional smoothing layer for jitter reduction)", wraplength=280).grid(row=18, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'use_ema_smoothing'):
                ema_smoothing_check = ttk.Checkbutton(tracking_frame, text="EMA Smoothing",
                                                      variable=self.parent_gui.use_ema_smoothing)
                ema_smoothing_check.grid(row=19, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(better than simple average, confidence-weighted)", wraplength=280).grid(row=19, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'use_optical_flow'):
                optical_flow_check = ttk.Checkbutton(tracking_frame, text="Use Optical Flow",
                                                    variable=self.parent_gui.use_optical_flow)
                optical_flow_check.grid(row=20, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(motion prediction to reduce tracking blinking)", wraplength=280).grid(row=20, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'enable_velocity_constraints'):
                velocity_constraints_check = ttk.Checkbutton(tracking_frame, text="Enable Velocity Constraints",
                                                             variable=self.parent_gui.enable_velocity_constraints)
                velocity_constraints_check.grid(row=21, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(prevent impossible jumps in tracking, recommended: ON)", wraplength=280).grid(row=21, column=2, sticky=tk.W, padx=5)
        
        # Minimum Detection Size
        if hasattr(self.parent_gui, 'min_bbox_area'):
            ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=22, column=0, columnspan=3, sticky=tk.EW, pady=10)
            ttk.Label(tracking_frame, text="Minimum Detection Size:", font=("Arial", 9, "bold")).grid(row=23, column=0, columnspan=2, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(tracking_frame, text="Min Area (px²):").grid(row=24, column=0, sticky=tk.W, padx=5, pady=5)
            min_area_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=2000, increment=1,
                                          textvariable=self.parent_gui.min_bbox_area, width=8)
            min_area_spinbox.grid(row=24, column=1, padx=5, pady=5)
            ttk.Label(tracking_frame, text="(minimum bbox area, lower = detect smaller objects, default: 200)", wraplength=280).grid(row=24, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'min_bbox_width'):
                ttk.Label(tracking_frame, text="Min Width (px):").grid(row=25, column=0, sticky=tk.W, padx=5, pady=5)
                min_width_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=100, increment=1,
                                               textvariable=self.parent_gui.min_bbox_width, width=8)
                min_width_spinbox.grid(row=25, column=1, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(minimum bbox width, default: 10)", wraplength=280).grid(row=25, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'min_bbox_height'):
                ttk.Label(tracking_frame, text="Min Height (px):").grid(row=26, column=0, sticky=tk.W, padx=5, pady=5)
                min_height_spinbox = ttk.Spinbox(tracking_frame, from_=1, to=100, increment=1,
                                                textvariable=self.parent_gui.min_bbox_height, width=8)
                min_height_spinbox.grid(row=26, column=1, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(minimum bbox height, default: 15)", wraplength=280).grid(row=26, column=2, sticky=tk.W, padx=5)
        
        # Occlusion & Fine-Tuning Parameters
        if hasattr(self.parent_gui, 'occlusion_recovery_seconds'):
            ttk.Separator(tracking_frame, orient=tk.HORIZONTAL).grid(row=27, column=0, columnspan=3, sticky=tk.EW, pady=10)
            ttk.Label(tracking_frame, text="Occlusion & Fine-Tuning Parameters:", 
                     font=("Arial", 9, "bold")).grid(row=28, column=0, columnspan=3, sticky=tk.W, padx=5, pady=5)
            
            ttk.Label(tracking_frame, text="Occlusion Recovery Time (s):").grid(row=29, column=0, sticky=tk.W, padx=5, pady=5)
            occlusion_recovery_spinbox = ttk.Spinbox(tracking_frame, from_=1.0, to=10.0, increment=0.5,
                                                     textvariable=self.parent_gui.occlusion_recovery_seconds, width=8, format="%.1f")
            occlusion_recovery_spinbox.grid(row=29, column=1, padx=5, pady=5)
            ttk.Label(tracking_frame, text="(how long to search for disappeared players, default: 3.0s)", wraplength=280).grid(row=29, column=2, sticky=tk.W, padx=5)
            
            if hasattr(self.parent_gui, 'occlusion_recovery_distance'):
                ttk.Label(tracking_frame, text="Occlusion Recovery Distance (px):").grid(row=30, column=0, sticky=tk.W, padx=5, pady=5)
                occlusion_distance_spinbox = ttk.Spinbox(tracking_frame, from_=100, to=500, increment=25,
                                                         textvariable=self.parent_gui.occlusion_recovery_distance, width=8)
                occlusion_distance_spinbox.grid(row=30, column=1, padx=5, pady=5)
                ttk.Label(tracking_frame, text="(max pixel distance for recovery, default: 250px)", wraplength=280).grid(row=30, column=2, sticky=tk.W, padx=5)
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            # Silently fail for optional methods
            pass

