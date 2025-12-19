"""
Analysis Tab Component
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
    from soccer_analysis.utils.tooltip import create_tooltip, TOOLTIP_DATABASE
except ImportError:
    try:
        from utils.tooltip import create_tooltip, TOOLTIP_DATABASE
    except ImportError:
        # Fallback: create dummy function
        def create_tooltip(widget, text, detailed_text=None):
            pass
        TOOLTIP_DATABASE = {}


class AnalysisTab:
    """Analysis Configuration Tab Component"""
    
    def __init__(self, parent_gui, parent_frame):
        """
        Initialize analysis tab
        
        Args:
            parent_gui: Reference to main GUI instance (for callbacks and variables)
            parent_frame: Parent frame to create tab in
        """
        self.parent_gui = parent_gui
        self.parent_frame = parent_frame
        self.create_tab()
    
    def create_tab(self):
        """Create the Analysis tab content"""
        # Ensure parent_frame has column configuration
        self.parent_frame.columnconfigure(1, weight=1)
        
        analysis_row = 0
        
        # Ball Tracking Settings
        ball_frame = ttk.LabelFrame(self.parent_frame, text="Ball Tracking Settings", padding="10")
        ball_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        ball_tracking_check = ttk.Checkbutton(ball_frame, text="Track Ball (detection + CSV export)", 
                       variable=self.parent_gui.ball_tracking_enabled)
        ball_tracking_check.grid(row=0, column=0, sticky=tk.W, pady=5)
        create_tooltip(ball_tracking_check, 
                      TOOLTIP_DATABASE.get("ball_tracking", {}).get("text", "Enable ball detection and tracking"),
                      TOOLTIP_DATABASE.get("ball_tracking", {}).get("detailed"))
        
        # Ball size detection range
        ball_size_frame = ttk.Frame(ball_frame)
        ball_size_frame.grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(ball_size_frame, text="Ball Size Range (pixels):").pack(side=tk.LEFT, padx=5)
        ball_min_spinbox = ttk.Spinbox(ball_size_frame, from_=3, to=20, increment=1,
                                      textvariable=self.parent_gui.ball_min_size, width=8)
        ball_min_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(ball_size_frame, text="to").pack(side=tk.LEFT, padx=5)
        ball_max_spinbox = ttk.Spinbox(ball_size_frame, from_=20, to=100, increment=5,
                                      textvariable=self.parent_gui.ball_max_size, width=8)
        ball_max_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(ball_size_frame, text="(min to max diameter for ball detection)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Ball trail settings
        trail_frame = ttk.Frame(ball_frame)
        trail_frame.grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(trail_frame, text="Show Ball Trail (red lines overlay)", 
                       variable=self.parent_gui.show_ball_trail).pack(side=tk.LEFT, padx=5)
        ttk.Label(trail_frame, text="Length:").pack(side=tk.LEFT, padx=(20, 2))
        trail_length_spinbox = ttk.Spinbox(trail_frame, from_=5, to=100, increment=5,
                                          textvariable=self.parent_gui.ball_trail_length, width=6)
        trail_length_spinbox.pack(side=tk.LEFT, padx=2)
        ttk.Label(trail_frame, text="frames", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=2)
        
        # YOLO Detection Settings
        yolo_frame = ttk.LabelFrame(self.parent_frame, text="YOLO Detection Settings", padding="10")
        yolo_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        # Confidence threshold
        conf_frame = ttk.Frame(yolo_frame)
        conf_frame.grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(conf_frame, text="Confidence Threshold:").pack(side=tk.LEFT, padx=5)
        conf_spinbox = ttk.Spinbox(conf_frame, from_=0.1, to=1.0, increment=0.05,
                                  textvariable=self.parent_gui.yolo_confidence, width=8, format="%.2f")
        conf_spinbox.pack(side=tk.LEFT, padx=5)
        create_tooltip(conf_spinbox, 
                      TOOLTIP_DATABASE.get("yolo_confidence", {}).get("text", "YOLO detection confidence threshold"),
                      TOOLTIP_DATABASE.get("yolo_confidence", {}).get("detailed"))
        ttk.Label(conf_frame, text="(0.1 = more detections, 1.0 = only very confident)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # IOU threshold
        iou_frame = ttk.Frame(yolo_frame)
        iou_frame.grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(iou_frame, text="IOU Threshold:").pack(side=tk.LEFT, padx=5)
        iou_spinbox = ttk.Spinbox(iou_frame, from_=0.1, to=1.0, increment=0.05,
                                 textvariable=self.parent_gui.yolo_iou_threshold, width=8, format="%.2f")
        iou_spinbox.pack(side=tk.LEFT, padx=5)
        create_tooltip(iou_spinbox, 
                      TOOLTIP_DATABASE.get("yolo_iou_threshold", {}).get("text", "YOLO IoU threshold"),
                      TOOLTIP_DATABASE.get("yolo_iou_threshold", {}).get("detailed"))
        ttk.Label(iou_frame, text="(Non-Maximum Suppression threshold)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Batch size
        batch_frame = ttk.Frame(yolo_frame)
        batch_frame.grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(batch_frame, text="Batch Size:").pack(side=tk.LEFT, padx=5)
        batch_spinbox = ttk.Spinbox(batch_frame, from_=1, to=32, 
                                   textvariable=self.parent_gui.batch_size, width=8)
        batch_spinbox.pack(side=tk.LEFT, padx=5)
        create_tooltip(batch_spinbox, "YOLO batch size",
                      "Number of frames to process together. Higher values use more GPU memory but process faster. Default: 8")
        ttk.Label(batch_frame, text="(higher = faster but uses more memory)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # YOLO Resolution
        yolo_res_frame = ttk.Frame(yolo_frame)
        yolo_res_frame.grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Label(yolo_res_frame, text="YOLO Resolution:").pack(side=tk.LEFT, padx=5)
        yolo_res_combo = ttk.Combobox(yolo_res_frame, textvariable=self.parent_gui.yolo_resolution,
                                     values=["640", "720", "1080", "full"], width=10, state="readonly")
        yolo_res_combo.pack(side=tk.LEFT, padx=5)
        create_tooltip(yolo_res_combo, 
                      TOOLTIP_DATABASE.get("yolo_resolution", {}).get("text", "YOLO processing resolution"),
                      TOOLTIP_DATABASE.get("yolo_resolution", {}).get("detailed"))
        ttk.Label(yolo_res_frame, text="(lower = faster, higher = more accurate)", 
                 foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Player Gallery Matching Settings
        gallery_frame = ttk.LabelFrame(self.parent_frame, text="Player Gallery Matching", padding="10")
        gallery_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        gallery_frame.columnconfigure(0, weight=0, minsize=200)  # Label column
        gallery_frame.columnconfigure(1, weight=0, minsize=100)  # Control column
        gallery_frame.columnconfigure(2, weight=1, minsize=300)   # Help text column
        
        # Gallery Similarity Threshold
        ttk.Label(gallery_frame, text="Gallery Similarity Threshold:", font=("Arial", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        gallery_thresh_spinbox = ttk.Spinbox(gallery_frame, from_=0.20, to=0.75, increment=0.05,
                                             textvariable=self.parent_gui.gallery_similarity_threshold, width=8, format="%.2f",
                                             command=lambda: self._call_parent_method('_validate_gallery_threshold'))
        gallery_thresh_spinbox.grid(row=0, column=1, padx=5, pady=5)
        gallery_thresh_spinbox.bind('<KeyRelease>', lambda e: self._call_parent_method('_validate_gallery_threshold'))
        create_tooltip(gallery_thresh_spinbox, 
                      TOOLTIP_DATABASE.get("gallery_similarity_threshold", {}).get("text", "Player gallery matching threshold"),
                      TOOLTIP_DATABASE.get("gallery_similarity_threshold", {}).get("detailed"))
        ttk.Label(gallery_frame, text="(0.20-0.75, for matching players across videos, default: 0.40)", wraplength=350).grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Processing Settings
        process_frame = ttk.LabelFrame(self.parent_frame, text="Processing Settings", padding="10")
        process_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
        analysis_row += 1
        
        dewarp_check = ttk.Checkbutton(process_frame, text="Apply Dewarping (Fix Fisheye Distortion)", 
                       variable=self.parent_gui.dewarp_enabled)
        dewarp_check.grid(row=0, column=0, sticky=tk.W, pady=5)
        create_tooltip(dewarp_check, 
                      TOOLTIP_DATABASE.get("dewarp_enabled", {}).get("text", "Correct fisheye distortion"),
                      TOOLTIP_DATABASE.get("dewarp_enabled", {}).get("detailed"))
        
        remove_net_check = ttk.Checkbutton(process_frame, text="Remove Net (essential for safety net recordings)", 
                       variable=self.parent_gui.remove_net_enabled)
        remove_net_check.grid(row=1, column=0, sticky=tk.W, pady=5)
        create_tooltip(remove_net_check, 
                      TOOLTIP_DATABASE.get("remove_net_enabled", {}).get("text", "Remove net from detection"),
                      TOOLTIP_DATABASE.get("remove_net_enabled", {}).get("detailed"))
        
        player_tracking_check = ttk.Checkbutton(process_frame, text="Track Players (YOLO detection + tracking)",
                       variable=self.parent_gui.player_tracking_enabled)
        player_tracking_check.grid(row=2, column=0, sticky=tk.W, pady=5)
        create_tooltip(player_tracking_check, 
                      TOOLTIP_DATABASE.get("player_tracking", {}).get("text", "Enable player detection and tracking"),
                      TOOLTIP_DATABASE.get("player_tracking", {}).get("detailed"))
        
        csv_export_check = ttk.Checkbutton(process_frame, text="Export CSV (tracking data)",
                       variable=self.parent_gui.csv_export_enabled)
        csv_export_check.grid(row=3, column=0, sticky=tk.W, pady=5)
        create_tooltip(csv_export_check, "Export tracking data to CSV file",
                      "When enabled, player and ball tracking data will be exported to a CSV file for analysis in Excel or other tools.")
        
        imperial_check = ttk.Checkbutton(process_frame, text="Use Imperial Units (feet & mph) - American units",
                       variable=self.parent_gui.use_imperial_units)
        imperial_check.grid(row=4, column=0, sticky=tk.W, pady=5)
        create_tooltip(imperial_check, 
                      TOOLTIP_DATABASE.get("use_imperial_units", {}).get("text", "Display measurements in feet and mph"),
                      TOOLTIP_DATABASE.get("use_imperial_units", {}).get("detailed"))
        
        # Re-ID Settings (if available)
        if hasattr(self.parent_gui, 'use_reid'):
            reid_frame = ttk.LabelFrame(self.parent_frame, text="Re-ID Settings", padding="10")
            reid_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            analysis_row += 1
            
            reid_check = ttk.Checkbutton(reid_frame, text="Enable Re-ID (Player Recognition Across Videos)",
                           variable=self.parent_gui.use_reid)
            reid_check.grid(row=0, column=0, sticky=tk.W, pady=5)
            create_tooltip(reid_check, 
                          TOOLTIP_DATABASE.get("use_reid", {}).get("text", "Enable Re-ID for player recognition"),
                          TOOLTIP_DATABASE.get("use_reid", {}).get("detailed"))
            
            # Re-ID similarity threshold
            reid_sim_frame = ttk.Frame(reid_frame)
            reid_sim_frame.grid(row=1, column=0, sticky=tk.W, pady=5)
            ttk.Label(reid_sim_frame, text="Re-ID Similarity Threshold:").pack(side=tk.LEFT, padx=5)
            reid_sim_spinbox = ttk.Spinbox(reid_sim_frame, from_=0.1, to=1.0, increment=0.05,
                                          textvariable=self.parent_gui.reid_similarity_threshold, width=8, format="%.2f")
            reid_sim_spinbox.pack(side=tk.LEFT, padx=5)
            create_tooltip(reid_sim_spinbox, 
                          TOOLTIP_DATABASE.get("reid_similarity_threshold", {}).get("text", "Re-ID similarity threshold"),
                          TOOLTIP_DATABASE.get("reid_similarity_threshold", {}).get("detailed"))
            ttk.Label(reid_sim_frame, text="(0.1 = more matches, 1.0 = only very confident)", 
                     foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
        
        # Temporal Smoothing
        if hasattr(self.parent_gui, 'temporal_smoothing'):
            smoothing_frame = ttk.LabelFrame(self.parent_frame, text="Temporal Smoothing", padding="10")
            smoothing_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            analysis_row += 1
            
            smoothing_check = ttk.Checkbutton(smoothing_frame, text="Enable Temporal Smoothing (GSI)",
                           variable=self.parent_gui.temporal_smoothing)
            smoothing_check.grid(row=0, column=0, sticky=tk.W, pady=5)
            create_tooltip(smoothing_check, 
                          TOOLTIP_DATABASE.get("temporal_smoothing", {}).get("text", "Apply temporal smoothing to tracks"),
                          TOOLTIP_DATABASE.get("temporal_smoothing", {}).get("detailed"))
            ttk.Label(smoothing_frame, text="(Reduces jitter in player positions)", 
                     foreground="gray", font=("Arial", 8)).grid(row=1, column=0, sticky=tk.W, padx=(20, 0))
        
        # Frame Processing
        if hasattr(self.parent_gui, 'process_every_nth'):
            frame_process_frame = ttk.LabelFrame(self.parent_frame, text="Frame Processing", padding="10")
            frame_process_frame.grid(row=analysis_row, column=0, columnspan=3, sticky=tk.W+tk.E, pady=5)
            analysis_row += 1
            
            frame_process_inner = ttk.Frame(frame_process_frame)
            frame_process_inner.grid(row=0, column=0, sticky=tk.W, pady=5)
            ttk.Label(frame_process_inner, text="Process Every Nth Frame:").pack(side=tk.LEFT, padx=5)
            process_nth_spinbox = ttk.Spinbox(frame_process_inner, from_=1, to=10, increment=1,
                                              textvariable=self.parent_gui.process_every_nth, width=8)
            process_nth_spinbox.pack(side=tk.LEFT, padx=5)
            ttk.Label(frame_process_inner, text="(1 = all frames, 2 = every 2nd frame, etc.)", 
                     foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=10)
    
    def _call_parent_method(self, method_name, *args, **kwargs):
        """Call a method on the parent GUI instance"""
        if hasattr(self.parent_gui, method_name):
            method = getattr(self.parent_gui, method_name)
            return method(*args, **kwargs)
        else:
            # Silently fail for optional methods
            pass

